import math
import time

from fastapi import HTTPException, Request, status
from limits import RateLimitItemPerMinute
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import FixedWindowRateLimiter

LOGIN_LIMIT = RateLimitItemPerMinute(10)

# Counters live in process memory: fine for the single uvicorn worker this app runs, but
# they reset on restart and are not shared between workers. A fixed window lets a client
# fit attempts at the end of one window and the start of the next back to back, which is
# acceptable at this limit because every attempt still costs a full password hash.
login_storage = MemoryStorage()
_login_limiter = FixedWindowRateLimiter(login_storage)


async def login_rate_limit(request: Request) -> None:
    """Rejects the request with 429 once its client address is over the login limit.

    Used as a dependency ahead of the database session and the password check, so a
    rejected request never opens a session or reaches Argon2, which also bounds how much
    hashing work an unauthenticated client can force. Keyed on request.client.host, so it
    only sees real client IPs if the reverse proxy chain is set up to forward them
    (uvicorn's --forwarded-allow-ips); clients without an address share one bucket rather
    than bypassing the limit.
    """
    client = request.client.host if request.client else "unknown"
    if await _login_limiter.hit(LOGIN_LIMIT, "login", client):
        return
    stats = await _login_limiter.get_window_stats(LOGIN_LIMIT, "login", client)
    retry_after = max(1, math.ceil(stats.reset_time - time.time()))
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many login attempts. Try again in a minute.",
        headers={"Retry-After": str(retry_after)},
    )
