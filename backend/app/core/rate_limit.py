"""A fixed-size sliding-window limiter kept in the process memory.

Good enough for one API process (the deployment in plan section 8). With several replicas each
would count on its own, so the real limit would be multiplied; that would need a shared store.
"""

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings

WINDOW_SECONDS = 60

_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def reset() -> None:
    _hits.clear()


def limit_per_minute(name: str, allowed: Callable[[], int]) -> Callable[[Request], None]:
    """A dependency that refuses the (allowed() + 1)th call of `name` per client in a minute."""

    def check(request: Request) -> None:
        maximum = allowed()
        if maximum <= 0:
            return
        client = request.client.host if request.client else "unknown"
        hits = _hits[(name, client)]
        now = time.monotonic()
        while hits and now - hits[0] >= WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= maximum:
            retry_after = max(1, int(WINDOW_SECONDS - (now - hits[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts, try again in a minute",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)

    return check


register_limit = limit_per_minute("register", lambda: settings.auth_attempts_per_minute)
login_limit = limit_per_minute("login", lambda: settings.auth_attempts_per_minute)
