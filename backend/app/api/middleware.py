"""Correlation id, per-request DB session, and a lightweight rate limiter."""

from __future__ import annotations

import ipaddress
import re
import time
import uuid
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.errors import RateLimited, error_envelope

_CORR_RE = re.compile(r"\A[A-Za-z0-9._-]{1,64}\Z")


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # An inbound id is echoed only if it is a sane short token (finding #14);
        # anything else is replaced with a fresh one.
        raw = request.headers.get("x-correlation-id")
        corr = raw if raw and _CORR_RE.match(raw) else _new_id()
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


def client_ip(request: Request) -> str:
    """The caller's IP, honouring a forwarded-for header only when the direct peer
    is a configured trusted proxy (finding #7)."""
    peer = request.client.host if request.client else "?"
    nets = get_settings().trusted_proxy_networks
    trusted = False
    if nets == ["*"]:
        trusted = True
    elif nets and peer != "?":
        try:
            ip = ipaddress.ip_address(peer)
            trusted = any(ip in n for n in nets)
        except ValueError:
            trusted = False
    if not trusted:
        return peer
    fwd = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip() or peer
    return peer


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-process sliding-window limiter keyed by client + path class.

    Single-node only; a Redis token bucket is the documented upgrade for
    multi-instance (OQ-3). Stale keys are evicted so memory stays bounded
    (finding #8).
    """

    _MAX_KEYS = 20_000
    _SWEEP_EVERY = 120.0

    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_sweep = 0.0

    def _sweep(self, now: float) -> None:
        if now - self._last_sweep < self._SWEEP_EVERY:
            return
        self._last_sweep = now
        for k in [k for k, w in self._hits.items() if not w or now - w[-1] > 60]:
            self._hits.pop(k, None)

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if settings.is_test or not request.url.path.startswith("/api/"):
            return await call_next(request)
        limit = settings.rate_limit_per_minute
        if request.url.path.startswith("/api/v1/auth"):
            limit = 20
        now = time.monotonic()
        self._sweep(now)
        if len(self._hits) >= self._MAX_KEYS:
            self._hits.clear()  # crude bound; recovers within a window
        key = f"{client_ip(request)}:{_bucket(request.url.path)}"
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
