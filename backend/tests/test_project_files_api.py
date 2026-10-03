import uuid
from pathlib import Path

from sqlalchemy import func, select

from app.models.file import File, FileTag, ProjectFile, ProjectFileTag, StoredFile
from app.models.project import Project
from tests.conftest import TEST_MAX_UPLOAD_BYTES
from tests.factories import create_project, create_user, ensure_role

SAMPLES = Path(__file__).parent / "fixtures" / "documents"


async def _login(client, db_session, *roles: str) -> None:
    """Signs in a user holding exactly `roles`."""
    first, *rest = roles
    user = await create_user(
        db_session, name_id="user@example.com", password="pw", role_name=first
    )
    for role in rest:
        await db_session.refresh(user, attribute_names=["roles"])
        user.roles.append(await ensure_role(db_session, role))
        await db_session.commit()
    response = await client.post(
        "/api/auth/login", json={"email": "user@example.com", "password": "pw"}
    )
    assert response.status_code == 200


def _sample(extension: str) -> bytes:
    return (SAMPLES / f"sample{extension}").read_bytes()


def _upload(name: str, data: bytes) -> dict:
    return {"file": (name, data, "application/octet-stream")}


def _files_url(project: Project) -> str:
    return f"/api/projects/{project.id}/files"


async def _post_file(client, project: Project, name="contract.pdf", data=None):
    return await client.post(
        _files_url(project), files=_upload(name, data or _sample(".pdf"))
    )


async def _tag_id(db_session, name: str) -> uuid.UUID:
    return (
        await db_session.execute(select(FileTag.id).where(FileTag.name == name))
    ).scalar_one()


async def _count(db_session, model) -> int:
    return (
        await db_session.execute(select(func.count()).select_from(model))
    ).scalar_one()


# --- access ----------------------------------------------------------------------


async def test_signed_out_clients_get_401(client, db_session) -> None:
    project = await create_project(db_session)
    assert (await client.get(_files_url(project))).status_code == 401
    assert (await _post_file(client, project)).status_code == 401
    assert (await client.get("/api/file-tags")).status_code == 401


async def test_only_project_admins_may_use_project_files(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "consultant")
    assert (await client.get(_files_url(project))).status_code == 403
    assert (await _post_file(client, project)).status_code == 403
    assert (await client.get("/api/file-tags")).status_code == 403


async def test_administrator_alone_grants_nothing(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "administrator")
    assert (await _post_file(client, project)).status_code == 403
    assert await _count(db_session, File) == 0


