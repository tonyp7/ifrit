import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, model_validator

from app.models.company import (
    AccountScheme,
    AddressType,
    IdentifierType,
    PaymentMeansCode,
)

SCHEME_ID_REQUIRED_TYPES = {"legal_registration", "peppol_participant"}

# Shape only: country, check digits, then 11 to 30 letters or digits. The per-country
# length is not checked (it is a table to keep current); the checksum below is what
# catches a mistyped digit.
_IBAN_SHAPE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$")
# Loose on purpose: since 2022 a BIC's first four characters may hold digits too.
_BIC_SHAPE = re.compile(r"^[A-Z0-9]{8}([A-Z0-9]{3})?$")


def is_valid_iban(value: str) -> bool:
    """ISO 13616 check: move the first four characters to the end, read every letter as a
    number (A=10 .. Z=35), and the whole must leave 1 modulo 97. `value` must already be
    compact and upper case."""
    if not _IBAN_SHAPE.match(value):
        return False
    rearranged = value[4:] + value[:4]
    return int("".join(str(int(char, 36)) for char in rearranged)) % 97 == 1


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class CompanyWrite(BaseModel):
    is_vendor: bool = False
    legal_name: str
    trading_name: str | None = None
    legal_form: str | None = None
    country_of_registration: str

    @model_validator(mode="after")
    def check_legal_name_and_country(self) -> CompanyWrite:
        if not self.legal_name.strip():
            raise ValueError("legal_name must not be empty")
        if len(self.country_of_registration) != 2:
            raise ValueError(
                "country_of_registration must be an ISO 3166-1 alpha-2 code"
            )
        return self


class CompanyListItem(BaseModel):
    id: uuid.UUID
    legal_name: str
    trading_name: str | None
    country_of_registration: str


class CompanyListResponse(BaseModel):
    items: list[CompanyListItem]
    total: int
    page: int
    page_size: int


class PartyIdentifierWrite(BaseModel):
    id_type: IdentifierType
    scheme_id: str | None = None
    id_value: str
    is_primary: bool = False
    valid_from: date | None = None
    valid_to: date | None = None

    @model_validator(mode="after")
    def check_scheme_id_required(self) -> PartyIdentifierWrite:
        if self.id_type in SCHEME_ID_REQUIRED_TYPES and not self.scheme_id:
            raise ValueError(f"scheme_id is required for id_type={self.id_type}")
        if not self.id_value.strip():
            raise ValueError("id_value must not be empty")
        return self


class PartyIdentifierOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    id_type: IdentifierType
    scheme_id: str | None
    id_value: str
    is_primary: bool
    valid_from: date | None
    valid_to: date | None


class AddressWrite(BaseModel):
    address_type: AddressType
    line1: str
    line2: str | None = None
    line3: str | None = None
    city: str
    postal_zone: str | None = None
    country_subdivision: str | None = None
    country_code: str
    is_primary: bool = False
    valid_from: date | None = None
    valid_to: date | None = None

    @model_validator(mode="after")
    def check_required_fields(self) -> AddressWrite:
        if not self.line1.strip():
            raise ValueError("line1 must not be empty")
        if not self.city.strip():
            raise ValueError("city must not be empty")
        if len(self.country_code) != 2:
            raise ValueError("country_code must be an ISO 3166-1 alpha-2 code")
        return self


class AddressOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    address_type: AddressType
    line1: str
    line2: str | None
    line3: str | None
    city: str
    postal_zone: str | None
    country_subdivision: str | None
    country_code: str
    is_primary: bool
    valid_from: date | None
    valid_to: date | None


class BankAddress(BaseModel):
    line1: str
    line2: str | None = None
    line3: str | None = None
    city: str
    postal_zone: str | None = None
    country_subdivision: str | None = None
    country_code: str

    @model_validator(mode="after")
    def check_required_fields(self) -> BankAddress:
        self.line1 = self.line1.strip()
        self.city = self.city.strip()
        self.country_code = self.country_code.strip().upper()
        self.line2 = _blank_to_none(self.line2)
        self.line3 = _blank_to_none(self.line3)
        self.postal_zone = _blank_to_none(self.postal_zone)
        self.country_subdivision = _blank_to_none(self.country_subdivision)
        if not self.line1:
            raise ValueError("bank_address.line1 must not be empty")
        if not self.city:
            raise ValueError("bank_address.city must not be empty")
        if len(self.country_code) != 2:
            raise ValueError(
                "bank_address.country_code must be an ISO 3166-1 alpha-2 code"
            )
        return self


class PayeeAccountWrite(BaseModel):
    payment_means_code: PaymentMeansCode
    account_scheme: AccountScheme
    account_identifier: str
    account_name: str | None = None
    currency_code: str
    bic: str | None = None
    bank_name: str | None = None
    # Absent altogether or complete enough to post a letter to: a city with no street and
    # no country is not an address anyone can use.
    bank_address: BankAddress | None = None
    is_primary: bool = False

    @model_validator(mode="after")
    def normalize_and_check(self) -> PayeeAccountWrite:
        if self.account_scheme == "iban":
            # IBANs are printed in groups of four but are one value: compare and store
            # them compact so `BE71 0961…` and `be710961…` are recognized as the same.
            self.account_identifier = "".join(self.account_identifier.split()).upper()
            if not is_valid_iban(self.account_identifier):
                raise ValueError("account_identifier is not a valid IBAN")
        else:
            # National formats carry meaning in their punctuation and case: keep them.
            self.account_identifier = self.account_identifier.strip()
            if not self.account_identifier:
                raise ValueError("account_identifier must not be empty")
        if self.payment_means_code == "58" and self.account_scheme != "iban":
            raise ValueError("a SEPA credit transfer requires an IBAN")
        self.account_name = _blank_to_none(self.account_name)
        self.bank_name = _blank_to_none(self.bank_name)
        self.currency_code = self.currency_code.strip().upper()
        bic = _blank_to_none(self.bic)
        if bic is not None:
            bic = bic.upper()
            if not _BIC_SHAPE.match(bic):
                raise ValueError("bic must be 8 or 11 letters or digits")
        self.bic = bic
        return self


class PayeeAccountOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    payment_means_code: PaymentMeansCode
    account_scheme: AccountScheme
    account_identifier: str
    account_name: str | None
    currency_code: str
    bic: str | None
    bank_name: str | None
    bank_address: BankAddress | None
    is_primary: bool


class CompanyDetail(BaseModel):
    id: uuid.UUID
    is_vendor: bool
    legal_name: str
    trading_name: str | None
    legal_form: str | None
    country_of_registration: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    identifiers: list[PartyIdentifierOut]
    addresses: list[AddressOut]
    payee_accounts: list[PayeeAccountOut]
