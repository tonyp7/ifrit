import logging
import uuid
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting
from app.settings_registry import SETTINGS_REGISTRY

logger = logging.getLogger(__name__)


class UnknownSettingGroupError(Exception):
    pass


class UnknownSettingKeyError(Exception):
    pass


def _schema(group: str) -> type[BaseModel]:
    schema = SETTINGS_REGISTRY.get(group)
    if schema is None:
        raise UnknownSettingGroupError(group)
    return schema


async def get_group(db: AsyncSession, group: str) -> BaseModel:
    """The group's current settings, with defaults for anything not stored.

    Always read from the database: there is a single reader today (a PDF export reads once
    per request) and a cache would only add stale reads and invalidation to get right.
    Reading never fails because of what is stored: a value that no longer satisfies the
    schema (a tightened range, a hand-edited row) is ignored with a warning, so one bad
    row cannot turn every consumer, such as a PDF export, into an error.
    """
    schema = _schema(group)
    rows = await db.execute(
        select(AppSetting.key, AppSetting.value).where(AppSetting.group_name == group)
    )
    known = schema.model_fields.keys()
    # Rows of keys the code no longer defines stay in the table but are not read.
    stored: dict[str, Any] = {key: value for key, value in rows if key in known}
    while True:
        try:
            return schema.model_validate(stored)
        except ValidationError as err:
            invalid = {e["loc"][0] for e in err.errors() if e["loc"]} & stored.keys()
            if not invalid:
                # Not caused by a stored value, so dropping rows cannot help.
                raise
            logger.warning(
                "Ignoring invalid stored settings in group %s: %s",
                group,
                sorted(invalid),
            )
            stored = {k: v for k, v in stored.items() if k not in invalid}


async def get_all_groups(db: AsyncSession) -> dict[str, BaseModel]:
    return {group: await get_group(db, group) for group in SETTINGS_REGISTRY}


async def update_group(
    db: AsyncSession, group: str, patch: dict[str, Any], user_id: uuid.UUID
) -> BaseModel:
    """Changes only the settings in `patch` and returns the whole updated group.

    The whole merged result is validated first, so one invalid value rejects the request
    and nothing is written. Raises pydantic's ValidationError for an unknown key, a wrong
    type or an out-of-range value.
    """
    schema = _schema(group)
    current = await get_group(db, group)
    merged = schema.model_validate({**current.model_dump(), **patch})

    # Only the keys sent are written, so the audit data of the others stays as it was and
    # two administrators editing different keys never overwrite each other.
    for key in patch:
        statement = insert(AppSetting).values(
            group_name=group,
            key=key,
            value=getattr(merged, key),
            updated_by=user_id,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["group_name", "key"],
            set_={
                "value": statement.excluded.value,
                "updated_by": user_id,
                "updated_at": func.now(),
            },
        )
        await db.execute(statement)

    await db.commit()
    return merged


async def reset_key(db: AsyncSession, group: str, key: str) -> BaseModel:
    """Discards one stored value so its default applies again. A no-op if none is stored."""
    schema = _schema(group)
    if key not in schema.model_fields:
        raise UnknownSettingKeyError(key)
    await db.execute(
        delete(AppSetting).where(AppSetting.group_name == group, AppSetting.key == key)
    )
    await db.commit()
    return await get_group(db, group)
