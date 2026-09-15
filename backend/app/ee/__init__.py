"""TESQIVO Enterprise edition.

PROPRIETARY - see backend/app/ee/LICENSE. Not covered by the repository-root AGPL.

Present only in the `tesqivo-enterprise` image. `app.main.create_app()` calls
``register_ee(app, prefix)`` when this package is importable; the Community image
does not ship it, so the /api/v1/ee/* routes simply do not exist there.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

log = logging.getLogger("tesqivo.ee")


def register_ee(app: FastAPI, *, prefix: str) -> None:
    from app.core.license import current_license, edition
    from app.ee.routers import ai
    from app.ee.routers import license as license_router

    app.include_router(license_router.router, prefix=prefix)
    app.include_router(ai.router, prefix=prefix)

    lic = current_license()
    log.info(
        "TESQIVO %s edition; license=%s",
        edition(),
        f"{lic.customer} features={list(lic.features)}" if lic else "none",
    )
