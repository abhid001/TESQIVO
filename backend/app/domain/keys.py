"""Readable entity-key minting (PRS §5, decision D-009).

Keys look like ``PAY-TC-142``. The per-(project, type) counter row is locked
FOR UPDATE so concurrent creates never collide or reuse a value.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EntityCounter, Project

ENTITY_ABBR = {
    "test_case": "TC",
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

    counter = await session.scalar(
        select(EntityCounter)
        .where(
            EntityCounter.project_id == project_id,
            EntityCounter.entity_type == entity_type,
        )
        .with_for_update()
    )
    if counter is None:
        counter = EntityCounter(project_id=project_id, entity_type=entity_type, next_seq=1)
        session.add(counter)
        await session.flush()
        counter = await session.scalar(
            select(EntityCounter)
            .where(
                EntityCounter.project_id == project_id,
                EntityCounter.entity_type == entity_type,
            )
            .with_for_update()
        )
        assert counter is not None

    seq = counter.next_seq
    counter.next_seq = seq + 1
    await session.flush()
    return f"{project_key}-{abbr}-{seq}"
