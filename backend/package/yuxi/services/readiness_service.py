"""Readiness probe for core API dependencies.

Adapted from the upstream Yuxi readiness service. Probing scope here is scoped to
the API's own runtime: the business PostgreSQL pool, the run-queue Redis, and the
application startup completion flag. The worker-side readiness/health is reported
separately via the admin detailed-health endpoint, since the worker lifecycle in
this codebase is managed independently.
"""

from __future__ import annotations

import asyncio
import copy
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import text
from yuxi.services.run_queue_service import get_redis_client
from yuxi.storage.postgres.manager import pg_manager

READINESS_PROBE_TIMEOUT_SECONDS = float(os.getenv("READINESS_PROBE_TIMEOUT_SECONDS", "2"))
READINESS_CACHE_TTL_SECONDS = float(os.getenv("READINESS_CACHE_TTL_SECONDS", "1"))
Probe = Callable[[], Awaitable[None]]
_readiness_cache: tuple[tuple, float, dict[str, Any]] | None = None
_readiness_inflight: dict[tuple, asyncio.Task] = {}


async def _probe_postgres() -> None:
    """Verify the business PostgreSQL pool can run a query."""
    async with pg_manager.get_async_session_context() as session:
        await session.execute(text("SELECT 1"))


async def _probe_redis() -> None:
    """Verify the run-queue Redis responds to commands."""
    redis = await get_redis_client()
    await redis.ping()


async def _run_probe(probe: Probe) -> dict[str, str]:
    try:
        await asyncio.wait_for(probe(), timeout=READINESS_PROBE_TIMEOUT_SECONDS)
    except TimeoutError:
        return {"status": "error", "code": "timeout"}
    except Exception as exc:
        return {"status": "error", "code": type(exc).__name__}
    return {"status": "ok"}


async def get_readiness(*, startup_complete: bool) -> dict[str, Any]:
    """Return structured readiness facts with a short cache and single-flight."""
    global _readiness_cache

    cache_key = (startup_complete, id(_probe_postgres), id(_probe_redis))
    now = time.monotonic()
    if _readiness_cache is not None:
        cached_key, expires_at, cached_result = _readiness_cache
        if cached_key == cache_key and now < expires_at:
            return copy.deepcopy(cached_result)

    task = _readiness_inflight.get(cache_key)
    if task is None:

        async def _compute() -> dict[str, Any]:
            postgres, redis = await asyncio.gather(
                _run_probe(_probe_postgres),
                _run_probe(_probe_redis),
            )
            checks = {
                "startup": {"status": "ok"} if startup_complete else {"status": "error", "code": "not_complete"},
                "postgres": postgres,
                "redis": redis,
            }
            ready = all(check["status"] == "ok" for check in checks.values())
            return {"status": "ready" if ready else "not_ready", "checks": checks}

        task = asyncio.create_task(_compute())
        _readiness_inflight[cache_key] = task
    try:
        result = await asyncio.shield(task)
    finally:
        if task.done() and _readiness_inflight.get(cache_key) is task:
            _readiness_inflight.pop(cache_key, None)

    _readiness_cache = (cache_key, time.monotonic() + max(0.0, READINESS_CACHE_TTL_SECONDS), result)
    return copy.deepcopy(result)
