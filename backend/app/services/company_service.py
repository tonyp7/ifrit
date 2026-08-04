import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.company import Address, AddressType, Company, PartyIdentifier
from app.schemas.company import (
    AddressOut,
    AddressWrite,
    CompanyDetail,
    CompanyWrite,
    PartyIdentifierOut,
    PartyIdentifierWrite,
)

PAGE_SIZE = 50


async def list_companies(
    db: AsyncSession,
    search: str | None,
    page: int,
    is_vendor: bool | None = None,
    is_active: bool | None = None,
) -> tuple[list[Company], int]:
    stmt = select(Company)
    count_stmt = select(func.count()).select_from(Company)

    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(Company.legal_name.ilike(pattern))
        count_stmt = count_stmt.where(Company.legal_name.ilike(pattern))
    # is_vendor/is_active: used by the Project form's vendor/client pickers (see
    # docs/requirements/project.md#1-entity-project) to narrow the list beyond the
    # companies admin screen's unfiltered/all-statuses default.
    if is_vendor is not None:
        stmt = stmt.where(Company.is_vendor == is_vendor)
        count_stmt = count_stmt.where(Company.is_vendor == is_vendor)
    if is_active is not None:
        stmt = stmt.where(Company.is_active == is_active)
        count_stmt = count_stmt.where(Company.is_active == is_active)

    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        stmt.order_by(Company.legal_name)
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    companies = list((await db.execute(stmt)).scalars().all())
    return companies, total


