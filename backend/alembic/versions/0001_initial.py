"""initial schema: users, roles, user_roles, companies, party_identifiers, addresses

Revision ID: 0001
Revises:
Create Date: 2026-08-01

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Local user: their email. SSO user: the IdP's SAML NameID (see auth.md) —
        # not typed/validated as an email since that isn't guaranteed.
        sa.Column("name_id", sa.String(length=255), nullable=False),
        # Null for SSO users, who have no local password.
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column(
            "is_sso", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        # Light/dark/system — see docs/requirements/home.md#appearance.
        sa.Column(
            "theme_preference", sa.String(length=10), nullable=False,
            server_default="system",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("name_id", name="uq_users_name_id"),
        sa.CheckConstraint(
            "theme_preference IN ('light', 'dark', 'system')",
            name="ck_users_theme_preference",
        ),
    )

    op.create_table(
        "user_roles",
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column(
            "role_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True,
        ),
    )

    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("name", sa.String),
        ),
        [
            {"id": "00000000-0000-0000-0000-000000000001", "name": "administrator"},
            {"id": "00000000-0000-0000-0000-000000000002", "name": "manager"},
            {"id": "00000000-0000-0000-0000-000000000003", "name": "consultant"},
        ],
    )

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "is_vendor", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("trading_name", sa.String(length=255), nullable=True),
        sa.Column("legal_form", sa.String(length=50), nullable=True),
        sa.Column("country_of_registration", sa.String(length=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "party_identifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("id_type", sa.String(length=20), nullable=False),
        sa.Column("scheme_id", sa.String(length=10), nullable=True),
        sa.Column("id_value", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "id_type IN ('legal_registration', 'vat', 'peppol_participant', 'duns', "
            "'gln', 'internal')",
            name="ck_party_identifiers_id_type",
        ),
    )
    op.create_index(
        "ix_party_identifiers_company_id", "party_identifiers", ["company_id"]
    )
    # COALESCE scheme_id to '' — a plain unique index on nullable scheme_id wouldn't catch
    # duplicates, since SQL treats NULL as distinct from NULL (scheme_id is NULL for most
    # id_types, e.g. `vat`).
    op.create_index(
        "uq_party_identifiers",
        "party_identifiers",
        ["company_id", "id_type", sa.text("COALESCE(scheme_id, '')"), "id_value"],
        unique=True,
    )

    op.create_table(
        "addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("address_type", sa.String(length=15), nullable=False),
        sa.Column("line1", sa.String(length=255), nullable=False),
        sa.Column("line2", sa.String(length=255), nullable=True),
        sa.Column("line3", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=False),
        sa.Column("postal_zone", sa.String(length=20), nullable=True),
        sa.Column("country_subdivision", sa.String(length=100), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "address_type IN ('registered', 'bill_to', 'ship_to', 'postal')",
            name="ck_addresses_address_type",
        ),
    )
    op.create_index("ix_addresses_company_id", "addresses", ["company_id"])
    # At most one primary address per (company_id, address_type) — see
    # docs/requirements/company.md §3 Validation rules.
    op.create_index(
        "uq_addresses_primary_per_type",
        "addresses",
        ["company_id", "address_type"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )


def downgrade() -> None:
    op.drop_table("addresses")
    op.drop_table("party_identifiers")
    op.drop_table("companies")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
