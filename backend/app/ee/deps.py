"""Enterprise feature gate. PROPRIETARY - see backend/app/ee/LICENSE."""

from __future__ import annotations

from app.core.errors import LicenseRequired
from app.core.license import current_license


def require_feature(name: str):
    """FastAPI dependency: 402 LICENSE_REQUIRED unless a valid license covers `name`."""

    async def _check() -> None:
        lic = current_license()
        if lic is None:
            raise LicenseRequired(
                f"This is an Enterprise feature. Add a valid TESQIVO_LICENSE_KEY that "
                f"includes '{name}'. See docs/enterprise.md."
            )
        if not lic.has(name):
            raise LicenseRequired(
                f"Your license does not include the '{name}' feature "
                f"(licensed: {', '.join(lic.features) or 'none'})."
            )

    return _check
