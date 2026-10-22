import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.company import (
    AccountScheme,
    AddressType,
    IdentifierType,
    PaymentMeansCode,
)
from app.models.invoice import InvoiceStatus, PaymentTerms, TaxBaseMode
from app.models.project import ProjectStatus, ProjectType, ReferenceKind, Uom
from app.schemas.company import BankAddress, PayeeAccountWrite
from app.schemas.project import MAX_PROJECT_REFERENCES, ProjectReferenceWrite

MAX_INVOICE_LINES = 200
MAX_INVOICE_TAXES = 20
TAX_LABEL_MAX = 100
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
# NUMERIC(22, 4): a typed tax amount must fit the column it is stored in.
_TAX_AMOUNT_LIMIT = Decimal(10) ** 18
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


class InvoiceTaxWrite(BaseModel):
    """A tax row as typed. Only the value the user typed counts: the rate of a rate-driven
    row, the amount of a hand-set row. The other one is worked out by the server, so
    whatever the client sends for it is dropped."""

    label: str
    base_mode: TaxBaseMode
    rate: Decimal | None = None
    amount: Decimal | None = None
    amount_set_by_hand: bool = False

    @model_validator(mode="after")
    def check_fields(self) -> InvoiceTaxWrite:
        self.label = self.label.strip()
        if not self.label:
            raise ValueError("label must not be empty")
        if len(self.label) > TAX_LABEL_MAX:
            raise ValueError(f"label must be at most {TAX_LABEL_MAX} characters")
        if self.amount_set_by_hand:
            if self.amount is None:
                raise ValueError("a hand-set tax row needs its amount")
            # The currency's own decimals are checked by the service, which knows them.
            if (
                abs(self.amount) >= _TAX_AMOUNT_LIMIT
                or _decimal_places(self.amount) > 4
            ):
                raise ValueError("amount is too large or has too many decimals")
            self.rate = None
        else:
            if self.rate is None:
                raise ValueError(
                    "a tax row needs a rate unless its amount is set by hand"
                )
            if not Decimal(0) <= self.rate <= Decimal(100):
                raise ValueError("rate must be between 0 and 100")
            if _decimal_places(self.rate) > 3:
                raise ValueError("rate must have at most 3 decimals")
            self.amount = None
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
    taxes: list[InvoiceTaxWrite] = Field(
        default_factory=list, max_length=MAX_INVOICE_TAXES
    )

    @model_validator(mode="after")
    def check_fields(self) -> InvoiceWrite:
        check_period(self.period_start, self.period_end)
        if self.payment_terms is not None and self.due_date is not None:
            raise ValueError("give either payment_terms or due_date, not both")
        return self


class GenerateTimeRequest(BaseModel):
    """Lines from the hours logged on service lines over a period (T&M and Capped T&M)."""

    kind: Literal["time"]
    project_id: uuid.UUID
    service_line_ids: list[uuid.UUID] = Field(min_length=1)
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def check_period(self) -> GenerateTimeRequest:
        check_period(self.period_start, self.period_end)
        return self


class GenerateMilestoneRequest(BaseModel):
    """One line per billing milestone (Fixed Price)."""

    kind: Literal["milestone"]
    project_id: uuid.UUID
    milestone_ids: list[uuid.UUID] = Field(min_length=1, max_length=MAX_INVOICE_LINES)


GenerateRequest = Annotated[
    GenerateTimeRequest | GenerateMilestoneRequest, Field(discriminator="kind")
]


class GeneratedLine(BaseModel):
    # The service line's name, null when it has none: the client writes the description
    # itself, so it can be translated and its dates follow the user's locale. For a
    # milestone, its description, used as is.
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
    "due_before_invoice_date",
    "no_due_date",
    "tax_rate_not_derivable",
    "negative_subtotal",
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


class InvoiceTaxOut(BaseModel):
    label: str
    base_mode: TaxBaseMode
    # Null when it cannot be worked back from a hand-set amount (a zero base).
    rate: Decimal | None
    amount: Decimal
    amount_set_by_hand: bool
    base_amount: Decimal


class InvoiceReferenceOut(BaseModel):
    kind: ReferenceKind
    label: str | None
    value: str


class SnapshotIdentifier(BaseModel):
    """A company identifier as it stood when the invoice was issued."""

    id_type: IdentifierType
    scheme_id: str | None
    id_value: str
    is_primary: bool


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
    taxes: list[InvoiceTaxOut]
    total: Decimal
    created_at: datetime
    updated_at: datetime
    warnings: list[InvoiceWarning]
    # Set once issued; all null on a draft.
    number: str | None
    invoice_date: date | None
    document_name: str | None
    vendor_identifiers: list[SnapshotIdentifier]
    client_identifiers: list[SnapshotIdentifier]
    issued_at: datetime | None
    issued_by_name: str | None
    voided_at: datetime | None
    voided_by_name: str | None
    void_reason: str | None
    has_pdf: bool


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
    number: str | None
    invoice_date: date | None
    issued_at: datetime | None
    # What Billed for shows when there is no period (a Fixed Price invoice): every line's
    # description in order, joined with ", ". Null when the invoice has no line.
    lines_summary: str | None
    # Whether a PDF was kept when the invoice was issued: false for a draft and for an
    # invoice issued before PDFs were kept.
    has_pdf: bool


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


class ContextMilestone(BaseModel):
    id: uuid.UUID
    description: str
    due_date: date | None
    value: Decimal


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
    # In their order; empty unless the project is Fixed Price.
    milestones: list[ContextMilestone]
    references: list[InvoiceReferenceOut]


BlockingReason = Literal["project_not_active", "no_lines"]


class IssuePreview(BaseModel):
    """What issuing a draft today would give, for the confirmation and the draft header.
    The number is the likely one: another invoice issued first would take it."""

    invoice_date: date
    due_date: date | None
    payment_terms: PaymentTerms | None
    number: str
    warnings: list[InvoiceWarning]
    blocking: list[BlockingReason]


class VoidWrite(BaseModel):
    # Trimmed first, so a reason of only spaces counts as none.
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str | None = Field(default=None, max_length=500)
