"""Shared setup for the invoice tests: billing users cannot create projects through the API,
so projects, service lines and time entries are built directly."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.currency import Currency
from app.models.project import Project, ServiceLine
from app.models.time_entry import TimeEntry
from app.models.user import User
from tests.factories import create_company, create_currency, create_user

_CURRENCIES = {"EUR": ("978", 2), "USD": ("840", 2), "JPY": ("392", 0)}


async def login(client, db_session: AsyncSession, role_name: str = "billing") -> User:
    email = f"{role_name}@example.com"
    user = await create_user(
        db_session, name_id=email, password="pw", role_name=role_name
    )
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": "pw"}
    )
    assert response.status_code == 200
    return user


async def ensure_currency(
    db_session: AsyncSession, code: str = "EUR", *, is_enabled: bool = True
) -> Currency:
    existing = await db_session.get(Currency, code)
    if existing is not None:
        return existing
    numeric, minor = _CURRENCIES.get(code, ("999", 2))
    return await create_currency(
        db_session,
        alpha_code=code,
        numeric_code=numeric,
        name=code,
        minor_unit=minor,
        is_enabled=is_enabled,
    )


async def make_project(
    db_session: AsyncSession,
    *,
    name: str = "Website redesign",
    project_type: str = "time_and_material",
    status: str = "active",
    currency: str = "EUR",
    vendor: Company | None = None,
    client: Company | None = None,
) -> Project:
    await ensure_currency(db_session, currency)
    vendor = vendor or await create_company(
        db_session, legal_name="Ifrit Consulting SAS", is_vendor=True
    )
    client = client or await create_company(db_session, legal_name="ACME Corp")
    project = Project(
        name=name,
        vendor_company_id=vendor.id,
        client_company_id=client.id,
        invoicing_currency=currency,
        project_type=project_type,
        status=status,
    )
    db_session.add(project)
    await db_session.commit()
    return project


async def add_service_line(
    db_session: AsyncSession,
    project: Project,
    *,
    name: str | None = "Senior developer",
    uom: str = "hours",
    unit_price: str = "95",
    is_active: bool = True,
) -> ServiceLine:
    line = ServiceLine(
        project_id=project.id,
        name=name,
        quantity=Decimal(100),
        uom=uom,
        unit_price=Decimal(unit_price),
        is_active=is_active,
    )
    db_session.add(line)
    await db_session.commit()
    return line


async def make_consultant(
    db_session: AsyncSession, email: str = "c@example.com"
) -> User:
    return await create_user(
        db_session, name_id=email, password="pw", role_name="consultant"
    )


async def log_hours(
    db_session: AsyncSession,
    user: User,
    line: ServiceLine,
    day: date,
    hours: float,
    *,
    locked: bool = False,
) -> TimeEntry:
    entry = TimeEntry(
        user_id=user.id,
        service_line_id=line.id,
        date=day,
        time_entry=timedelta(hours=hours),
        is_locked=locked,
    )
    db_session.add(entry)
    await db_session.commit()
    return entry
