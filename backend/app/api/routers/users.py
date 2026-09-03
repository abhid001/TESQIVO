"""Instance user management - System Admin only (increment 2)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.api.deps import CurrentActor, DbSession, RequestCtx
from app.core.errors import Forbidden
from app.domain import access, auth
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
    password: str = Field(min_length=1, max_length=256)
    is_system_admin: bool = False


class StatusRequest(BaseModel):
    status: str


class UpdateUserRequest(BaseModel):
    display_name: str | None = None
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=1, max_length=256)


class ResetOut(BaseModel):
    temporary_password: str
    note: str = "The user signs in with this password and must set a new one immediately."


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


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str, body: UpdateUserRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> UserOut:
    import uuid

    user = await auth.update_user(
        db, actor, ctx, user_id=uuid.UUID(user_id),
        display_name=body.display_name, email=body.email, password=body.password,
    )
    return _out(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: str, actor: CurrentActor, db: DbSession, ctx: RequestCtx):
    import uuid

    await auth.delete_user(db, actor, ctx, user_id=uuid.UUID(user_id))


class UserMembershipOut(BaseModel):
    project_id: str
    project_key: str
    project_name: str
    role: str


@router.get("/{user_id}/memberships", response_model=list[UserMembershipOut])
async def user_memberships(
    user_id: str, actor: CurrentActor, db: DbSession
) -> list[UserMembershipOut]:
    import uuid

    rows = await access.user_memberships(db, actor, user_id=uuid.UUID(user_id))
    return [
        UserMembershipOut(
            project_id=str(p.id), project_key=p.key, project_name=p.name, role=m.role
        )
        for (m, p) in rows
    ]


@router.post("/{user_id}/password-reset", response_model=ResetOut, status_code=201)
async def initiate_reset(
    user_id: str, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> ResetOut:
    import uuid

    temp = await auth.initiate_password_reset(db, actor, ctx, user_id=uuid.UUID(user_id))
    return ResetOut(temporary_password=temp)
