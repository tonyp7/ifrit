import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import (
    DEFAULT_FILE_TAGS,
    File,
    FileTag,
    ProjectFile,
    ProjectFileTag,
    SettingFile,
    StoredFile,
)
from app.models.project import Project
from tests.factories import create_project


async def _make_file(
    db: AsyncSession, *, key: str = "org_logo", checksum: str = "a" * 64
) -> File:
    stored = (
        await db.execute(
            select(StoredFile).where(StoredFile.checksum_sha256 == checksum)
        )
    ).scalar_one_or_none()
    if stored is None:
        stored = StoredFile(
            checksum_sha256=checksum,
            size_bytes=3,
            detected_content_type="image/png",
            bucket_key=f"{checksum[:2]}/{checksum[2:4]}/{checksum}.png",
            status="ready",
        )
        db.add(stored)
        await db.flush()
    file = File(stored_file_id=stored.id, kind="setting", original_filename="x.png")
    db.add(file)
    await db.flush()
    db.add(SettingFile(file_id=file.id, kind="setting", setting_key=key))
    await db.commit()
    return file


async def _count(db: AsyncSession, model: type) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


@pytest.mark.asyncio
async def test_deleting_a_link_row_removes_its_file_record(db_session: AsyncSession):
    file = await _make_file(db_session)
    await db_session.execute(
        text("DELETE FROM setting_files WHERE file_id = :id"), {"id": file.id}
    )
    await db_session.commit()

    assert await _count(db_session, File) == 0
    # Stored content is never removed by this path (RESTRICT / cleanup job).
    assert await _count(db_session, StoredFile) == 1


@pytest.mark.asyncio
async def test_deleting_a_file_record_cascades_to_its_link_row(
    db_session: AsyncSession,
):
    file = await _make_file(db_session)
    await db_session.execute(text("DELETE FROM files WHERE id = :id"), {"id": file.id})
    await db_session.commit()

    assert await _count(db_session, SettingFile) == 0
    assert await _count(db_session, File) == 0


@pytest.mark.asyncio
async def test_single_slot_setting_allows_only_one_file(db_session: AsyncSession):
    await _make_file(db_session)
    with pytest.raises(IntegrityError):
        await _make_file(db_session, checksum="b" * 64)
    await db_session.rollback()
    assert await _count(db_session, SettingFile) == 1


@pytest.mark.asyncio
async def test_unknown_setting_key_is_rejected(db_session: AsyncSession):
    with pytest.raises(IntegrityError):
        await _make_file(db_session, key="something_else")


@pytest.mark.asyncio
async def test_stored_content_with_attachments_cannot_be_deleted(
    db_session: AsyncSession,
):
    file = await _make_file(db_session)
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("DELETE FROM stored_files WHERE id = :id"), {"id": file.stored_file_id}
        )


async def _make_project_file(
    db: AsyncSession, project: Project, *, checksum: str = "c" * 64
) -> File:
    stored = (
        await db.execute(
            select(StoredFile).where(StoredFile.checksum_sha256 == checksum)
        )
    ).scalar_one_or_none()
    if stored is None:
        stored = StoredFile(
            checksum_sha256=checksum,
            size_bytes=3,
            detected_content_type="application/pdf",
            bucket_key=f"{checksum[:2]}/{checksum[2:4]}/{checksum}.pdf",
            status="ready",
        )
        db.add(stored)
        await db.flush()
    file = File(stored_file_id=stored.id, kind="project", original_filename="c.pdf")
    db.add(file)
    await db.flush()
    db.add(ProjectFile(file_id=file.id, kind="project", project_id=project.id))
    await db.commit()
    return file


async def _tag(db: AsyncSession, name: str) -> FileTag:
    return (
        await db.execute(select(FileTag).where(FileTag.name == name))
    ).scalar_one()


@pytest.mark.asyncio
async def test_project_file_links_only_from_the_project_table(
    db_session: AsyncSession,
):
    project = await create_project(db_session)
    file = await _make_project_file(db_session, project)
    file_id = file.id  # a rollback below expires the instance

    # The composite key (file_id, kind) means a project-kind file cannot also be a
    # setting file: the setting link table only accepts kind = 'setting'.
    with pytest.raises(IntegrityError):
        db_session.add(SettingFile(file_id=file_id, kind="project", setting_key="org_logo"))
        await db_session.commit()
    await db_session.rollback()
    with pytest.raises(IntegrityError):
        db_session.add(SettingFile(file_id=file_id, kind="setting", setting_key="org_logo"))
        await db_session.commit()
    await db_session.rollback()
    assert await _count(db_session, SettingFile) == 0


