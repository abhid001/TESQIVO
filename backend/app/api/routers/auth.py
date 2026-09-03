"""Session lifecycle + current-user + password reset completion."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import CSRF_COOKIE, SESSION_COOKIE, CurrentActor, DbSession, RequestCtx
from app.core.config import get_settings
from app.core.errors import Forbidden
from app.core.security import csrf_matches
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
    email: str
    is_system_admin: bool
    must_change_password: bool
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
    # Logout is an unsafe cookie-authenticated request, so it still needs the CSRF
    # double-submit check (finding #11) - but not a *live* account, so it does not
    # go through CurrentActor (a disabled / password-expired user can still log out).
    if not csrf_matches(request.cookies.get(CSRF_COOKIE, ""), request.headers.get("x-csrf-token")):
        raise Forbidden("Missing or invalid CSRF token.")
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
    new_password: str = Field(min_length=1, max_length=256)


@router.post("/password-reset/complete", status_code=204)
async def complete_password_reset(
    body: PasswordResetComplete, db: DbSession, ctx: RequestCtx
):
    await auth.complete_password_reset(db, ctx, token=body.token, new_password=body.new_password)


class PasswordResetRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320, description="Username or email")


class PasswordResetRequestOut(BaseModel):
    outcome: str
    message: str
    email_configured: bool


@router.post("/password-reset/request", response_model=PasswordResetRequestOut)
async def request_password_reset(
    body: PasswordResetRequest, db: DbSession, ctx: RequestCtx
) -> PasswordResetRequestOut:
    outcome, message = await auth.request_password_reset(db, ctx, identifier=body.identifier)
    return PasswordResetRequestOut(
        outcome=outcome, message=message, email_configured=get_settings().email_enabled
    )


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


@router.post("/password", status_code=204)
async def change_password(
    body: ChangePasswordRequest, request: Request, actor: CurrentActor, db: DbSession, ctx: RequestCtx
):
    await auth.change_own_password(
        db, actor, ctx,
        current_password=body.current_password,
        new_password=body.new_password,
        keep_session_token_hash=getattr(request.state, "session_token_hash", None),
    )


def _me(actor) -> MeOut:
    return MeOut(
        id=str(actor.id),
        username=actor.username,
        display_name=actor.display_name,
        email=actor.email,
        is_system_admin=actor.is_system_admin,
        must_change_password=actor.must_change_password,
        memberships=[
            MembershipOut(project_id=str(m.project_id), project_key=m.project_key, role=m.role.value)
            for m in actor.memberships.values()
        ],
    )
