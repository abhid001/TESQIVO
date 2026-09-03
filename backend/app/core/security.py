"""Password hashing (Argon2id), session token generation, CSRF helpers."""

from __future__ import annotations

import hmac
import secrets
from hashlib import sha256

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings

_hasher: PasswordHasher | None = None

MIN_PASSWORD_LENGTH = 12

# Human-readable statement of the policy, shown in prompts and error messages.
PASSWORD_POLICY = (
    f"at least {MIN_PASSWORD_LENGTH} characters, and must include an upper-case letter, "
    "a lower-case letter, a digit, and a special character (for example ! ? @ # $ % & *). "
    "Any extra letters, digits, or symbols beyond these are fine."
)


def _ph() -> PasswordHasher:
    global _hasher
    if _hasher is None:
        s = get_settings()
        _hasher = PasswordHasher(
            time_cost=s.argon2_time_cost,
            memory_cost=s.argon2_memory_cost_kib,
            parallelism=s.argon2_parallelism,
        )
    return _hasher


def hash_password(plain: str) -> str:
    return _ph().hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph().verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError, Exception):
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _ph().check_needs_rehash(hashed)
    except Exception:
        return False


def password_policy_errors(plain: str) -> list[str]:
    """Return one message per unmet requirement (empty list = acceptable).

    Every check is a *minimum* ("contains at least one ..."); nothing is
    forbidden, so a longer password with extra letters or symbols always passes
    as long as the required character classes are present.
    """
    errs: list[str] = []
    if len(plain) < MIN_PASSWORD_LENGTH:
        errs.append(f"Use at least {MIN_PASSWORD_LENGTH} characters (yours has {len(plain)}).")
    if not any(c.islower() for c in plain):
        errs.append("Add at least one lower-case letter (a-z).")
    if not any(c.isupper() for c in plain):
        errs.append("Add at least one upper-case letter (A-Z).")
    if not any(c.isdigit() for c in plain):
        errs.append("Add at least one digit (0-9).")
    if not any(not c.isalnum() and not c.isspace() for c in plain):
        errs.append("Add at least one special character, e.g. ! ? @ # $ % & *")
    return errs


def new_session_id() -> str:
    """256 bits of entropy, url-safe."""
    return secrets.token_urlsafe(32)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def csrf_matches(cookie_value: str, header_value: str | None) -> bool:
    if not header_value:
        return False
    return hmac.compare_digest(cookie_value, header_value)


def hash_token(raw: str) -> str:
    """Store only the hash of one-time tokens (password reset)."""
    return sha256(raw.encode()).hexdigest()
