from __future__ import annotations

import asyncio
import base64
import os
from collections.abc import Sequence
from pathlib import Path

import ormsgpack
from yuxi.agents.backends.sandbox.paths import (
    sandbox_outputs_dir,
    sandbox_uploads_dir,
    sandbox_workspace_dir,
)
from yuxi.config.app import config
from yuxi.services.run_queue_service import get_redis_client
from yuxi.utils.logging_config import logger

MENTION_EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

MAX_MENTION_RESULTS = 50
MAX_ENTRIES_PER_DIR = 500
MAX_SEARCH_DEPTH = 15
CACHE_TTL = 60  # Cache validity period 60 seconds
MAX_CACHED_ENTRIES = 100000
REDIS_KEY_PREFIX = "yuxi:mention:cache:"
WORKSPACE_CACHE_PREFIX = f"{REDIS_KEY_PREFIX}workspace:"
THREAD_CACHE_PREFIX = f"{REDIS_KEY_PREFIX}thread:"
WORKSPACE_THREAD_PLACEHOLDER = "_workspace"
MENTION_SOURCES = {"workspace", "thread"}


def _scan_pruned_files(root: Path, max_entries: int) -> list[tuple[str, str]]:
    """
    Simultaneously scan disk file directories and perform multiple quota pruning protection (Prevent large file warehouse from getting stuck)
    """
    results: list[tuple[str, str]] = []
    if not root.exists():
        return results

    root_str = str(root)
    for dirpath, dirnames, filenames in os.walk(root_str):
        # 1. Prune blacklist and hidden directories (modify directly in dirnames to prevent os.walk from going deeper)
        dirnames[:] = [d for d in dirnames if d not in MENTION_EXCLUDE_DIRS and not d.startswith(".")]

        # 2. Depth protection: Limit the maximum search depth (root itself is layer 0, and the length of rel.parts at layer 15 is exactly 15)
        try:
            rel = Path(dirpath).relative_to(root)
            if len(rel.parts) >= MAX_SEARCH_DEPTH:
                dirnames.clear()
                continue
        except Exception:
            pass

        # 3. Collection of qualified "subdirectory entities" under width and global quota protection
        for dirname in dirnames:
            full_dir_path = Path(dirpath) / dirname
            rel_dir_path = full_dir_path.relative_to(root).as_posix()

            # Use a virtual relative path ending with '/' to indicate that this is a directory
            virtual_dir_path = f"{rel_dir_path}/"
            results.append((dirname, virtual_dir_path))

            if len(results) >= max_entries:
                return results

        # 4. Width limit protection: A single-layer directory is limited to reading up to 500 files to prevent flat and ultra-wide directories from getting stuck.
        scan_filenames = filenames[:MAX_ENTRIES_PER_DIR]
        for filename in scan_filenames:
            full_path = Path(dirpath) / filename
            # Calculate relative path relative to root path
            rel_path = full_path.relative_to(root).as_posix()

            # Save as compact tuple (filename, relative_path)
            results.append((filename, rel_path))

            # 5. Global upper limit protection: If the total number of files reaches the upper limit, the circuit breaker will exit.
            if len(results) >= max_entries:
                return results

    return results


async def _read_cached_index(redis, redis_key: str) -> list[tuple[str, str]] | None:
    cached_str = await redis.get(redis_key)
    if not cached_str:
        return None
    try:
        packed_bytes = base64.b64decode(cached_str)
        return ormsgpack.unpackb(packed_bytes)
    except Exception as e:
        logger.warning(f"Failed to unpack mention cache {redis_key}: {e}")
        return None


async def _write_cached_index(redis, redis_key: str, entries: list[tuple[str, str]]) -> None:
    try:
        packed_bytes = ormsgpack.packb(entries)
        packed_str = base64.b64encode(packed_bytes).decode("ascii")
        await redis.set(redis_key, packed_str, ex=CACHE_TTL)
    except Exception as e:
        logger.warning(f"Failed to write mention cache {redis_key}: {e}")


def _normalize_sources(sources: Sequence[str] | None, *, has_thread: bool) -> tuple[str, ...]:
    if not sources:
        return ("thread", "workspace") if has_thread else ("workspace",)

    normalized = []
    for source in sources:
        value = str(source or "").strip().lower()
        if value in MENTION_SOURCES and value not in normalized:
            normalized.append(value)

    if not has_thread:
        normalized = [source for source in normalized if source == "workspace"]
    return tuple(normalized or (["workspace"] if not has_thread else ["thread", "workspace"]))


def _workspace_root(uid: str) -> Path:
    return sandbox_workspace_dir(WORKSPACE_THREAD_PLACEHOLDER, uid)


async def _scan_virtual_root(root: Path, virtual_prefix: str, max_entries: int) -> list[tuple[str, str]]:
    scan_results = await asyncio.to_thread(_scan_pruned_files, root, max_entries)
    return [
        (name, f"{virtual_prefix}/{rel_path}" if rel_path and rel_path != "." else virtual_prefix)
        for name, rel_path in scan_results
    ]


