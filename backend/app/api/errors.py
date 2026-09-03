"""Maps exceptions to the PRS §13 error envelope. No stack traces / SQL / secrets."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.errors import DomainError, ValidationFailed, error_envelope

log = logging.getLogger("tesqivo.error")


def _corr(request: Request) -> str:
    return getattr(request.state, "correlation_id", "unknown")


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    if exc.status >= 500:
        log.error("domain error %s: %s", exc.code, exc.message, extra={"correlation_id": _corr(request)})
    return JSONResponse(status_code=exc.status, content=error_envelope(exc, _corr(request)))


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "field": "/" + "/".join(str(p) for p in err["loc"][1:]),
            "code": err["type"].upper(),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    envelope = error_envelope(
        ValidationFailed("One or more fields are invalid.", details=details), _corr(request)
    )
    return JSONResponse(status_code=422, content=envelope)


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    log.warning("integrity error", extra={"correlation_id": _corr(request)})
    env = error_envelope(
        DomainError("The request conflicts with existing data.", code="DUPLICATE_RESOURCE", status=409),
        _corr(request),
    )
    return JSONResponse(status_code=409, content=env)


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    # A bare ValueError out of a router almost always means malformed input that
    # was fed to a converter - most commonly uuid.UUID("...") on a bad path
    # segment (finding #6). Return the structured 422 rather than a 500.
    env = error_envelope(
        ValidationFailed("The request contains an invalid identifier or value."),
        _corr(request),
    )
    return JSONResponse(status_code=422, content=env)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error", extra={"correlation_id": _corr(request)})
    env = error_envelope(DomainError("An internal error occurred."), _corr(request))
    return JSONResponse(status_code=500, content=env)


def install(app) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
