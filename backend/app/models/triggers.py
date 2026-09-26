"""Postgres triggers that keep `project_managers` free of deactivated users.

A deactivated (soft-deleted) user must never be a project manager. The app already
removes their assignments when it deactivates a user (see
`user_service.deactivate_user`); these triggers are the backstop so the database can't
end up in that state through any other path (raw SQL, a future code path, a race
between "assign" and "deactivate").

The statements are plain strings shared by the Alembic migration and by the SQLAlchemy
`after_create` hooks below (which is how the test database, built with `create_all`,
not migrations, gets them too). Deliberately free of `%` and `:` so they survive both
`DDL()` and `op.execute()` unmodified. One statement per string: asyncpg can't run
several commands in one prepared statement.
"""

from sqlalchemy import DDL, event

USERS_TRIGGER_STATEMENTS = [
    """
    CREATE OR REPLACE FUNCTION ifrit_clear_pm_on_user_deactivate() RETURNS trigger AS $$
    BEGIN
        DELETE FROM project_managers WHERE user_id = NEW.id;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE TRIGGER trg_users_clear_pm_on_deactivate
    AFTER UPDATE OF is_active ON users
    FOR EACH ROW
    WHEN (OLD.is_active AND NOT NEW.is_active)
    EXECUTE FUNCTION ifrit_clear_pm_on_user_deactivate()
    """,
]

PROJECT_MANAGERS_TRIGGER_STATEMENTS = [
    # FOR SHARE locks the user row until this transaction ends, so a concurrent
    # deactivation waits for it and then clears the row this insert just made: an
    # assignment racing a deletion can't leave a stale project manager behind.
    """
    CREATE OR REPLACE FUNCTION ifrit_require_active_project_manager() RETURNS trigger AS $$
    DECLARE
        user_is_active boolean;
    BEGIN
        SELECT is_active INTO user_is_active FROM users WHERE id = NEW.user_id FOR SHARE;
        IF user_is_active IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'A deactivated user cannot be a project manager'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE TRIGGER trg_project_managers_require_active_user
    BEFORE INSERT OR UPDATE OF user_id ON project_managers
    FOR EACH ROW
    EXECUTE FUNCTION ifrit_require_active_project_manager()
    """,
]

DROP_STATEMENTS = [
    "DROP TRIGGER IF EXISTS trg_project_managers_require_active_user ON project_managers",
    "DROP TRIGGER IF EXISTS trg_users_clear_pm_on_deactivate ON users",
    "DROP FUNCTION IF EXISTS ifrit_require_active_project_manager()",
    "DROP FUNCTION IF EXISTS ifrit_clear_pm_on_user_deactivate()",
]


def attach() -> None:
    """Registers the triggers to be created right after their tables (`create_all`)."""
    from app.models.project import project_manager_assignments
    from app.models.user import User

    for statement in USERS_TRIGGER_STATEMENTS:
        event.listen(User.__table__, "after_create", DDL(statement))
    for statement in PROJECT_MANAGERS_TRIGGER_STATEMENTS:
        event.listen(project_manager_assignments, "after_create", DDL(statement))
