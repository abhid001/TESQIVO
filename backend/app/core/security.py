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
    errs: list[str] = []
    if len(plain) < MIN_PASSWORD_LENGTH:
        errs.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if plain.lower() == plain or plain.upper() == plain:
        errs.append("Password must contain both upper and lower case letters.")
    if not any(c.isdigit() for c in plain):
        errs.append("Password must contain at least one digit.")
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
