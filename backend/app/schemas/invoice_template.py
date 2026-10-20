from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TemplateInfo(BaseModel):
    """The template invoice PDFs are made from."""

    source: Literal["default", "custom"]
    filename: str
    size_bytes: int
    # Only for an uploaded template.
    uploaded_by_name: str | None
    uploaded_at: datetime | None
    # The placeholders the template uses, in order of first appearance.
    placeholders: list[str]


class TemplateFinding(BaseModel):
    """One problem or warning about an uploaded file: where it is and what is wrong."""

    part: str
    message: str
    snippet: str | None = None


class TemplateSaved(TemplateInfo):
    warnings: list[TemplateFinding]
