from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.information_banner import BannerPlacement, PublicBanner
from app.services import app_settings
from app.settings_registry import InformationBannerSettings


async def get_public_banner(db: AsyncSession) -> PublicBanner:
    """The banner for each placement. A placement is None unless its switch is on and there
    is a message to show, so a draft written while the banner is off is never sent to anyone:
    the decision is made here, not left to the browser."""
    group = await app_settings.get_group(db, "information-banner")
    assert isinstance(group, InformationBannerSettings)
    placement = (
        BannerPlacement(message=group.message, icon=group.icon, color=group.color)
        if group.message
        else None
    )
    return PublicBanner(
        login=placement if group.show_on_login else None,
        site_wide=placement if group.show_site_wide else None,
    )
