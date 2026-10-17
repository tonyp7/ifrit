import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.company import AccountScheme, AddressType, PaymentMeansCode
from app.models.invoice import InvoiceStatus, PaymentTerms
from app.models.project import ProjectStatus, ProjectType, ReferenceKind, Uom
from app.schemas.company import BankAddress, PayeeAccountWrite
from app.schemas.project import MAX_PROJECT_REFERENCES, ProjectReferenceWrite

MAX_INVOICE_LINES = 200
MAX_INVOICE_REFERENCES = MAX_PROJECT_REFERENCES
DESCRIPTION_MAX = 500
PARTY_NAME_MAX = 255
# Long enough for a year of monthly invoicing to be fixed in one go, short enough that a
# mistyped year cannot sum a decade of time entries.
MAX_PERIOD_DAYS = 366
# The largest values NUMERIC(12, 5) and NUMERIC(14, 4) hold: anything larger would fail in
# the database rather than as a validation error.
_QUANTITY_LIMIT = Decimal(10) ** 7
_UNIT_PRICE_LIMIT = Decimal(10) ** 10
_CURRENCY_SHAPE = re.compile(r"^[A-Z]{3}$")


def _decimal_places(value: Decimal) -> int:
    exponent = value.normalize().as_tuple().exponent
    return -exponent if isinstance(exponent, int) and exponent < 0 else 0


def check_period(start: date | None, end: date | None) -> None:
    """Both dates or neither, in order, and no longer than MAX_PERIOD_DAYS."""
    if (start is None) != (end is None):
        raise ValueError("period_start and period_end must be given together")
    if start is not None and end is not None:
        if end < start:
            raise ValueError("period_end must not be before period_start")
        if (end - start).days + 1 > MAX_PERIOD_DAYS:
            raise ValueError(f"a period must be at most {MAX_PERIOD_DAYS} days long")


class PartyWrite(BaseModel):
    name: str
    # Absent altogether or complete enough to post a letter to, as for a bank address.
    address: BankAddress | None = None

    @model_validator(mode="after")
    def check_name(self) -> PartyWrite:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name must not be empty")
        if len(self.name) > PARTY_NAME_MAX:
            raise ValueError(f"name must be at most {PARTY_NAME_MAX} characters")
        return self


class InvoicePayeeWrite(BaseModel):
    """A company payee account's fields, checked by the very same rules, minus what only
    matters on the company (the primary flag). The currency only has to be an ISO 4217
    code, not an enabled one: a copy must stay valid after its currency is disabled."""

    payment_means_code: PaymentMeansCode
    account_scheme: AccountScheme
    account_identifier: str
    account_name: str | None = None
    currency_code: str
    bic: str | None = None
    bank_name: str | None = None
    bank_address: BankAddress | None = None

    @model_validator(mode="after")
    def normalize_and_check(self) -> InvoicePayeeWrite:
        # Reuses the company account's validation (IBAN checksum, SEPA needs IBAN, BIC
        # shape, blanks to null) and keeps its normalized values.
        checked = PayeeAccountWrite(**self.model_dump())
        self.account_identifier = checked.account_identifier
        self.account_name = checked.account_name
        self.currency_code = checked.currency_code
        self.bic = checked.bic
        self.bank_name = checked.bank_name
        if not _CURRENCY_SHAPE.match(self.currency_code):
            raise ValueError("currency_code must be an ISO 4217 code")
        return self


class InvoiceLineWrite(BaseModel):
    description: str
    quantity: Decimal
    uom: Uom
    unit_price: Decimal

    @model_validator(mode="after")
    def check_fields(self) -> InvoiceLineWrite:
        self.description = self.description.strip()
        if not self.description:
            raise ValueError("description must not be empty")
        if len(self.description) > DESCRIPTION_MAX:
            raise ValueError(
                f"description must be at most {DESCRIPTION_MAX} characters"
            )
        # Zero is allowed: a generated `Each` line waits for its quantity, with a warning.
        if self.quantity < 0:
            raise ValueError("quantity must not be negative")
        if self.quantity >= _QUANTITY_LIMIT or _decimal_places(self.quantity) > 5:
            raise ValueError(
                "quantity must be below 10,000,000 with at most 5 decimals"
            )
        # Negative is allowed: that is how a discount or a correction is written.
        if (
            abs(self.unit_price) >= _UNIT_PRICE_LIMIT
            or _decimal_places(self.unit_price) > 4
        ):
            raise ValueError(
                "unit_price must be below 10,000,000,000 with at most 4 decimals"
            )
        return self


