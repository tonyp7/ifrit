from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The path /api/settings/org-logo already belongs to the organization logo, so a group
# of that name would be unreachable.
RESERVED_GROUP_NAMES = frozenset({"org-logo"})


class PdfExportSettings(BaseModel):
    # Strict, so "25" or 25.0 is a validation error instead of being coerced into an int,
    # and what is stored keeps the JSON type the client sent.
    model_config = ConfigDict(extra="forbid", strict=True)

    export_logo: bool = True
    logo_height_mm: int = Field(default=20, ge=1, le=60)


class GeneralSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    # Converts logged hours into days when invoicing a service line billed in days. Whole
    # seconds so the hh:mm:ss input stores exactly what is shown, and the range runs from
    # half an hour to a full 24-hour day.
    standard_workday_seconds: int = Field(default=28800, ge=1800, le=86400)


class InvoicingSettings(BaseModel):
    # Spaces are stripped before the length check, so a name of only spaces fails
    # min_length and is rejected as blank rather than stored.
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    # Some jurisdictions require the title "Tax Invoice" instead of "Invoice".
    document_name: str = Field(default="Invoice", min_length=1, max_length=60)


class InformationBannerSettings(BaseModel):
    # Whitespace is stripped before the length check, so a message of only spaces or line
    # breaks is stored as "" instead of being rejected.
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    # The message, icon and color are validated and kept whatever the two switches say, so an
    # administrator can write and review the text before turning it on. Which placement shows
    # what is decided on the server (see information_banner_service), never by the browser.
    show_on_login: bool = False
    show_site_wide: bool = False
    # Short on purpose: it is a notice, and the sign-in page has to stay usable around it.
    message: str = Field(default="", max_length=200)
    # Stored as stable keys, not as the names of icons in a UI library.
    icon: Literal["none", "info", "warning"] = "info"
    color: Literal["neutral", "blue", "yellow", "red"] = "neutral"


# The single source of truth for which groups and keys exist. Every field needs a default
# (a missing row must never be an error) and must be a scalar: bool, int, str, or float
# declared with allow_inf_nan=False, since JSONB cannot hold NaN or infinity.
SETTINGS_REGISTRY: dict[str, type[BaseModel]] = {
    "pdf-export": PdfExportSettings,
    "general": GeneralSettings,
    "invoicing": InvoicingSettings,
    "information-banner": InformationBannerSettings,
}


def _check_registry() -> None:
    reserved = RESERVED_GROUP_NAMES & SETTINGS_REGISTRY.keys()
    if reserved:
        raise RuntimeError(f"Reserved settings group name(s): {sorted(reserved)}")


_check_registry()