async def get_company(db: AsyncSession, company_id: uuid.UUID) -> Company | None:
    # populate_existing=True: add_identifier/add_address insert child rows directly
    # rather than through company.identifiers.append(...), so if this company is
    # already in the session's identity map with those collections previously loaded,
    # SQLAlchemy won't otherwise re-fetch them here — they'd stay stale for the rest
    # of the session (matters most for multi-call flows within one session, e.g. add
    # an identifier then immediately duplicate the company).
    result = await db.execute(
        select(Company)
        .options(selectinload(Company.identifiers), selectinload(Company.addresses))
        .where(Company.id == company_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def create_company(db: AsyncSession, data: CompanyWrite) -> Company:
    company = Company(**data.model_dump())
    db.add(company)
    await db.commit()
    # Re-fetch via get_company (selectinload) rather than db.refresh(): once an object
    # goes from pending to persistent, its never-touched relationship collections need
    # an explicit load to be accessed safely — db.refresh() doesn't eager-load them, it
    # just expires them, so a later `company.identifiers` access would lazy-load outside
    # of an async-safe context and raise MissingGreenlet.
    persisted = await get_company(db, company.id)
    assert persisted is not None
    return persisted


async def update_company(
    db: AsyncSession, company: Company, data: CompanyWrite
) -> Company:
    for field, value in data.model_dump().items():
        setattr(company, field, value)
    await db.commit()
    return company


async def deactivate_company(db: AsyncSession, company: Company) -> None:
    company.is_active = False
    await db.commit()


async def duplicate_company(db: AsyncSession, source: Company) -> Company:
    new_company = Company(
        is_vendor=source.is_vendor,
        legal_name=source.legal_name,
        trading_name=source.trading_name,
        legal_form=source.legal_form,
        country_of_registration=source.country_of_registration,
        is_active=True,
    )
    for identifier in source.identifiers:
        new_company.identifiers.append(
            PartyIdentifier(
                id_type=identifier.id_type,
                scheme_id=identifier.scheme_id,
                id_value=identifier.id_value,
                is_primary=identifier.is_primary,
            )
        )
    for address in source.addresses:
        new_company.addresses.append(
            Address(
                address_type=address.address_type,
                line1=address.line1,
                line2=address.line2,
                line3=address.line3,
                city=address.city,
                postal_zone=address.postal_zone,
                country_subdivision=address.country_subdivision,
                country_code=address.country_code,
                is_primary=address.is_primary,
            )
        )
    db.add(new_company)
    await db.commit()
    # Re-fetch via get_company (selectinload) — see create_company for why db.refresh()
    # isn't the right tool here either.
    persisted = await get_company(db, new_company.id)
    assert persisted is not None
    return persisted


async def add_identifier(
    db: AsyncSession, company: Company, data: PartyIdentifierWrite
) -> PartyIdentifier:
    identifier = PartyIdentifier(company_id=company.id, **data.model_dump())
    db.add(identifier)
    await db.commit()
    await db.refresh(identifier)
    return identifier


async def get_identifier(
    db: AsyncSession, company_id: uuid.UUID, identifier_id: uuid.UUID
) -> PartyIdentifier | None:
    result = await db.execute(
        select(PartyIdentifier).where(
            PartyIdentifier.id == identifier_id,
            PartyIdentifier.company_id == company_id,
        )
    )
    return result.scalar_one_or_none()


async def update_identifier(
    db: AsyncSession, identifier: PartyIdentifier, data: PartyIdentifierWrite
) -> PartyIdentifier:
    for field, value in data.model_dump().items():
        setattr(identifier, field, value)
    await db.commit()
    await db.refresh(identifier)
    return identifier


async def delete_identifier(db: AsyncSession, identifier: PartyIdentifier) -> None:
    await db.delete(identifier)
    await db.commit()


async def get_conflicting_primary_address(
    db: AsyncSession,
    company_id: uuid.UUID,
    address_type: AddressType,
    exclude_address_id: uuid.UUID | None = None,
) -> Address | None:
    """The existing primary Address of this type for this company, if any — used to
    reject a second one (see docs/requirements/company.md §3 Validation rules)."""
    stmt = select(Address).where(
        Address.company_id == company_id,
        Address.address_type == address_type,
        Address.is_primary.is_(True),
    )
    if exclude_address_id is not None:
        stmt = stmt.where(Address.id != exclude_address_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def add_address(
    db: AsyncSession, company: Company, data: AddressWrite
) -> Address:
    address = Address(company_id=company.id, **data.model_dump())
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return address


async def get_address(
    db: AsyncSession, company_id: uuid.UUID, address_id: uuid.UUID
) -> Address | None:
    result = await db.execute(
        select(Address).where(
            Address.id == address_id, Address.company_id == company_id
        )
    )
    return result.scalar_one_or_none()


async def update_address(
    db: AsyncSession, address: Address, data: AddressWrite
) -> Address:
    for field, value in data.model_dump().items():
        setattr(address, field, value)
    await db.commit()
    await db.refresh(address)
    return address


async def delete_address(db: AsyncSession, address: Address) -> None:
    await db.delete(address)
    await db.commit()


def to_identifier_out(identifier: PartyIdentifier) -> PartyIdentifierOut:
    return PartyIdentifierOut(
        id=identifier.id,
        company_id=identifier.company_id,
        id_type=identifier.id_type,
        scheme_id=identifier.scheme_id,
        id_value=identifier.id_value,
        is_primary=identifier.is_primary,
        valid_from=identifier.valid_from,
        valid_to=identifier.valid_to,
    )


def to_address_out(address: Address) -> AddressOut:
    return AddressOut(
        id=address.id,
        company_id=address.company_id,
        address_type=address.address_type,
        line1=address.line1,
        line2=address.line2,
        line3=address.line3,
        city=address.city,
        postal_zone=address.postal_zone,
        country_subdivision=address.country_subdivision,
        country_code=address.country_code,
        is_primary=address.is_primary,
        valid_from=address.valid_from,
        valid_to=address.valid_to,
    )


def to_company_detail(company: Company) -> CompanyDetail:
    return CompanyDetail(
        id=company.id,
        is_vendor=company.is_vendor,
        legal_name=company.legal_name,
        trading_name=company.trading_name,
        legal_form=company.legal_form,
        country_of_registration=company.country_of_registration,
        is_active=company.is_active,
        created_at=company.created_at,
        updated_at=company.updated_at,
        identifiers=[to_identifier_out(i) for i in company.identifiers],
        addresses=[to_address_out(a) for a in company.addresses],
    )
