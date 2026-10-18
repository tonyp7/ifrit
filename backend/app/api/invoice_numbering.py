from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.db import get_db
from app.models.user import User
from app.schemas.invoice_numbering import (
    NextNumberWrite,
    NumberingFormatWrite,
    NumberingState,
)
from app.services import invoice_numbering_service
from app.services.invoice_numbering_service import (
    NumberCollisionError,
    UnconfirmedFormatChangeError,
)

# Part of Configuration, so administrators only, like the rest of it.
_administrator = Depends(require_roles("administrator"))

router = APIRouter(
    prefix="/invoice-numbering",
    tags=["invoice-numbering"],
    dependencies=[_administrator],
)


@router.get("", response_model=NumberingState)
async def get_numbering(db: AsyncSession = Depends(get_db)) -> NumberingState:
    return await invoice_numbering_service.get_state(db)


@router.put("", response_model=NumberingState)
async def replace_numbering_format(
    payload: NumberingFormatWrite,
    user: User = _administrator,
    db: AsyncSession = Depends(get_db),
) -> NumberingState:
    try:
        await invoice_numbering_service.replace_format(
            db, payload, payload.confirm, user.id
        )
    except UnconfirmedFormatChangeError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Invoices have already been issued: confirm that the new numbering applies to "
                "newly issued invoices only"
            ),
        ) from err
    return await invoice_numbering_service.get_state(db)


@router.put("/next", response_model=NumberingState)
async def set_next_number(
    payload: NextNumberWrite, db: AsyncSession = Depends(get_db)
) -> NumberingState:
    try:
        await invoice_numbering_service.set_next(db, payload.next_value)
    except NumberCollisionError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The number {err.number} already exists",
        ) from err
    return await invoice_numbering_service.get_state(db)
