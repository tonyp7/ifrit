"""The test database is built once per session and emptied after every test, rather than
dropped and recreated. These check that the reset leaves the state a fresh schema would."""

from sqlalchemy import delete, func, select

from app.models.file import DEFAULT_FILE_TAGS, FileTag
from app.models.user import Role
from tests.conftest import reset_database


async def test_the_reset_empties_tables_and_restores_the_seed(db_session) -> None:
    db_session.add(Role(name="auditor"))
    await db_session.execute(
        delete(FileTag).where(FileTag.name == DEFAULT_FILE_TAGS[0])
    )
    await db_session.commit()

    conn = await db_session.connection()
    await reset_database(conn)
    await db_session.commit()

    roles = (await db_session.execute(select(func.count(Role.id)))).scalar_one()
    tags = (await db_session.execute(select(FileTag.name))).scalars().all()
    assert roles == 0
    assert sorted(tags) == sorted(DEFAULT_FILE_TAGS)
