"""GET /api/v1/ee/license - current entitlements. PROPRIETARY - see ee/LICENSE."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentActor
from app.core.errors import Forbidden
from app.core.license import current_license, edition

router = APIRouter(prefix="/ee", tags=["enterprise"])


@router.get("/license")
async def license_status(actor: CurrentActor) -> dict:
    if not actor.is_system_admin:
        raise Forbidden("System administrator access required.")
    lic = current_license()
    return {
        "edition": edition(),
        "licensed": lic is not None,
        **(lic.summary() if lic else {"customer": None, "features": [], "valid": False}),
    }
