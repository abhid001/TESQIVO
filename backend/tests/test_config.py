"""Session-secret resolution: explicit env > persisted file > generated."""

import pytest

from app.core.config import Settings

BASE = dict(
    db_url="postgresql+asyncpg://u:p@h/db",
    redis_url="redis://h:6379/0",
    public_url="http://x",
)


def test_explicit_secret_key_is_used_and_no_file_written(tmp_path):
    sk = "k" * 40
    s = Settings(**BASE, secret_key=sk, secret_key_file=str(tmp_path / "sk"))
    assert s.secret_key == sk
    assert not (tmp_path / "sk").exists()


def test_short_explicit_secret_key_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        Settings(**BASE, secret_key="too-short", secret_key_file=str(tmp_path / "sk"))


def test_secret_key_is_generated_persisted_and_reused(tmp_path):
    path = tmp_path / "nested" / "secret_key"
    first = Settings(**BASE, secret_key="", secret_key_file=str(path))
    assert path.is_file()
    assert len(first.secret_key.encode()) >= 32
    assert oct(path.stat().st_mode)[-3:] == "600"

    second = Settings(**BASE, secret_key="", secret_key_file=str(path))
    assert second.secret_key == first.secret_key


def test_unresolvable_secret_key_fails_fast(tmp_path):
    with pytest.raises(ValueError):
        Settings(**BASE, secret_key="", secret_key_file="/dev/null/secret_key")
