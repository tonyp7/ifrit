"""Dev-only: seed a default administrator user so login can be tested end-to-end
before a real user-management flow exists. Credentials come from env vars
(SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD); do not run against production data
with the default password.

Assigned `administrator`, `manager` and `billing` roles: the `projects`, `Reporting` and
`Invoices` screens are granted by the literal `manager` and `billing` roles only, not inferred
from `administrator`, so an administrator-only bootstrap account would have no way to reach
them, and this bootstrap account is meant to be able to exercise every screen.

When the account already exists, any bootstrap role it lacks is added (a role introduced
after it was seeded, for instance) and nothing else changes. Roles are never removed.

Usage (from backend/): uv run python -m scripts.seed_admin
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import hash_password
from app.core.config import settings
from app.core.db import async_session_factory
from app.models.user import Role, User

_BOOTSTRAP_ROLE_NAMES = ["administrator", "manager", "billing"]


async def _bootstrap_roles(db: AsyncSession) -> list[Role]:
    roles = []
    for role_name in _BOOTSTRAP_ROLE_NAMES:
        role = (
            await db.execute(select(Role).where(Role.name == role_name))
        ).scalar_one_or_none()
        if role is None:
            raise RuntimeError(
                f"'{role_name}' role not found: run migrations first "
                "(uv run alembic upgrade head)"
            )
        roles.append(role)
    return roles


async def seed_admin() -> None:
    async with async_session_factory() as db:
        roles = await _bootstrap_roles(db)
        existing = (
            await db.execute(
                select(User)
                .options(selectinload(User.roles))
                .where(
                    User.name_id == settings.seed_admin_email, User.is_active.is_(True)
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            held = {role.name for role in existing.roles}
            missing = [role for role in roles if role.name not in held]
            if not missing:
                print(
                    f"Admin user {settings.seed_admin_email} already exists, skipping."
                )
                return
            existing.roles.extend(missing)
            await db.commit()
            added = ", ".join(role.name for role in missing)
            print(
                f"Admin user {settings.seed_admin_email} already exists, added: {added}"
            )
            return

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
