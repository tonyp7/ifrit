"""Dev-only: seed a default administrator user so login can be tested end-to-end
before a real user-management flow exists. Credentials come from env vars
(SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD); do not run against production data
with the default password.

Assigned both `administrator` and `manager` roles — `projects` access is granted by the
literal `manager` role only, not inferred from `administrator` (see
docs/requirements/user.md#role--screen-access), so an administrator-only bootstrap account
would have no way to reach `projects` to verify/manage anything there.

Usage (from backend/): uv run python -m scripts.seed_admin
"""

import asyncio

from sqlalchemy import select

from app.auth.security import hash_password
from app.core.config import settings
from app.core.db import async_session_factory
from app.models.user import Role, User


async def seed_admin() -> None:
    async with async_session_factory() as db:
        existing = await db.execute(
            select(User).where(User.name_id == settings.seed_admin_email)
        )
        if existing.scalar_one_or_none() is not None:
            print(f"Admin user {settings.seed_admin_email} already exists, skipping.")
            return

        admin_role = (
            await db.execute(select(Role).where(Role.name == "administrator"))
        ).scalar_one_or_none()
        if admin_role is None:
            raise RuntimeError(
                "'administrator' role not found — run migrations first (uv run alembic upgrade head)"
            )
        manager_role = (
            await db.execute(select(Role).where(Role.name == "manager"))
        ).scalar_one_or_none()
        if manager_role is None:
            raise RuntimeError(
                "'manager' role not found — run migrations first (uv run alembic upgrade head)"
            )

        user = User(
            name_id=settings.seed_admin_email,
            hashed_password=hash_password(settings.seed_admin_password),
            full_name="Default Administrator",
            roles=[admin_role, manager_role],
        )
        db.add(user)
        await db.commit()
        print(f"Seeded admin user: {settings.seed_admin_email}")


if __name__ == "__main__":
    asyncio.run(seed_admin())
