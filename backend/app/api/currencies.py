from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.db import get_db
from app.schemas.currency import CurrencyOut
from app.services import currency_service

router = APIRouter(
    prefix="/currencies", tags=["currencies"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[CurrencyOut])
async def list_currencies(db: AsyncSession = Depends(get_db)) -> list[CurrencyOut]:
    currencies = await currency_service.list_enabled_currencies(db)
    return [
        CurrencyOut(
            alpha_code=c.alpha_code,
            name=c.name,
            minor_unit=c.minor_unit,
            symbol=c.symbol,
        )
        for c in currencies
    ]
