"""Password policy: length + upper + lower + digit + special, flexible on extras."""

import pytest

from app.core.security import password_policy_errors
from app.domain.auth import _generate_temp_password


def test_a_compliant_password_passes():
    assert password_policy_errors("Str0ng-Passphrase!") == []


def test_extra_letters_and_symbols_are_allowed():
    # Well past the minimum, lots of extra characters — still fine.
    assert password_policy_errors("A very l0ng pass-phrase with $ymbols & spaces!!") == []


@pytest.mark.parametrize(
    "pw, needle",
    [
        ("Sh0rt!", "at least 12 characters"),
        ("alllowercase1!", "upper-case"),
        ("ALLUPPERCASE1!", "lower-case"),
        ("NoDigitsHere!!", "digit"),
        ("NoSpecials1234", "special character"),
    ],
)
def test_each_missing_class_is_reported(pw, needle):
    errs = password_policy_errors(pw)
    assert any(needle in e for e in errs), errs


def test_multiple_failures_are_all_listed():
    errs = password_policy_errors("short")
    assert len(errs) >= 3  # too short, no upper, no digit, no special


def test_generated_temp_password_satisfies_the_policy():
    for _ in range(50):
        assert password_policy_errors(_generate_temp_password()) == []


@pytest.mark.asyncio
async def test_setup_endpoint_returns_the_specific_requirements(client):
    r = await client.post(
        "/api/v1/setup",
        json={"username": "admin", "email": "a@x.com", "display_name": "A", "password": "weakpass"},
        headers={"X-Bootstrap-Token": "test-bootstrap-token"},
    )
    assert r.status_code == 422
    err = r.json()["error"]
    assert "special character" in err["message"]
    messages = [d["message"] for d in err["details"]]
    assert any("special character" in m for m in messages)
    assert any("digit" in m for m in messages)
    assert all(d["code"] == "WEAK_PASSWORD" for d in err["details"])
