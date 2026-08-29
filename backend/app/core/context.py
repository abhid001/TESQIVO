"""Request context passed from transport into domain services.

Domain services never see FastAPI Request objects (PRS §21.6). They receive an
`Actor` plus a `Ctx` carrying correlation id and request source.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    project_admin = "project_admin"
    test_manager = "test_manager"
    tester = "tester"
    viewer = "viewer"


class Source(str, Enum):
    gui = "gui"
    api = "api"
    import_ = "import"
    bulk = "bulk"
    system = "system"


@dataclass(frozen=True)
class Membership:
    project_id: uuid.UUID
    project_key: str
    role: Role


@dataclass(frozen=True)
class Actor:
    id: uuid.UUID
    username: str
    display_name: str
    is_system_admin: bool
    email: str = ""
    must_change_password: bool = False
    memberships: dict[uuid.UUID, Membership] = field(default_factory=dict)

    def membership(self, project_id: uuid.UUID) -> Membership | None:
        return self.memberships.get(project_id)

    @classmethod
    def system(cls) -> Actor:
        return cls(
            id=uuid.UUID(int=0),
            username="system",
            display_name="System",
            is_system_admin=True,
        )


@dataclass(frozen=True)
class Ctx:
    correlation_id: str
    source: Source = Source.api
    idempotency_key: str | None = None
