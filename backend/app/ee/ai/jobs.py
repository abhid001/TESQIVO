"""Worker binding for the AI generator. PROPRIETARY - see app/ee/LICENSE.

Imported by `app.ee.register_worker()`; registering is the import side effect.
"""

from __future__ import annotations

import uuid

from app.core.license import current_license
from app.ee.ai import generator
from app.worker import handler


@handler(generator.JOB_TYPE)
async def run_ai_generation(job_id: uuid.UUID) -> None:
    from app.core.db import get_sessionmaker
    from app.models import BackgroundJob

    async with get_sessionmaker()() as session:
        job = await session.get(BackgroundJob, job_id)
        gen_id = (job.scope_snapshot or {}).get("generation_id") if job else None
    if not gen_id:
        return
    lic = current_license()
    if lic is None or not lic.has("ai"):
        # The licence lapsed between request and run: never send data to the provider.
        await generator._finish(uuid.UUID(gen_id), failed="The Enterprise licence no longer covers AI generation.")
        return
    await generator.run_generation(uuid.UUID(gen_id))
