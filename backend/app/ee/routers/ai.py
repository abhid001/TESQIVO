"""AI-assisted test authoring (Enterprise). PROPRIETARY - see ee/LICENSE.

STUB in this release: the endpoint proves the licensed-feature path end to end.
The real LLM provider wiring (TESQIVO_LLM_PROVIDER / key, prompt, httpx call,
streaming) lands in a later release.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import CurrentActor
from app.ee.deps import require_feature

router = APIRouter(prefix="/ee/ai", tags=["enterprise"])


class DraftRequest(BaseModel):
    requirement_text: str = Field(min_length=1, max_length=8000)


@router.post("/draft-test-case", dependencies=[Depends(require_feature("ai"))])
async def draft_test_case(body: DraftRequest, actor: CurrentActor) -> dict:
    return {
        "status": "stub",
        "echo": body.requirement_text,
        "note": "AI test authoring is licensed and enabled; LLM generation ships in a later release.",
    }
