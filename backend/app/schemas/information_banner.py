from typing import Literal

from pydantic import BaseModel


class BannerPlacement(BaseModel):
    message: str
    icon: Literal["none", "info", "warning"]
    color: Literal["neutral", "blue", "yellow", "red"]


class PublicBanner(BaseModel):
    """What each place a banner can appear should show, or None for nothing. Deliberately
    holds no switch values and no other setting: it is readable without signing in."""

    login: BannerPlacement | None
    site_wide: BannerPlacement | None
