"""Test repository, versioning, workflow (increments 4-5)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentActor, DbSession, RequestCtx
from app.core.errors import ResourceNotFound
from app.domain import authz
from app.domain.test_case import service as tc_service
from app.domain.test_case.service import StepInput
from app.models import TestCase, TestCaseVersion, TestFolder, TestStep

router = APIRouter(tags=["repository"])


class StepModel(BaseModel):
    action: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    is_required: bool = True


class CreateTestCase(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    preconditions: str | None = None
    folder_id: str | None = None
    steps: list[StepModel] = Field(default_factory=list)
    automation_status: str = "candidate"


class UpdateTestCase(BaseModel):
    expected_version: int
    title: str | None = None
    description: str | None = None
    preconditions: str | None = None
    steps: list[StepModel] | None = None
    folder_id: str | None = None
    change_summary: str | None = None


class TransitionRequest(BaseModel):
    to: str
    expected_version: int


class VersionOut(BaseModel):
    id: str
    version_number: int
    status: str
    title: str
    description: str | None
    preconditions: str | None
    change_summary: str | None
    steps: list[StepModel]


class TestCaseOut(BaseModel):
    id: str
    key: str
    project_id: str
    folder_id: str | None
    title: str
    lifecycle_state: str
    current_version_id: str | None
    approved_version_id: str | None
    has_draft_changes: bool
    automation_status: str
    version: int


class FolderOut(BaseModel):
    id: str
    name: str
    parent_id: str | None
    path: str


def _tc_out(tc: TestCase) -> TestCaseOut:
    return TestCaseOut(
        id=str(tc.id),
        key=tc.key,
        project_id=str(tc.project_id),
        folder_id=str(tc.folder_id) if tc.folder_id else None,
        title=tc.title,
        lifecycle_state=tc.lifecycle_state,
        current_version_id=str(tc.current_version_id) if tc.current_version_id else None,
        approved_version_id=str(tc.approved_version_id) if tc.approved_version_id else None,
        has_draft_changes=tc.current_version_id != tc.approved_version_id
        and tc.approved_version_id is not None,
        automation_status=tc.automation_status,
        version=tc.version,
    )


def _steps(model_steps: list[StepModel] | None) -> list[StepInput] | None:
    if model_steps is None:
        return None
    return [StepInput(s.action, s.expected_result, s.is_required) for s in model_steps]


@router.post("/projects/{project_id}/folders", response_model=FolderOut, status_code=201)
async def create_folder(
    project_id: str, body: dict, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> FolderOut:
    f = await tc_service.create_folder(
        db, actor, ctx, project_id=uuid.UUID(project_id),
        name=body["name"], parent_id=uuid.UUID(body["parent_id"]) if body.get("parent_id") else None,
    )
    return FolderOut(id=str(f.id), name=f.name, parent_id=str(f.parent_id) if f.parent_id else None, path=f.path)


@router.get("/projects/{project_id}/folders", response_model=list[FolderOut])
async def list_folders(project_id: str, actor: CurrentActor, db: DbSession) -> list[FolderOut]:
    pid = uuid.UUID(project_id)
    authz.require_member(actor, pid)
    rows = (await db.scalars(select(TestFolder).where(TestFolder.project_id == pid))).all()
    return [
        FolderOut(id=str(f.id), name=f.name, parent_id=str(f.parent_id) if f.parent_id else None, path=f.path)
        for f in rows
    ]


@router.post("/projects/{project_id}/test-cases", response_model=TestCaseOut, status_code=201)
async def create_test_case(
    project_id: str, body: CreateTestCase, actor: CurrentActor, db: DbSession, ctx: RequestCtx,
    response: Response,
) -> TestCaseOut:
    tc = await tc_service.create_test_case(
        db, actor, ctx, project_id=uuid.UUID(project_id), title=body.title,
        description=body.description, preconditions=body.preconditions,
        folder_id=uuid.UUID(body.folder_id) if body.folder_id else None,
        steps=_steps(body.steps), automation_status=body.automation_status,
    )
    response.headers["Location"] = f"/api/v1/test-cases/{tc.id}"
    return _tc_out(tc)


@router.get("/projects/{project_id}/test-cases")
async def list_test_cases(
    project_id: str, actor: CurrentActor, db: DbSession,
    folder_id: str | None = None, state: str | None = None, q: str | None = None,
    sort: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
) -> dict:
    rows, total = await tc_service.list_test_cases(
        db, actor, project_id=uuid.UUID(project_id),
        folder_id=uuid.UUID(folder_id) if folder_id else None,
        state=state, query=q, sort=sort, page=page, page_size=page_size,
    )
    pages = max(1, (total + page_size - 1) // page_size)
    return {
        "items": [_tc_out(tc).model_dump() for tc in rows],
        "page": page, "page_size": page_size, "total": total, "pages": pages,
        "links": {"self": f"/api/v1/projects/{project_id}/test-cases?page={page}"},
    }


@router.get("/test-cases/{tc_id}", response_model=TestCaseOut)
async def get_test_case(tc_id: str, actor: CurrentActor, db: DbSession) -> TestCaseOut:
    tc = await tc_service.get_test_case(db, actor, uuid.UUID(tc_id))
    return _tc_out(tc)


@router.get("/test-cases/{tc_id}/versions", response_model=list[VersionOut])
async def list_versions(tc_id: str, actor: CurrentActor, db: DbSession) -> list[VersionOut]:
    tc = await tc_service.get_test_case(db, actor, uuid.UUID(tc_id))
    versions = (
        await db.scalars(
            select(TestCaseVersion)
            .where(TestCaseVersion.test_case_id == tc.id)
            .order_by(TestCaseVersion.version_number)
        )
    ).all()
    out: list[VersionOut] = []
    for v in versions:
        steps = (
            await db.scalars(
                select(TestStep).where(TestStep.version_id == v.id).order_by(TestStep.order_index)
            )
        ).all()
        out.append(
            VersionOut(
                id=str(v.id), version_number=v.version_number, status=v.status, title=v.title,
                description=v.description, preconditions=v.preconditions, change_summary=v.change_summary,
                steps=[StepModel(action=s.action, expected_result=s.expected_result, is_required=s.is_required) for s in steps],
            )
        )
    return out


@router.get("/test-case-versions/{version_id}", response_model=VersionOut)
async def get_version(version_id: str, actor: CurrentActor, db: DbSession) -> VersionOut:
    v = await db.get(TestCaseVersion, uuid.UUID(version_id))
    if v is None:
        raise ResourceNotFound("Version not found.")
    tc = await db.get(TestCase, v.test_case_id)
    authz.require_member(actor, tc.project_id)
    steps = (
        await db.scalars(
            select(TestStep).where(TestStep.version_id == v.id).order_by(TestStep.order_index)
        )
    ).all()
    return VersionOut(
        id=str(v.id), version_number=v.version_number, status=v.status, title=v.title,
        description=v.description, preconditions=v.preconditions, change_summary=v.change_summary,
        steps=[StepModel(action=s.action, expected_result=s.expected_result, is_required=s.is_required) for s in steps],
    )


@router.patch("/test-cases/{tc_id}", response_model=TestCaseOut)
async def update_test_case(
    tc_id: str, body: UpdateTestCase, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> TestCaseOut:
    kwargs: dict = dict(
        tc_id=uuid.UUID(tc_id), expected_version=body.expected_version, title=body.title,
        description=body.description, preconditions=body.preconditions, steps=_steps(body.steps),
        change_summary=body.change_summary,
    )
    if body.folder_id is not None:
        kwargs["folder_id"] = uuid.UUID(body.folder_id)
    tc = await tc_service.update_test_case(db, actor, ctx, **kwargs)
    return _tc_out(tc)


@router.post("/test-cases/{tc_id}/version-transitions", response_model=TestCaseOut)
async def transition_version(
    tc_id: str, body: TransitionRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> TestCaseOut:
    tc = await tc_service.transition_version(
        db, actor, ctx, tc_id=uuid.UUID(tc_id), to_status=body.to, expected_version=body.expected_version
    )
    return _tc_out(tc)


@router.post("/test-cases/{tc_id}/lifecycle-transitions", response_model=TestCaseOut)
async def transition_lifecycle(
    tc_id: str, body: TransitionRequest, actor: CurrentActor, db: DbSession, ctx: RequestCtx
) -> TestCaseOut:
    tc = await tc_service.transition_lifecycle(
        db, actor, ctx, tc_id=uuid.UUID(tc_id), to_state=body.to, expected_version=body.expected_version
    )
    return _tc_out(tc)
