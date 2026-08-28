"""FastAPI application factory. Serves /api/v1 and the generated OpenAPI document."""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.api import errors, middleware
from app.api.routers import auth as auth_router
from app.api.routers import execution as execution_router
from app.api.routers import planning as planning_router
from app.api.routers import projects as projects_router
from app.api.routers import reporting as reporting_router
from app.api.routers import repository as repository_router
from app.api.routers import scenarios as scenarios_router
from app.api.routers import system as system_router
from app.api.routers import traceability as traceability_router
from app.api.routers import users as users_router

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(
        title="TESQIVO API",
        version=__version__,
        description="Open-source API-first test management platform - Phase 1",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
    )
    errors.install(app)
    middleware.install(app)

    for r in (
        system_router.router,
        auth_router.router,
        users_router.router,
        projects_router.router,
        repository_router.router,
        scenarios_router.router,
        planning_router.router,
        execution_router.router,
        traceability_router.router,
        reporting_router.router,
    ):
        app.include_router(r, prefix=API_PREFIX)

    return app


app = create_app()
