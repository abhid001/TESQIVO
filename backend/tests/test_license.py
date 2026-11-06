"""Enterprise license-key verification (app/core/license.py)."""

import time

import pytest

from app.core import license as lic_mod
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear():
    lic_mod.reset_cache_for_tests()
    yield
    lic_mod.reset_cache_for_tests()


def test_no_key_or_no_pubkey_is_no_license(issue_license):
    # issue_license installs a pubkey but we never mint a key
    assert lic_mod.current_license() is None
    assert lic_mod.licensed_features() == []


def test_valid_key_verifies(issue_license):
    issue_license(features=["ai", "sso"], seats=10, sub="Acme Inc")
    lic = lic_mod.current_license()
    assert lic is not None
    assert lic.customer == "Acme Inc"
    assert lic.has("ai") and lic.has("sso")
    assert not lic.has("other")
    assert lic.seats == 10
    assert lic.valid


def test_tampered_key_is_rejected(issue_license):
    issue_license(features=["ai"], tamper=True)
    assert lic_mod.current_license() is None


def test_expired_key_is_rejected(issue_license):
    issue_license(features=["ai"], exp_delta=-5)
    assert lic_mod.current_license() is None


def test_perpetual_key(issue_license):
    issue_license(features=["ai"], exp_delta=None)
    lic = lic_mod.current_license()
    assert lic and lic.valid and lic.expires_at == 0


def test_wrong_pubkey_is_rejected(issue_license, monkeypatch):
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    issue_license(features=["ai"])
    other = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    monkeypatch.setattr(
        get_settings(), "license_pubkey", base64.urlsafe_b64encode(other).decode().rstrip("=")
    )
    lic_mod.reset_cache_for_tests()
    assert lic_mod.current_license() is None


def test_edition_is_enterprise_in_this_tree():
    lic_mod.edition.cache_clear()
    assert lic_mod.edition() == "enterprise"  # app/ee/ is present in the repo


def test_issue_script_roundtrips(tmp_path, ee_keypair):
    import base64
    import json
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    priv_b64, _ = ee_keypair
    priv_file = tmp_path / "priv.b64"
    priv_file.write_text(priv_b64)
    out = subprocess.check_output(
        [sys.executable, str(repo / "scripts/license/issue.py"), "--private-key", f"@{priv_file}",
         "--customer", "T", "--features", "ai", "--days", "1"],
        text=True,
    ).strip()
    payload_b64 = out.split(".", 1)[0]
    data = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
    assert data["features"] == ["ai"] and data["exp"] > time.time()
