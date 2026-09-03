"""TESQIVO - API-first test management platform (Phase 1)."""

import os

# The release build stamps the tag in via TESQIVO_VERSION; source checkouts and
# tests fall back to the value tracked here (kept in step with pyproject.toml).
__version__ = os.environ.get("TESQIVO_VERSION", "").strip() or "0.3.0"
