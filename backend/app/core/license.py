"""Enterprise license-key verification.

Lives in the Community codebase (so `/api/v1/version` can report the edition), but
never imports `cryptography` unless a license key AND a verification public key are
both present - which only happens in the Enterprise image. The Community image has
neither, so `current_license()` short-circuits to ``None``.

Key format:  b64url(payload_json) + "." + b64url(ed25519_signature_over_payload_b64)
Payload:     {"iss":"tesqivo","sub":<customer>,"features":[...],"iat":<unix>,
              "exp":<unix, 0 = never>,"seats":<int>}
"""

from __future__ import annotations

import base64
import importlib.util
import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings

log = logging.getLogger("tesqivo.license")


@dataclass(frozen=True)
class License:
    customer: str
    features: tuple[str, ...]
    issued_at: int
    expires_at: int  # unix seconds; 0 = perpetual
    seats: int

    @property
    def valid(self) -> bool:
        return self.expires_at == 0 or self.expires_at > int(time.time())

    def has(self, feature: str) -> bool:
        return self.valid and feature in self.features

    def summary(self) -> dict:
        return {
            "customer": self.customer,
            "features": list(self.features),
            "issued_at": self.issued_at or None,
            "expires_at": self.expires_at or None,
            "seats": self.seats or None,
            "valid": self.valid,
        }


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _read_key() -> str:
    s = get_settings()
    if s.license_key.strip():
        return s.license_key.strip()
    try:
        path = Path(s.license_key_file)
        if path.is_file():
            return path.read_text().strip()
    except OSError:
        pass
    return ""


@lru_cache(maxsize=1)
def current_license() -> License | None:
    raw = _read_key()
    pubkey = get_settings().license_pubkey.strip()
    if not raw or not pubkey:
        return None
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        payload_b64, sig_b64 = raw.split(".", 1)
        Ed25519PublicKey.from_public_bytes(_b64d(pubkey)).verify(_b64d(sig_b64), payload_b64.encode())
        data = json.loads(_b64d(payload_b64))
    except Exception as exc:  # noqa: BLE001 - any failure = no valid license
        log.warning("license key rejected (%s)", type(exc).__name__)
        return None

    lic = License(
        customer=str(data.get("sub", "")),
        features=tuple(str(f) for f in data.get("features", [])),
        issued_at=int(data.get("iat", 0)),
        expires_at=int(data.get("exp", 0)),
        seats=int(data.get("seats", 0)),
    )
    if not lic.valid:
        log.warning("license for %r expired", lic.customer)
        return None
    return lic


@lru_cache(maxsize=1)
def edition() -> str:
    """'enterprise' when the ee/ subtree is present in this build, else 'community'."""
    return "enterprise" if importlib.util.find_spec("app.ee") is not None else "community"


def licensed_features() -> list[str]:
    lic = current_license()
    return list(lic.features) if lic else []


def reset_cache_for_tests() -> None:
    current_license.cache_clear()
    edition.cache_clear()
