"""FastAPI dependencies: DB session, request context, current actor, CSRF guard."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor, Ctx, Source
from app.core.errors import AuthenticationRequired, Forbidden
from app.core.security import csrf_matches
from app.domain import auth

SESSION_COOKIE = "tesqivo_session"
CSRF_COOKIE = "tesqivo_csrf"

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


async def get_db(request: Request) -> AsyncSession:
    return request.state.db


def get_ctx(
    request: Request,
    x_correlation_id: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Ctx:
    corr = getattr(request.state, "correlation_id", None) or x_correlation_id or "unknown"
    src = Source.gui if request.headers.get("x-tesqivo-client") == "web" else Source.api
    return Ctx(correlation_id=corr, source=src, idempotency_key=idempotency_key)


async def current_actor(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Actor:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise AuthenticationRequired("Authentication required.")
    resolved = await auth.resolve_session(db, token)
    if resolved is None:
        raise AuthenticationRequired("Session expired or invalid.")
    actor, us = resolved
    # CSRF: unsafe methods require the double-submit token to match (decision D-011).
    if request.method not in _SAFE_METHODS:
        header = request.headers.get("x-csrf-token")
        if not csrf_matches(us.csrf_token, header):
            raise Forbidden("Missing or invalid CSRF token.")
    request.state.actor = actor
    return actor


CurrentActor = Annotated[Actor, Depends(current_actor)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
RequestCtx = Annotated[Ctx, Depends(get_ctx)]
