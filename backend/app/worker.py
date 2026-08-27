"""Background worker entrypoint (increment 10 foundation).

Phase 1 job types: large CSV export, orphan attachment cleanup, bulk apply. Job
state of record is PostgreSQL (`background_job` / `job_item`); Redis is only the
queue transport. Worker leases + per-item mutation keys prevent duplicate success
on retry or worker restart (PRS §11).

This module is intentionally small: the heavy lifting is in the domain services
that the same single-item API paths use.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models import BackgroundJob

log = logging.getLogger("tesqivo.worker")
LEASE_SECONDS = 60
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


async def _claim_next_job(session) -> BackgroundJob | None:
    now = datetime.now(UTC)
    job = await session.scalar(
        select(BackgroundJob)
        .where(
            BackgroundJob.status.in_(("queued", "running")),
            (BackgroundJob.lease_expires_at.is_(None)) | (BackgroundJob.lease_expires_at < now),
        )
        .order_by(BackgroundJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    job.status = "running"
    job.lease_owner = WORKER_ID
    job.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
    if job.started_at is None:
        job.started_at = now
    await session.commit()
    return job


HANDLERS: dict[str, callable] = {}


def handler(job_type: str):
    def deco(fn):
        HANDLERS[job_type] = fn
        return fn

    return deco


async def _process(job: BackgroundJob) -> None:
    fn = HANDLERS.get(job.type)
    sm = get_sessionmaker()
    if fn is None:
        async with sm() as s:
            j = await s.get(BackgroundJob, job.id)
            j.status = "failed"
            j.error_summary = f"No handler registered for job type '{job.type}'."
            j.finished_at = datetime.now(UTC)
            await s.commit()
        return
    await fn(job.id)


@handler("noop")
async def _noop(job_id: uuid.UUID) -> None:
    sm = get_sessionmaker()
    async with sm() as s:
        j = await s.get(BackgroundJob, job_id)
        j.status = "completed"
        j.finished_at = datetime.now(UTC)
        await s.commit()


async def run_forever(poll_interval: float = 2.0) -> None:
    logging.basicConfig(level=logging.INFO)
    log.info("worker %s started", WORKER_ID)
    sm = get_sessionmaker()
    while True:
        async with sm() as session:
            job = await _claim_next_job(session)
        if job is None:
            await asyncio.sleep(poll_interval)
            continue
        try:
            await _process(job)
        except Exception:
            log.exception("job %s failed", job.id)
            async with sm() as s:
                j = await s.get(BackgroundJob, job.id)
                if j and j.status == "running":
                    j.status = "failed"
                    j.error_summary = "Unhandled worker error (see logs)."
                    j.finished_at = datetime.now(UTC)
                    await s.commit()


def main() -> None:
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
