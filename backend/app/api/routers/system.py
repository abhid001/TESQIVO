"""Health checks and first-admin setup (increments 1-2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text

from app import __version__
from app.api.deps import DbSession, RequestCtx
from app.core.config import get_settings
from app.domain import auth

router = APIRouter(tags=["system"])


@router.get("/healthz")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/version")
async def version() -> dict[str, str]:
    return {"version": __version__, "environment": get_settings().environment}


@router.get("/readyz")
async def readiness(db: DbSession, response: Response) -> dict[str, object]:
    checks: dict[str, str] = {}
    ok = True
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
        ok = False
    if not ok:
        response.status_code = 503
    return {"status": "ok" if ok else "degraded", "checks": checks}


class SetupStatus(BaseModel):
    needs_setup: bool


@router.get("/setup/status", response_model=SetupStatus)
async def setup_status(db: DbSession) -> SetupStatus:
    return SetupStatus(needs_setup=await auth.needs_setup(db))


class SetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    display_name: str
    is_system_admin: bool
    status: str


@router.post("/setup", response_model=UserOut, status_code=201)
async def complete_setup(
    body: SetupRequest,
    db: DbSession,
    ctx: RequestCtx,
    x_bootstrap_token: Annotated[str | None, Header(alias="X-Bootstrap-Token")] = None,
) -> UserOut:
    user = await auth.complete_setup(
        db,
        ctx,
        bootstrap_token=x_bootstrap_token,
        username=body.username,
        email=body.email,
        display_name=body.display_name,
        password=body.password,
    )
    return UserOut(
        id=str(user.id),
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        is_system_admin=user.is_system_admin,
        status=user.status,
    )
