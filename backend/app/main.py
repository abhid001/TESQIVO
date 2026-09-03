"""FastAPI application factory. Serves /api/v1, the generated OpenAPI document, and
- when a build of the web UI is present - the single-page app at /."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import errors, middleware
from app.api.routers import access as access_router
from app.api.routers import auth as auth_router
from app.api.routers import execution as execution_router
from app.api.routers import feedback as feedback_router
from app.api.routers import notifications as notifications_router
from app.api.routers import planning as planning_router
from app.api.routers import projects as projects_router
from app.api.routers import reporting as reporting_router
from app.api.routers import repository as repository_router
from app.api.routers import scenarios as scenarios_router
from app.api.routers import system as system_router
from app.api.routers import traceability as traceability_router
from app.api.routers import users as users_router
from app.core.config import get_settings
from app.core.errors import ResourceNotFound

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(
        title="TESQIVO API",
        version=__version__,
        description="API-first test management platform - Phase 1",
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
        access_router.router,
        projects_router.router,
        repository_router.router,
        scenarios_router.router,
        planning_router.router,
        execution_router.router,
        traceability_router.router,
        reporting_router.router,
        feedback_router.router,
        notifications_router.router,
    ):
        app.include_router(r, prefix=API_PREFIX)

    _mount_web_ui(app)
    return app


def _mount_web_ui(app: FastAPI) -> None:
    """Serve the built SPA at / when TESQIVO_STATIC_DIR points at a real directory.

    Registered after the API routers, so /api/* and the docs routes always win; a
    client-side route (e.g. /p/DEMO/dashboard) falls through to index.html.
    """
    configured = get_settings().static_dir
    if not configured:
        return
    static = Path(configured)
    if not static.is_dir() or not (static / "index.html").is_file():
        return

    root = static.resolve()
    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index = root / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise ResourceNotFound("Not found.")
        target = (root / full_path).resolve()
        if full_path and target.is_file() and root in target.parents:
            return FileResponse(target)
        return FileResponse(index)


app = create_app()
