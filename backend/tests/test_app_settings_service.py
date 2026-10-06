import logging
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.models.app_setting import AppSetting
from app.models.user import User, user_roles
from app.services import app_settings
from tests.factories import create_user


async def _store(db_session, key: str, value, group: str = "pdf-export") -> None:
    db_session.add(AppSetting(group_name=group, key=key, value=value))
    await db_session.commit()


async def _row(db_session, key: str) -> AppSetting | None:
    result = await db_session.execute(
        select(AppSetting).where(
            AppSetting.group_name == "pdf-export", AppSetting.key == key
        )
    )
    row: AppSetting | None = result.scalar_one_or_none()
    return row


async def _admin(db_session) -> User:
    return await create_user(
        db_session, name_id="a@example.com", password="pw", role_name="administrator"
    )


# --- reading ----------------------------------------------------------------------


async def test_a_group_with_no_rows_reads_as_its_defaults(db_session) -> None:
    group = await app_settings.get_group(db_session, "pdf-export")
    assert group.model_dump() == {"export_logo": True, "logo_height_mm": 20}


async def test_stored_values_override_the_defaults(db_session) -> None:
    await _store(db_session, "logo_height_mm", 35)
    group = await app_settings.get_group(db_session, "pdf-export")
    assert group.model_dump() == {"export_logo": True, "logo_height_mm": 35}


async def test_stale_keys_are_ignored(db_session) -> None:
    await _store(db_session, "removed_setting", "x")
    group = await app_settings.get_group(db_session, "pdf-export")
    assert group.model_dump() == {"export_logo": True, "logo_height_mm": 20}


async def test_an_invalid_stored_value_falls_back_to_its_default(
    db_session, caplog
) -> None:
    await _store(db_session, "logo_height_mm", 500)
    await _store(db_session, "export_logo", False)

    with caplog.at_level(logging.WARNING):
        group = await app_settings.get_group(db_session, "pdf-export")

    # The other key keeps its stored value.
    assert group.model_dump() == {"export_logo": False, "logo_height_mm": 20}
    assert "logo_height_mm" in caplog.text


async def test_a_wrongly_typed_stored_value_falls_back_to_its_default(
    db_session,
) -> None:
    await _store(db_session, "logo_height_mm", "tall")
    await _store(db_session, "export_logo", 1)
    group = await app_settings.get_group(db_session, "pdf-export")
    assert group.model_dump() == {"export_logo": True, "logo_height_mm": 20}


async def test_an_unknown_group_is_an_error(db_session) -> None:
    with pytest.raises(app_settings.UnknownSettingGroupError):
        await app_settings.get_group(db_session, "nope")


async def test_get_all_groups_lists_every_registered_group(db_session) -> None:
    groups = await app_settings.get_all_groups(db_session)
    assert list(groups) == ["pdf-export"]


async def test_a_read_right_after_a_write_sees_the_new_value(db_session) -> None:
    admin = await _admin(db_session)
    await app_settings.update_group(
        db_session, "pdf-export", {"logo_height_mm": 33}, admin.id
    )
    group = await app_settings.get_group(db_session, "pdf-export")
    assert group.model_dump()["logo_height_mm"] == 33


# --- updating ---------------------------------------------------------------------


async def test_update_writes_only_the_keys_sent(db_session) -> None:
    admin = await _admin(db_session)

    result = await app_settings.update_group(
        db_session, "pdf-export", {"logo_height_mm": 25}, admin.id
    )

    assert result.model_dump() == {"export_logo": True, "logo_height_mm": 25}
    assert await _row(db_session, "export_logo") is None
    row = await _row(db_session, "logo_height_mm")
    assert row is not None and row.value == 25 and row.updated_by == admin.id


async def test_an_unsent_key_keeps_its_audit_data(db_session) -> None:
    admin = await _admin(db_session)
    await app_settings.update_group(
        db_session, "pdf-export", {"export_logo": False}, admin.id
    )
    first = await _row(db_session, "export_logo")
    assert first is not None
    stamped_at = first.updated_at

    await app_settings.update_group(
        db_session, "pdf-export", {"logo_height_mm": 40}, admin.id
    )

    await db_session.refresh(first)
    assert first.updated_at == stamped_at
    assert first.value is False


