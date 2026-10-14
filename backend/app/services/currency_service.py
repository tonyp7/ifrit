from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.currency import Currency


async def list_enabled_currencies(db: AsyncSession) -> list[Currency]:
    result = await db.execute(
        select(Currency).where(Currency.is_enabled.is_(True)).order_by(Currency.name)
    )
    return list(result.scalars().all())


async def get_enabled_currency(db: AsyncSession, alpha_code: str) -> Currency | None:
    """The currency, or None when it does not exist or is not enabled: only enabled
    currencies may be chosen on a new or edited record."""
    result = await db.execute(
        select(Currency).where(
            Currency.alpha_code == alpha_code, Currency.is_enabled.is_(True)
        )
    )
    return result.scalar_one_or_none()
