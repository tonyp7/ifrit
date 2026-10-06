import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

ThemePreference = Literal["light", "dark", "system"]

user_roles = Table(
    "user_roles",
    Base.metadata,
    # Role links go with their user or role, as in the migration.
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # unique, single-attribute key -> functionally determines nothing else here, so this
    # table trivially satisfies BCNF.
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    users: Mapped[list["User"]] = relationship(
        secondary=user_roles, back_populates="roles"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Identity used to match a login: for a local user this is their email; for an SSO
    # user this is the SAML NameID asserted by the IdP, which is conventionally
    # email-shaped but not guaranteed to be a valid email.
    # Unique only among *active* users (see the partial index below): a deactivated
    # user keeps their name_id so history stays accurate, and a new user may reuse it.
    # Every lookup by name_id must therefore filter `is_active`.
    name_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # Null for SSO users: an is_sso account has no local password and cannot log in
    # via email/password.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_sso: Mapped[bool] = mapped_column(default=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Set from the profile menu, persisted so it follows the user across devices/sessions
    # rather than living in browser storage. Plain column, not a lookup table: a
    # single-valued attribute fully dependent on the user's key, already in BCNF.
    theme_preference: Mapped[ThemePreference] = mapped_column(
        String(10), default="system", server_default="system"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    # Embedded in every issued token as the `tv` claim and compared on each request:
    # incrementing it invalidates every access/refresh token issued so far (logout,
    # password reset), which stateless JWTs can't otherwise do before they expire.
    token_version: Mapped[int] = mapped_column(default=0, server_default="0")

    roles: Mapped[list[Role]] = relationship(secondary=user_roles, back_populates="users")

    __table_args__ = (
        Index(
            "uq_users_name_id_active",
            "name_id",
            unique=True,
            postgresql_where=is_active.is_(True),
        ),
        CheckConstraint(
            "theme_preference IN ('light', 'dark', 'system')",
            name="ck_users_theme_preference",
        ),
    )
