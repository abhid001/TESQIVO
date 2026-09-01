"""Correlation id, per-request DB session, and a lightweight rate limiter."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.errors import RateLimited, error_envelope


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        corr = request.headers.get("x-correlation-id") or _new_id()
        request.state.correlation_id = corr
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr
        return response


class DbSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        async with get_sessionmaker()() as session:
            request.state.db = session
            try:
                response = await call_next(request)
            except Exception:
                await session.rollback()
                raise
            return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-process sliding-window limiter keyed by client + path class.

    Sufficient for a single-node Phase 1 deployment; a Redis token bucket is the
    documented upgrade for multi-instance (OQ-3).
    """

    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if settings.is_test or not request.url.path.startswith("/api/"):
            return await call_next(request)
        limit = settings.rate_limit_per_minute
        if request.url.path.startswith("/api/v1/auth"):
            limit = 20
        key = f"{request.client.host if request.client else '?'}:{_bucket(request.url.path)}"
        now = time.monotonic()
        window = self._hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit:
            corr = getattr(request.state, "correlation_id", "unknown")
            return JSONResponse(
                status_code=429,
                content=error_envelope(RateLimited("Too many requests. Slow down."), corr),
                headers={"Retry-After": "30"},
            )
        window.append(now)
        return await call_next(request)


def _new_id() -> str:
    return uuid.uuid4().hex


def _bucket(path: str) -> str:
    parts = path.strip("/").split("/")
    return "/".join(parts[:4])


def install(app) -> None:
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(DbSessionMiddleware)
    app.add_middleware(CorrelationMiddleware)
