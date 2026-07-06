"""In-process abuse controls: request rate limiting + pipeline concurrency caps.

We deliberately avoid a new dependency (e.g. slowapi) because Wandr runs as a
single process with an in-memory session store. A shared-nothing, in-memory
limiter matches that model and keeps our deps lean. If we ever scale to multiple
instances, swap these for a Redis-backed store so limits are enforced globally.

Both limiters are safe under FastAPI's single-threaded event loop: each public
method runs to completion without awaiting, so its read-modify-write is atomic
relative to other coroutines.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from ai.config.settings import settings


class SlidingWindowLimiter:
    """Per-key sliding-window rate limiter backed by timestamp deques."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, limit: int, window_seconds: float) -> tuple[bool, float]:
        """Record an attempt. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - window_seconds
        bucket = self._hits[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = window_seconds - (now - bucket[0])
            return False, max(retry_after, 0.0)
        bucket.append(now)
        return True, 0.0


class PipelineConcurrencyLimiter:
    """Caps how many pipeline tasks run at once, per user and globally."""

    def __init__(self) -> None:
        self._per_user: dict[str, int] = defaultdict(int)
        self._global = 0

    def try_acquire(self, user_id: str, per_user_max: int, global_max: int) -> bool:
        """Reserve a pipeline slot if capacity allows. Returns True on success."""
        if self._global >= global_max:
            return False
        if self._per_user[user_id] >= per_user_max:
            return False
        self._global += 1
        self._per_user[user_id] += 1
        return True

    def release(self, user_id: str) -> None:
        """Return a previously acquired slot. Safe to call once per acquire."""
        self._global = max(0, self._global - 1)
        remaining = self._per_user.get(user_id, 0)
        if remaining <= 1:
            self._per_user.pop(user_id, None)
        else:
            self._per_user[user_id] = remaining - 1


_request_limiter = SlidingWindowLimiter()
pipeline_limiter = PipelineConcurrencyLimiter()


def client_ip(request: Request) -> str:
    """Best-effort client IP. Trusts the first X-Forwarded-For hop when present.

    Behind Google Cloud Run / a load balancer the platform appends the real
    client to X-Forwarded-For. Direct callers fall back to the socket peer.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(key: str, limit: int, window_seconds: float) -> None:
    """Raise HTTP 429 with a Retry-After header if `key` is over its budget."""
    if not settings.rate_limit_enabled:
        return
    allowed, retry_after = _request_limiter.hit(key, limit, window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down and try again shortly.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )
