"""invoice PDFs: the file an issued invoice keeps

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-20

An invoice's PDF is stored like any other file, with the new file kind `invoice`, and the
invoice points at it with `invoices.pdf_file_id`. A draft never has one. Invoices issued
before this have none, so the column is nullable and nothing is required of issued rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_files_kind", "files", type_="check")
    op.create_check_constraint(
        "ck_files_kind", "files", "kind IN ('setting', 'project', 'invoice')"
    )
    op.add_column(
        "invoices",
        sa.Column("pdf_file_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_invoices_pdf_file_id_files",
        "invoices",
        "files",
        ["pdf_file_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_invoices_pdf_file_id", "invoices", ["pdf_file_id"])
    op.create_check_constraint(
        "ck_invoices_pdf_draft", "invoices", "status <> 'draft' OR pdf_file_id IS NULL"
    )


def downgrade() -> None:
    # Refused while an invoice file exists, which would violate the older kind check: the
    # stored PDFs are the record of what was sent and are never deleted by a downgrade.
    op.drop_constraint("ck_invoices_pdf_draft", "invoices", type_="check")
    op.drop_index("ix_invoices_pdf_file_id", table_name="invoices")
    op.drop_constraint("fk_invoices_pdf_file_id_files", "invoices", type_="foreignkey")
    op.drop_column("invoices", "pdf_file_id")
    op.drop_constraint("ck_files_kind", "files", type_="check")
    op.create_check_constraint(
        "ck_files_kind", "files", "kind IN ('setting', 'project')"
    )
