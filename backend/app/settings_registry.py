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


# The single source of truth for which groups and keys exist. Every field needs a default
# (a missing row must never be an error) and must be a scalar: bool, int, str, or float
# declared with allow_inf_nan=False, since JSONB cannot hold NaN or infinity.
SETTINGS_REGISTRY: dict[str, type[BaseModel]] = {
    "pdf-export": PdfExportSettings,
}


def _check_registry() -> None:
    reserved = RESERVED_GROUP_NAMES & SETTINGS_REGISTRY.keys()
    if reserved:
        raise RuntimeError(f"Reserved settings group name(s): {sorted(reserved)}")


_check_registry()
