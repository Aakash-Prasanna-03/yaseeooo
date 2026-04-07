"""Celery tasks: crawl + content cycles."""
from __future__ import annotations

import asyncio
import uuid

from app import database as db
from app.celery_app import celery_app


async def _run_coro_and_close_pool(coro):
    """Run async work and tear down the DB pool before the event loop closes.

    asyncpg pools are bound to the loop they were created on; Celery tasks each
    use a fresh loop via asyncio.run(), so we must not reuse a pool across tasks.
    """
    try:
        return await coro
    finally:
        await db.close_pool()


def _run_async(coro):
    return asyncio.run(_run_coro_and_close_pool(coro))


@celery_app.task(name="yeseeeooo.crawl_workspace")
def crawl_workspace_task(workspace_id: str) -> str:
    from app.services import crawl_worker

    _run_async(crawl_worker.run_crawl(uuid.UUID(workspace_id)))
    return workspace_id


@celery_app.task(name="yeseeeooo.daily_content_cycle")
def daily_content_cycle_task(workspace_id: str) -> str:
    from app.graph.pipeline import run_content_cycle

    _run_async(run_content_cycle(workspace_id))
    return workspace_id


@celery_app.task(name="yeseeeooo.trigger_cycle")
def trigger_cycle_task(workspace_id: str) -> str:
    from app.graph.pipeline import run_content_cycle

    _run_async(run_content_cycle(workspace_id))
    return workspace_id
