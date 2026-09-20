from typing import Any

from sqlalchemy import UnaryExpression
from sqlalchemy.orm import InstrumentedAttribute


def resolve_sort(
    sortable_columns: dict[str, InstrumentedAttribute[Any]],
    sort_by: str | None,
    sort_dir: str | None,
    default: UnaryExpression[Any],
) -> UnaryExpression[Any]:
    """Maps a client-supplied `sort_by` to a whitelisted column, never pass a raw
    client string into `order_by()`/`getattr()` directly. Falls back to `default`
    (the endpoint's own pre-existing default order) when `sort_by` is missing or
    not in the whitelist, rather than rejecting the request: a stale/unrecognized
    value on a GET degrades gracefully instead of erroring. `sort_dir` is
    similarly permissive, anything other than the literal `"desc"` means
    ascending, so an invalid direction just falls back to ascending rather than
    failing. Callers must still append a stable tie-breaker (e.g. the model's
    `id`) to whatever this returns: without one, rows with equal sort values can
    shift between pages or be skipped/duplicated across two paginated fetches,
    since Postgres doesn't otherwise guarantee stable ordering for ties.
    """
    column = sortable_columns.get(sort_by) if sort_by else None
    if column is None:
        return default
    return column.desc() if sort_dir == "desc" else column.asc()
