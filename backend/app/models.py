"""SQLAlchemy models for the TESQIVO Phase 1 logical ER model.

See docs/architecture/07_logical_er_model.md. Enums are stored as strings (portable
across PostgreSQL and the SQLite test engine); the domain layer owns the value sets.
All internal ids are UUIDs; readable keys are project-unique and never reused.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, UUIDMixin
from app.core.types import UTCDateTime

# ---------------------------------------------------------------------------
# Identity / accounts
# ---------------------------------------------------------------------------


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "app_user"

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_system_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)  # active|disabled
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        CheckConstraint("status in ('active','disabled')", name="status_valid"),
    )


class UserSession(UUIDMixin, Base):
    __tablename__ = "user_session"

    # id doubles as the opaque cookie value (256-bit token stored as the PK string)
    token_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))


class PasswordResetToken(UUIDMixin, Base):
    __tablename__ = "password_reset_token"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


# ---------------------------------------------------------------------------
# Project boundary
# ---------------------------------------------------------------------------


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "project"

    key: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)  # active|archived
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        CheckConstraint("key = upper(key)", name="key_upper"),
        CheckConstraint("status in ('active','archived')", name="status_valid"),
    )


class ProjectMembership(UUIDMixin, Base):
    __tablename__ = "project_membership"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)  # active|removed
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )
    removed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    removed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (
        CheckConstraint(
            "role in ('project_admin','test_manager','tester','viewer')", name="role_valid"
        ),
        UniqueConstraint("project_id", "user_id", "status", name="one_active_membership"),
    )


class ReferenceValue(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reference_value"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "kind in ('component','environment','tag','test_type','attachment_policy')",
            name="kind_valid",
        ),
        UniqueConstraint("project_id", "kind", "value", name="unique_ref_value"),
    )


class EntityCounter(Base):
    __tablename__ = "entity_counter"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id"), primary_key=True
    )
    entity_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    next_seq: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


# ---------------------------------------------------------------------------
# Test repository + versioning
# ---------------------------------------------------------------------------


class TestFolder(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "test_folder"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_folder.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    path: Mapped[str] = mapped_column(String(1000), nullable=False, default="/")
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class TestCase(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "test_case"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    folder_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_folder.id"), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_case_version.id", use_alter=True, name="fk_tc_current_version")
    )
    approved_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_case_version.id", use_alter=True, name="fk_tc_approved_version")
    )
    automation_status: Mapped[str] = mapped_column(
        String(20), default="candidate", nullable=False
    )  # not_applicable|candidate|automated
    is_eligible_for_automation: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "lifecycle_state in "
            "('draft','in_review','approved','active','deprecated','archived')",
            name="lifecycle_valid",
        ),
        CheckConstraint(
            "automation_status in ('not_applicable','candidate','automated')",
            name="automation_status_valid",
        ),
    )

    versions: Mapped[list[TestCaseVersion]] = relationship(
        back_populates="test_case",
        foreign_keys="TestCaseVersion.test_case_id",
        order_by="TestCaseVersion.version_number",
    )


class TestCaseVersion(UUIDMixin, Base):
    __tablename__ = "test_case_version"

    test_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_case.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    preconditions: Mapped[str | None] = mapped_column(Text)
    controlled_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text)
    content_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("test_case_id", "version_number", name="unique_version_number"),
        CheckConstraint(
            "status in ('draft','in_review','approved','superseded')", name="version_status_valid"
        ),
    )

    test_case: Mapped[TestCase] = relationship(
        back_populates="versions", foreign_keys=[test_case_id]
    )
    steps: Mapped[list[TestStep]] = relationship(
        back_populates="version", order_by="TestStep.order_index", cascade="all, delete-orphan"
    )


class TestStep(UUIDMixin, Base):
    __tablename__ = "test_step"

    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_case_version.id"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("version_id", "order_index", name="unique_step_order"),)

    version: Mapped[TestCaseVersion] = relationship(back_populates="steps")


# ---------------------------------------------------------------------------
# Requirements / Releases / Defects
# ---------------------------------------------------------------------------


class Requirement(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "requirement"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    req_type: Mapped[str] = mapped_column(String(32), default="functional", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    component: Mapped[str | None] = mapped_column(String(120))
    release_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("release.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(400))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status in ('draft','active','fulfilled','archived')", name="req_status_valid"
        ),
    )


class Release(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "release"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="planned", nullable=False)
    start_date: Mapped[datetime | None] = mapped_column(UTCDateTime)
    end_date: Mapped[datetime | None] = mapped_column(UTCDateTime)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    version_label: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status in ('planned','active','released','cancelled','archived')",
            name="release_status_valid",
        ),
    )


class Defect(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "defect"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="major", nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    reporter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    environment: Mapped[str | None] = mapped_column(String(120))
    release_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("release.id"), index=True)
    detected_build: Mapped[str | None] = mapped_column(String(64))
    resolved_build: Mapped[str | None] = mapped_column(String(64))
    resolution: Mapped[str | None] = mapped_column(String(64))
    source_type: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(400))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status in ('new','open','in_progress','resolved','closed','rejected')",
            name="defect_status_valid",
        ),
        CheckConstraint(
            "severity in ('critical','high','major','minor','trivial')", name="severity_valid"
        ),
    )


# ---------------------------------------------------------------------------
# Plans / Cycles / Execution
# ---------------------------------------------------------------------------


class TestPlan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "test_plan"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    release_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("release.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status in ('draft','active','completed','archived')", name="plan_status_valid"
        ),
    )


class PlanScopeItem(UUIDMixin, Base):
    __tablename__ = "plan_scope_item"

    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_plan.id"), nullable=False, index=True)
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_case.id"), nullable=False, index=True
    )
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )
    source: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    filter_snapshot: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (UniqueConstraint("plan_id", "test_case_id", name="unique_plan_scope"),)


class TestCycle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "test_cycle"

    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_plan.id"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    release_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("release.id"), index=True)
    environment: Mapped[str] = mapped_column(String(120), nullable=False, default="default")
    build: Mapped[str] = mapped_column(String(64), nullable=False, default="unspecified")
    browser: Mapped[str | None] = mapped_column(String(64))
    device: Mapped[str | None] = mapped_column(String(64))
    platform: Mapped[str | None] = mapped_column(String(64))
    start_date: Mapped[datetime | None] = mapped_column(UTCDateTime)
    end_date: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status in ('draft','active','completed','reopened','archived')",
            name="cycle_status_valid",
        ),
    )


class CycleTest(UUIDMixin, Base):
    __tablename__ = "cycle_test"

    cycle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cycle.id"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_case.id"), nullable=False, index=True
    )
    test_case_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_case_version.id")
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"), index=True)
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )
    removed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    retest_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    snapshot_taken_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    steps: Mapped[list[CycleTestStep]] = relationship(
        order_by="CycleTestStep.order_index", cascade="all, delete-orphan"
    )


class CycleTestStep(UUIDMixin, Base):
    __tablename__ = "cycle_test_step"

    cycle_test_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cycle_test.id"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("cycle_test_id", "order_index", name="unique_cycle_step_order"),
    )


class ExecutionAttempt(UUIDMixin, Base):
    __tablename__ = "execution_attempt"

    cycle_test_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cycle_test.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_plan.id"), nullable=False)
    cycle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cycle.id"), nullable=False, index=True)
    test_case_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_case_version.id")
    )
    release_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("release.id"))
    environment: Mapped[str] = mapped_column(String(120), nullable=False)
    build: Mapped[str] = mapped_column(String(64), nullable=False)
    tester_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="IN_PROGRESS", nullable=False)
    overall_result: Mapped[str | None] = mapped_column(String(16))
    result_overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    override_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status in ('IN_PROGRESS','PASSED','FAILED','BLOCKED','SKIPPED','ABORTED')",
            name="attempt_status_valid",
        ),
    )

    steps: Mapped[list[ExecutionStep]] = relationship(
        order_by="ExecutionStep.order_index", cascade="all, delete-orphan"
    )
    corrections: Mapped[list[ExecutionCorrection]] = relationship(
        order_by="ExecutionCorrection.created_at"
    )


class ExecutionStep(UUIDMixin, Base):
    __tablename__ = "execution_step"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execution_attempt.id"), nullable=False, index=True
    )
    cycle_test_step_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cycle_test_step.id"))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    result: Mapped[str] = mapped_column(String(16), default="not_run", nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (
        CheckConstraint(
            "result in ('not_run','passed','failed','blocked','skipped')", name="step_result_valid"
        ),
        UniqueConstraint("attempt_id", "order_index", name="unique_exec_step_order"),
    )


class ExecutionCorrection(UUIDMixin, Base):
    __tablename__ = "execution_correction"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execution_attempt.id"), nullable=False, index=True
    )
    field: Mapped[str] = mapped_column(String(40), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )


class AttemptDefectLink(UUIDMixin, Base):
    __tablename__ = "attempt_defect_link"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execution_attempt.id"), nullable=False, index=True
    )
    defect_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("defect.id"), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("attempt_id", "defect_id", name="unique_attempt_defect"),)


# ---------------------------------------------------------------------------
# Traceability / attachments / audit / jobs
# ---------------------------------------------------------------------------


class TraceLink(UUIDMixin, Base):
    __tablename__ = "trace_link"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False)
    origin: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )
    removed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    removed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    external_reference: Mapped[str | None] = mapped_column(String(400))


class Attachment(UUIDMixin, Base):
    __tablename__ = "attachment"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
    parent_type: Mapped[str] = mapped_column(String(16), nullable=False)  # version|attempt|step
    parent_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(400), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(400), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class AuditEvent(UUIDMixin, Base):
    __tablename__ = "audit_event"

    occurred_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False, index=True
    )
    actor_type: Mapped[str] = mapped_column(String(8), default="user", nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_user.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    entity_key: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(8), default="api", nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("background_job.id"))


class BackgroundJob(UUIDMixin, Base):
    __tablename__ = "background_job"

    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("project.id"), index=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False)
    scope_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), index=True)
    payload_fingerprint: Mapped[str | None] = mapped_column(String(128))
    requested_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolved_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    succeeded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unchanged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_ref: Mapped[str | None] = mapped_column(String(400))
    retryable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(80))
    lease_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    error_summary: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status in ('queued','running','completed','partially_completed','failed','cancelled')",
            name="job_status_valid",
        ),
    )


class JobItem(UUIDMixin, Base):
    __tablename__ = "job_item"

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("background_job.id"), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    target_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(Text)
    mutation_key: Mapped[str] = mapped_column(String(200), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (UniqueConstraint("job_id", "mutation_key", name="unique_job_mutation"),)


class MetricDefinition(Base):
    __tablename__ = "metric_definition"

    metric_id: Mapped[str] = mapped_column(String(8), primary_key=True)
    formula_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sql_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )


class IdempotencyRecord(UUIDMixin, Base):
    """Generic idempotency ledger for retry-sensitive creates (PRS §13)."""

    __tablename__ = "idempotency_record"

    key: Mapped[str] = mapped_column(String(200), nullable=False)
    scope: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("scope", "key", name="unique_idempotency_key"),)
