"""Authentication + instance user management (increment 2).

Local auth only in Phase 1: Argon2id hashing, server-side sessions, failed-login
lockout, disabled accounts, admin-initiated password reset (decision D-004).
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, or_, select, update
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
        email=user.email,
        must_change_password=user.must_change_password,
        memberships=memberships,
    )


def _bare_actor(user: User) -> Actor:
    return Actor(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_system_admin=user.is_system_admin,
        email=user.email,
        must_change_password=user.must_change_password,
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


async def _create_user_row(
    session: AsyncSession, *, username: str, email: str, display_name: str,
    password: str, is_system_admin: bool = False,
) -> User:
    _validate_password(password)
    existing = await session.scalar(
        select(User).where(
            (func.lower(User.username) == username.strip().lower())
            | (func.lower(User.email) == email.strip().lower())
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
    return user


async def provision_user(
    session: AsyncSession, ctx: Ctx, *, username: str, email: str, display_name: str, password: str
) -> User:
    """Create a plain (non-admin) user. Authorization is the caller's responsibility
    (e.g. a project admin adding a member)."""
    user = await _create_user_row(
        session, username=username, email=email, display_name=display_name,
        password=password, is_system_admin=False,
    )
    audit.record(
        session, actor=Actor.system(), ctx=ctx, entity_type="user", action="user.provisioned",
        entity_id=user.id, after={"username": user.username},
    )
    return user


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


async def update_user(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, user_id: uuid.UUID,
    display_name: str | None = None, email: str | None = None, password: str | None = None,
) -> User:
    _require_sysadmin(actor)
    user = await session.get(User, user_id)
    if user is None:
        raise ResourceNotFound("User not found.")
    if password is not None:
        _validate_password(password)
        user.password_hash = hash_password(password)
        user.must_change_password = False
        user.failed_login_count = 0
        user.locked_until = None
        await session.execute(
            UserSession.__table__.update()
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=_now())
        )
    if display_name is not None:
        if not display_name.strip():
            raise ValidationFailed("Display name must not be empty.")
        user.display_name = display_name.strip()
    if email is not None:
        email = email.strip().lower()
        if not email:
            raise ValidationFailed("Email must not be empty.")
        clash = await session.scalar(
            select(User).where(func.lower(User.email) == email, User.id != user_id)
        )
        if clash is not None:
            raise ValidationFailed("Another user already has that email.")
        user.email = email
    user.version += 1
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="user", action="user.updated",
        entity_id=user.id, after={"display_name": user.display_name},
    )
    await session.commit()
    return user


async def delete_user(
    session: AsyncSession, actor: Actor, ctx: Ctx, *, user_id: uuid.UUID
) -> None:
    _require_sysadmin(actor)
    if user_id == actor.id:
        raise ValidationFailed("You cannot delete your own account.")
    user = await session.get(User, user_id)
    if user is None:
        raise ResourceNotFound("User not found.")
    if user.is_system_admin:
        raise ValidationFailed(
            "Administrator accounts cannot be deleted — disable the account instead."
        )

    from app.models import (
        AuditEvent,
        Defect,
        Feedback,
        PasswordResetToken,
        Project,
        ProjectAccessRequest,
        ProjectMembership,
        Release,
        Requirement,
        Scenario,
        TestCase,
        TestPlan,
        UserSession,
    )

    footprint = [
        select(func.count()).select_from(ProjectMembership).where(ProjectMembership.user_id == user_id),
        select(func.count()).select_from(Requirement).where(Requirement.created_by == user_id),
        select(func.count()).select_from(TestCase).where(TestCase.created_by == user_id),
        select(func.count()).select_from(Defect).where(Defect.created_by == user_id),
        select(func.count()).select_from(TestPlan).where(TestPlan.created_by == user_id),
        select(func.count()).select_from(Release).where(Release.created_by == user_id),
        select(func.count()).select_from(Scenario).where(Scenario.created_by == user_id),
        select(func.count()).select_from(Project).where(Project.created_by == user_id),
    ]
    for q in footprint:
        if await session.scalar(q):
            raise ValidationFailed(
                "This user belongs to a project or has authored content. Disable the "
                "account instead of deleting it."
            )

    await session.execute(delete(UserSession).where(UserSession.user_id == user_id))
    await session.execute(
        delete(PasswordResetToken).where(
            or_(PasswordResetToken.user_id == user_id, PasswordResetToken.created_by == user_id)
        )
    )
    await session.execute(delete(Feedback).where(Feedback.user_id == user_id))
    await session.execute(delete(ProjectAccessRequest).where(ProjectAccessRequest.user_id == user_id))
    await session.execute(
        update(AuditEvent).where(AuditEvent.actor_id == user_id).values(actor_id=None)
    )
    await session.execute(
        update(Feedback).where(Feedback.resolved_by == user_id).values(resolved_by=None)
    )
    await session.execute(
        update(ProjectAccessRequest)
        .where(ProjectAccessRequest.decided_by == user_id)
        .values(decided_by=None)
    )
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="user", action="user.deleted",
        entity_id=user_id, before={"username": user.username},
    )
    await session.delete(user)
    await session.commit()


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
    """Admin-issued temporary password. The user signs in with it directly and is
    forced to choose a new password immediately. Returns the plaintext temp password
    for the admin to hand over out-of-band."""
    _require_sysadmin(actor)
    user = await session.get(User, user_id)
    if user is None:
        raise ResourceNotFound("User not found.")
    temp = _generate_temp_password()
    user.password_hash = hash_password(temp)
    user.must_change_password = True
    user.failed_login_count = 0
    user.locked_until = None
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
        action="user.password_reset_by_admin",
        entity_id=user_id,
    )
    await session.commit()
    return temp


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
    user.must_change_password = False
    audit.record(
        session,
        actor=_bare_actor(user),
        ctx=ctx,
        entity_type="user",
        action="user.password_reset_completed",
        entity_id=user.id,
    )
    await session.commit()


# --- self-service "forgot password" (decision D-019) ---

_TEMP_PW_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"


def _generate_temp_password(length: int = 16) -> str:
    # Always satisfies the password policy (mixed case + digit, >= 12).
    body = "".join(secrets.choice(_TEMP_PW_ALPHABET) for _ in range(length - 3))
    return (
        secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ")
        + secrets.choice("abcdefghijkmnpqrstuvwxyz")
        + secrets.choice("23456789")
        + body
    )


class ResetOutcome:
    EMAIL_SENT = "email_sent"
    EMAIL_UNAVAILABLE = "email_unavailable"
    CONTACT_MAINTAINER = "contact_maintainer"


_OUTCOME_MESSAGES = {
    ResetOutcome.EMAIL_SENT: (
        "If an account matches that username or email, a temporary password has been "
        "sent to the address on file. Sign in with it, then choose a new password."
    ),
    ResetOutcome.EMAIL_UNAVAILABLE: (
        "Password reset by email is not configured on this server. Contact your "
        "administrator to have your password reset."
    ),
    ResetOutcome.CONTACT_MAINTAINER: (
        "Administrator accounts cannot be reset from this screen. Contact the person "
        "who maintains this TESQIVO instance."
    ),
}


async def request_password_reset(
    session: AsyncSession, ctx: Ctx, *, identifier: str
) -> tuple[str, str]:
    """User-initiated forgot-password. Returns (outcome_code, message).

    The response never confirms whether a normal account exists. Administrator
    accounts always get CONTACT_MAINTAINER (they must not be reset without a human
    in the loop). When SMTP is not configured, everyone is told to contact an
    administrator.
    """
    from app.core.mailer import get_mailer

    settings = get_settings()
    ident = identifier.strip().lower()
    user = await session.scalar(
        select(User).where(
            (func.lower(User.username) == ident) | (func.lower(User.email) == ident)
        )
    )

    if user is not None and user.is_system_admin:
        return ResetOutcome.CONTACT_MAINTAINER, _OUTCOME_MESSAGES[ResetOutcome.CONTACT_MAINTAINER]

    if not settings.email_enabled:
        audit.record(
            session, actor=Actor.system(), ctx=ctx, entity_type="user",
            action="user.password_reset_requested_email_unavailable",
            entity_id=user.id if user else None,
        )
        await session.commit()
        return (
            ResetOutcome.EMAIL_UNAVAILABLE,
            _OUTCOME_MESSAGES[ResetOutcome.EMAIL_UNAVAILABLE],
        )

    # Email is configured. Only act for a real, active, non-admin account; otherwise
    # return the same generic message so account existence is not disclosed.
    if user is not None and user.status == "active":
        temp = _generate_temp_password()
        user.password_hash = hash_password(temp)
        user.must_change_password = True
        user.failed_login_count = 0
        user.locked_until = None
        await session.execute(
            UserSession.__table__.update()
            .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=_now())
        )
        audit.record(
            session, actor=Actor.system(), ctx=ctx, entity_type="user",
            action="user.password_reset_email_sent", entity_id=user.id,
        )
        await session.commit()
        try:
            await get_mailer().send(
                to=user.email,
                subject="TESQIVO temporary password",
                body=(
                    f"Hello {user.display_name},\n\n"
                    "A password reset was requested for your TESQIVO account.\n\n"
                    f"Temporary password: {temp}\n\n"
                    f"Sign in at {settings.public_url} with this temporary password. "
                    "You will be asked to set a new password immediately.\n\n"
                    "If you did not request this, contact your administrator - your "
                    "previous password no longer works.\n"
                ),
            )
        except Exception:  # noqa: BLE001
            log = __import__("logging").getLogger("tesqivo.mailer")
            log.exception("failed to send password-reset email")
    else:
        audit.record(
            session, actor=Actor.system(), ctx=ctx, entity_type="user",
            action="user.password_reset_requested_no_match", entity_id=None,
        )
        await session.commit()

    return ResetOutcome.EMAIL_SENT, _OUTCOME_MESSAGES[ResetOutcome.EMAIL_SENT]


async def change_own_password(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    current_password: str,
    new_password: str,
) -> None:
    user = await session.get(User, actor.id)
    if user is None:
        raise ResourceNotFound("User not found.")
    if not verify_password(current_password, user.password_hash):
        raise InvalidCredentials("Your current password is incorrect.")
    _validate_password(new_password)
    if verify_password(new_password, user.password_hash):
        raise ValidationFailed("The new password must be different from the current one.")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="user",
        action="user.password_changed", entity_id=user.id,
    )
    await session.commit()
