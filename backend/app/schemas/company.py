import uuid
from datetime import date, datetime

from pydantic import BaseModel, model_validator

from app.models.company import AddressType, IdentifierType

SCHEME_ID_REQUIRED_TYPES = {"legal_registration", "peppol_participant"}


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
            raise ValueError("country_of_registration must be an ISO 3166-1 alpha-2 code")
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
