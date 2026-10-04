import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app import settings_registry
from app.core.db import Base
from app.models.app_setting import AppSetting
from app.settings_registry import PdfExportSettings


def test_the_table_is_registered_with_the_models() -> None:
    assert "app_settings" in Base.metadata.tables


@pytest.mark.parametrize("value", [True, False, 20, 2.5, "text"])
async def test_scalar_values_are_accepted(db_session, value) -> None:
    db_session.add(AppSetting(group_name="g", key="k", value=value))
    await db_session.commit()


@pytest.mark.parametrize("value", [{"a": 1}, [1, 2], []])
async def test_trees_are_rejected_by_the_database(db_session, value) -> None:
    db_session.add(AppSetting(group_name="g", key="k", value=value))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_json_null_is_rejected_by_the_database(db_session) -> None:
    from sqlalchemy import text

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO app_settings (group_name, key, value) "
                "VALUES ('g', 'k', 'null'::jsonb)"
            )
        )


def test_pdf_export_defaults() -> None:
    settings = PdfExportSettings()
    assert settings.export_logo is True
    assert settings.logo_height_mm == 20


@pytest.mark.parametrize("height", [1, 20, 60])
def test_logo_height_accepts_the_range_edges(height) -> None:
    assert PdfExportSettings(logo_height_mm=height).logo_height_mm == height


@pytest.mark.parametrize("height", [0, 61, -5, 500])
def test_logo_height_outside_the_range_is_rejected(height) -> None:
    with pytest.raises(ValidationError):
        PdfExportSettings(logo_height_mm=height)


@pytest.mark.parametrize("height", ["25", 25.5, 25.0, True, None])
def test_logo_height_of_the_wrong_type_is_rejected(height) -> None:
    with pytest.raises(ValidationError):
        PdfExportSettings.model_validate({"logo_height_mm": height})


@pytest.mark.parametrize("flag", ["true", 1, None])
def test_export_logo_of_the_wrong_type_is_rejected(flag) -> None:
    with pytest.raises(ValidationError):
        PdfExportSettings.model_validate({"export_logo": flag})


def test_unknown_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        PdfExportSettings.model_validate({"nope": 1})


def test_a_group_named_like_the_logo_endpoint_is_refused(monkeypatch) -> None:
    monkeypatch.setitem(
        settings_registry.SETTINGS_REGISTRY, "org-logo", PdfExportSettings
    )
    with pytest.raises(RuntimeError, match="org-logo"):
        settings_registry._check_registry()
