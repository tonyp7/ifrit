import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.db import get_db
from app.models.company import Company
from app.schemas.company import (
    AddressOut,
    AddressWrite,
    CompanyDetail,
    CompanyListItem,
    CompanyListResponse,
    CompanyWrite,
    PartyIdentifierOut,
    PartyIdentifierWrite,
)
from app.services import company_service

router = APIRouter(prefix="/companies", tags=["companies"])

# Read-only lookups are also needed by the `projects` screen (manager-accessible,
# not just `configuration`) to populate its vendor/client pickers — see
# docs/requirements/project.md's own "As a manager, I want to create a project by
# selecting... vendor... client..." user story. Every write below stays
# administrator-only: that's genuine Companies-configuration management, not a
# read a manager needs. Router-level `dependencies` used to gate everything to
# administrator only, including these two GETs, which is why a manager hit a 403
# just loading the project form's dropdowns.
_read_roles = Depends(require_roles("administrator", "manager"))
_write_roles = Depends(require_roles("administrator"))


async def _get_company_or_404(db: AsyncSession, company_id: uuid.UUID) -> Company:
    company = await company_service.get_company(db, company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found"
        )
    return company


@router.get("", response_model=CompanyListResponse, dependencies=[_read_roles])
async def list_companies(
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    is_vendor: bool | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> CompanyListResponse:
    companies, total = await company_service.list_companies(
        db, search, page, is_vendor=is_vendor, is_active=is_active
    )
    return CompanyListResponse(
        items=[
            CompanyListItem(
                id=c.id,
                legal_name=c.legal_name,
                country_of_registration=c.country_of_registration,
                is_active=c.is_active,
            )
            for c in companies
        ],
        total=total,
        page=page,
        page_size=company_service.PAGE_SIZE,
    )


@router.post(
    "",
    response_model=CompanyDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_write_roles],
)
async def create_company(
    payload: CompanyWrite, db: AsyncSession = Depends(get_db)
) -> CompanyDetail:
    company = await company_service.create_company(db, payload)
    return company_service.to_company_detail(company)


@router.get("/{company_id}", response_model=CompanyDetail, dependencies=[_read_roles])
async def get_company(
    company_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> CompanyDetail:
    company = await _get_company_or_404(db, company_id)
    return company_service.to_company_detail(company)


@router.patch(
    "/{company_id}", response_model=CompanyDetail, dependencies=[_write_roles]
)
async def update_company(
    company_id: uuid.UUID, payload: CompanyWrite, db: AsyncSession = Depends(get_db)
) -> CompanyDetail:
    company = await _get_company_or_404(db, company_id)
    company = await company_service.update_company(db, company, payload)
    return company_service.to_company_detail(company)


@router.post(
    "/{company_id}/duplicate",
    response_model=CompanyDetail,
    dependencies=[_write_roles],
)
async def duplicate_company(
    company_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> CompanyDetail:
    company = await _get_company_or_404(db, company_id)
    new_company = await company_service.duplicate_company(db, company)
    return company_service.to_company_detail(new_company)


@router.post(
    "/{company_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_write_roles],
)
async def deactivate_company(
    company_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    company = await _get_company_or_404(db, company_id)
    await company_service.deactivate_company(db, company)


@router.post(
    "/{company_id}/identifiers",
    response_model=PartyIdentifierOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_write_roles],
)
async def add_identifier(
    company_id: uuid.UUID,
    payload: PartyIdentifierWrite,
    db: AsyncSession = Depends(get_db),
) -> PartyIdentifierOut:
    company = await _get_company_or_404(db, company_id)
    try:
        identifier = await company_service.add_identifier(db, company, payload)
    except IntegrityError as err:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An identical identifier already exists for this company",
        ) from err
    return company_service.to_identifier_out(identifier)


@router.patch(
    "/{company_id}/identifiers/{identifier_id}",
    response_model=PartyIdentifierOut,
    dependencies=[_write_roles],
)
async def update_identifier(
    company_id: uuid.UUID,
    identifier_id: uuid.UUID,
    payload: PartyIdentifierWrite,
    db: AsyncSession = Depends(get_db),
) -> PartyIdentifierOut:
    identifier = await company_service.get_identifier(db, company_id, identifier_id)
    if identifier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Identifier not found"
        )
    try:
        identifier = await company_service.update_identifier(db, identifier, payload)
    except IntegrityError as err:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An identical identifier already exists for this company",
        ) from err
    return company_service.to_identifier_out(identifier)


@router.delete(
    "/{company_id}/identifiers/{identifier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_write_roles],
)
async def delete_identifier(
    company_id: uuid.UUID, identifier_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    identifier = await company_service.get_identifier(db, company_id, identifier_id)
    if identifier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Identifier not found"
        )
    await company_service.delete_identifier(db, identifier)


@router.post(
    "/{company_id}/addresses",
    response_model=AddressOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_write_roles],
)
async def add_address(
    company_id: uuid.UUID, payload: AddressWrite, db: AsyncSession = Depends(get_db)
) -> AddressOut:
    company = await _get_company_or_404(db, company_id)
    if payload.is_primary:
        conflict = await company_service.get_conflicting_primary_address(
            db, company_id, payload.address_type
        )
        if conflict is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A primary {payload.address_type} address already exists for this "
                "company",
            )
    address = await company_service.add_address(db, company, payload)
    return company_service.to_address_out(address)


@router.patch(
    "/{company_id}/addresses/{address_id}",
    response_model=AddressOut,
    dependencies=[_write_roles],
)
async def update_address(
    company_id: uuid.UUID,
    address_id: uuid.UUID,
    payload: AddressWrite,
    db: AsyncSession = Depends(get_db),
) -> AddressOut:
    address = await company_service.get_address(db, company_id, address_id)
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Address not found"
        )
    if payload.is_primary:
        conflict = await company_service.get_conflicting_primary_address(
            db, company_id, payload.address_type, exclude_address_id=address_id
        )
        if conflict is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A primary {payload.address_type} address already exists for this "
                "company",
            )
    address = await company_service.update_address(db, address, payload)
    return company_service.to_address_out(address)


@router.delete(
    "/{company_id}/addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_write_roles],
)
async def delete_address(
    company_id: uuid.UUID, address_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    address = await company_service.get_address(db, company_id, address_id)
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Address not found"
        )
    await company_service.delete_address(db, address)
