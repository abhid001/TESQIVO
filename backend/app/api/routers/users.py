"""Instance user management - System Admin only (increment 2)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.api.deps import CurrentActor, DbSession, RequestCtx
from app.core.errors import Forbidden
from app.domain import auth
from app.models import User

router = APIRouter(prefix="/users", tags=["users"])


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    display_name: str
    is_system_admin: bool
    status: str


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=256)
    is_system_admin: bool = False


class StatusRequest(BaseModel):
    status: str


class ResetOut(BaseModel):
    reset_token: str
    note: str = "Deliver this token to the user out-of-band. It expires in 24 hours."


def _out(u: User) -> UserOut:
    return UserOut(
        id=str(u.id),
        username=u.username,
        email=u.email,
        display_name=u.display_name,
        is_system_admin=u.is_system_admin,
        status=u.status,
    )


@router.get("", response_model=list[UserOut])
async def list_users(actor: CurrentActor, db: DbSession) -> list[UserOut]:
    if not actor.is_system_admin:
        raise Forbidden("System administrator access required.")
    rows = (await db.scalars(select(User).order_by(User.username))).all()
    return [_out(u) for u in rows]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    body: CreateUserRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> UserOut:
    user = await auth.create_user(
        db,
        actor,
        ctx,
        username=body.username,
        email=body.email,
        display_name=body.display_name,
        password=body.password,
        is_system_admin=body.is_system_admin,
    )
    return _out(user)


@router.put("/{user_id}/status", response_model=UserOut)
async def set_status(
    user_id: str, body: StatusRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> UserOut:
    import uuid

    user = await auth.set_user_status(
        db, actor, ctx, user_id=uuid.UUID(user_id), status=body.status
    )
    return _out(user)


@router.post("/{user_id}/password-reset", response_model=ResetOut, status_code=201)
async def initiate_reset(
    user_id: str, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> ResetOut:
    import uuid

    token = await auth.initiate_password_reset(db, actor, ctx, user_id=uuid.UUID(user_id))
    return ResetOut(reset_token=token)
