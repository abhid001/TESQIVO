"""Shared identity validation for user creation - used by both the HTTP setup /
user-admin routes and the CLI so they cannot diverge (finding #12)."""

from __future__ import annotations

import re

from email_validator import EmailNotValidError
from email_validator import validate_email as _validate_email

from app.core.errors import ValidationFailed

USERNAME_MIN, USERNAME_MAX = 3, 64
DISPLAY_NAME_MIN, DISPLAY_NAME_MAX = 1, 200
EMAIL_MAX = 320

# letters/digits, then letters/digits plus . _ -  ; must start alphanumeric
_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def identity_errors(*, username: str, email: str, display_name: str) -> list[str]:
    errs: list[str] = []

    u = (username or "").strip()
    if not (USERNAME_MIN <= len(u) <= USERNAME_MAX) or not _USERNAME_RE.match(u):
        errs.append(
            f"Username must be {USERNAME_MIN}-{USERNAME_MAX} characters using letters, digits, "
            "'.', '_' or '-', and start with a letter or digit."
        )

    e = (email or "").strip()
    if len(e) > EMAIL_MAX:
        errs.append(f"Email address must be at most {EMAIL_MAX} characters.")
    else:
        try:
            _validate_email(e, check_deliverability=False)
        except EmailNotValidError:
            errs.append("Enter a valid email address.")

    # An empty display name is allowed at creation time (callers default it to the
    # username); only reject one that is actually present and too long.
    d = (display_name or "").strip()
    if d and len(d) > DISPLAY_NAME_MAX:
        errs.append(f"Display name must be at most {DISPLAY_NAME_MAX} characters.")

    return errs


def validate_identity(*, username: str, email: str, display_name: str) -> None:
    errs = identity_errors(username=username, email=email, display_name=display_name)
    if errs:
        raise ValidationFailed(
            "The account details are not valid. " + " ".join(errs),
            details=[{"field": "/identity", "code": "INVALID_IDENTITY", "message": e} for e in errs],
        )
