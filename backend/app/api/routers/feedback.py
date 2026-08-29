"""Product feedback: submit (any user) + triage / export (system admin)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.api.deps import CurrentActor, DbSession, RequestCtx
from app.domain import feedback
from app.models import Feedback, Project, User

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    category: str = "other"
    project_id: str | None = None
    page_path: str | None = None


class FeedbackUpdate(BaseModel):
    status: str | None = None
    admin_note: str | None = None


class FeedbackOut(BaseModel):
    id: str
    category: str
    message: str
    page_path: str | None
    status: str
    admin_note: str | None
    created_at: str
    resolved_at: str | None
    user_username: str
    user_email: str
    user_display_name: str
    project_key: str | None
    project_id: str | None


def _out(fb: Feedback, u: User, p: Project | None) -> FeedbackOut:
    return FeedbackOut(
        id=str(fb.id),
        category=fb.category,
        message=fb.message,
        page_path=fb.page_path,
        status=fb.status,
        admin_note=fb.admin_note,
        created_at=fb.created_at.isoformat(),
        resolved_at=fb.resolved_at.isoformat() if fb.resolved_at else None,
        user_username=u.username if u else "",
        user_email=u.email if u else "",
        user_display_name=u.display_name if u else "",
        project_key=p.key if p else None,
        project_id=str(p.id) if p else None,
    )


@router.post("", status_code=201)
async def submit_feedback(
    body: FeedbackIn, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> dict:
    fb = await feedback.submit_feedback(
        db,
        actor,
        ctx,
        message=body.message,
        category=body.category,
        project_id=uuid.UUID(body.project_id) if body.project_id else None,
        page_path=body.page_path,
    )
    return {"id": str(fb.id), "status": fb.status}


@router.get("", response_model=list[FeedbackOut])
async def list_feedback(
    actor: CurrentActor, db: DbSession, status: str | None = None
) -> list[FeedbackOut]:
    rows = await feedback.list_feedback(db, actor, status=status)
    return [_out(fb, u, p) for (fb, u, p) in rows]


@router.get("/export")
async def export_feedback(
    actor: CurrentActor, db: DbSession, format: str = "csv", status: str | None = None
) -> PlainTextResponse:
    rows = await feedback.list_feedback(db, actor, status=status)
    if format == "txt":
        return PlainTextResponse(
            feedback.feedback_text(rows),
            headers={"Content-Disposition": 'attachment; filename="feedback.txt"'},
        )
    return PlainTextResponse(
        feedback.feedback_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="feedback.csv"'},
    )


@router.patch("/{feedback_id}", response_model=FeedbackOut)
async def update_feedback(
    feedback_id: str,
    body: FeedbackUpdate,
    actor: CurrentActor,
    db: DbSession,
    ctx: RequestCtx,
) -> FeedbackOut:
    fb = await feedback.update_feedback(
        db,
        actor,
        ctx,
        feedback_id=uuid.UUID(feedback_id),
        status=body.status,
        admin_note=body.admin_note,
    )
    u = await db.get(User, fb.user_id)
    p = await db.get(Project, fb.project_id) if fb.project_id else None
    return _out(fb, u, p)
