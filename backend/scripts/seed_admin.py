"""Dev-only: seed a default administrator user so login can be tested end-to-end
before a real user-management flow exists. Credentials come from env vars
(SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD); do not run against production data
with the default password.

Assigned `administrator`, `project_admin`, and `project_manager` roles — `projects` access
is granted by the literal `project_admin` role only, not inferred from `administrator` (see
specs/requirements/user.md#role--screen-access), so an administrator-only bootstrap account
would have no way to reach `projects` to verify/manage anything there. `project_manager` is
included for the same reason: it's the only way to reach the `Validation` sub-destination
(see specs/requirements/home.md#timesheet-menu), and this bootstrap account is meant to be
able to exercise every screen. Note `project_manager`'s actual authority is scoped to
projects that user is assigned to (see specs/requirements/project.md#project-managers) —
holding the role alone is what's needed to reach the nav entry point, not to see non-empty
data there unless this account is also assigned as a project manager on a real project.

Usage (from backend/): uv run python -m scripts.seed_admin
"""

import asyncio

from sqlalchemy import select

from app.auth.security import hash_password
from app.core.config import settings
from app.core.db import async_session_factory
from app.models.user import Role, User

_BOOTSTRAP_ROLE_NAMES = ["administrator", "project_admin", "project_manager"]


async def seed_admin() -> None:
    async with async_session_factory() as db:
        existing = await db.execute(
            select(User).where(User.name_id == settings.seed_admin_email)
        )
        if existing.scalar_one_or_none() is not None:
            print(f"Admin user {settings.seed_admin_email} already exists, skipping.")
            return

        roles = []
        for role_name in _BOOTSTRAP_ROLE_NAMES:
            role = (
                await db.execute(select(Role).where(Role.name == role_name))
            ).scalar_one_or_none()
            if role is None:
                raise RuntimeError(
                    f"'{role_name}' role not found — run migrations first "
                    "(uv run alembic upgrade head)"
                )
            roles.append(role)

        user = User(
            name_id=settings.seed_admin_email,
            hashed_password=hash_password(settings.seed_admin_password),
            full_name="Default Administrator",
            roles=roles,
        )
        db.add(user)
        await db.commit()
        print(f"Seeded admin user: {settings.seed_admin_email}")


if __name__ == "__main__":
    asyncio.run(seed_admin())
