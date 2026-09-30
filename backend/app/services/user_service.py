import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import hash_password, verify_password
from app.models.project import project_manager_assignments
from app.models.user import Role, ThemePreference, User
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services.sorting import resolve_sort

PAGE_SIZE = 50

# Whitelist of client-sortable columns for the Users List Screen: `roles` is
# deliberately excluded, a list of role chips has no meaningful single-column order.
# Never resolve `sort_by` against the model dynamically (see app/services/sorting.py).
_SORTABLE_COLUMNS = {
    "full_name": User.full_name,
    "name_id": User.name_id,
    "is_sso": User.is_sso,
}


class SelfLockoutError(Exception):
    """Raised when an administrator attempts to deactivate their own account or
    remove their own `administrator` role: without this, an administrator could
    accidentally lock every administrator out of the app with no way back in."""


async def get_user_by_name_id(db: AsyncSession, name_id: str) -> User | None:
    # Active only: name_id is unique among active users, so a deactivated user's
    # (kept) name_id may also belong to a newer active one.
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(User.name_id == name_id, User.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    # Active only: a deactivated user is treated as not existing by every caller
    # (users routes -> 404, get_current_user -> 401).
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == user_id, User.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def list_users(
    db: AsyncSession,
    role: str | None = None,
    search: str | None = None,
    page: int = 1,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> tuple[list[User], int]:
    """Users, optionally filtered to a single role: e.g. `role=consultant` for the
    Service Line consultant-assignment picker, and/or a `full_name`/`name_id`
    substring match (that same picker's server-side search, and the Users List
    Screen's header search). Always paginated at `PAGE_SIZE`, matching
    list_companies/list_projects: the
    picker only ever needs page 1 anyway, since it narrows via `role`/`search` first,
    and never passes `sort_by`/`sort_dir`: it has no sortable-header UI, so the
    default (`full_name` ascending) always applies there.
    """
    # Deactivated users are never listed: no way to see or reactivate one through the
    # API.
    stmt = select(User).options(selectinload(User.roles)).where(User.is_active.is_(True))
    count_stmt = select(func.count()).select_from(User).where(User.is_active.is_(True))

    if role:
        stmt = stmt.join(User.roles).where(Role.name == role)
        count_stmt = count_stmt.join(User.roles).where(Role.name == role)
    if search:
        pattern = f"%{search}%"
        condition = or_(User.full_name.ilike(pattern), User.name_id.ilike(pattern))
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    total = (await db.execute(count_stmt)).scalar_one()

    order = resolve_sort(_SORTABLE_COLUMNS, sort_by, sort_dir, default=User.full_name.asc())
    # `User.id` is a stable tie-breaker: see app/services/sorting.py.
    stmt = stmt.order_by(order, User.id).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)

    result = await db.execute(stmt)
    return list(result.scalars().unique().all()), total


async def _roles_by_name(db: AsyncSession, names: list[str]) -> list[Role]:
    result = await db.execute(select(Role).where(Role.name.in_(names)))
    roles = list(result.scalars().all())
    # Every name in `names` is already validated as one of VALID_ROLES by the
    # UserCreate/UserUpdate schema, so a mismatch here means a seeded Role row is
    # genuinely missing (migration 0001 should have created it): fail loudly rather
    # than silently saving a user with fewer roles than the admin actually granted.
    found = {role.name for role in roles}
    missing = set(names) - found
    if missing:
        raise ValueError(f"Unknown role(s): {sorted(missing)}")
    return roles


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    roles = await _roles_by_name(db, data.roles)
    user = User(
        full_name=data.full_name,
        name_id=data.name_id,
        is_sso=data.is_sso,
        hashed_password=hash_password(data.password) if data.password else None,
        roles=roles,
    )
    db.add(user)
    await db.commit()
    persisted = await get_user_by_id(db, user.id)
    assert persisted is not None
    return persisted


async def update_user(
    db: AsyncSession, user: User, data: UserUpdate, current_user: User
) -> User:
    """Handles the two is_sso-transition directions (password becomes permanently
    unrecoverable going local -> SSO; a new password is required going SSO ->
    local) and enforces the self-lockout rule: an administrator can't remove their
    own administrator role."""
    is_self = user.id == current_user.id
    was_administrator = any(role.name == "administrator" for role in user.roles)
    will_be_administrator = "administrator" in data.roles

    if is_self and was_administrator and not will_be_administrator:
        raise SelfLockoutError("You can't remove your own administrator access.")

    if data.is_sso and not user.is_sso:
        # Local -> SSO: the password becomes permanently unrecoverable, not just
        # hidden: hashed_password is cleared outright, not preserved for a
        # possible future switch back.
        user.hashed_password = None
        user.token_version += 1
    elif not data.is_sso and user.is_sso:
        # SSO -> local: a password is required to make the account usable again.
        if not data.password:
            raise ValueError("password is required when switching an SSO user to local")
        user.hashed_password = hash_password(data.password)
        user.token_version += 1

    if "project_manager" not in data.roles and any(
        role.name == "project_manager" for role in user.roles
    ):
        # Same invariant as deactivation: only holders of the role can be assigned.
        await _clear_project_manager_assignments(db, user.id)

    user.full_name = data.full_name
    user.name_id = data.name_id
    user.is_sso = data.is_sso
    user.roles = await _roles_by_name(db, data.roles)
    await db.commit()
    persisted = await get_user_by_id(db, user.id)
    assert persisted is not None
    return persisted


async def _clear_project_manager_assignments(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        delete(project_manager_assignments).where(
            project_manager_assignments.c.user_id == user_id
        )
    )


async def deactivate_user(db: AsyncSession, user: User, current_user: User) -> None:
    is_self = user.id == current_user.id
    is_administrator = any(role.name == "administrator" for role in user.roles)
    if is_self and is_administrator:
        raise SelfLockoutError("You can't remove your own administrator access.")
    # A deactivated user can't stay a project manager: drop their assignments in the same
    # transaction (a DB trigger backs this up: see app/models/triggers.py). Deliberately
    # bypasses a closed project's read-only rule; this is a system change, not an edit.
    await _clear_project_manager_assignments(db, user.id)
    user.is_active = False
    await db.commit()


# Computed once at import: a real Argon2 hash with this app's own parameters, so a
# miss costs exactly what a hit costs. The plaintext is irrelevant and unusable.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-credential")


async def authenticate_local_user(
    db: AsyncSession, name_id: str, password: str
) -> User | None:
    user = await get_user_by_name_id(db, name_id)
    # Always hash against something, even when there's nothing real to check, so a
    # nonexistent/inactive/SSO account costs the same time as a real password check
    # (otherwise response time would reveal which emails are registered).
    candidate_hash = (
        user.hashed_password
        if user is not None and user.is_active and not user.is_sso and user.hashed_password
        else _DUMMY_HASH
    )
    matched = verify_password(password, candidate_hash)
    if user is None or not user.is_active or user.is_sso or user.hashed_password is None:
        return None
    return user if matched else None


async def reset_password(db: AsyncSession, user: User, new_password: str) -> None:
    user.hashed_password = hash_password(new_password)
    # A reset is what an admin does when an account may be compromised: sessions
    # already issued must not survive it.
    user.token_version += 1
    await db.commit()


async def revoke_sessions(db: AsyncSession, user: User) -> None:
    user.token_version += 1
    await db.commit()


async def update_theme_preference(
    db: AsyncSession, user: User, theme_preference: ThemePreference
) -> None:
    user.theme_preference = theme_preference
    await db.commit()


def to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name_id=user.name_id,
        full_name=user.full_name,
        roles=[role.name for role in user.roles],
        is_sso=user.is_sso,
        is_active=user.is_active,
        theme_preference=user.theme_preference,
    )
