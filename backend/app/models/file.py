import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

FileStatus = Literal["pending", "scanning", "processing", "ready", "rejected", "failed"]
# The kind of object a file is attached to. Only instance-wide settings exist so far;
# a new attachable object adds its value here and a `<object>_files` link table.
FileKind = Literal["setting"]
SettingKey = Literal["org_logo"]


class StoredFile(Base):
    """The bytes and the facts about them: one row per distinct stored content."""

    __tablename__ = "stored_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # SHA-256 of the bytes as stored (after image re-encoding), the dedup key.
    checksum_sha256: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # From the file's bytes, never from the client's header or extension.
    detected_content_type: Mapped[str] = mapped_column(Text, nullable=False)
    # Relative path below STORAGE_ROOT.
    bucket_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # Uploads are validated inside the request, so rows are only ever written as
    # "ready" for now. The full set exists so adding background scanning later
    # needs no schema change.
    status: Mapped[str] = mapped_column(Text, nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'scanning', 'processing', 'ready', 'rejected',"
            " 'failed')",
            name="ck_stored_files_status",
        ),
    )


class File(Base):
    """One upload: a named attachment of stored content to exactly one object."""

    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # RESTRICT: stored content is only removed by the (deferred) cleanup job once no
    # attachment refers to it, never as a side effect of deleting an attachment.
    stored_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stored_files.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    # Audit only, not an access grant.
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Display only (control characters stripped, length capped): never used as a path.
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    stored_file: Mapped[StoredFile] = relationship()

    __table_args__ = (
        # A superkey that lets link tables point at (id, kind), so a file can be linked
        # only from the one link table matching its kind.
        UniqueConstraint("id", "kind", name="uq_files_id_kind"),
        CheckConstraint("kind IN ('setting')", name="ck_files_kind"),
    )


class SettingFile(Base):
    """Attaches a file to an app-defined instance-wide slot (e.g. the organization logo).

    The slot is named in code rather than stored as a row, so there is nothing to
    reference: the CHECK on `setting_key` is what rules out an unknown slot.
    """

    __tablename__ = "setting_files"

    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="setting")
    setting_key: Mapped[str] = mapped_column(Text, nullable=False)

    file: Mapped[File] = relationship()

    __table_args__ = (
        ForeignKeyConstraint(
            ["file_id", "kind"],
            ["files.id", "files.kind"],
            ondelete="CASCADE",
            name="fk_setting_files_file_id_kind",
        ),
        CheckConstraint("kind = 'setting'", name="ck_setting_files_kind"),
        CheckConstraint("setting_key IN ('org_logo')", name="ck_setting_files_key"),
        # A single-slot setting holds at most one file and keeps no history. Keys that
        # may hold several files are simply left out of this index.
        Index(
            "setting_files_single_slot",
            "setting_key",
            unique=True,
            postgresql_where=text("setting_key IN ('org_logo')"),
        ),
    )
