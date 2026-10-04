import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AppSetting(Base):
    """One instance-wide runtime setting, identified by its group and key.

    The code (the settings registry) decides which groups and keys exist and what values
    they accept; this table only stores the values an administrator has saved. A missing
    row means "use the default", so deleting a row resets a setting.
    """

    __tablename__ = "app_settings"
    __table_args__ = (
        # Settings are flat: the registry only declares scalar fields, and this keeps
        # objects, arrays and JSON null out even when a row is edited by hand.
        CheckConstraint(
            "jsonb_typeof(value) IN ('boolean', 'number', 'string')",
            name="ck_app_settings_scalar_value",
        ),
    )

    # `group_name` rather than `group`, which is a reserved SQL word.
    group_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    # Set explicitly by the upsert in the service as well: `onupdate` only fires for ORM
    # updates, not for INSERT ... ON CONFLICT.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # Records who last touched the row, not whose data it is, so deleting that user must
    # never delete the setting. NULL also means "seeded by the migration".
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