async def test_project_manager_alone_grants_nothing(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_manager")
    assert (await _post_file(client, project)).status_code == 403


# --- upload and list ---------------------------------------------------------------


async def test_upload_returns_the_new_file_and_lists_it(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")

    response = await _post_file(client, project)

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "contract.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(_sample(".pdf"))
    assert body["tags"] == []
    listed = (await client.get(_files_url(project))).json()
    assert [f["file_id"] for f in listed] == [body["file_id"]]


async def test_files_are_listed_oldest_first(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    names = ["b.pdf", "a.pdf", "c.pdf"]
    for name in names:
        assert (await _post_file(client, project, name)).status_code == 201

    listed = (await client.get(_files_url(project))).json()

    assert [f["original_filename"] for f in listed] == names


async def test_the_same_name_can_be_uploaded_twice(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")

    first = await _post_file(client, project)
    second = await _post_file(client, project)

    assert first.json()["file_id"] != second.json()["file_id"]
    assert len((await client.get(_files_url(project))).json()) == 2
    # Identical content is stored once.
    assert await _count(db_session, StoredFile) == 1


async def test_stored_under_a_generated_path_with_the_allowlisted_extension(
    client, db_session, _storage_settings
) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")

    response = await _post_file(client, project, "../../Contract.PDF")

    assert response.status_code == 201
    assert response.json()["original_filename"] == "Contract.PDF"
    stored = (await db_session.execute(select(StoredFile))).scalar_one()
    assert stored.bucket_key.endswith(".pdf")
    assert (_storage_settings / stored.bucket_key).read_bytes() == _sample(".pdf")


async def test_unknown_project_and_deleted_project_are_404(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    assert (
        await client.get(f"/api/projects/{uuid.uuid4()}/files")
    ).status_code == 404

    project.is_active = False
    await db_session.commit()
    assert (await client.get(_files_url(project))).status_code == 404
    assert (await _post_file(client, project)).status_code == 404


async def test_disallowed_extension_is_415_and_persists_nothing(
    client, db_session, _storage_settings
) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")

    response = await _post_file(client, project, "setup.exe", b"MZ\x90\x00")

    assert response.status_code == 415
    assert await _count(db_session, File) == 0
    assert await _count(db_session, StoredFile) == 0
    assert not any(_storage_settings.rglob("*.pdf"))


async def test_content_that_disagrees_with_its_extension_is_415(
    client, db_session
) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")

    response = await _post_file(client, project, "report.pdf", b"#!/bin/sh\necho hi\n")

    assert response.status_code == 415
    assert await _count(db_session, File) == 0


async def test_oversized_upload_is_413_and_persists_nothing(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    data = _sample(".pdf")
    padded = data + b"\n" * (TEST_MAX_UPLOAD_BYTES + 1 - len(data))

    response = await _post_file(client, project, "big.pdf", padded)

    assert response.status_code == 413
    assert await _count(db_session, File) == 0
    assert await _count(db_session, StoredFile) == 0


# --- delete -------------------------------------------------------------------------


async def test_delete_removes_the_file_its_link_and_its_tags(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project)).json()["file_id"]
    tag = await _tag_id(db_session, "contract")
    await client.put(f"{_files_url(project)}/{file_id}/tags/{tag}")

    response = await client.delete(f"{_files_url(project)}/{file_id}")

    assert response.status_code == 204
    assert (await client.get(_files_url(project))).json() == []
    assert await _count(db_session, File) == 0
    assert await _count(db_session, ProjectFile) == 0
    assert await _count(db_session, ProjectFileTag) == 0
    # Other attachments may share the content, so it is left for the cleanup job.
    assert await _count(db_session, StoredFile) == 1


async def test_deleting_one_copy_keeps_the_other(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    first = (await _post_file(client, project)).json()["file_id"]
    await _post_file(client, project)

    await client.delete(f"{_files_url(project)}/{first}")

    assert len((await client.get(_files_url(project))).json()) == 1


async def test_deleting_an_unknown_file_is_404(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    response = await client.delete(f"{_files_url(project)}/{uuid.uuid4()}")
    assert response.status_code == 404


# --- scoping to the project ------------------------------------------------------------


async def test_another_projects_file_id_is_404(client, db_session) -> None:
    project_a = await create_project(db_session, name="A")
    project_b = await create_project(db_session, name="B")
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project_a)).json()["file_id"]
    tag = await _tag_id(db_session, "contract")

    assert (
        await client.delete(f"{_files_url(project_b)}/{file_id}")
    ).status_code == 404
    assert (
        await client.put(f"{_files_url(project_b)}/{file_id}/tags/{tag}")
    ).status_code == 404
    assert (
        await client.delete(f"{_files_url(project_b)}/{file_id}/tags/{tag}")
    ).status_code == 404
    # Untouched on the project that owns it.
    assert len((await client.get(_files_url(project_a))).json()) == 1


# --- tags ----------------------------------------------------------------------------


async def test_the_vocabulary_is_listed_by_name(client, db_session) -> None:
    await _login(client, db_session, "project_admin")

    body = (await client.get("/api/file-tags")).json()

    assert [t["name"] for t in body] == sorted(
        [
            "contract",
            "purchase order",
            "statement of work",
            "proposal",
            "master service agreement",
            "non-disclosure agreement",
            "invoice",
            "addendum",
        ]
    )


async def test_a_file_can_carry_several_tags(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project)).json()["file_id"]
    for name in ("contract", "addendum", "invoice"):
        tag = await _tag_id(db_session, name)
        response = await client.put(f"{_files_url(project)}/{file_id}/tags/{tag}")
        assert response.status_code == 204

    listed = (await client.get(_files_url(project))).json()

    assert [t["name"] for t in listed[0]["tags"]] == ["addendum", "contract", "invoice"]


async def test_adding_a_tag_twice_leaves_it_once(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project)).json()["file_id"]
    tag = await _tag_id(db_session, "contract")

    first = await client.put(f"{_files_url(project)}/{file_id}/tags/{tag}")
    second = await client.put(f"{_files_url(project)}/{file_id}/tags/{tag}")

    assert (first.status_code, second.status_code) == (204, 204)
    assert await _count(db_session, ProjectFileTag) == 1


async def test_removing_a_tag_the_file_lacks_is_not_an_error(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project)).json()["file_id"]
    tag = await _tag_id(db_session, "contract")

    response = await client.delete(f"{_files_url(project)}/{file_id}/tags/{tag}")

    assert response.status_code == 204


async def test_removing_a_tag_takes_it_off_the_file(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project)).json()["file_id"]
    tag = await _tag_id(db_session, "contract")
    await client.put(f"{_files_url(project)}/{file_id}/tags/{tag}")

    await client.delete(f"{_files_url(project)}/{file_id}/tags/{tag}")

    assert (await client.get(_files_url(project))).json()[0]["tags"] == []


async def test_an_unknown_tag_is_404(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project)).json()["file_id"]
    ghost = uuid.uuid4()

    assert (
        await client.put(f"{_files_url(project)}/{file_id}/tags/{ghost}")
    ).status_code == 404
    assert (
        await client.delete(f"{_files_url(project)}/{file_id}/tags/{ghost}")
    ).status_code == 404


async def test_identical_content_in_two_projects_keeps_separate_tags(
    client, db_session
) -> None:
    project_a = await create_project(db_session, name="A")
    project_b = await create_project(db_session, name="B")
    await _login(client, db_session, "project_admin")
    file_a = (await _post_file(client, project_a)).json()["file_id"]
    await _post_file(client, project_b)
    tag = await _tag_id(db_session, "contract")

    await client.put(f"{_files_url(project_a)}/{file_a}/tags/{tag}")

    assert (await client.get(_files_url(project_a))).json()[0]["tags"] != []
    assert (await client.get(_files_url(project_b))).json()[0]["tags"] == []
    assert await _count(db_session, StoredFile) == 1


# --- closed projects ---------------------------------------------------------------------


async def _close(db_session, project: Project, status: str = "closed") -> None:
    project.status = status
    await db_session.commit()


async def test_a_closed_project_refuses_every_document_change(
    client, db_session, _storage_settings
) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project)).json()["file_id"]
    tag = await _tag_id(db_session, "contract")
    await client.put(f"{_files_url(project)}/{file_id}/tags/{tag}")
    await _close(db_session, project)
    stored_before = await _count(db_session, StoredFile)

    upload = await _post_file(client, project, "another.docx", _sample(".docx"))
    delete = await client.delete(f"{_files_url(project)}/{file_id}")
    add = await client.put(
        f"{_files_url(project)}/{file_id}/tags/{await _tag_id(db_session, 'invoice')}"
    )
    remove = await client.delete(f"{_files_url(project)}/{file_id}/tags/{tag}")

    assert (upload.status_code, delete.status_code, add.status_code, remove.status_code) == (
        409,
        409,
        409,
        409,
    )
    assert await _count(db_session, StoredFile) == stored_before
    listed = (await client.get(_files_url(project))).json()
    assert len(listed) == 1 and [t["name"] for t in listed[0]["tags"]] == ["contract"]


async def test_reopening_restores_document_changes(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    await _close(db_session, project)
    assert (await _post_file(client, project)).status_code == 409

    await _close(db_session, project, "active")

    assert (await _post_file(client, project)).status_code == 201


# --- duplicate -------------------------------------------------------------------------------


async def test_duplicating_a_project_does_not_copy_its_documents(
    client, db_session
) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    first = (await _post_file(client, project)).json()["file_id"]
    await _post_file(client, project, "second.docx", _sample(".docx"))
    tag = await _tag_id(db_session, "contract")
    await client.put(f"{_files_url(project)}/{first}/tags/{tag}")

    response = await client.post(f"/api/projects/{project.id}/duplicate")

    assert response.status_code == 200
    copy_id = response.json()["id"]
    assert (await client.get(f"/api/projects/{copy_id}/files")).json() == []
    original = (await client.get(_files_url(project))).json()
    assert len(original) == 2
    assert [t["name"] for t in original[0]["tags"]] == ["contract"]


# --- download -------------------------------------------------------------------------------


def _content_url(file_id: str) -> str:
    return f"/api/files/{file_id}/content"


async def test_a_project_admin_downloads_a_project_file_as_an_attachment(
    client, db_session
) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project)).json()["file_id"]

    response = await client.get(_content_url(file_id))

    assert response.status_code == 200
    assert response.content == _sample(".pdf")
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "contract.pdf" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == "sandbox; default-src 'none'"


async def test_a_signed_out_client_cannot_download_a_project_file(
    client, db_session
) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project)).json()["file_id"]
    client.cookies.clear()

    assert (await client.get(_content_url(file_id))).status_code == 401


async def test_other_roles_cannot_download_a_project_file(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project)).json()["file_id"]
    client.cookies.clear()
    await create_user(
        db_session, name_id="admin@example.com", password="pw", role_name="administrator"
    )
    await client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": "pw"}
    )

    assert (await client.get(_content_url(file_id))).status_code == 403


async def test_html_and_svg_are_never_served_inline(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    for extension in (".html", ".svg", ".xml"):
        file_id = (
            await _post_file(client, project, f"page{extension}", _sample(extension))
        ).json()["file_id"]

        response = await client.get(_content_url(file_id))

        assert response.status_code == 200
        assert response.headers["content-disposition"].startswith("attachment;")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "sandbox" in response.headers["content-security-policy"]


async def test_a_hostile_file_name_cannot_break_the_header(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    name = 'evil";\r\nX-Injected: 1.pdf'
    file_id = (await _post_file(client, project, name)).json()["file_id"]

    response = await client.get(_content_url(file_id))

    assert response.status_code == 200
    assert "x-injected" not in response.headers
    assert response.headers["content-disposition"].startswith("attachment;")


async def test_a_deleted_file_is_404(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project)).json()["file_id"]
    await client.delete(f"{_files_url(project)}/{file_id}")

    assert (await client.get(_content_url(file_id))).status_code == 404


async def test_a_file_of_a_deleted_project_is_404(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project)).json()["file_id"]
    project.is_active = False
    await db_session.commit()

    assert (await client.get(_content_url(file_id))).status_code == 404


async def test_a_closed_projects_file_still_downloads(client, db_session) -> None:
    project = await create_project(db_session)
    await _login(client, db_session, "project_admin")
    file_id = (await _post_file(client, project)).json()["file_id"]
    await _close(db_session, project)

    assert (await client.get(_content_url(file_id))).status_code == 200
