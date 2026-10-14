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
    PayeeAccountOut,
    PayeeAccountWrite,
)
from app.services import company_service, currency_service

router = APIRouter(prefix="/companies", tags=["companies"])

# Read-only lookups are also needed by the `projects` screen (manager-accessible,
# not just `configuration`) to populate its vendor/client pickers. Every write below
# stays administrator-only: that's genuine Companies-configuration management, not a
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
    sort_by: str | None = None,
    sort_dir: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> CompanyListResponse:
    companies, total = await company_service.list_companies(
        db,
        search,
        page,
        is_vendor=is_vendor,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return CompanyListResponse(
        items=[
            CompanyListItem(
                id=c.id,
                legal_name=c.legal_name,
                trading_name=c.trading_name,
                country_of_registration=c.country_of_registration,
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
    await _get_company_or_404(db, company_id)
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
    await _get_company_or_404(db, company_id)
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
    await _get_company_or_404(db, company_id)
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
    await _get_company_or_404(db, company_id)
    address = await company_service.get_address(db, company_id, address_id)
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Address not found"
        )
    await company_service.delete_address(db, address)


_DUPLICATE_ACCOUNT_DETAIL = (
    "An account with this identifier already exists for this company"
)


async def _check_payee_account(
    db: AsyncSession,
    company_id: uuid.UUID,
    payload: PayeeAccountWrite,
    exclude_account_id: uuid.UUID | None = None,
) -> None:
    """Refuse up front what the database would refuse anyway, so each refusal carries a
    message naming its own reason rather than a raw constraint violation."""
    if await currency_service.get_enabled_currency(db, payload.currency_code) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="currency_code must reference an enabled currency",
        )
    if await company_service.get_payee_account_by_identifier(
        db,
        company_id,
        payload.account_identifier,
        exclude_account_id=exclude_account_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_ACCOUNT_DETAIL
        )
    if (
        payload.is_primary
        and await company_service.get_conflicting_primary_payee_account(
            db, company_id, payload.currency_code, exclude_account_id=exclude_account_id
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A primary account in {payload.currency_code} already exists for this "
            "company",
        )


@router.post(
    "/{company_id}/payee-accounts",
    response_model=PayeeAccountOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_write_roles],
)
async def add_payee_account(
    company_id: uuid.UUID,
    payload: PayeeAccountWrite,
    db: AsyncSession = Depends(get_db),
) -> PayeeAccountOut:
    company = await _get_company_or_404(db, company_id)
    await _check_payee_account(db, company_id, payload)
    try:
        account = await company_service.add_payee_account(db, company, payload)
    except IntegrityError as err:
        # Only reachable when a concurrent request wins the race past the checks above.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_ACCOUNT_DETAIL
        ) from err
    return company_service.to_payee_account_out(account)


@router.patch(
    "/{company_id}/payee-accounts/{account_id}",
    response_model=PayeeAccountOut,
    dependencies=[_write_roles],
)
async def update_payee_account(
    company_id: uuid.UUID,
    account_id: uuid.UUID,
    payload: PayeeAccountWrite,
    db: AsyncSession = Depends(get_db),
) -> PayeeAccountOut:
    await _get_company_or_404(db, company_id)
    account = await company_service.get_payee_account(db, company_id, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payee account not found"
        )
    await _check_payee_account(db, company_id, payload, exclude_account_id=account_id)
    try:
        account = await company_service.update_payee_account(db, account, payload)
    except IntegrityError as err:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_ACCOUNT_DETAIL
        ) from err
    return company_service.to_payee_account_out(account)


@router.delete(
    "/{company_id}/payee-accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_write_roles],
)
async def delete_payee_account(
    company_id: uuid.UUID, account_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    await _get_company_or_404(db, company_id)
    account = await company_service.get_payee_account(db, company_id, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payee account not found"
        )
    await company_service.delete_payee_account(db, account)
