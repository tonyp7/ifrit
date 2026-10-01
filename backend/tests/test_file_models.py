import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File, SettingFile, StoredFile


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
