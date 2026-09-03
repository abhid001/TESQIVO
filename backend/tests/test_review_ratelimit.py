"""Code-review fixes #7 (trusted-proxy client IP) and #14 (correlation id bound)."""

from types import SimpleNamespace

import pytest

from app.api.middleware import _CORR_RE, client_ip
from app.core.config import get_settings


def _req(peer: str, **headers):
    return SimpleNamespace(
        client=SimpleNamespace(host=peer),
        headers={k.lower().replace("_", "-"): v for k, v in headers.items()},
    )


@pytest.fixture
def proxies(monkeypatch):
    def _set(value: str):
        monkeypatch.setenv("TESQIVO_TRUSTED_PROXIES", value)
        get_settings.cache_clear()
    yield _set
    get_settings.cache_clear()


def test_forwarded_header_ignored_without_trusted_proxies(proxies):
    proxies("")
    assert client_ip(_req("10.0.0.9", cf_connecting_ip="9.9.9.9")) == "10.0.0.9"


def test_cf_connecting_ip_used_when_peer_is_a_trusted_proxy(proxies):
    proxies("10.0.0.0/8, 127.0.0.1")
    assert client_ip(_req("10.1.2.3", cf_connecting_ip="203.0.113.7")) == "203.0.113.7"
    assert client_ip(_req("127.0.0.1", x_forwarded_for="203.0.113.8, 10.1.1.1")) == "203.0.113.8"


def test_untrusted_peer_forwarded_header_is_ignored(proxies):
    proxies("10.0.0.0/8")
    assert client_ip(_req("8.8.8.8", x_forwarded_for="1.1.1.1")) == "8.8.8.8"


def test_wildcard_trusts_any_peer(proxies):
    proxies("*")
    assert client_ip(_req("8.8.8.8", cf_connecting_ip="203.0.113.9")) == "203.0.113.9"


@pytest.mark.parametrize("good", ["deadbeef" * 4, "abc-123_x.y", "A" * 64])
def test_correlation_id_accepts_sane_tokens(good):
    assert _CORR_RE.match(good)


@pytest.mark.parametrize("bad", ["", "a" * 65, "has space", "x\n", "'; DROP--"])
def test_correlation_id_rejects_junk(bad):
    assert not _CORR_RE.match(bad)
