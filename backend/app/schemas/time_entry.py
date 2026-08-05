import uuid
from datetime import date as date_
from decimal import Decimal

from pydantic import BaseModel, model_validator


class TimeEntryUpsert(BaseModel):
    service_line_id: uuid.UUID
    date: date_
    hours: Decimal

    @model_validator(mode="after")
    def check_hours(self) -> "TimeEntryUpsert":
        if self.hours < 0 or self.hours > 24:
            raise ValueError("hours must be between 0 and 24")
        if (self.hours * 2) % 1 != 0:
            raise ValueError("hours must be in 0.5 increments")
        return self


class TimeEntryOut(BaseModel):
    id: uuid.UUID
    service_line_id: uuid.UUID
    service_line_name: str | None
    project_id: uuid.UUID
    project_name: str
    date: date_
    hours: Decimal
    is_locked: bool


class TimeEntryListResponse(BaseModel):
    items: list[TimeEntryOut]


class EligibleServiceLineOut(BaseModel):
    service_line_id: uuid.UUID
    service_line_name: str | None
    project_id: uuid.UUID
    project_name: str


class EligibleServiceLineListResponse(BaseModel):
    items: list[EligibleServiceLineOut]
