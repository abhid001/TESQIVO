"""Authorization service (PRS §10).

Enforced on every domain operation. System Admin is instance-wide; every other
permission requires an active project membership. Rules evaluate concrete
conditions (actor owns / is assigned), not symbolic role labels. GUI visibility
is not authorization.

A non-member asking about a project resource gets ResourceNotFound, not Forbidden
(decision D-010) - existence is not disclosed.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from app.core.context import Actor, Role
from app.core.errors import Forbidden, ResourceNotFound

# action -> set of roles that may perform it (before extra predicate)
_ROLE_MATRIX: dict[str, set[Role]] = {
    "project.settings": {Role.project_admin},
    "membership.manage": {Role.project_admin},
    "reference.manage": {Role.project_admin, Role.test_manager},
    "audit.view": {Role.project_admin, Role.test_manager},
    "folder.manage": {Role.test_manager},
    "test_case.create": {Role.test_manager},
    "test_case.edit": {Role.test_manager, Role.tester},
    "test_case.delete": {Role.test_manager},
    "version.transition": {Role.test_manager},
    "plan.manage": {Role.test_manager},
    "plan.delete": {Role.test_manager},
    "plan.reopen": {Role.test_manager},
    "cycle.manage": {Role.test_manager},
    "cycle.reopen": {Role.test_manager},
    "cycle_test.execute": {Role.test_manager, Role.tester},
    "attempt.correct": {Role.test_manager},
    "requirement.manage": {Role.test_manager, Role.tester},
    "requirement.delete": {Role.test_manager},
    "release.manage": {Role.test_manager},
    "defect.manage": {Role.test_manager, Role.tester},
    "defect.delete": {Role.test_manager},
    "trace_link.manage": {Role.test_manager, Role.tester},
    "bulk.run": {Role.test_manager},
    "import.run": {Role.test_manager},
    "export.run": {Role.project_admin, Role.test_manager, Role.tester, Role.viewer},
    "attachment.manage": {Role.test_manager, Role.tester},
    "report.view": {Role.project_admin, Role.test_manager, Role.tester, Role.viewer},
    "project.read": {Role.project_admin, Role.test_manager, Role.tester, Role.viewer},
}


@dataclass
class AuthzContext:
    """Concrete facts a predicate may inspect."""

    actor: Actor
    role: Role
    resource: object | None = None


Predicate = Callable[[AuthzContext], bool]

# extra predicates for self/assigned operations
_PREDICATES: dict[str, Predicate] = {
    "test_case.edit": lambda c: c.role == Role.test_manager
    or _attr(c.resource, "created_by") == c.actor.id,
    "cycle_test.execute": lambda c: c.role == Role.test_manager
    or _attr(c.resource, "assigned_to") in (None, c.actor.id),
    "trace_link.manage": lambda c: c.role == Role.test_manager
    or _attr(c.resource, "created_by") in (None, c.actor.id),
}


def _attr(obj: object | None, name: str):
    return getattr(obj, name, None) if obj is not None else None


def require_member(actor: Actor, project_id: uuid.UUID) -> Role:
    """Return the actor's effective role in the project or raise ResourceNotFound."""
    if actor.is_system_admin:
        return Role.project_admin  # system admin acts with full project authority
    membership = actor.membership(project_id)
    if membership is None:
        raise ResourceNotFound("Resource not found.")
    return membership.role


def authorize(
    actor: Actor,
    action: str,
    *,
    project_id: uuid.UUID,
    resource: object | None = None,
) -> None:
    role = require_member(actor, project_id)
    if actor.is_system_admin:
        return
    allowed_roles = _ROLE_MATRIX.get(action)
    if allowed_roles is None:
        raise Forbidden(f"Unknown action '{action}'.")
    if role not in allowed_roles:
        raise Forbidden("You do not have permission to perform this action.")
    predicate = _PREDICATES.get(action)
    if predicate is not None and not predicate(AuthzContext(actor, role, resource)):
        raise Forbidden("You may only perform this action on your own or assigned items.")


def can(actor: Actor, action: str, *, project_id: uuid.UUID, resource: object | None = None) -> bool:
    try:
        authorize(actor, action, project_id=project_id, resource=resource)
        return True
    except (Forbidden, ResourceNotFound):
        return False