class InvoiceWrite(BaseModel):
    project_id: uuid.UUID
    bill_from: PartyWrite
    bill_to: PartyWrite
    period_start: date | None = None
    period_end: date | None = None
    payment_terms: PaymentTerms | None = None
    due_date: date | None = None
    payee: InvoicePayeeWrite | None = None
    references: list[ProjectReferenceWrite] = Field(
        default_factory=list, max_length=MAX_INVOICE_REFERENCES
    )
    lines: list[InvoiceLineWrite] = Field(
        default_factory=list, max_length=MAX_INVOICE_LINES
    )

    @model_validator(mode="after")
    def check_fields(self) -> InvoiceWrite:
        check_period(self.period_start, self.period_end)
        if self.payment_terms is not None and self.due_date is not None:
            raise ValueError("give either payment_terms or due_date, not both")
        return self


class GenerateRequest(BaseModel):
    project_id: uuid.UUID
    service_line_ids: list[uuid.UUID] = Field(min_length=1)
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def check_period(self) -> GenerateRequest:
        check_period(self.period_start, self.period_end)
        return self


class GeneratedLine(BaseModel):
    # The service line's name, null when it has none: the client writes the description
    # itself, so it can be translated and its dates follow the user's locale.
    name: str | None
    quantity: Decimal
    uom: Uom
    unit_price: Decimal


class OmittedServiceLine(BaseModel):
    service_line_id: uuid.UUID
    name: str | None
    uom: Uom
    unit_price: Decimal


WarningCode = Literal[
    "unlocked_hours",
    "zero_quantity",
    "no_payee_account",
    "payee_currency",
    "inactive_company",
]


class UnlockedServiceLine(BaseModel):
    name: str | None
    uom: Uom
    unit_price: Decimal
    days: int


class InvoiceWarning(BaseModel):
    code: WarningCode
    # unlocked_hours: the lines with unlocked days in the period, and how many days.
    service_lines: list[UnlockedServiceLine] = []
    # inactive_company: which side was deactivated.
    companies: list[Literal["vendor", "client"]] = []


class GenerateResponse(BaseModel):
    lines: list[GeneratedLine]
    omitted: list[OmittedServiceLine]
    warnings: list[InvoiceWarning]


class PartyOut(BaseModel):
    name: str
    address: BankAddress | None


class InvoicePayeeOut(BaseModel):
    payment_means_code: PaymentMeansCode
    account_scheme: AccountScheme
    account_identifier: str
    account_name: str | None
    currency_code: str
    bic: str | None
    bank_name: str | None
    bank_address: BankAddress | None


class InvoiceLineOut(BaseModel):
    description: str
    quantity: Decimal
    uom: Uom
    unit_price: Decimal
    amount: Decimal


class InvoiceReferenceOut(BaseModel):
    kind: ReferenceKind
    label: str | None
    value: str


class InvoiceDetail(BaseModel):
    id: uuid.UUID
    status: InvoiceStatus
    project_id: uuid.UUID
    project_name: str
    currency_code: str
    currency_minor_unit: int | None
    bill_from: PartyOut
    bill_to: PartyOut
    period_start: date | None
    period_end: date | None
    payment_terms: PaymentTerms | None
    due_date: date | None
    payee: InvoicePayeeOut | None
    references: list[InvoiceReferenceOut]
    lines: list[InvoiceLineOut]
    subtotal: Decimal
    total: Decimal
    created_at: datetime
    updated_at: datetime
    warnings: list[InvoiceWarning]


class InvoiceListItem(BaseModel):
    id: uuid.UUID
    status: InvoiceStatus
    project_id: uuid.UUID
    project_name: str
    client_name: str
    period_start: date | None
    period_end: date | None
    currency_code: str
    currency_minor_unit: int | None
    total: Decimal
    payment_terms: PaymentTerms | None
    due_date: date | None
    created_at: datetime


class InvoiceListResponse(BaseModel):
    items: list[InvoiceListItem]
    total: int
    page: int
    page_size: int


class InvoiceableProject(BaseModel):
    id: uuid.UUID
    name: str
    project_type: ProjectType
    status: ProjectStatus
    client_name: str | None
    currency_code: str


class ContextAddress(BaseModel):
    id: uuid.UUID
    address_type: AddressType
    line1: str
    line2: str | None
    line3: str | None
    city: str
    postal_zone: str | None
    country_subdivision: str | None
    country_code: str
    is_primary: bool


class ContextCompany(BaseModel):
    id: uuid.UUID
    display_name: str
    is_active: bool
    addresses: list[ContextAddress]


class ContextPayeeAccount(InvoicePayeeOut):
    id: uuid.UUID
    is_primary: bool


class ContextServiceLine(BaseModel):
    id: uuid.UUID
    name: str | None
    uom: Uom
    unit_price: Decimal


class BillingContext(BaseModel):
    """What the invoice form needs to know about a project, read through the invoice API
    so that billing users need no access to the project and company endpoints."""

    id: uuid.UUID
    name: str
    project_type: ProjectType
    status: ProjectStatus
    is_active: bool
    currency_code: str
    currency_minor_unit: int | None
    vendor: ContextCompany | None
    client: ContextCompany | None
    payee_accounts: list[ContextPayeeAccount]
    service_lines: list[ContextServiceLine]
    references: list[InvoiceReferenceOut]
