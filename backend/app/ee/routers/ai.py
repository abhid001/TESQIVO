"""AI test-case generation (Enterprise). PROPRIETARY - see ee/LICENSE.

POST a generation request -> the worker runs it -> poll the generation -> review
each suggestion (edit / reject; accept = Test Manager) -> Draft test cases.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import CurrentActor, DbSession, RequestCtx
from app.ee.ai import generator
from app.ee.deps import require_feature
from app.models import AiGeneration, AiSuggestion, TestCase

router = APIRouter(prefix="/ee/ai", tags=["enterprise"], dependencies=[Depends(require_feature("ai"))])


class GenerateRequest(BaseModel):
    requirement_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    scenario_id: uuid.UUID | None = None
    story_text: str | None = Field(default=None, max_length=20000)
    focus: list[str] = Field(default_factory=lambda: ["happy_path", "negative", "boundary"], max_length=10)
    max_cases: int = 8
    instructions: str | None = Field(default=None, max_length=2000)


class EditSuggestion(BaseModel):
    expected_version: int
    payload: dict[str, Any]


class RejectSuggestion(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AcceptSuggestion(BaseModel):
    folder_id: uuid.UUID | None = None


def _gen_out(g: AiGeneration) -> dict:
    return {
        "id": str(g.id), "project_id": str(g.project_id), "status": g.status,
        "requested_by": str(g.requested_by),
        "sources": [{"type": r["type"], "id": r["id"], "key": r["key"], "title": r["title"]} for r in g.source_refs],
        "story_text": g.story_text, "options": g.options, "model": g.model,
        "prompt_version": g.prompt_version, "input_tokens": g.input_tokens, "output_tokens": g.output_tokens,
        "assumptions": g.assumptions, "open_questions": g.open_questions, "error_summary": g.error_summary,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "finished_at": g.finished_at.isoformat() if g.finished_at else None,
    }


def _sugg_out(s: AiSuggestion, tc_key: str | None = None) -> dict:
    return {
        "id": str(s.id), "generation_id": str(s.generation_id), "ordinal": s.ordinal,
        "payload": s.payload, "status": s.status, "edited": s.edited,
        "possible_duplicate_of": s.possible_duplicate_of, "reject_reason": s.reject_reason,
        "test_case_id": str(s.test_case_id) if s.test_case_id else None, "test_case_key": tc_key,
        "version": s.version,
    }


@router.get("/options")
async def generation_options(actor: CurrentActor) -> dict:
    from app.core.config import get_settings

    return {
        "focus_areas": [{"value": k, "label": v} for k, v in generator.FOCUS_AREAS.items()],
        "max_cases": get_settings().ai_max_cases_per_generation,
        "max_requirements": generator.MAX_REQUIREMENTS,
    }


@router.post("/projects/{project_id}/generations", status_code=202)
async def create_generation(
    project_id: uuid.UUID, body: GenerateRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> dict:
    g = await generator.request_generation(
        db, actor, ctx, project_id=project_id, requirement_ids=body.requirement_ids,
        scenario_id=body.scenario_id, story_text=body.story_text, focus=body.focus,
        max_cases=body.max_cases, instructions=body.instructions,
    )
    return _gen_out(g)


@router.get("/projects/{project_id}/generations")
async def list_generations(project_id: uuid.UUID, actor: CurrentActor, db: DbSession) -> list[dict]:
    return [_gen_out(g) for g in await generator.list_generations(db, actor, project_id)]


@router.get("/generations/{generation_id}")
async def get_generation(generation_id: uuid.UUID, actor: CurrentActor, db: DbSession) -> dict:
    g = await generator.get_generation(db, actor, generation_id)
    suggestions = await generator.list_suggestions(db, g.id)
    keys: dict[uuid.UUID, str] = {}
    for s in suggestions:
        if s.test_case_id:
            tc = await db.get(TestCase, s.test_case_id)
            if tc:
                keys[s.test_case_id] = tc.key
    return {**_gen_out(g), "suggestions": [_sugg_out(s, keys.get(s.test_case_id)) for s in suggestions]}


@router.patch("/suggestions/{suggestion_id}")
async def edit_suggestion(
    suggestion_id: uuid.UUID, body: EditSuggestion, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> dict:
    s = await generator.edit_suggestion(
        db, actor, ctx, suggestion_id=suggestion_id, payload=body.payload, expected_version=body.expected_version
    )
    return _sugg_out(s)


@router.post("/suggestions/{suggestion_id}/reject")
async def reject_suggestion(
    suggestion_id: uuid.UUID, body: RejectSuggestion, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> dict:
    return _sugg_out(await generator.reject_suggestion(db, actor, ctx, suggestion_id=suggestion_id, reason=body.reason))


@router.post("/suggestions/{suggestion_id}/accept")
async def accept_suggestion(
    suggestion_id: uuid.UUID, body: AcceptSuggestion, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> dict:
    s = await generator.accept_suggestion(db, actor, ctx, suggestion_id=suggestion_id, folder_id=body.folder_id)
    tc = await db.get(TestCase, s.test_case_id) if s.test_case_id else None
    return _sugg_out(s, tc.key if tc else None)
