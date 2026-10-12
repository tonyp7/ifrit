"""merge project_admin and project_manager into manager

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12

The two roles always went to the same people, and project_admin could list itself as
manager of any project, so the per-project scope of project_manager protected nothing.
One `manager` role now covers both. Project manager assignments are left untouched: they
still say who manages which project, they just no longer gate anything.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Ids seeded by 0001.
_PROJECT_ADMIN_ID = "00000000-0000-0000-0000-000000000002"
_PROJECT_MANAGER_ID = "00000000-0000-0000-0000-000000000004"


def upgrade() -> None:
    # Renaming (rather than inserting a new row) keeps every project_admin holder's
    # user_roles row as is.
    op.execute(f"UPDATE roles SET name = 'manager' WHERE id = '{_PROJECT_ADMIN_ID}'")
    op.execute(
        f"""
        INSERT INTO user_roles (user_id, role_id)
        SELECT user_id, '{_PROJECT_ADMIN_ID}' FROM user_roles
        WHERE role_id = '{_PROJECT_MANAGER_ID}'
        ON CONFLICT DO NOTHING
        """
    )
    # user_roles.role_id cascades, so the old project_manager rows go with it.
    op.execute(f"DELETE FROM roles WHERE id = '{_PROJECT_MANAGER_ID}'")


def downgrade() -> None:
    # Who held which of the two roles is gone, so every manager gets both: the closest
    # pre-merge state to what they could actually do, so a rollback takes no access away.
    op.execute(f"UPDATE roles SET name = 'project_admin' WHERE id = '{_PROJECT_ADMIN_ID}'")
    op.execute(
        f"INSERT INTO roles (id, name) VALUES ('{_PROJECT_MANAGER_ID}', 'project_manager')"
    )
    op.execute(
        f"""
        INSERT INTO user_roles (user_id, role_id)
        SELECT user_id, '{_PROJECT_MANAGER_ID}' FROM user_roles
        WHERE role_id = '{_PROJECT_ADMIN_ID}'
        """
    )
