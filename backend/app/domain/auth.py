"""Authentication + instance user management (increment 2).

Local auth only in Phase 1: Argon2id hashing, server-side sessions, failed-login
lockout, disabled accounts, admin-initiated password reset (decision D-004).
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.context import Actor, Ctx, Membership, Role
from app.core.errors import (
    Forbidden,
    InvalidCredentials,
    ResourceNotFound,
    SetupAlreadyCompleted,
    ValidationFailed,
)
from app.core.security import (
    hash_password,
    hash_token,
    needs_rehash,
    new_csrf_token,
    new_session_id,
    password_policy_errors,
    verify_password,
)
from app.domain import audit
from app.models import PasswordResetToken, Project, ProjectMembership, User, UserSession


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class SessionCreated:
    token_id: str
    csrf_token: str
    expires_at: datetime
    actor: Actor


async def needs_setup(session: AsyncSession) -> bool:
    count = await session.scalar(select(func.count()).select_from(User))
    return (count or 0) == 0


async def complete_setup(
    session: AsyncSession,
    ctx: Ctx,
    *,
    bootstrap_token: str | None,
    username: str,
    email: str,
    display_name: str,
    password: str,
) -> User:
    if not await needs_setup(session):
        raise SetupAlreadyCompleted("Initial setup has already been completed.")
    expected = get_settings().bootstrap_token
    if not expected or not bootstrap_token or not secrets.compare_digest(bootstrap_token, expected):
        raise Forbidden("Invalid or missing bootstrap token.")
    _validate_password(password)
    user = User(
        username=username.strip(),
        email=email.strip().lower(),
        display_name=display_name.strip() or username,
        password_hash=hash_password(password),
        is_system_admin=True,
        status="active",
    )
    session.add(user)
    await session.flush()
    audit.record(
        session,
        actor=Actor.system(),
        ctx=ctx,
        entity_type="user",
        action="setup.first_admin_created",
        entity_id=user.id,
        after={"username": user.username, "is_system_admin": True},
    )
    await session.commit()
    return user


async def authenticate(
    session: AsyncSession,
    ctx: Ctx,
    *,
    username: str,
    password: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> SessionCreated:
    settings = get_settings()
    user = await session.scalar(select(User).where(User.username == username))
    # Uniform failure for missing / disabled / locked / bad password.
    if user is None:
        # spend comparable time to reduce user enumeration via timing
        verify_password(password, hash_password("dummy-timing-guard"))
        raise InvalidCredentials("Invalid username or password.")
    if user.status == "disabled":
        raise InvalidCredentials("Invalid username or password.")
    if user.locked_until is not None and user.locked_until > _now():
        raise InvalidCredentials("Invalid username or password.")

    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.failed_login_threshold:
            user.locked_until = _now() + timedelta(minutes=settings.failed_login_lockout_minutes)
            user.failed_login_count = 0
        await session.commit()
        raise InvalidCredentials("Invalid username or password.")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None

    token_id = new_session_id()
    csrf = new_csrf_token()
    expires = _now() + timedelta(hours=settings.session_ttl_hours)
    session.add(
        UserSession(
            token_id=token_id,
            user_id=user.id,
            csrf_token=csrf,
            expires_at=expires,
            ip=ip,
            user_agent=(user_agent or "")[:400] or None,
        )
    )
    audit.record(
        session,
        actor=_bare_actor(user),
        ctx=ctx,
        entity_type="session",
        action="auth.login",
        entity_id=user.id,
    )
    await session.commit()
    actor = await load_actor(session, user.id)
    return SessionCreated(token_id=token_id, csrf_token=csrf, expires_at=expires, actor=actor)


async def resolve_session(session: AsyncSession, token_id: str) -> tuple[Actor, UserSession] | None:
    us = await session.scalar(select(UserSession).where(UserSession.token_id == token_id))
    if us is None or us.revoked_at is not None:
        return None
    if us.expires_at <= _now():
        return None
    user = await session.get(User, us.user_id)
    if user is None or user.status == "disabled":
        return None
    us.last_seen_at = _now()
    actor = await load_actor(session, user.id)
    return actor, us


async def logout(session: AsyncSession, ctx: Ctx, token_id: str) -> None:
    us = await session.scalar(select(UserSession).where(UserSession.token_id == token_id))
    if us is not None and us.revoked_at is None:
        us.revoked_at = _now()
        await session.commit()


async def load_actor(session: AsyncSession, user_id: uuid.UUID) -> Actor:
    user = await session.get(User, user_id)
    if user is None:
        raise ResourceNotFound("User not found.")
    rows = (
        await session.execute(
            select(ProjectMembership, Project.key)
            .join(Project, Project.id == ProjectMembership.project_id)
            .where(
                ProjectMembership.user_id == user_id,
                ProjectMembership.status == "active",
            )
        )
    ).all()
    memberships = {
        m.project_id: Membership(project_id=m.project_id, project_key=key, role=Role(m.role))
        for (m, key) in rows
    }
    return Actor(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_system_admin=user.is_system_admin,
        memberships=memberships,
    )


def _bare_actor(user: User) -> Actor:
    return Actor(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_system_admin=user.is_system_admin,
    )


# --- instance user management (system admin only) ---


def _require_sysadmin(actor: Actor) -> None:
    if not actor.is_system_admin:
        raise Forbidden("System administrator access required.")


def _validate_password(password: str) -> None:
    errs = password_policy_errors(password)
    if errs:
        raise ValidationFailed(
            "Password does not meet the policy.",
            details=[{"field": "/password", "code": "WEAK_PASSWORD", "message": e} for e in errs],
        )


async def create_user(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    username: str,
    email: str,
    display_name: str,
    password: str,
    is_system_admin: bool = False,
) -> User:
    _require_sysadmin(actor)
    _validate_password(password)
    existing = await session.scalar(
        select(User).where(
            (User.username == username.strip()) | (User.email == email.strip().lower())
        )
    )
    if existing is not None:
        raise ValidationFailed("A user with that username or email already exists.")
    user = User(
        username=username.strip(),
        email=email.strip().lower(),
        display_name=display_name.strip() or username,
        password_hash=hash_password(password),
        is_system_admin=is_system_admin,
        status="active",
    )
    session.add(user)
    await session.flush()
    audit.record(
        session,
        actor=actor,
        ctx=ctx,
        entity_type="user",
        action="user.created",
        entity_id=user.id,
        after={"username": user.username, "is_system_admin": is_system_admin},
    )
    await session.commit()
    return user


async def set_user_status(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, user_id: uuid.UUID, status: str
) -> User:
    _require_sysadmin(actor)
    if status not in ("active", "disabled"):
        raise ValidationFailed("status must be 'active' or 'disabled'.")
    user = await session.get(User, user_id)
    if user is None:
        raise ResourceNotFound("User not found.")
    if status == "disabled" and user.id == actor.id:
        raise ValidationFailed("You cannot disable your own account.")
    before = {"status": user.status}
    user.status = status
    if status == "disabled":
        await session.execute(
            UserSession.__table__.update()
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=_now())
        )
    audit.record(
        session,
        actor=actor,
        ctx=ctx,
        entity_type="user",
        action="user.status_changed",
        entity_id=user.id,
        before=before,
        after={"status": status},
    )
    await session.commit()
    return user


async def initiate_password_reset(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, user_id: uuid.UUID
) -> str:
    """Returns a one-time token to hand to the user out-of-band (no email in Phase 1)."""
    _require_sysadmin(actor)
    user = await session.get(User, user_id)
    if user is None:
        raise ResourceNotFound("User not found.")
    raw = secrets.token_urlsafe(32)
    session.add(
        PasswordResetToken(
            user_id=user_id,
            token_hash=hash_token(raw),
            created_by=actor.id,
            expires_at=_now() + timedelta(hours=24),
        )
    )
    audit.record(
        session,
        actor=actor,
        ctx=ctx,
        entity_type="user",
        action="user.password_reset_initiated",
        entity_id=user_id,
    )
    await session.commit()
    return raw


async def complete_password_reset(
    session: AsyncSession, ctx: Ctx, *, token: str, new_password: str
) -> None:
    _validate_password(new_password)
    th = hash_token(token)
    prt = await session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == th)
    )
    if prt is None or prt.used_at is not None or prt.expires_at <= _now():
        raise InvalidCredentials("Invalid or expired reset token.")
    user = await session.get(User, prt.user_id)
    if user is None:
        raise InvalidCredentials("Invalid or expired reset token.")
    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    prt.used_at = _now()
    await session.execute(
        UserSession.__table__.update()
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    audit.record(
        session,
        actor=_bare_actor(user),
        ctx=ctx,
        entity_type="user",
        action="user.password_reset_completed",
        entity_id=user.id,
    )
    await session.commit()
