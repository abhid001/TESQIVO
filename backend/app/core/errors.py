"""Domain error hierarchy and the PRS §13 error envelope.

Domain services raise these transport-agnostic errors. The API error handler maps
them to the stable JSON envelope. Errors never expose stack traces, SQL, secrets,
or inaccessible-resource details.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class. `code` is a stable string from the PRS §13 catalogue."""

    code: str = "INTERNAL_ERROR"
    status: int = 500
    retryable: bool = False

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[dict[str, Any]] | None = None,
        code: str | None = None,
        status: int | None = None,
    ) -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or "An error occurred."
        self.details = details or []
        if code:
            self.code = code
        if status:
            self.status = status


class AuthenticationRequired(DomainError):
    code = "AUTHENTICATION_REQUIRED"
    status = 401


class InvalidCredentials(DomainError):
    code = "INVALID_CREDENTIALS"
    status = 401


class Forbidden(DomainError):
    code = "FORBIDDEN"
    status = 403


class PasswordChangeRequired(DomainError):
    """The session is valid but the account must set a new password before it can
    do anything else. Only /auth/me, /auth/password and logout are permitted."""

    code = "PASSWORD_CHANGE_REQUIRED"
    status = 403


class ResourceNotFound(DomainError):
    code = "RESOURCE_NOT_FOUND"
    status = 404


class VersionConflict(DomainError):
    code = "VERSION_CONFLICT"
    status = 409


class StateTransitionNotAllowed(DomainError):
    code = "STATE_TRANSITION_NOT_ALLOWED"
    status = 409


class DuplicateResource(DomainError):
    code = "DUPLICATE_RESOURCE"
    status = 409


class IdempotencyKeyReuse(DomainError):
    code = "IDEMPOTENCY_KEY_REUSED"
    status = 409


class ValidationFailed(DomainError):
    code = "VALIDATION_ERROR"
    status = 422


class FileTooLarge(DomainError):
    code = "FILE_TOO_LARGE"
    status = 413


class UnsupportedMediaType(DomainError):
    code = "UNSUPPORTED_MEDIA_TYPE"
    status = 415


class RateLimited(DomainError):
    code = "RATE_LIMITED"
    status = 429
    retryable = True


class DependencyUnavailable(DomainError):
    code = "DEPENDENCY_UNAVAILABLE"
    status = 503
    retryable = True


class SetupAlreadyCompleted(DomainError):
    code = "SETUP_ALREADY_COMPLETED"
    status = 409


def error_envelope(err: DomainError, correlation_id: str) -> dict[str, Any]:
    return {
        "error": {
            "code": err.code,
            "message": err.message,
            "status": err.status,
            "correlation_id": correlation_id,
            "details": err.details,
            "retryable": err.retryable,
        }
    }
