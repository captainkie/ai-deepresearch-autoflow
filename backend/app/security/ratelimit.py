"""Lightweight in-process rate limiting for auth endpoints.

A per-key sliding-window counter kept in memory — sufficient for a single-process
self-hosted deployment (the target). It is not a distributed limiter; if you run
multiple workers behind a load balancer, put a real limiter (e.g. Redis) in front.

Used as a FastAPI dependency that keys on the client IP + a route scope, and is
skipped entirely when ``settings.rate_limit_enabled`` is False (tests).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import get_app_settings
from app.settings import AppSettings


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_s: float) -> None:
        self._max = max_events
        self._window = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float) -> bool:
        """Record a hit for ``key`` and return whether it is within the limit."""
        dq = self._hits[key]
        cutoff = now - self._window
        while dq and dq[0] <= cutoff:
            dq.popleft()
        if len(dq) >= self._max:
            return False
        dq.append(now)
        if not dq:  # unreachable, but keeps the map from growing unbounded
            del self._hits[key]
        return True


def _client_ip(request: Request) -> str:
    """The real client IP for rate-limit keying.

    Prefer the left-most ``X-Forwarded-For`` hop (set by the hosting proxy, e.g.
    Render/Cloudflare) over the socket peer — behind a proxy the peer is always
    the proxy, so without this every client collapses into one shared bucket.
    Note: ``X-Forwarded-For`` is client-spoofable when no trusted proxy overwrites
    it; acceptable here since the demo forces mock providers (abuse can't run up
    cost) and a real deployment should sit behind a proxy that sets it.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def rate_limit(max_events: int, window_s: float, scope: str) -> Callable[..., None]:
    """Build a dependency that limits ``max_events`` per ``window_s`` per client IP."""
    limiter = SlidingWindowLimiter(max_events, window_s)

    def dependency(
        request: Request,
        settings: AppSettings = Depends(get_app_settings),
    ) -> None:
        if not settings.rate_limit_enabled:
            return
        ip = _client_ip(request)
        if not limiter.allow(f"{scope}:{ip}", time.monotonic()):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests — please slow down and try again shortly.",
            )

    return dependency
