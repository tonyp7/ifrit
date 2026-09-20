import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, model_validator

from app.models.project import ProjectStatus, ProjectType, Uom


class ProjectWrite(BaseModel):
    name: str
    vendor_company_id: uuid.UUID
    client_company_id: uuid.UUID
    invoicing_currency: str
    project_type: ProjectType
    status: ProjectStatus = "draft"
    # Held/saved as part of the Project itself, not a separate child-entity flow with
    # its own create/update/delete endpoints.
    project_manager_ids: list[uuid.UUID] = []

    @model_validator(mode="after")
    def check_name(self) -> "ProjectWrite":
        if not self.name.strip():
            raise ValueError("name must not be empty")
        return self


class ProjectListItem(BaseModel):
    id: uuid.UUID
    name: str
    status: ProjectStatus
    project_type: ProjectType
    client_company_id: uuid.UUID | None
    client_company_name: str | None
    vendor_company_id: uuid.UUID | None
    vendor_company_name: str | None
    created_at: datetime


class ProjectListResponse(BaseModel):
    items: list[ProjectListItem]
    total: int
    page: int
    page_size: int


class ServiceLineWrite(BaseModel):
    name: str | None = None
    quantity: Decimal
    uom: Uom
    unit_price: Decimal
    user_ids: list[uuid.UUID] = []

    @model_validator(mode="after")
    def check_amounts(self) -> "ServiceLineWrite":
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if self.unit_price < 0:
            raise ValueError("unit_price must not be negative")
        return self


class ServiceLineConsultantOut(BaseModel):
    id: uuid.UUID
    full_name: str
    # False for a since-deleted user who is still on the line (history): shown in red
    # and removable, but can't be saved back onto a line.
    is_active: bool


class ProjectManagerOut(BaseModel):
    id: uuid.UUID
    full_name: str


class ServiceLineOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str | None
    quantity: Decimal
    uom: Uom
    unit_price: Decimal
    value: Decimal
    is_active: bool
    users: list[ServiceLineConsultantOut]


class ProjectDetail(BaseModel):
    id: uuid.UUID
    name: str
    # Null only on a duplicate whose source company was soft-deleted. A non-null company
    # with *_is_active = false is still a valid link, but must be replaced on next edit.
    vendor_company_id: uuid.UUID | None
    vendor_company_name: str | None
    vendor_company_is_active: bool | None
    client_company_id: uuid.UUID | None
    client_company_name: str | None
    client_company_is_active: bool | None
    invoicing_currency: str
    project_type: ProjectType
    status: ProjectStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime
    service_lines: list[ServiceLineOut]
    project_managers: list[ProjectManagerOut]
    total_value: Decimal
