"""Ask TESQIVO help assistant (Community). Streams answers as Server-Sent Events."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import CurrentActor
from app.core.errors import DomainError
from app.core.license import current_license, edition
from app.domain.ai import assistant
from app.domain.ai.provider import ai_available

router = APIRouter(tags=["assistant"])
log = logging.getLogger("tesqivo.ai")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=20000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    project_id: uuid.UUID | None = None
    page_path: str | None = Field(default=None, max_length=500)


@router.get("/assistant/status")
async def assistant_status(actor: CurrentActor) -> dict[str, bool]:
    """Which AI features this user's UI should offer."""
    on = ai_available()
    lic = current_license()
    return {
        "assistant": on,
        "generator": on and edition() == "enterprise" and lic is not None and lic.has("ai"),
    }


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _events(chunks: AsyncIterator[str]) -> AsyncIterator[str]:
    try:
        async for text in chunks:
            yield _sse({"type": "delta", "text": text})
    except DomainError as exc:
        yield _sse({"type": "error", "code": exc.code, "message": exc.message})
        return
    except Exception:
        log.exception("assistant stream failed")
        yield _sse({"type": "error", "code": "INTERNAL_ERROR", "message": "Something went wrong. Try again."})
        return
    yield _sse({"type": "done"})


@router.post("/assistant/chat")
async def assistant_chat(body: ChatRequest, actor: CurrentActor) -> StreamingResponse:
    ctx = assistant.build_context(actor, project_id=body.project_id, page_path=body.page_path)
    chunks = assistant.start(actor, ctx, [m.model_dump() for m in body.messages])
    return StreamingResponse(
        _events(chunks),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
