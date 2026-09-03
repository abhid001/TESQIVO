"""Readable entity-key minting (PRS §5, decision D-009).

Keys look like ``PAY-TC-142``. The per-(project, type) counter row is locked
FOR UPDATE so concurrent creates never collide or reuse a value.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EntityCounter, Project

ENTITY_ABBR = {
    "test_case": "TC",
    "scenario": "SCN",
    "requirement": "REQ",
    "release": "REL",
    "defect": "DEF",
    "test_plan": "PLAN",
    "test_cycle": "CYC",
    "test_folder": "FLD",
}


async def next_key(session: AsyncSession, project_id: uuid.UUID, entity_type: str) -> str:
    abbr = ENTITY_ABBR[entity_type]
    project_key = await session.scalar(select(Project.key).where(Project.id == project_id))
    if project_key is None:
        raise ValueError(f"unknown project {project_id}")

    locked = (
        select(EntityCounter)
        .where(
            EntityCounter.project_id == project_id,
            EntityCounter.entity_type == entity_type,
        )
        .with_for_update()
    )
    counter = await session.scalar(locked)
    if counter is None:
        # First key of this type for this project. Two concurrent creators can
        # both reach here; the loser's INSERT hits the PK constraint, so isolate
        # it in a savepoint and then take the row lock the winner is holding
        # (finding #3).
        try:
            async with session.begin_nested():
                session.add(
                    EntityCounter(project_id=project_id, entity_type=entity_type, next_seq=1)
                )
                await session.flush()
        except IntegrityError:
            pass
        counter = await session.scalar(locked)
        assert counter is not None

    seq = counter.next_seq
    counter.next_seq = seq + 1
    await session.flush()
    return f"{project_key}-{abbr}-{seq}"
