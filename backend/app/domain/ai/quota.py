"""Per-user AI request budget (PRS §17 "rate / cost controls").

In-process sliding window, like the API rate limiter in app/api/middleware.py:
enough for a single-node deployment. A Redis bucket is the multi-instance upgrade.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from app.core.config import get_settings
from app.core.errors import RateLimited

_WINDOW_SECONDS = 3600
_hits: dict[uuid.UUID, deque[float]] = defaultdict(deque)


def consume(user_id: uuid.UUID) -> None:
    """Count one AI request for `user_id`, or raise RateLimited when over budget."""
    limit = get_settings().ai_requests_per_user_hour
    now = time.monotonic()
    window = _hits[user_id]
    while window and now - window[0] > _WINDOW_SECONDS:
        window.popleft()
    if len(window) >= limit:
        raise RateLimited(
            f"You've reached the limit of {limit} AI requests per hour. Try again later."
        )
    window.append(now)


def reset_for_tests() -> None:
    _hits.clear()