async def test_a_key_sent_with_its_current_value_is_stamped_again(db_session) -> None:
    admin = await _admin(db_session)
    await app_settings.update_group(
        db_session, "pdf-export", {"logo_height_mm": 25}, admin.id
    )
    first = await _row(db_session, "logo_height_mm")
    assert first is not None
    first_at = first.updated_at

    await app_settings.update_group(
        db_session, "pdf-export", {"logo_height_mm": 25}, admin.id
    )

    await db_session.refresh(first)
    assert first.updated_at > first_at


async def test_an_invalid_value_alongside_a_valid_one_writes_nothing(
    db_session,
) -> None:
    admin = await _admin(db_session)

    with pytest.raises(ValidationError):
        await app_settings.update_group(
            db_session,
            "pdf-export",
            {"export_logo": False, "logo_height_mm": 500},
            admin.id,
        )

    assert await _row(db_session, "export_logo") is None
    assert await _row(db_session, "logo_height_mm") is None


@pytest.mark.parametrize("patch", [{"nope": 1}, {"logo_height_mm": "25"}])
async def test_unknown_keys_and_wrong_types_are_rejected(db_session, patch) -> None:
    admin = await _admin(db_session)
    with pytest.raises(ValidationError):
        await app_settings.update_group(db_session, "pdf-export", patch, admin.id)


async def test_an_empty_patch_writes_nothing(db_session) -> None:
    admin = await _admin(db_session)
    result = await app_settings.update_group(db_session, "pdf-export", {}, admin.id)
    assert result.model_dump() == {"export_logo": True, "logo_height_mm": 20}
    assert (await db_session.execute(select(AppSetting))).first() is None


async def test_an_update_of_an_unknown_group_is_an_error(db_session) -> None:
    with pytest.raises(app_settings.UnknownSettingGroupError):
        await app_settings.update_group(db_session, "nope", {}, uuid.uuid4())


async def test_the_height_is_kept_while_the_logo_is_off(db_session) -> None:
    admin = await _admin(db_session)
    await app_settings.update_group(
        db_session, "pdf-export", {"logo_height_mm": 35}, admin.id
    )
    result = await app_settings.update_group(
        db_session, "pdf-export", {"export_logo": False}, admin.id
    )
    assert result.model_dump() == {"export_logo": False, "logo_height_mm": 35}


async def test_an_update_merges_over_the_stored_state(db_session) -> None:
    admin = await _admin(db_session)
    await _store(db_session, "export_logo", False)
    result = await app_settings.update_group(
        db_session, "pdf-export", {"logo_height_mm": 10}, admin.id
    )
    assert result.model_dump() == {"export_logo": False, "logo_height_mm": 10}


# --- reset ------------------------------------------------------------------------


async def test_reset_restores_the_default(db_session) -> None:
    await _store(db_session, "logo_height_mm", 35)
    result = await app_settings.reset_key(db_session, "pdf-export", "logo_height_mm")
    assert result.model_dump()["logo_height_mm"] == 20
    assert await _row(db_session, "logo_height_mm") is None


async def test_reset_of_a_key_with_no_row_succeeds(db_session) -> None:
    result = await app_settings.reset_key(db_session, "pdf-export", "logo_height_mm")
    assert result.model_dump() == {"export_logo": True, "logo_height_mm": 20}


async def test_reset_validates_the_group_and_the_key(db_session) -> None:
    with pytest.raises(app_settings.UnknownSettingGroupError):
        await app_settings.reset_key(db_session, "nope", "x")
    with pytest.raises(app_settings.UnknownSettingKeyError):
        await app_settings.reset_key(db_session, "pdf-export", "nope")


# --- audit ------------------------------------------------------------------------


async def test_deleting_the_author_keeps_the_setting_with_no_author(
    db_session,
) -> None:
    admin = await _admin(db_session)
    await app_settings.update_group(
        db_session, "pdf-export", {"logo_height_mm": 25}, admin.id
    )

    # Users are deactivated, not deleted, in the app; this is the database-level guarantee
    # if one is ever removed. Their role links go with them (ON DELETE CASCADE).
    await db_session.execute(delete(User).where(User.id == admin.id))
    await db_session.commit()
    links = await db_session.execute(
        select(user_roles).where(user_roles.c.user_id == admin.id)
    )
    assert links.first() is None

    row = await _row(db_session, "logo_height_mm")
    assert row is not None
    await db_session.refresh(row)
    assert row.value == 25
    assert row.updated_by is None
