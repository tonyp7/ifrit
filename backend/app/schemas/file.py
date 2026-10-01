import uuid
from datetime import datetime

from pydantic import BaseModel


class FileOut(BaseModel):
    """What the API says about a stored file. The bytes are served separately, by
    GET /api/files/{id}/content."""

    file_id: uuid.UUID
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime
