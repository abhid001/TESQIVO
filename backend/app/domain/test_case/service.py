"""Test repository, versioning, and workflow (increments 4-5).

Decision D-016: a controlled edit to an Approved/Active test case forks a new Draft
version but the logical `lifecycle_state` stays Approved/Active. `approved_version_id`
keeps pointing at the last approved version (still used by existing cycles). The GUI
shows a "draft changes pending review" indicator derived from
``current_version_id != approved_version_id``. This keeps design-coverage stable while
a new version is in progress, consistent with PRS §6.2.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import Actor, Ctx
from app.core.errors import (
    ResourceNotFound,
    StateTransitionNotAllowed,
    ValidationFailed,
)
from app.domain import audit, authz
from app.domain.concurrency import check_version
from app.domain.keys import next_key
from app.domain.test_case.controlled_fields import touches_controlled_content
from app.models import Project, TestCase, TestCaseVersion, TestFolder, TestStep

LIFECYCLE = ("draft", "in_review", "approved", "active", "deprecated", "archived")


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class StepInput:
    action: str
    expected_result: str
    is_required: bool = True


async def _project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    p = await session.get(Project, project_id)
    if p is None:
        raise ResourceNotFound("Project not found.")
    return p


async def get_test_case(session: AsyncSession, actor: Actor, tc_id: uuid.UUID) -> TestCase:
    tc = await session.get(TestCase, tc_id)
    if tc is None:
        raise ResourceNotFound("Test case not found.")
    authz.require_member(actor, tc.project_id)
    return tc


# --------------------------------------------------------------------------- folders


async def create_folder(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    project_id: uuid.UUID,
    name: str,
    parent_id: uuid.UUID | None = None,
) -> TestFolder:
    await _project(session, project_id)
    authz.authorize(actor, "folder.manage", project_id=project_id)
    path = "/"
    if parent_id is not None:
        parent = await session.get(TestFolder, parent_id)
        if parent is None or parent.project_id != project_id:
            raise ValidationFailed("Parent folder not found in this project.")
        path = f"{parent.path.rstrip('/')}/{parent.name}"
    folder = TestFolder(project_id=project_id, parent_id=parent_id, name=name.strip(), path=path)
    session.add(folder)
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="test_folder", action="folder.created",
        entity_id=folder.id, project_id=project_id, after={"name": folder.name},
    )
    await session.commit()
    return folder


# --------------------------------------------------------------------------- create


async def create_test_case(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    project_id: uuid.UUID,
    title: str,
    description: str | None = None,
    preconditions: str | None = None,
    folder_id: uuid.UUID | None = None,
    scenario_id: uuid.UUID | None = None,
    steps: list[StepInput] | None = None,
    automation_status: str = "candidate",
) -> TestCase:
    await _project(session, project_id)
    authz.authorize(actor, "test_case.create", project_id=project_id)
    if not title.strip():
        raise ValidationFailed("Title is required.", details=[{"field": "/title", "code": "REQUIRED", "message": "Title is required."}])
    if folder_id is not None:
        folder = await session.get(TestFolder, folder_id)
        if folder is None or folder.project_id != project_id:
            raise ValidationFailed("Folder not found in this project.")
    if scenario_id is not None:
        from app.models import Scenario

        sc = await session.get(Scenario, scenario_id)
        if sc is None or sc.project_id != project_id:
            raise ValidationFailed("Scenario not found in this project.")

    key = await next_key(session, project_id, "test_case")
    tc = TestCase(
        project_id=project_id,
        key=key,
        folder_id=folder_id,
        scenario_id=scenario_id,
        title=title.strip(),
        lifecycle_state="draft",
        automation_status=automation_status,
        is_eligible_for_automation=automation_status != "not_applicable",
        created_by=actor.id,
    )
    session.add(tc)
    await session.flush()

    version = TestCaseVersion(
        test_case_id=tc.id,
        version_number=1,
        status="draft",
        title=title.strip(),
        description=description,
        preconditions=preconditions,
        author_id=actor.id,
        change_summary="Initial draft",
    )
    session.add(version)
    await session.flush()
    for i, s in enumerate(steps or [], start=1):
        session.add(
            TestStep(
                version_id=version.id,
                order_index=i,
                action=s.action.strip(),
                expected_result=s.expected_result.strip(),
                is_required=s.is_required,
            )
        )
    tc.current_version_id = version.id
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="test_case", action="test_case.created",
        entity_id=tc.id, entity_key=tc.key, project_id=project_id,
        after={"title": tc.title, "version": 1},
    )
    await session.commit()
    return tc


# --------------------------------------------------------------------------- edit


async def update_test_case(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    tc_id: uuid.UUID,
    expected_version: int,
    title: str | None = None,
    description: str | None = None,
    preconditions: str | None = None,
    steps: list[StepInput] | None = None,
    folder_id: uuid.UUID | None = ...,  # type: ignore[assignment]
    change_summary: str | None = None,
) -> TestCase:
    tc = await get_test_case(session, actor, tc_id)
    authz.authorize(actor, "test_case.edit", project_id=tc.project_id, resource=tc)
    check_version(tc.version, expected_version, entity="test case")
    if tc.lifecycle_state == "archived":
        raise StateTransitionNotAllowed("Archived test cases cannot be edited; restore first.")

    current = await session.get(TestCaseVersion, tc.current_version_id)
    assert current is not None
    current_steps = list(
        await session.scalars(
            select(TestStep).where(TestStep.version_id == current.id).order_by(TestStep.order_index)
        )
    )

    changed_version_fields: set[str] = set()
    new_title = current.title if title is None else title.strip()
    new_desc = current.description if description is None else description
    new_pre = current.preconditions if preconditions is None else preconditions
    if title is not None and new_title != current.title:
        changed_version_fields.add("title")
    if description is not None and new_desc != current.description:
        changed_version_fields.add("description")
    if preconditions is not None and new_pre != current.preconditions:
        changed_version_fields.add("preconditions")

    steps_changed = steps is not None and _steps_differ(current_steps, steps)
    controlled = touches_controlled_content(
        changed_version_fields=changed_version_fields, steps_changed=steps_changed
    )

    # non-controlled: folder move
    if folder_id is not ... and folder_id != tc.folder_id:
        if folder_id is not None:
            f = await session.get(TestFolder, folder_id)
            if f is None or f.project_id != tc.project_id:
                raise ValidationFailed("Folder not found in this project.")
        before_folder = str(tc.folder_id) if tc.folder_id else None
        tc.folder_id = folder_id
        audit.record(
            session, actor=actor, ctx=ctx, entity_type="test_case", action="test_case.moved",
            entity_id=tc.id, entity_key=tc.key, project_id=tc.project_id,
            before={"folder_id": before_folder}, after={"folder_id": str(folder_id) if folder_id else None},
        )

    if not controlled:
        if changed_version_fields or steps_changed:
            pass  # already equal; nothing to do
        tc.version += 1
        await session.commit()
        return tc

    if current.status == "draft":
        target = current  # mutate the working draft in place
        action = "test_case.draft_updated"
    else:
        target = TestCaseVersion(
            test_case_id=tc.id,
            version_number=await _next_version_number(session, tc.id),
            status="draft",
            title=new_title,
            description=new_desc,
            preconditions=new_pre,
            author_id=actor.id,
            change_summary=change_summary or "Controlled edit",
        )
        session.add(target)
        await session.flush()
        action = "test_case.version_forked"

    target.title = new_title
    target.description = new_desc
    target.preconditions = new_pre
    if change_summary:
        target.change_summary = change_summary

    if steps is not None:
        await session.execute(TestStep.__table__.delete().where(TestStep.version_id == target.id))
        for i, s in enumerate(steps, start=1):
            session.add(
                TestStep(
                    version_id=target.id, order_index=i, action=s.action.strip(),
                    expected_result=s.expected_result.strip(), is_required=s.is_required,
                )
            )
    elif target.id != current.id:
        # forked: copy the current steps forward
        for st in current_steps:
            session.add(
                TestStep(
                    version_id=target.id, order_index=st.order_index, action=st.action,
                    expected_result=st.expected_result, is_required=st.is_required,
                )
            )

    tc.current_version_id = target.id
    tc.title = new_title
    tc.version += 1
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="test_case", action=action,
        entity_id=tc.id, entity_key=tc.key, project_id=tc.project_id,
        after={"version": target.version_number, "fields": sorted(changed_version_fields)},
    )
    await session.commit()
    return tc


# --------------------------------------------------------------------------- workflow


_VERSION_TRANSITIONS = {
    ("draft", "in_review"): "submit_for_review",
    ("in_review", "draft"): "request_changes",
    ("in_review", "approved"): "approve",
}


async def transition_version(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    tc_id: uuid.UUID,
    to_status: str,
    expected_version: int,
) -> TestCase:
    tc = await get_test_case(session, actor, tc_id)
    authz.authorize(actor, "version.transition", project_id=tc.project_id)
    check_version(tc.version, expected_version, entity="test case")
    current = await session.get(TestCaseVersion, tc.current_version_id)
    assert current is not None
    key = (current.status, to_status)
    if key not in _VERSION_TRANSITIONS:
        raise StateTransitionNotAllowed(
            f"Cannot move version from '{current.status}' to '{to_status}'."
        )
    if to_status == "in_review":
        current_steps = list(
            await session.scalars(
                select(TestStep).where(TestStep.version_id == current.id)
            )
        )
        _assert_reviewable(current, current_steps)

    current.status = to_status
    if to_status == "in_review":
        tc.lifecycle_state = "in_review"
    elif to_status == "draft":
        tc.lifecycle_state = "draft"
    elif to_status == "approved":
        # supersede the previous approved version
        if tc.approved_version_id and tc.approved_version_id != current.id:
            prev = await session.get(TestCaseVersion, tc.approved_version_id)
            if prev is not None:
                prev.status = "superseded"
        tc.approved_version_id = current.id
        current.content_locked = True
        tc.lifecycle_state = "approved"

    tc.version += 1
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="test_case_version",
        action=f"version.{_VERSION_TRANSITIONS[key]}", entity_id=current.id,
        entity_key=tc.key, project_id=tc.project_id, after={"status": to_status},
    )
    await session.commit()
    return tc


_LOGICAL_TRANSITIONS = {
    ("approved", "active"): "activate",
    ("active", "deprecated"): "deprecate",
    ("deprecated", "active"): "reinstate",
    ("active", "archived"): "archive",
    ("deprecated", "archived"): "archive",
    ("approved", "archived"): "archive",
    ("draft", "archived"): "archive",
    ("in_review", "archived"): "archive",
    ("archived", "draft"): "restore",
}


async def transition_lifecycle(
    session: AsyncSession,
    actor: Actor,
    ctx: Ctx,
    *,
    tc_id: uuid.UUID,
    to_state: str,
    expected_version: int,
) -> TestCase:
    tc = await get_test_case(session, actor, tc_id)
    authz.authorize(actor, "version.transition", project_id=tc.project_id)
    check_version(tc.version, expected_version, entity="test case")
    key = (tc.lifecycle_state, to_state)
    if key not in _LOGICAL_TRANSITIONS:
        raise StateTransitionNotAllowed(
            f"Cannot move test case from '{tc.lifecycle_state}' to '{to_state}'."
        )
    if to_state == "active" and tc.approved_version_id is None:
        raise StateTransitionNotAllowed("Approve a version before activating the test case.")
    before = tc.lifecycle_state
    tc.lifecycle_state = to_state
    tc.version += 1
    await session.flush()
    audit.record(
        session, actor=actor, ctx=ctx, entity_type="test_case",
        action=f"test_case.{_LOGICAL_TRANSITIONS[key]}", entity_id=tc.id, entity_key=tc.key,
        project_id=tc.project_id, before={"state": before}, after={"state": to_state},
    )
    await session.commit()
    return tc


# --------------------------------------------------------------------------- helpers


def _assert_reviewable(version: TestCaseVersion, steps: list[TestStep]) -> None:
    errs: list[dict] = []
    if not version.title.strip():
        errs.append({"field": "/title", "code": "REQUIRED", "message": "Title is required."})
    valid_steps = [s for s in steps if s.action.strip() and s.expected_result.strip()]
    if not valid_steps:
        errs.append(
            {"field": "/steps", "code": "REQUIRED", "message": "At least one valid step is required."}
        )
    if errs:
        raise ValidationFailed("The draft is not ready for review.", details=errs)


def _steps_differ(existing: list[TestStep], incoming: list[StepInput]) -> bool:
    if len(existing) != len(incoming):
        return True
    for e, i in zip(sorted(existing, key=lambda s: s.order_index), incoming, strict=False):
        if (
            e.action != i.action.strip()
            or e.expected_result != i.expected_result.strip()
            or e.is_required != i.is_required
        ):
            return True
    return False


async def _next_version_number(session: AsyncSession, tc_id: uuid.UUID) -> int:
    n = await session.scalar(
        select(func.max(TestCaseVersion.version_number)).where(
            TestCaseVersion.test_case_id == tc_id
        )
    )
    return int(n or 0) + 1


_TC_SORT = {
    "key": None,  # filled below (natural)
    "title": [func.lower(TestCase.title)],
    "state": [TestCase.lifecycle_state],
    "lifecycle_state": [TestCase.lifecycle_state],
    "automation": [TestCase.automation_status],
    "automation_status": [TestCase.automation_status],
    "updated_at": [TestCase.updated_at],
    "created_at": [TestCase.created_at],
}


async def list_test_cases(
    session: AsyncSession,
    actor: Actor,
    *,
    project_id: uuid.UUID,
    folder_id: uuid.UUID | None = None,
    scenario_id: uuid.UUID | None = None,
    plan_id: uuid.UUID | None = None,
    unassigned: bool = False,
    state: str | None = None,
    query: str | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[TestCase], int]:
    from app.domain.sorting import apply_sort, natural_key_order
    from app.models import PlanScopeItem

    authz.require_member(actor, project_id)
    stmt = select(TestCase).where(TestCase.project_id == project_id)
    if folder_id is not None:
        stmt = stmt.where(TestCase.folder_id == folder_id)
    if scenario_id is not None:
        stmt = stmt.where(TestCase.scenario_id == scenario_id)
    if plan_id is not None:
        stmt = stmt.where(
            TestCase.id.in_(
                select(PlanScopeItem.test_case_id).where(PlanScopeItem.plan_id == plan_id)
            )
        )
    if unassigned:
        stmt = stmt.where(
            ~TestCase.id.in_(select(PlanScopeItem.test_case_id))
        )
    if state:
        stmt = stmt.where(TestCase.lifecycle_state == state)
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(func.lower(TestCase.title).like(like) | func.lower(TestCase.key).like(like))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    allowed = {**_TC_SORT, "key": natural_key_order(TestCase)}
    stmt = apply_sort(stmt, sort=sort, allowed=allowed, default=natural_key_order(TestCase))
    rows = (
        await session.scalars(stmt.limit(page_size).offset((page - 1) * page_size))
    ).all()
    return list(rows), int(total)