@pytest.mark.asyncio
async def test_deleting_a_project_row_removes_its_files_and_tags(
    db_session: AsyncSession,
):
    project = await create_project(db_session)
    file = await _make_project_file(db_session, project)
    db_session.add(
        ProjectFileTag(file_id=file.id, tag_id=(await _tag(db_session, "contract")).id)
    )
    await db_session.commit()

    await db_session.execute(
        text("DELETE FROM projects WHERE id = :id"), {"id": project.id}
    )
    await db_session.commit()

    assert await _count(db_session, ProjectFile) == 0
    assert await _count(db_session, ProjectFileTag) == 0
    assert await _count(db_session, File) == 0
    assert await _count(db_session, StoredFile) == 1


@pytest.mark.asyncio
async def test_deleting_a_project_link_row_removes_its_file_record(
    db_session: AsyncSession,
):
    project = await create_project(db_session)
    file = await _make_project_file(db_session, project)
    await db_session.execute(
        text("DELETE FROM project_files WHERE file_id = :id"), {"id": file.id}
    )
    await db_session.commit()

    assert await _count(db_session, File) == 0


@pytest.mark.asyncio
async def test_deleting_a_file_record_cascades_to_project_link_and_tags(
    db_session: AsyncSession,
):
    project = await create_project(db_session)
    file = await _make_project_file(db_session, project)
    db_session.add(
        ProjectFileTag(file_id=file.id, tag_id=(await _tag(db_session, "invoice")).id)
    )
    await db_session.commit()

    await db_session.execute(text("DELETE FROM files WHERE id = :id"), {"id": file.id})
    await db_session.commit()

    assert await _count(db_session, ProjectFile) == 0
    assert await _count(db_session, ProjectFileTag) == 0


@pytest.mark.asyncio
async def test_unknown_file_kind_is_rejected(db_session: AsyncSession):
    stored = StoredFile(
        checksum_sha256="d" * 64,
        size_bytes=1,
        detected_content_type="application/pdf",
        bucket_key="dd/dd/x.pdf",
        status="ready",
    )
    db_session.add(stored)
    await db_session.flush()
    db_session.add(File(stored_file_id=stored.id, kind="time_entry", original_filename="x"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_a_file_can_carry_several_tags_once_each(db_session: AsyncSession):
    project = await create_project(db_session)
    file = await _make_project_file(db_session, project)
    for name in ("contract", "addendum"):
        db_session.add(
            ProjectFileTag(file_id=file.id, tag_id=(await _tag(db_session, name)).id)
        )
    await db_session.commit()
    assert await _count(db_session, ProjectFileTag) == 2

    db_session.add(
        ProjectFileTag(file_id=file.id, tag_id=(await _tag(db_session, "contract")).id)
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_vocabulary_is_seeded_with_exactly_the_default_tags(
    db_session: AsyncSession,
):
    names = (await db_session.execute(select(FileTag.name))).scalars().all()
    assert sorted(names) == sorted(DEFAULT_FILE_TAGS)
    assert sorted(DEFAULT_FILE_TAGS) == sorted(
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_name", ["  Purchase   Order ", "Contract", " contract", "a  b", ""]
)
async def test_unnormalized_tag_names_are_rejected(
    db_session: AsyncSession, bad_name: str
):
    db_session.add(FileTag(name=bad_name))
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_duplicate_tag_names_are_rejected(db_session: AsyncSession):
    db_session.add(FileTag(name="contract"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_an_in_use_tag_cannot_be_deleted(db_session: AsyncSession):
    project = await create_project(db_session)
    file = await _make_project_file(db_session, project)
    tag = await _tag(db_session, "contract")
    db_session.add(ProjectFileTag(file_id=file.id, tag_id=tag.id))
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("DELETE FROM file_tags WHERE id = :id"), {"id": tag.id}
        )
        await db_session.commit()
