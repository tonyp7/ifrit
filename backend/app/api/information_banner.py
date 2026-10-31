from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.information_banner import PublicBanner
from app.services import information_banner_service

# No authentication dependency, on purpose: the sign-in page shows the banner to people who
# are not signed in. It lives outside /settings so that every route under that prefix stays
# administrator-only.
router = APIRouter(prefix="/information-banner", tags=["information-banner"])


@router.get("", response_model=PublicBanner)
async def get_information_banner(
    response: Response, db: AsyncSession = Depends(get_db)
) -> PublicBanner:
    # A banner switched on or off must show on the next load, not after a cache expires.
    response.headers["Cache-Control"] = "no-store"
    return await information_banner_service.get_public_banner(db)
