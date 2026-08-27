"""Session lifecycle + current-user + password reset completion."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import CSRF_COOKIE, SESSION_COOKIE, CurrentActor, DbSession, RequestCtx
from app.core.config import get_settings
from app.domain import auth

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class MembershipOut(BaseModel):
    project_id: str
    project_key: str
    role: str


class MeOut(BaseModel):
    id: str
    username: str
    display_name: str
    is_system_admin: bool
    memberships: list[MembershipOut]


def _set_session_cookies(response: Response, token_id: str, csrf: str) -> None:
    settings = get_settings()
    secure = settings.public_url.startswith("https")
    max_age = settings.session_ttl_hours * 3600
    response.set_cookie(
        SESSION_COOKIE, token_id, httponly=True, secure=secure, samesite="lax", max_age=max_age
    )
    response.set_cookie(
        CSRF_COOKIE, csrf, httponly=False, secure=secure, samesite="lax", max_age=max_age
    )


@router.post("/session", response_model=MeOut, status_code=201)
async def create_session(
    body: LoginRequest, request: Request, response: Response, db: DbSession, ctx: RequestCtx
) -> MeOut:
    result = await auth.authenticate(
        db,
        ctx,
        username=body.username,
        password=body.password,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookies(response, result.token_id, result.csrf_token)
    return _me(result.actor)


@router.delete("/session", status_code=204)
async def delete_session(request: Request, response: Response, db: DbSession, ctx: RequestCtx):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await auth.logout(db, ctx, token)
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(CSRF_COOKIE)


@router.get("/me", response_model=MeOut)
async def me(actor: CurrentActor) -> MeOut:
    return _me(actor)


class PasswordResetComplete(BaseModel):
    token: str
    new_password: str = Field(min_length=12, max_length=256)


@router.post("/password-reset/complete", status_code=204)
async def complete_password_reset(
    body: PasswordResetComplete, db: DbSession, ctx: RequestCtx
):
    await auth.complete_password_reset(db, ctx, token=body.token, new_password=body.new_password)


def _me(actor) -> MeOut:
    return MeOut(
        id=str(actor.id),
        username=actor.username,
        display_name=actor.display_name,
        is_system_admin=actor.is_system_admin,
        memberships=[
            MembershipOut(project_id=str(m.project_id), project_key=m.project_key, role=m.role.value)
            for m in actor.memberships.values()
        ],
    )
