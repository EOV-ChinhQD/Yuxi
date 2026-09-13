"""Redis cache for knowledge base runtime config."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from yuxi.storage.redis import get_async_redis_client
from yuxi.utils.logging_config import logger

KNOWLEDGE_BASE_CACHE_KEY_PREFIX = "yuxi:knowledge_base:"
KNOWLEDGE_BASE_CACHE_TTL_SECONDS = 3600
KNOWLEDGE_BASE_CACHE_LOCK_TIMEOUT_SECONDS = 30
KNOWLEDGE_BASE_CACHE_LOCK_WAIT_SECONDS = 10


def _cache_key(kb_id: str) -> str:
    return f"{KNOWLEDGE_BASE_CACHE_KEY_PREFIX}{kb_id}"


def _cache_lock_key(kb_id: str) -> str:
    return f"{_cache_key(kb_id)}:lock"


@asynccontextmanager
async def kb_config_cache_lock(kb_id: str) -> AsyncIterator[None]:
    """Serialize cache backfill and persistence updates for a single knowledge base."""
    redis = await get_async_redis_client()
    lock = redis.lock(
        _cache_lock_key(kb_id),
        timeout=KNOWLEDGE_BASE_CACHE_LOCK_TIMEOUT_SECONDS,
        blocking_timeout=KNOWLEDGE_BASE_CACHE_LOCK_WAIT_SECONDS,
    )
    async with lock:
        yield


def serialize_kb_config(row: Any) -> dict[str, Any]:
    """Convert a knowledge base record into a minimal runtime config snapshot."""
    additional_params = dict(row.additional_params or {})
    additional_params.pop("stats", None)
    return {
        "kb_id": row.kb_id,
        "kb_type": row.kb_type or "milvus",
        "embedding_model_spec": row.embedding_model_spec,
        "query_params": row.query_params,
        "additional_params": additional_params,
    }


async def get_cached_kb_config(kb_id: str) -> dict[str, Any] | None:
    """Read the cache for a single knowledge base; return a miss when Redis is down or the cache is invalid."""
    try:
        redis = await get_async_redis_client()
        raw = await redis.get(_cache_key(kb_id))
        if not raw:
            return None
        snapshot = json.loads(raw)
        if not isinstance(snapshot, dict) or snapshot.get("kb_id") != kb_id:
            logger.warning(f"Invalid knowledge base cache snapshot: kb_id={kb_id}")
            return None
        return snapshot
    except Exception as exc:
        logger.warning(f"Failed to read knowledge base cache: kb_id={kb_id}: {exc}")
        return None


async def cache_kb_config(row: Any) -> None:
    """Write a single knowledge base runtime snapshot; the read path falls back to PostgreSQL on failure."""
    try:
        redis = await get_async_redis_client()
        snapshot = serialize_kb_config(row)
        await redis.set(
            _cache_key(row.kb_id),
            json.dumps(snapshot, ensure_ascii=False),
            ex=KNOWLEDGE_BASE_CACHE_TTL_SECONDS,
        )
    except Exception as exc:
        logger.warning(f"Failed to write knowledge base cache: kb_id={row.kb_id}: {exc}")


async def delete_cached_kb_config(kb_id: str) -> None:
    """Delete a single knowledge base runtime snapshot; the caller aborts the write on failure."""
    redis = await get_async_redis_client()
    await redis.delete(_cache_key(kb_id))