async def get_or_build_workspace_index(uid: str) -> list[tuple[str, str]]:
    redis = await get_redis_client()
    redis_key = f"{WORKSPACE_CACHE_PREFIX}{uid}"
    cached = await _read_cached_index(redis, redis_key)
    if cached is not None:
        return cached

    entries = await _scan_virtual_root(_workspace_root(uid), "workspace", MAX_CACHED_ENTRIES)
    await _write_cached_index(redis, redis_key, entries)
    return entries


async def get_or_build_thread_index(thread_id: str) -> list[tuple[str, str]]:
    redis = await get_redis_client()
    redis_key = f"{THREAD_CACHE_PREFIX}{thread_id}"
    cached = await _read_cached_index(redis, redis_key)
    if cached is not None:
        return cached

    entries: list[tuple[str, str]] = []
    for virtual_prefix, root in (
        ("uploads", sandbox_uploads_dir(thread_id)),
        ("outputs", sandbox_outputs_dir(thread_id)),
    ):
        needed = MAX_CACHED_ENTRIES - len(entries)
        if needed <= 0:
            break
        entries.extend(await _scan_virtual_root(root, virtual_prefix, needed))

    await _write_cached_index(redis, redis_key, entries)
    return entries


async def get_or_build_file_index(
    thread_id: str | None,
    uid: str,
    sources: Sequence[str] | None = None,
) -> list[tuple[str, str, str]]:
    """Get or build the current mentionable file index, workspace and thread cache are separated."""
    selected_sources = _normalize_sources(sources, has_thread=bool(thread_id))
    entries: list[tuple[str, str, str]] = []

    for source in selected_sources:
        if source == "thread" and thread_id:
            entries.extend(
                (name, virtual_path, "thread") for name, virtual_path in await get_or_build_thread_index(thread_id)
            )
        elif source == "workspace":
            entries.extend(
                (name, virtual_path, "workspace") for name, virtual_path in await get_or_build_workspace_index(uid)
            )

    return entries


def _rank_mention_entries(index: list[tuple[str, str, str]], query: str) -> list[dict]:
    query_lower = query.lower()
    prefix = (config.sandbox_virtual_path_prefix or "/home/gem/user-data").rstrip("/")
    name_matched = []
    path_matched = []

    for name, virtual_path, source in index:
        name_lower = name.lower()
        path_lower = virtual_path.lower()
        is_dir = virtual_path.endswith("/")

        if query_lower in name_lower:
            if name_lower == query_lower:
                score = 1000.0
            else:
                score = 500.0
                if name_lower.startswith(query_lower):
                    score += 50.0
                if name_lower.endswith(query_lower):
                    score += 20.0
                start_idx = name_lower.find(query_lower)
                if start_idx != -1:
                    score -= min(start_idx, 30.0)
                score -= min(len(name) * 0.5, 50.0)

            name_matched.append(
                {"name": name, "path": f"{prefix}/{virtual_path}", "is_dir": is_dir, "source": source, "score": score}
            )
        elif query_lower in path_lower:
            score = 10.0 - min(len(virtual_path) * 0.1, 5.0)
            path_matched.append(
                {"name": name, "path": f"{prefix}/{virtual_path}", "is_dir": is_dir, "source": source, "score": score}
            )

    name_matched.sort(key=lambda x: -x["score"])
    path_matched.sort(key=lambda x: len(x["path"]))
    return [*name_matched, *path_matched]


async def search_mention_files_in_index(
    thread_id: str | None,
    uid: str,
    query: str,
    sources: Sequence[str] | None = None,
) -> list[dict]:
    """Search mentionable files; only search user workspace when thread is not bound."""
    if not query:
        return []

    selected_sources = _normalize_sources(sources, has_thread=bool(thread_id))
    results: list[dict] = []

    for source in selected_sources:
        source_index = await get_or_build_file_index(thread_id, uid, [source])
        source_results = _rank_mention_entries(source_index, query)
        remaining = MAX_MENTION_RESULTS - len(results)
        if remaining <= 0:
            break
        results.extend(source_results[:remaining])

    return [
        {"name": item["name"], "path": item["path"], "is_dir": item["is_dir"], "source": item["source"]}
        for item in results[:MAX_MENTION_RESULTS]
    ]


async def invalidate_mention_cache(thread_id: str) -> None:
    """Cleans the mention file cache for the specified thread."""
    try:
        redis = await get_redis_client()
        await redis.delete(f"{THREAD_CACHE_PREFIX}{thread_id}")
        await redis.delete(f"{REDIS_KEY_PREFIX}{thread_id}")
    except Exception as e:
        logger.warning(f"Failed to invalidate mention cache for thread {thread_id}: {e}")


async def invalidate_workspace_mention_cache(uid: str) -> None:
    """Cleans the mention file cache for the specified user's workspace."""
    try:
        redis = await get_redis_client()
        await redis.delete(f"{WORKSPACE_CACHE_PREFIX}{uid}")
    except Exception as e:
        logger.warning(f"Failed to invalidate workspace mention cache for uid {uid}: {e}")
