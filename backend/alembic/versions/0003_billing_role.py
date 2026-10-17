"""add the billing role

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-17

`billing` grants invoicing on its own, next to administrator, manager and consultant. No user
is given it here: an administrator assigns it.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A fixed id like the roles seeded by 0001. Not ...0004: 0002's downgrade puts project_manager
# back under that id.
_BILLING_ID = "00000000-0000-0000-0000-000000000005"


def upgrade() -> None:
    op.execute(f"INSERT INTO roles (id, name) VALUES ('{_BILLING_ID}', 'billing')")


def downgrade() -> None:
    # user_roles.role_id cascades, so every assignment of the role goes with it.
    op.execute(f"DELETE FROM roles WHERE id = '{_BILLING_ID}'")
