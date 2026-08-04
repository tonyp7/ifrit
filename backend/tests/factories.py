from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.models.company import Company
from app.models.currency import Currency
from app.models.user import Role, User


async def ensure_role(db_session: AsyncSession, name: str) -> Role:
    """Get-or-create a Role row. The test DB is set up via Base.metadata.create_all
    (see tests/conftest.py), not `alembic upgrade head`, so migration 0001's seeded
    administrator/manager/consultant rows never exist unless a test puts them there
    itself — this is that."""
    role = (
        await db_session.execute(select(Role).where(Role.name == name))
    ).scalar_one_or_none()
    if role is None:
        role = Role(name=name)
        db_session.add(role)
        await db_session.commit()
    return role


async def create_user(
    db_session: AsyncSession,
    *,
    name_id: str,
    password: str | None,
    role_name: str,
    full_name: str = "Jane Doe",
    is_sso: bool = False,
) -> User:
    role = await ensure_role(db_session, role_name)

    user = User(
        name_id=name_id,
        hashed_password=hash_password(password) if password is not None else None,
        full_name=full_name,
        roles=[role],
        is_sso=is_sso,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def create_company(
    db_session: AsyncSession,
    *,
    legal_name: str = "Acme Manufacturing SA",
    is_vendor: bool = False,
    country_of_registration: str = "BE",
    is_active: bool = True,
) -> Company:
    company = Company(
        legal_name=legal_name,
        is_vendor=is_vendor,
        country_of_registration=country_of_registration,
        is_active=is_active,
    )
    db_session.add(company)
    await db_session.commit()
    return company


async def create_currency(
    db_session: AsyncSession,
    *,
    alpha_code: str = "USD",
    numeric_code: str = "840",
    name: str = "US Dollar",
    minor_unit: int | None = 2,
    symbol: str | None = "$",
    is_active: bool = True,
    is_enabled: bool = True,
) -> Currency:
    currency = Currency(
        alpha_code=alpha_code,
        numeric_code=numeric_code,
        name=name,
        minor_unit=minor_unit,
        symbol=symbol,
        is_active=is_active,
        is_enabled=is_enabled,
    )
    db_session.add(currency)
    await db_session.commit()
    return currency
