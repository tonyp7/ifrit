from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.currency import Currency


async def list_enabled_currencies(db: AsyncSession) -> list[Currency]:
    result = await db.execute(
        select(Currency).where(Currency.is_enabled.is_(True)).order_by(Currency.name)
    )
    return list(result.scalars().all())
