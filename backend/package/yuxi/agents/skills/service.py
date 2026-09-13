from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import tempfile
import threading
import time
import uuid
import zipfile
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi import config as sys_config
from yuxi.agents.mcp.service import get_enabled_mcp_server_slugs
from yuxi.agents.skills.repository import SkillRepository
from yuxi.permissions import ResourcePermission, normalize_permission_config, resolve_skill_permission
from yuxi.storage.postgres.models_business import Skill, User
from yuxi.storage.redis import get_async_redis_client
from yuxi.utils.logging_config import logger
from yuxi.utils.paths import ensure_within_root

SKILL_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SKILL_NAME_PATTERN = SKILL_SLUG_PATTERN

TEXT_FILE_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".js",
    ".ts",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".xml",
    ".html",
    ".css",
    ".sql",
    ".sh",
    ".bat",
    ".ps1",
    ".env",
    ".csv",
    ".tsv",
    ".rst",
    ".ipynb",
    ".vue",
    ".jsx",
    ".tsx",
}

BUILTIN_SKILL_OPERATOR = "builtin-system"
SKILL_SOURCE_TYPES = {"builtin", "upload", "remote"}
ADMIN_ROLES = {"admin", "superadmin"}
DEFAULT_SKILL_SHARE_CONFIG = {"access_level": "user", "department_ids": [], "user_uids": []}
BUILTIN_SKILL_SHARE_CONFIG = {"access_level": "global", "department_ids": [], "user_uids": []}
SKILL_DRAFT_TTL_SECONDS = 60 * 60
PERSONAL_SKILL_CACHE_TTL_SECONDS = 5 * 60
PERSONAL_SKILL_CACHE_PREFIX = "yuxi:skills:personal:v1:"
PERSONAL_SKILL_SCAN_LOCK_PREFIX = "yuxi:skills:personal:scan-lock:v1:"
PERSONAL_SKILL_SCAN_LOCK_TIMEOUT_SECONDS = 30
PERSONAL_SKILL_SCAN_LOCK_WAIT_SECONDS = 10
PERSONAL_SKILL_SOURCE_TYPE = "personal"
WORKSPACE_SKILLS_RELATIVE_DIR = Path("agents") / "skills"
_THREAD_SKILLS_LOCK = threading.Lock()
_THREAD_SKILLS_LOCKS: dict[str, threading.Lock] = {}


@dataclass(frozen=True, slots=True)
class ResolvedSkill:
    """Describe the Skills effectively available to the current user and their true origin."""

    id: Any
    slug: str
    name: str
    description: str
    source_type: str
    source_scope: str
    source_dir: Path
    enabled: bool
    created_by: str | None
    share_config: dict[str, Any] | None
    tool_dependencies: list[str]
    mcp_dependencies: list[str]
    skill_dependencies: list[str]
    overrides_shared: bool = False
    shadowed_by_personal: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return Skill metadata safe to expose to the frontend."""
        data = {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "source_type": self.source_type,
            "source_scope": self.source_scope,
            "enabled": self.enabled,
            "created_by": self.created_by,
            "tool_dependencies": self.tool_dependencies,
            "mcp_dependencies": self.mcp_dependencies,
            "skill_dependencies": self.skill_dependencies,
            "overrides_shared": self.overrides_shared,
            "shadowed_by_personal": self.shadowed_by_personal,
        }
        if self.share_config is not None:
            data["share_config"] = self.share_config
        return data


@dataclass(frozen=True, slots=True)
class PersonalSkillSnapshot:
    """Hold one personal Skill metadata snapshot."""

    items: list[ResolvedSkill]
    scanned_at: str
    from_cache: bool


def _get_thread_skills_lock(thread_id: str) -> threading.Lock:
    with _THREAD_SKILLS_LOCK:
        lock = _THREAD_SKILLS_LOCKS.get(thread_id)
        if lock is None:
            lock = threading.Lock()
            _THREAD_SKILLS_LOCKS[thread_id] = lock
        return lock


def normalize_string_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def is_valid_skill_slug(slug: str) -> bool:
    if not isinstance(slug, str):
        return False
    return bool(SKILL_SLUG_PATTERN.match(slug.strip()))


def is_builtin_skill(item: Skill | dict) -> bool:
    source_type = item.get("source_type") if isinstance(item, dict) else item.source_type
    return source_type == "builtin"


def get_allowed_skill_access_levels(user: User) -> list[str]:
    if user.role in ADMIN_ROLES:
        return ["global", "department", "user"]
    return ["user"]


def normalize_skill_share_config(
    share_config: dict | None,
    *,
    operator_uid: str,
    source_type: str = "upload",
    allowed_access_levels: set[str] | None = None,
) -> dict:
    if source_type == "builtin":
        return {"version": 2, "read_scope": BUILTIN_SKILL_SHARE_CONFIG.copy(), "manage_scope": None}

    default_scope = {
        "access_level": "user",
        "department_ids": [],
        "user_uids": [operator_uid],
    }
    return normalize_permission_config(
        share_config or {"version": 2, "read_scope": default_scope, "manage_scope": None},
        allowed_access_levels=allowed_access_levels,
        unauthorized_access_level_message="Người dùng hiện tại không có quyền dùng phạm vi chia sẻ Skill này",
        strict=True,
    )


def user_can_access_skill(user: User, skill: Skill, *, require_enabled: bool = True) -> bool:
    if require_enabled and not skill.enabled:
        return False
    return resolve_skill_permission(user, skill) != ResourcePermission.NONE


def user_can_manage_skill(user: User, skill: Skill) -> bool:
    if is_builtin_skill(skill):
        return user.role in ADMIN_ROLES
    return resolve_skill_permission(user, skill) == ResourcePermission.MANAGE


def can_skill_depend_on(parent: Skill, dependency: Skill) -> bool:
    if not dependency.enabled:
        return False
    if is_builtin_skill(dependency):
        return True

    dep_config = normalize_permission_config(dependency.share_config)
    parent_config = normalize_permission_config(parent.share_config)
    dependency_scopes = [scope for scope in (dep_config["read_scope"], dep_config["manage_scope"]) if scope]
    parent_scopes = [scope for scope in (parent_config["read_scope"], parent_config["manage_scope"]) if scope]
    owner_scope = {"access_level": "user", "department_ids": [], "user_uids": []}
    if not dependency_scopes:
        dependency_scopes = [{**owner_scope, "user_uids": [str(dependency.created_by or "")]}]
    if not parent_scopes:
        parent_scopes = [{**owner_scope, "user_uids": [str(parent.created_by or "")]}]
    return all(
        any(_scope_contains(dependency_scope, parent_scope) for dependency_scope in dependency_scopes)
        for parent_scope in parent_scopes
    )


def _scope_contains(container: dict, target: dict) -> bool:
    """Check whether one share scope fully covers another."""

    container_level = container.get("access_level")
    target_level = target.get("access_level")
    if container_level == "global":
        return True
    if target_level == "global" or container_level != target_level:
        return False
    if target_level == "department":
        container_ids = {int(value) for value in container.get("department_ids") or []}
        target_ids = {int(value) for value in target.get("department_ids") or []}
        return target_ids.issubset(container_ids)
    if target_level == "user":
        container_uids = {str(value) for value in container.get("user_uids") or []}
        target_uids = {str(value) for value in target.get("user_uids") or []}
        return target_uids.issubset(container_uids)
    return False


def _ensure_non_builtin(item: Skill) -> None:
    if is_builtin_skill(item):
        raise ValueError("Built-in skill does not allow this operation")


def get_skills_root_dir() -> Path:
    root = Path(sys_config.save_dir) / "skills"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_skill_drafts_root_dir() -> Path:
    root = Path(sys_config.save_dir) / "skill_import_drafts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _cleanup_expired_skill_drafts() -> None:
    root = get_skill_drafts_root_dir()
    now = time.time()
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        metadata_path = entry / "metadata.json"
        try:
            if not metadata_path.exists() or now - entry.stat().st_mtime > SKILL_DRAFT_TTL_SECONDS:
                shutil.rmtree(entry, ignore_errors=True)
                continue
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            if data.get("expires_at", 0) < now:
                shutil.rmtree(entry, ignore_errors=True)
        except Exception:
            shutil.rmtree(entry, ignore_errors=True)


def _load_skill_draft(draft_id: str) -> tuple[Path, dict]:
    if not re.fullmatch(r"[0-9a-fA-F-]{32,36}", str(draft_id or "")):
        raise ValueError("Invalid installation draft")
    draft_dir = (get_skill_drafts_root_dir() / draft_id).resolve()
    try:
        draft_dir.relative_to(get_skill_drafts_root_dir().resolve())
    except ValueError:
        raise ValueError("Invalid installation draft") from None
    metadata_path = draft_dir / "metadata.json"
    if not metadata_path.exists():
        raise ValueError("Installation draft does not exist or has expired")
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    if data.get("expires_at", 0) < time.time():
        shutil.rmtree(draft_dir, ignore_errors=True)
        raise ValueError("Installation draft has expired")
    return draft_dir, data


def _load_and_select_draft_items(
    draft_id: str, slugs: list[str] | None, operator: User
) -> tuple[Path, dict, list[dict]]:
    """Load an install draft, validate permission and source type, and filter selected items."""
    draft_dir, data = _load_skill_draft(draft_id)
    if data.get("created_by") != operator.uid and operator.role not in ADMIN_ROLES:
        raise ValueError("Unauthorized to confirm this skill install draft")
    if data.get("source_type") not in {"upload", "remote"}:
        raise ValueError("Invalid install draft source")

    draft_items = data.get("items") or []
    if slugs is not None:
        selected_slugs = set(slugs)
        if not selected_slugs:
            raise ValueError("Select at least one Skill")
        available_slugs = {str(item.get("slug") or "").strip() for item in draft_items}
        if selected_slugs - available_slugs:
            raise ValueError("Confirmed install contains Skills outside the draft")
        draft_items = [item for item in draft_items if str(item.get("slug") or "").strip() in selected_slugs]

    return draft_dir, data, draft_items


def get_thread_skills_root_dir(thread_id: str) -> Path:
    safe_thread_id = str(thread_id or "").strip()
    if not safe_thread_id:
        raise ValueError("thread_id is required")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", safe_thread_id):
        raise ValueError("thread_id contains invalid characters")

    root = Path(sys_config.save_dir) / "threads" / safe_thread_id / "skills"
    root.mkdir(parents=True, exist_ok=True)
    return root


async def sync_thread_readable_skills_async(
    thread_id: str,
    selected_slugs: list[str] | None,
    source_dirs: dict[str, str | Path] | None = None,
) -> Path:
    """Sync the shared Skill projection in a thread pool to avoid blocking the agent event loop."""
    return await asyncio.to_thread(
        sync_thread_readable_skills,
        thread_id,
        selected_slugs,
        source_dirs,
    )


def sync_thread_readable_skills(
    thread_id: str,
    selected_slugs: list[str] | None,
    source_dirs: dict[str, str | Path] | None = None,
) -> Path:
    """Sync the effective Skill sources to the thread read-only directory."""
    skills_root = get_skills_root_dir().resolve()
    thread_skills_root = get_thread_skills_root_dir(thread_id)
    normalized_slugs = [slug for slug in normalize_string_list(selected_slugs) if is_valid_skill_slug(slug)]
    normalized_sources = {
        slug: Path(path).resolve()
        for slug, path in (source_dirs or {}).items()
        if slug in normalized_slugs and isinstance(path, (str, Path))
    }
    readable_slugs = set(normalized_slugs)
    with _get_thread_skills_lock(thread_id):
        for entry in thread_skills_root.iterdir():
            if entry.name in readable_slugs:
                continue
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()

        for slug in normalized_slugs:
            source_dir = normalized_sources.get(slug, (skills_root / slug).resolve())
            target_dir = thread_skills_root / slug

            if source_dir.is_symlink() or not source_dir.is_dir() or _dir_contains_symlink(source_dir):
                logger.warning(f"Skip missing Skill source or one containing symlinks: slug={slug}")
                if target_dir.exists() or target_dir.is_symlink():
                    if target_dir.is_dir() and not target_dir.is_symlink():
                        shutil.rmtree(target_dir)
                    else:
                        target_dir.unlink()
                continue

            if target_dir.exists():
                if target_dir.is_symlink():
                    target_dir.unlink()
                elif target_dir.is_dir():
                    if _dirs_equal(target_dir, source_dir):
                        continue
                    shutil.rmtree(target_dir)
                else:
                    target_dir.unlink()

            temp_target = thread_skills_root / f".{slug}.tmp-{uuid.uuid4().hex[:8]}"
            try:
                shutil.copytree(source_dir, temp_target, symlinks=False)
                temp_target.rename(target_dir)
            finally:
                if temp_target.exists():
                    shutil.rmtree(temp_target, ignore_errors=True)

    return thread_skills_root


def get_builtin_skill_specs() -> list[Any]:
    from yuxi.agents.skills.buildin import BUILTIN_SKILLS

    return BUILTIN_SKILLS


def _build_builtin_skill_dir_path(slug: str) -> str:
    return (Path("skills") / slug).as_posix()


def _dir_contains_symlink(path: Path) -> bool:
    """Check whether a directory contains any symlinked sub-path."""
    return any(child.is_symlink() for child in path.rglob("*"))


def _dirs_equal(dir1: Path, dir2: Path) -> bool:
    """Kiểm tra hai thư mục có tập tin và nội dung hoàn toàn giống nhau hay không."""
    if not dir1.exists() or not dir2.exists():
        return False
    return _compute_dir_hash(dir1) == _compute_dir_hash(dir2)


def _compute_dir_hash(source_dir: Path) -> str:
    hasher = hashlib.sha256()
    file_paths = sorted(path for path in source_dir.rglob("*") if path.is_file())
    for file_path in file_paths:
        relative_path = file_path.relative_to(source_dir).as_posix()
        hasher.update(relative_path.encode("utf-8"))
        hasher.update(b"\0")
        with file_path.open("rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        hasher.update(b"\0")
    return hasher.hexdigest()


def _replace_skill_target(
    target_dir: Path,
    source_dir: Path,
    *,
    validate: Callable[[Path], None] | None = None,
) -> None:
    """Atomically copy source_dir to target_dir: copy to a temp dir first, then validate and replace."""
    temp_target = target_dir.with_name(f".{target_dir.name}.tmp-{uuid.uuid4().hex[:8]}")
    trash_dir: Path | None = None
    if temp_target.exists():
        shutil.rmtree(temp_target, ignore_errors=True)

    shutil.copytree(source_dir, temp_target, symlinks=False)
    try:
        if validate is not None:
            validate(temp_target)
        if target_dir.exists():
            trash_dir = target_dir.with_name(f".{target_dir.name}.bak-{uuid.uuid4().hex[:8]}")
            target_dir.rename(trash_dir)
        temp_target.rename(target_dir)
    except Exception:
        shutil.rmtree(temp_target, ignore_errors=True)
        if trash_dir and trash_dir.exists() and not target_dir.exists():
            trash_dir.rename(target_dir)
        raise

    if trash_dir and trash_dir.exists():
        shutil.rmtree(trash_dir, ignore_errors=True)


async def list_accessible_skills(
    db: AsyncSession,
    user: User,
    *,
    require_enabled: bool = True,
    refresh_personal: bool = False,
) -> list[ResolvedSkill]:
    """Return the effective shared and personal Skills for the current user."""
    shared_items, personal_snapshot = await asyncio.gather(
        _list_accessible_shared_skills(db, user, require_enabled=require_enabled),
        list_personal_skills(str(user.uid), refresh=refresh_personal),
    )
    personal_by_slug = {item.slug: item for item in personal_snapshot.items}

    effective: dict[str, ResolvedSkill] = {}
    for item in shared_items:
        effective[item.slug] = _resolved_shared_skill(
            item,
            shadowed_by_personal=item.slug in personal_by_slug,
        )
    for slug, item in personal_by_slug.items():
        effective[slug] = replace(item, overrides_shared=slug in effective)
    return list(effective.values())


async def list_skill_cards_for_user(
    db: AsyncSession,
    user: User,
    *,
    refresh_personal: bool = False,
) -> tuple[list[ResolvedSkill], PersonalSkillSnapshot]:
    """Return the shared and personal Skill cards needed by the management page."""
    shared_items, personal_snapshot = await asyncio.gather(
        list_visible_skills_for_management(db, user),
        list_personal_skills(str(user.uid), refresh=refresh_personal),
    )
    personal_slugs = {item.slug for item in personal_snapshot.items}
    shared_slugs = {item.slug for item in shared_items}

    personal_cards = [replace(item, overrides_shared=item.slug in shared_slugs) for item in personal_snapshot.items]
    shared_cards = [
        _resolved_shared_skill(item, shadowed_by_personal=item.slug in personal_slugs) for item in shared_items
    ]
    return [*personal_cards, *shared_cards], personal_snapshot


async def list_manageable_skills(db: AsyncSession, user: User) -> list[Skill]:
    repo = SkillRepository(db)
    return [item for item in await repo.list_all() if user_can_manage_skill(user, item)]


async def list_visible_skills_for_management(db: AsyncSession, user: User) -> list[Skill]:
    repo = SkillRepository(db)
    visible: list[Skill] = []
    seen: set[str] = set()
    for item in await repo.list_all():
        if item.slug in seen:
            continue
        if user_can_manage_skill(user, item) or (item.enabled and user_can_access_skill(user, item)):
            visible.append(item)
            seen.add(item.slug)
    return visible


async def list_skills(db: AsyncSession) -> list[Skill]:
    repo = SkillRepository(db)
    return await repo.list_all()


async def list_skill_slugs(db: AsyncSession, *, user: User | None = None) -> list[str]:
    if user is not None:
        return await _list_shared_skill_slugs(db, user)
    result = await db.execute(
        select(Skill.slug).where(Skill.enabled.is_(True)).order_by(Skill.updated_at.desc(), Skill.id.desc())
    )
    return [slug for slug in result.scalars().all() if isinstance(slug, str)]


async def get_skill_dependency_options(
    db: AsyncSession, user: User, slug: str | None = None
) -> dict[str, list[str] | list[dict]]:
    from yuxi.agents.toolkits.service import get_tool_metadata

    def get_tools():
        all_tools = get_tool_metadata()
        return [{"slug": tool["slug"], "name": tool.get("name", tool["slug"])} for tool in all_tools]

    skill_slugs, tool_list, mcp_names = await asyncio.gather(
        list_skill_slugs(db, user=user),
        asyncio.to_thread(get_tools),
        get_enabled_mcp_server_slugs(db=db),
    )
    if slug:
        skill_slugs = [item for item in skill_slugs if item != slug]

    return {
        "tools": tool_list,
        "mcps": mcp_names,
        "skills": skill_slugs,
    }


async def _list_accessible_shared_skills(
    db: AsyncSession,
    user: User,
    *,
    require_enabled: bool = True,
) -> list[Skill]:
    """Return the database Skills accessible to the user under current share scopes."""
    repo = SkillRepository(db)
    items = await repo.list_enabled() if require_enabled else await repo.list_all()
    return [item for item in items if user_can_access_skill(user, item, require_enabled=require_enabled)]


async def _list_shared_skill_slugs(db: AsyncSession, user: User) -> list[str]:
    """Return the shared Skill slugs available for dependency configuration."""
    return [item.slug for item in await _list_accessible_shared_skills(db, user) if isinstance(item.slug, str)]


def _get_all_tool_names() -> list[str]:
    """
    Get all tool names (including buildin and other sources)
    """
    from yuxi.agents.toolkits.service import get_tool_metadata

    all_tools = get_tool_metadata()
    return [tool["slug"] for tool in all_tools]


async def _validate_dependencies(
    *,
    parent: Skill,
    tool_dependencies: list[str],
    mcp_dependencies: list[str],
    skill_dependencies: list[str],
    available_skills: dict[str, Skill],
) -> tuple[list[str], list[str], list[str]]:
    tools = normalize_string_list(tool_dependencies)
    mcps = normalize_string_list(mcp_dependencies)
    skills = normalize_string_list(skill_dependencies)

    available_tools = set(_get_all_tool_names())
    invalid_tools = [name for name in tools if name not in available_tools]
    if invalid_tools:
        raise ValueError(f"Invalid tool dependencies: {', '.join(invalid_tools)}")

    available_mcps = set(await get_enabled_mcp_server_slugs(db=None))
    invalid_mcps = [name for name in mcps if name not in available_mcps]
    if invalid_mcps:
        raise ValueError(f"Invalid MCP dependencies: {', '.join(invalid_mcps)}")

    invalid_skills = [name for name in skills if name not in available_skills]
    if invalid_skills:
        raise ValueError(f"Invalid skill dependencies: {', '.join(invalid_skills)}")

    if parent.slug in skills:
        raise ValueError("skill_dependencies does not allow self-references")

    forbidden_skills = [name for name in skills if not can_skill_depend_on(parent, available_skills[name])]
    if forbidden_skills:
        raise ValueError(f"Permission scope mismatch for skill dependencies: {', '.join(forbidden_skills)}")

    return tools, mcps, skills


async def update_skill_dependencies(
    db: AsyncSession,
    *,
    slug: str,
    tool_dependencies: list[str],
    mcp_dependencies: list[str],
    skill_dependencies: list[str],
    operator: User,
) -> Skill:
    item = await get_manageable_skill_or_raise(db, operator, slug)
    _ensure_non_builtin(item)
    repo = SkillRepository(db)
    skill_items = await _list_accessible_shared_skills(db, operator)
    available_skills = {skill.slug: skill for skill in skill_items}
    tools, mcps, skills = await _validate_dependencies(
        parent=item,
        tool_dependencies=tool_dependencies,
        mcp_dependencies=mcp_dependencies,
        skill_dependencies=skill_dependencies,
        available_skills=available_skills,
    )

    return await repo.update_dependencies(
        item,
        tool_dependencies=tools,
        mcp_dependencies=mcps,
        skill_dependencies=skills,
        updated_by=operator.uid,
    )


def _validate_skill_slug_value(slug: str, *, field_name: str) -> str:
    slug = slug.strip()
    if not slug:
        raise ValueError(f"SKILL.md frontmatter {field_name}")
    if len(slug) > 128:
        raise ValueError(f"SKILL.md frontmatter.{field_name} length cannot exceed 128")
    if not SKILL_NAME_PATTERN.match(slug):
        raise ValueError(
            f"SKILL.md frontmatter.{field_name} must be lowercase letters/numbers/hyphens, and cannot contain consecutive hyphens"
        )
    return slug


def _validate_skill_display_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("SKILL.md frontmatter missing name")
    if len(name) > 128:
        raise ValueError("SKILL.md frontmatter.name length cannot exceed 128")
    return name


def _split_frontmatter(content: str) -> tuple[str, str]:
    if not content.startswith("---"):
        raise ValueError("SKILL.md missing valid frontmatter (--- ... ---)")

    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md missing valid frontmatter (--- ... ---)")

    frontmatter_lines: list[str] = []
    body_start = 0
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            body_start = index + 1
            break
        frontmatter_lines.append(line)
    else:
        raise ValueError("SKILL.md missing valid frontmatter (--- ... ---)")

    frontmatter_raw = "".join(frontmatter_lines)
    body = "".join(lines[body_start:])
    return frontmatter_raw, body


def _parse_skill_markdown(content: str) -> tuple[str, str, str, dict[str, Any]]:
    frontmatter_raw, _body = _split_frontmatter(content)
    try:
        data = yaml.safe_load(frontmatter_raw)
    except yaml.YAMLError as e:
        raise ValueError(f"SKILL.md frontmatter YAML parsing failed: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("SKILL.md frontmatter must be an object")

    name = _validate_skill_display_name(str(data.get("name", "")))
    raw_slug = str(data.get("slug", "")).strip()
    slug = (
        _validate_skill_slug_value(raw_slug, field_name="slug")
        if raw_slug
        else _validate_skill_slug_value(name, field_name="name")
    )
    description = str(data.get("description", "")).strip()
    if not description:
        raise ValueError("SKILL.md frontmatter missing description")

    return slug, name, description, data


def _rewrite_frontmatter_slug(content: str, new_slug: str) -> str:
    frontmatter_raw, body = _split_frontmatter(content)
    data = yaml.safe_load(frontmatter_raw)
    if not isinstance(data, dict):
        raise ValueError("SKILL.md frontmatter must be an object")
    if data.get("slug"):
        data["slug"] = new_slug
    else:
        data["name"] = new_slug
    dumped = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{dumped}\n---\n{body}"


def _validate_zip_paths(zip_file: zipfile.ZipFile) -> None:
    for name in zip_file.namelist():
        pure = PurePosixPath(name)
        if pure.is_absolute():
            raise ValueError(f"ZIP contains unsafe absolute paths: {name}")
        if ".." in pure.parts:
            raise ValueError(f"ZIP contains path traversal fragments: {name}")


async def _generate_available_slug(repo: SkillRepository, base_slug: str) -> str:
    root = get_skills_root_dir()
    if not await repo.exists_slug(base_slug) and not (root / base_slug).exists():
        return base_slug

    idx = 2
    while True:
        candidate = f"{base_slug}-v{idx}"
        if not await repo.exists_slug(candidate) and not (root / candidate).exists():
            return candidate
        idx += 1


def _parse_skill_dir_metadata(source_skill_dir: Path) -> dict[str, Any]:
    skill_md_path = source_skill_dir / "SKILL.md"
    if not skill_md_path.exists() or not skill_md_path.is_file():
        raise ValueError("skill directory missing root-level SKILL.md")

    content = skill_md_path.read_text(encoding="utf-8")
    parsed_slug, parsed_name, parsed_desc, meta = _parse_skill_markdown(content)
    return {
        "slug": parsed_slug,
        "name": parsed_name,
        "description": parsed_desc,
        "tool_dependencies": normalize_string_list(meta.get("tool_dependencies")),
        "mcp_dependencies": normalize_string_list(meta.get("mcp_dependencies")),
        "skill_dependencies": normalize_string_list(meta.get("skill_dependencies")),
    }


def get_personal_skills_root_dir(uid: str) -> Path:
    """Return the personal Skill root directory of the authenticated user."""
    from yuxi.agents.backends.sandbox.paths import sandbox_workspace_dir
    from yuxi.services.mention_search_service import WORKSPACE_THREAD_PLACEHOLDER

    root = sandbox_workspace_dir(WORKSPACE_THREAD_PLACEHOLDER, uid) / WORKSPACE_SKILLS_RELATIVE_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


async def list_personal_skills(uid: str, *, refresh: bool = False) -> PersonalSkillSnapshot:
    """Read the personal Skill Redis snapshot, rescanning the workspace when needed."""
    redis = await get_async_redis_client()
    root = get_personal_skills_root_dir(uid)

    if not refresh:
        cached = await _read_personal_skill_cache(redis, uid, root)
        if cached is not None:
            return cached

    async with _personal_skill_scan_lock(redis, uid):
        if not refresh:
            cached = await _read_personal_skill_cache(redis, uid, root)
            if cached is not None:
                return cached
        return await _scan_and_cache_personal_skills(redis, uid)


async def install_personal_skill_dir(
    uid: str,
    source_dir: Path | str,
    *,
    refresh_cache: bool = True,
) -> ResolvedSkill:
    """Atomically install a Skill into the current user personal workspace."""
    redis = await get_async_redis_client()
    async with _personal_skill_scan_lock(redis, uid):
        item = await asyncio.to_thread(_install_personal_skill_dir_sync, uid, Path(source_dir))
        if refresh_cache:
            try:
                await _scan_and_cache_personal_skills(redis, uid)
            except Exception as exc:
                logger.exception(f"Personal Skill installed but cache refresh failed: uid={uid}, slug={item.slug}")
                raise RuntimeError(
                    "Personal Skill installed, but list cache refresh failed; please refresh manually"
                ) from exc
        return item


async def read_personal_skill_file(uid: str, slug: str, relative_path: str) -> dict[str, Any]:
    """Read a text file inside a personal Skill."""
    skill_dir = _resolve_personal_skill_dir(uid, slug)
    if not skill_dir.is_dir():
        raise ValueError("Personal Skill does not exist")
    target, normalized_path = _resolve_relative_path(skill_dir, relative_path)
    if not target.is_file():
        raise ValueError("File does not exist")
    if not _is_text_path(target):
        raise ValueError("Only text files can be read")
    return {"path": normalized_path, "content": target.read_text(encoding="utf-8")}


async def delete_personal_skill(uid: str, slug: str) -> PersonalSkillSnapshot:
    """Delete the current user personal Skill and refresh the cache immediately."""
    redis = await get_async_redis_client()
    async with _personal_skill_scan_lock(redis, uid):
        skill_dir = _resolve_personal_skill_dir(uid, slug)
        if not skill_dir.is_dir():
            raise ValueError("Personal Skill does not exist")
        await asyncio.to_thread(shutil.rmtree, skill_dir)
        try:
            return await _scan_and_cache_personal_skills(redis, uid)
        except Exception as exc:
            logger.exception(f"Personal Skill deleted but cache refresh failed: uid={uid}, slug={slug}")
            raise RuntimeError(
                "Personal Skill deleted, but list cache refresh failed; please refresh manually"
            ) from exc


def _resolved_shared_skill(item: Skill, *, shadowed_by_personal: bool = False) -> ResolvedSkill:
    """Adapt a database Skill to a unified effective Skill description."""
    source_scope = "builtin" if is_builtin_skill(item) else "shared"
    return ResolvedSkill(
        id=item.id,
        slug=item.slug,
        name=item.name,
        description=item.description,
        source_type=item.source_type,
        source_scope=source_scope,
        source_dir=_resolve_skill_dir(item),
        enabled=bool(item.enabled),
        created_by=item.created_by,
        share_config=normalize_permission_config(
            item.share_config,
        ),
        tool_dependencies=normalize_string_list(item.tool_dependencies),
        mcp_dependencies=normalize_string_list(item.mcp_dependencies),
        skill_dependencies=normalize_string_list(item.skill_dependencies),
        shadowed_by_personal=shadowed_by_personal,
    )


def _resolved_personal_skill(uid: str, root: Path, metadata: dict[str, Any]) -> ResolvedSkill:
    """Adapt personal directory metadata to an effective Skill description without sharing semantics."""
    slug = str(metadata["slug"])
    if not is_valid_skill_slug(slug):
        raise ValueError("Personal Skill cache contains an invalid slug")
    source_dir = ensure_within_root((root / slug).resolve(), root, error_message="Personal Skill path out of bounds")

    return ResolvedSkill(
        id=f"personal:{slug}",
        slug=slug,
        name=str(metadata["name"]),
        description=str(metadata["description"]),
        source_type=PERSONAL_SKILL_SOURCE_TYPE,
        source_scope=PERSONAL_SKILL_SOURCE_TYPE,
        source_dir=source_dir,
        enabled=True,
        created_by=uid,
        share_config=None,
        tool_dependencies=[],
        mcp_dependencies=[],
        skill_dependencies=[],
    )


@asynccontextmanager
async def _personal_skill_scan_lock(redis: Any, uid: str) -> AsyncIterator[None]:
    """Serialize personal Skill scans and file changes for the same user."""
    lock = redis.lock(
        _personal_skill_scan_lock_key(uid),
        timeout=PERSONAL_SKILL_SCAN_LOCK_TIMEOUT_SECONDS,
        blocking_timeout=PERSONAL_SKILL_SCAN_LOCK_WAIT_SECONDS,
    )
    async with lock:
        yield


async def _read_personal_skill_cache(
    redis: Any,
    uid: str,
    root: Path,
) -> PersonalSkillSnapshot | None:
    """Read and validate one user personal Skill cache."""
    cache_key = _personal_skill_cache_key(uid)
    cached = await redis.get(cache_key)
    if not cached:
        return None

    try:
        payload = json.loads(cached)
        if payload.get("schema_version") != 1:
            raise ValueError("Personal Skill cache version mismatch")
        items = [_resolved_personal_skill(uid, root, item) for item in payload["items"]]
        return PersonalSkillSnapshot(
            items=items,
            scanned_at=str(payload["scanned_at"]),
            from_cache=True,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning(f"Personal Skill cache invalid, rescanning: uid={uid}, error={exc}")
        await redis.delete(cache_key)
        return None


async def _scan_and_cache_personal_skills(
    redis: Any,
    uid: str,
) -> PersonalSkillSnapshot:
    """Scan personal Skills and write a five-minute Redis snapshot."""
    items = await asyncio.to_thread(_scan_personal_skills, uid)
    scanned_at = datetime.now(UTC).isoformat()
    payload = {
        "schema_version": 1,
        "scanned_at": scanned_at,
        "items": [{"slug": item.slug, "name": item.name, "description": item.description} for item in items],
    }
    await redis.set(
        _personal_skill_cache_key(uid),
        json.dumps(payload, ensure_ascii=False),
        ex=PERSONAL_SKILL_CACHE_TTL_SECONDS,
    )
    return PersonalSkillSnapshot(items=items, scanned_at=scanned_at, from_cache=False)


def _scan_personal_skills(uid: str) -> list[ResolvedSkill]:
    """Scan and validate the direct subdirectories of the current user personal Skills."""
    root = get_personal_skills_root_dir(uid)
    items: list[ResolvedSkill] = []
    for entry in sorted(root.iterdir(), key=lambda path: path.name):
        if entry.is_symlink() or not entry.is_dir() or not is_valid_skill_slug(entry.name):
            logger.warning(f"Skip invalid personal Skill directory: uid={uid}, name={entry.name}")
            continue
        if _dir_contains_symlink(entry):
            logger.warning(f"Skip personal Skill containing symlinks: uid={uid}, slug={entry.name}")
            continue

        try:
            metadata = _parse_skill_dir_metadata(entry)
            if metadata["slug"] != entry.name:
                raise ValueError("Directory name must match the SKILL.md slug")
            items.append(_resolved_personal_skill(uid, root, metadata))
        except Exception as exc:
            logger.warning(f"Skip unparsable personal Skill: uid={uid}, slug={entry.name}, error={exc}")
    return items


def _install_personal_skill_dir_sync(uid: str, source_dir: Path) -> ResolvedSkill:
    """Atomically copy a Skill into the personal directory while holding the user-level lock."""
    root = get_personal_skills_root_dir(uid)
    source_dir = source_dir.resolve()
    if source_dir.is_symlink() or _dir_contains_symlink(source_dir):
        raise ValueError("Personal Skills must not contain symlinks")

    metadata = _parse_skill_dir_metadata(source_dir)
    slug = metadata["slug"]
    target_dir = root / slug
    if target_dir.exists() or target_dir.is_symlink():
        raise ValueError(f"Personal workspace already has a Skill with the same name: {slug}")

    def _validate_slug_unchanged(copied_dir: Path) -> None:
        copied_metadata = _parse_skill_dir_metadata(copied_dir)
        if copied_metadata["slug"] != slug:
            raise ValueError("Personal Skill slug changed during copy")

    _replace_skill_target(target_dir, source_dir, validate=_validate_slug_unchanged)
    return _resolved_personal_skill(uid, root, metadata)


def _resolve_personal_skill_dir(uid: str, slug: str) -> Path:
    """Safely resolve the current user personal Skill directory."""
    if not is_valid_skill_slug(slug):
        raise ValueError("Invalid skill slug")
    root = get_personal_skills_root_dir(uid)
    target = ensure_within_root((root / slug).resolve(), root, error_message="Personal Skill path out of bounds")
    if target.is_symlink():
        raise ValueError("Invalid personal Skill path")
    return target


def _personal_skill_cache_key(uid: str) -> str:
    """Return the personal Skill cache key for the current user."""
    return f"{PERSONAL_SKILL_CACHE_PREFIX}{uid}"


def _personal_skill_scan_lock_key(uid: str) -> str:
    """Return the personal Skill scan lock key for the current user."""
    return f"{PERSONAL_SKILL_SCAN_LOCK_PREFIX}{uid}"


async def _stage_skill_draft_item(
    repo: SkillRepository,
    *,
    source_skill_dir: Path,
    draft_items_dir: Path,
) -> dict[str, Any]:
    item_id = uuid.uuid4().hex
    item_dir = draft_items_dir / item_id
    shutil.copytree(source_skill_dir, item_dir, symlinks=False)
    parsed = _parse_skill_dir_metadata(item_dir)
    final_slug = await _generate_available_slug(repo, parsed["slug"])
    return {
        "draft_item_id": item_id,
        "source_dir": f"items/{item_id}",
        "slug": final_slug,
        "name": parsed["name"],
        "original_name": parsed["slug"],
        "description": parsed["description"],
        "tool_dependencies": parsed["tool_dependencies"],
        "mcp_dependencies": parsed["mcp_dependencies"],
        "skill_dependencies": parsed["skill_dependencies"],
        "warnings": [f"Original slug {parsed['slug']} already exists, will be installed as {final_slug}"]
        if final_slug != parsed["slug"]
        else [],
        "success": True,
    }


def _build_default_share_payload(operator: User) -> dict[str, Any]:
    default_share_config = normalize_skill_share_config(
        None,
        operator_uid=operator.uid,
        allowed_access_levels=set(get_allowed_skill_access_levels(operator)),
    )
    return {
        "default_share_config": default_share_config,
        "allowed_access_levels": get_allowed_skill_access_levels(operator),
    }


async def _import_skill_dir_impl(
    db: AsyncSession,
    *,
    source_skill_dir: Path,
    created_by: str | None,
    source_type: str,
    share_config: dict,
) -> Skill:
    repo = SkillRepository(db)
    skills_root = get_skills_root_dir()
    parsed = _parse_skill_dir_metadata(source_skill_dir)
    final_slug = await _generate_available_slug(repo, parsed["slug"])
    with tempfile.TemporaryDirectory(prefix=".skill-import-", dir=str(skills_root.parent)) as temp_root:
        stage_dir = Path(temp_root) / "stage"
        shutil.copytree(source_skill_dir, stage_dir)

        if final_slug != parsed["slug"]:
            content = (stage_dir / "SKILL.md").read_text(encoding="utf-8")
            (stage_dir / "SKILL.md").write_text(_rewrite_frontmatter_slug(content, final_slug), encoding="utf-8")

        temp_target = skills_root / f".{final_slug}.tmp-{uuid.uuid4().hex[:8]}"
        if temp_target.exists():
            await asyncio.to_thread(shutil.rmtree, temp_target)
        shutil.move(str(stage_dir), str(temp_target))

        final_dir = skills_root / final_slug
        if final_dir.exists():
            await asyncio.to_thread(shutil.rmtree, temp_target, ignore_errors=True)
            raise ValueError(f"skill directory conflict, please try again: {final_slug}")
        temp_target.rename(final_dir)

        try:
            item = await repo.create(
                slug=final_slug,
                name=parsed["name"],
                description=parsed["description"],
                source_type=source_type,
                tool_dependencies=parsed["tool_dependencies"],
                mcp_dependencies=parsed["mcp_dependencies"],
                skill_dependencies=parsed["skill_dependencies"],
                dir_path=(Path("skills") / final_slug).as_posix(),
                share_config=share_config,
                enabled=True,
                created_by=created_by,
            )
        except Exception:
            await asyncio.to_thread(shutil.rmtree, final_dir, ignore_errors=True)
            raise

    return item


def _resolve_skill_dir(item: Skill) -> Path:
    dir_path = Path(item.dir_path)
    if dir_path.is_absolute():
        return dir_path
    return (Path(sys_config.save_dir) / dir_path).resolve()


def _resolve_relative_path(skill_dir: Path, relative_path: str, *, allow_root: bool = False) -> tuple[Path, str]:
    rel = (relative_path or "").strip().replace("\\", "/")
    rel = rel.lstrip("/")
    if not rel and not allow_root:
        raise ValueError("Đường dẫn không được để trống")
    pure = PurePosixPath(rel) if rel else PurePosixPath(".")
    if ".." in pure.parts:
        raise ValueError("Đường dẫn không hợp lệ: Không cho phép tham chiếu đường dẫn cấp trên")

    target = ensure_within_root(
        (skill_dir / pure).resolve(),
        skill_dir,
        error_message="Đường dẫn không hợp lệ: Từ chối truy cập vượt quá giới hạn",
    )

    return target, rel


def _is_text_path(path: Path) -> bool:
    if path.name == "SKILL.md":
        return True
    suffix = path.suffix.lower()
    return suffix in TEXT_FILE_EXTENSIONS


def _build_tree(path: Path, base_dir: Path) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        rel = child.relative_to(base_dir).as_posix()
        if child.is_dir():
            children.append(
                {
                    "name": child.name,
                    "path": rel,
                    "is_dir": True,
                    "children": _build_tree(child, base_dir),
                }
            )
        else:
            children.append(
                {
                    "name": child.name,
                    "path": rel,
                    "is_dir": False,
                }
            )
    return children


async def prepare_skill_upload(
    db: AsyncSession,
    *,
    filename: str,
    file_bytes: bytes,
    operator: User,
) -> dict[str, Any]:
    normalized_filename = filename.lower()
    is_zip_upload = normalized_filename.endswith(".zip")
    is_skill_md_upload = normalized_filename.endswith("skill.md")
    if not is_zip_upload and not is_skill_md_upload:
        raise ValueError("Chỉ hỗ trợ tải lên file .zip hoặc SKILL.md")

    repo = SkillRepository(db)
    draft_dir = get_skill_drafts_root_dir() / str(uuid.uuid4())
    items_dir = draft_dir / "items"
    draft_dir.mkdir(parents=True, exist_ok=False)
    items_dir.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(prefix=".skill-prepare-", dir=str(get_skills_root_dir().parent)) as temp_root:
            extract_dir = Path(temp_root) / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)
            if is_zip_upload:
                zip_path = Path(temp_root) / "upload.zip"
                zip_path.write_bytes(file_bytes)
                with zipfile.ZipFile(zip_path, "r") as zf:
                    _validate_zip_paths(zf)
                    zf.extractall(extract_dir)
                skill_md_files = list(extract_dir.rglob("SKILL.md"))
                if len(skill_md_files) != 1:
                    raise ValueError("ZIP phải và chỉ được chứa một kỹ năng (phát hiện một SKILL.md)")
                source_skill_dir = skill_md_files[0].parent
            else:
                source_skill_dir = extract_dir
                (source_skill_dir / "SKILL.md").write_bytes(file_bytes)

            item = await _stage_skill_draft_item(repo, source_skill_dir=source_skill_dir, draft_items_dir=items_dir)

        data = {
            "draft_id": draft_dir.name,
            "created_by": operator.uid,
            "source_type": "upload",
            "source": filename,
            "created_at": time.time(),
            "expires_at": time.time() + SKILL_DRAFT_TTL_SECONDS,
            "items": [item],
            **_build_default_share_payload(operator),
        }
        (draft_dir / "metadata.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data
    except Exception:
        shutil.rmtree(draft_dir, ignore_errors=True)
        raise


async def prepare_remote_skill_install(
    db: AsyncSession,
    *,
    source: str,
    skills: list[str],
    operator: User,
) -> dict[str, Any]:
    from yuxi.agents.skills.remote_install import prepare_remote_skills_batch

    repo = SkillRepository(db)
    draft_dir = get_skill_drafts_root_dir() / str(uuid.uuid4())
    items_dir = draft_dir / "items"
    draft_dir.mkdir(parents=True, exist_ok=False)
    items_dir.mkdir(parents=True, exist_ok=True)

    preparation = None
    try:
        preparation = await prepare_remote_skills_batch(source=source, skills=skills)
        items: list[dict[str, Any]] = []
        for result in preparation.results:
            slug = result.get("slug", "")
            if not result.get("success"):
                item = {"slug": slug, "success": False, "error": result.get("error", "Cài đặt thất bại")}
                items.append(item)
                continue

            try:
                item = await _stage_skill_draft_item(
                    repo,
                    source_skill_dir=Path(result["source_dir"]),
                    draft_items_dir=items_dir,
                )
            except Exception as e:
                item = {"slug": slug, "success": False, "error": str(e)}
                items.append(item)
                continue

            items.append(item)

        data = {
            "draft_id": draft_dir.name,
            "created_by": operator.uid,
            "source_type": "remote",
            "source": source,
            "created_at": time.time(),
            "expires_at": time.time() + SKILL_DRAFT_TTL_SECONDS,
            "items": items,
            **_build_default_share_payload(operator),
        }
        (draft_dir / "metadata.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data
    except Exception:
        shutil.rmtree(draft_dir, ignore_errors=True)
        raise
    finally:
        if preparation is not None:
            await preparation.cleanup()


async def confirm_skill_install_draft(
    db: AsyncSession,
    *,
    draft_id: str,
    share_config: dict | None,
    slugs: list[str] | None = None,
    operator: User,
) -> list[dict[str, Any]]:
    draft_dir, data, draft_items = _load_and_select_draft_items(draft_id, slugs, operator)
    source_type = data.get("source_type")

    normalized_share_config = normalize_skill_share_config(
        share_config,
        operator_uid=operator.uid,
        source_type=source_type,
        allowed_access_levels=set(get_allowed_skill_access_levels(operator)),
    )

    repo = SkillRepository(db)
    skills_root = get_skills_root_dir()
    results: list[dict[str, Any]] = []

    for draft_item in draft_items:
        slug = str(draft_item.get("slug") or "").strip()
        if not draft_item.get("success", True):
            result = {"slug": slug, "success": False, "error": draft_item.get("error", "Cài đặt thất bại")}
            results.append(result)
            continue

        if not is_valid_skill_slug(slug):
            result = {"slug": slug, "success": False, "error": "Skill slug không hợp lệ"}
            results.append(result)
            continue
        if await repo.exists_slug(slug) or (skills_root / slug).exists():
            result = {
                "slug": slug,
                "success": False,
                "error": "Skill slug đã bị chiếm dụng, vui lòng phân tích và cài đặt lại",
            }
            results.append(result)
            continue

        source_dir = (draft_dir / str(draft_item.get("source_dir", ""))).resolve()
        try:
            source_dir.relative_to(draft_dir.resolve())
        except ValueError:
            result = {"slug": slug, "success": False, "error": "Đường dẫn bản nháp cài đặt không hợp lệ"}
            results.append(result)
            continue

        try:
            parsed = _parse_skill_dir_metadata(source_dir)
            with tempfile.TemporaryDirectory(prefix=".skill-confirm-", dir=str(skills_root.parent)) as temp_root:
                stage_dir = Path(temp_root) / "stage"
                shutil.copytree(source_dir, stage_dir)
                if parsed["slug"] != slug:
                    content = (stage_dir / "SKILL.md").read_text(encoding="utf-8")
                    (stage_dir / "SKILL.md").write_text(_rewrite_frontmatter_slug(content, slug), encoding="utf-8")

                temp_target = skills_root / f".{slug}.tmp-{uuid.uuid4().hex[:8]}"
                shutil.move(str(stage_dir), str(temp_target))
                final_dir = skills_root / slug
                if final_dir.exists():
                    shutil.rmtree(temp_target, ignore_errors=True)
                    result = {
                        "slug": slug,
                        "success": False,
                        "error": "Skill slug đã bị chiếm dụng, vui lòng phân tích và cài đặt lại",
                    }
                    results.append(result)
                    continue
                temp_target.rename(final_dir)

                try:
                    item = await repo.create(
                        slug=slug,
                        name=parsed["name"],
                        description=parsed["description"],
                        source_type=source_type,
                        tool_dependencies=parsed["tool_dependencies"],
                        mcp_dependencies=parsed["mcp_dependencies"],
                        skill_dependencies=parsed["skill_dependencies"],
                        dir_path=(Path("skills") / slug).as_posix(),
                        share_config=normalized_share_config,
                        enabled=True,
                        created_by=operator.uid,
                    )
                    result = {"slug": item.slug, "success": True, "skill": item.to_dict()}
                    results.append(result)
                except Exception:
                    shutil.rmtree(final_dir, ignore_errors=True)
                    raise
        except Exception as e:
            if hasattr(db, "rollback"):
                await db.rollback()
            result = {"slug": slug, "success": False, "error": str(e)}
            results.append(result)

    if any(item.get("success") for item in results):
        shutil.rmtree(draft_dir, ignore_errors=True)
    return results


async def confirm_personal_skill_install_draft(
    *,
    draft_id: str,
    slugs: list[str] | None,
    operator: User,
) -> list[dict[str, Any]]:
    """Confirm the draft and install the selected Skills into the current user personal workspace."""
    draft_dir, _data, draft_items = _load_and_select_draft_items(draft_id, slugs, operator)

    results: list[dict[str, Any]] = []
    for draft_item in draft_items:
        requested_slug = str(draft_item.get("slug") or "").strip()
        personal_slug = str(draft_item.get("original_name") or requested_slug).strip()
        if not draft_item.get("success", True):
            results.append(
                {
                    "slug": personal_slug,
                    "requested_slug": requested_slug,
                    "success": False,
                    "error": draft_item.get("error", "Install failed"),
                }
            )
            continue
        if not is_valid_skill_slug(personal_slug):
            results.append(
                {
                    "slug": personal_slug,
                    "requested_slug": requested_slug,
                    "success": False,
                    "error": "Invalid skill slug",
                }
            )
            continue

        source_dir = (draft_dir / str(draft_item.get("source_dir", ""))).resolve()
        try:
            source_dir.relative_to(draft_dir.resolve())
            parsed = _parse_skill_dir_metadata(source_dir)
            if parsed["slug"] != personal_slug:
                raise ValueError("Personal Skill slug in the install draft is inconsistent")
            item = await install_personal_skill_dir(
                str(operator.uid),
                source_dir,
                refresh_cache=False,
            )
            results.append(
                {
                    "slug": item.slug,
                    "requested_slug": requested_slug,
                    "success": True,
                    "skill": item.to_dict(),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "slug": personal_slug,
                    "requested_slug": requested_slug,
                    "success": False,
                    "error": str(exc),
                }
            )

    if any(item.get("success") for item in results):
        await list_personal_skills(str(operator.uid), refresh=True)
        shutil.rmtree(draft_dir, ignore_errors=True)
    return results


async def discard_skill_install_draft(*, draft_id: str, operator: User) -> None:
    draft_dir, data = _load_skill_draft(draft_id)
    if data.get("created_by") != operator.uid and operator.role not in ADMIN_ROLES:
        raise ValueError("Không có quyền xóa bản nháp cài đặt này")
    shutil.rmtree(draft_dir, ignore_errors=True)


async def import_skill_dir(
    db: AsyncSession,
    *,
    source_dir: Path | str,
    created_by: str | None,
    source_type: str = "upload",
    share_config: dict | None = None,
) -> Skill:
    source_skill_dir = Path(source_dir).resolve()
    tmp_root = Path(tempfile.gettempdir()).resolve()
    if not source_skill_dir.is_relative_to(tmp_root):
        raise ValueError("Đường dẫn thư mục kỹ năng không hợp lệ")
    if not source_skill_dir.exists() or not source_skill_dir.is_dir():
        raise ValueError("Thư mục kỹ năng không tồn tại")
    return await _import_skill_dir_impl(
        db,
        source_skill_dir=source_skill_dir,
        created_by=created_by,
        source_type=source_type,
        share_config=normalize_skill_share_config(
            share_config,
            operator_uid=created_by or "",
            source_type=source_type,
        ),
    )


async def get_skill_or_raise(db: AsyncSession, slug: str) -> Skill:
    slug = slug.strip() if isinstance(slug, str) else ""
    if not is_valid_skill_slug(slug):
        raise ValueError("Skill slug không hợp lệ")

    repo = SkillRepository(db)
    item = await repo.get_by_slug(slug)
    if not item:
        raise ValueError(f"Kỹ năng '{slug}' không tồn tại")
    return item


async def get_accessible_skill_or_raise(db: AsyncSession, user: User, slug: str) -> Skill:
    item = await get_skill_or_raise(db, slug)
    if not user_can_access_skill(user, item):
        raise ValueError(f"Kỹ năng '{slug}' không tồn tại hoặc không có quyền truy cập")
    return item


async def get_management_readable_skill_or_raise(db: AsyncSession, user: User, slug: str) -> Skill:
    item = await get_skill_or_raise(db, slug)
    if not user_can_manage_skill(user, item) and not user_can_access_skill(user, item):
        raise ValueError(f"Kỹ năng '{slug}' không tồn tại hoặc không có quyền truy cập")
    return item


async def get_manageable_skill_or_raise(db: AsyncSession, user: User, slug: str) -> Skill:
    item = await get_skill_or_raise(db, slug)
    if not user_can_manage_skill(user, item):
        raise ValueError(f"Kỹ năng '{slug}' không tồn tại hoặc không có quyền quản lý")
    return item


async def get_skill_tree(db: AsyncSession, slug: str) -> list[dict[str, Any]]:
    item = await get_skill_or_raise(db, slug)
    skill_dir = _resolve_skill_dir(item)
    if not skill_dir.exists() or not skill_dir.is_dir():
        raise ValueError(f"Thư mục kỹ năng không tồn tại: {item.dir_path}")
    return _build_tree(skill_dir, skill_dir)


async def read_skill_file(db: AsyncSession, slug: str, relative_path: str) -> dict[str, Any]:
    item = await get_skill_or_raise(db, slug)
    skill_dir = _resolve_skill_dir(item)
    target, rel = _resolve_relative_path(skill_dir, relative_path)
    if not target.exists() or not target.is_file():
        raise ValueError(f"Tệp không tồn tại: {relative_path}")
    if not _is_text_path(target):
        raise ValueError("Chỉ hỗ trợ đọc file văn bản")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"Định dạng tệp không được hỗ trợ (chỉ hỗ trợ UTF-8): {e}") from e

    return {"path": rel, "content": content}


async def create_skill_node(
    db: AsyncSession,
    *,
    slug: str,
    relative_path: str,
    is_dir: bool,
    content: str | None,
    updated_by: str | None,
) -> None:
    item = await get_skill_or_raise(db, slug)
    if is_builtin_skill(item):
        raise ValueError("Không cho phép sửa đổi trực tiếp file của skill tích hợp")
    skill_dir = _resolve_skill_dir(item)
    target, _ = _resolve_relative_path(skill_dir, relative_path)
    if target.exists():
        raise ValueError("Mục tiêu đã tồn tại")

    if is_dir:
        target.mkdir(parents=True, exist_ok=False)
        return

    if not _is_text_path(target):
        raise ValueError("Chỉ hỗ trợ tạo file văn bản")

    target.parent.mkdir(parents=True, exist_ok=True)

    # Write to file first, then update metadata
    target.write_text(content or "", encoding="utf-8")

    await _update_skill_metadata_if_skills_md(db, item, content or "", skill_dir, target, updated_by)


async def update_skill_file(
    db: AsyncSession,
    *,
    slug: str,
    relative_path: str,
    content: str,
    updated_by: str | None,
) -> None:
    item = await get_skill_or_raise(db, slug)
    if is_builtin_skill(item):
        raise ValueError("Không cho phép sửa đổi trực tiếp file của skill tích hợp")
    skill_dir = _resolve_skill_dir(item)
    target, _ = _resolve_relative_path(skill_dir, relative_path)
    if not target.exists() or not target.is_file():
        raise ValueError("File không tồn tại")
    if not _is_text_path(target):
        raise ValueError("Chỉ hỗ trợ chỉnh sửa file văn bản")

    await _update_skill_metadata_if_skills_md(db, item, content, skill_dir, target, updated_by)

    target.write_text(content, encoding="utf-8")


async def _update_skill_metadata_if_skills_md(
    db: AsyncSession,
    item: Skill,
    content: str,
    skill_dir: Path,
    target: Path,
    updated_by: str | None,
) -> None:
    """If the target file is SKILL.md, then parse and update the metadata"""
    if target.name == "SKILL.md" and target.parent == skill_dir:
        parsed_slug, parsed_name, parsed_desc, _ = _parse_skill_markdown(content)
        if parsed_slug != item.slug:
            raise ValueError("SKILL.md frontmatter.slug phải khớp với skill slug")
        repo = SkillRepository(db)
        await repo.update_metadata(item, name=parsed_name, description=parsed_desc, updated_by=updated_by)


async def delete_skill_node(db: AsyncSession, *, slug: str, relative_path: str) -> None:
    item = await get_skill_or_raise(db, slug)
    if is_builtin_skill(item):
        raise ValueError("Không cho phép sửa đổi trực tiếp file của skill tích hợp")
    skill_dir = _resolve_skill_dir(item)
    target, rel = _resolve_relative_path(skill_dir, relative_path, allow_root=False)
    if not target.exists():
        raise ValueError("Mục tiêu không tồn tại")

    if rel == "SKILL.md":
        raise ValueError("Không được phép xóa thư mục gốc SKILL.md")

    if target.is_dir():
        await asyncio.to_thread(shutil.rmtree, target)
    else:
        target.unlink()


async def export_skill_zip(db: AsyncSession, slug: str) -> tuple[str, str]:
    item = await get_skill_or_raise(db, slug)
    skill_dir = _resolve_skill_dir(item)
    if not skill_dir.exists() or not skill_dir.is_dir():
        raise ValueError("Thư mục kỹ năng không tồn tại")

    fd, export_path = tempfile.mkstemp(prefix=f"skill-{slug}-", suffix=".zip")
    Path(export_path).unlink(missing_ok=True)
    export_file = Path(export_path)
    try:
        with zipfile.ZipFile(export_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in skill_dir.rglob("*"):
                arcname = Path(slug) / p.relative_to(skill_dir)
                zf.write(p, arcname.as_posix())
    except Exception:
        export_file.unlink(missing_ok=True)
        raise
    return export_path, f"{slug}.zip"


async def delete_skill(db: AsyncSession, *, slug: str) -> None:
    repo = SkillRepository(db)
    item = await repo.get_by_slug(slug, for_update=True)
    if not item:
        raise ValueError(f"Kỹ năng '{slug}' không tồn tại")
    _ensure_non_builtin(item)

    skill_dir = _resolve_skill_dir(item)
    trash_dir: Path | None = None

    if skill_dir.exists():
        trash_dir = skill_dir.with_name(f".deleted-{slug}-{uuid.uuid4().hex[:8]}")
        skill_dir.rename(trash_dir)

    try:
        await repo.delete(item)
    except Exception:
        if trash_dir and trash_dir.exists():
            trash_dir.rename(skill_dir)
        raise

    if trash_dir and trash_dir.exists():
        await asyncio.to_thread(shutil.rmtree, trash_dir, ignore_errors=True)


async def delete_skills_batch(db: AsyncSession, *, slugs: list[str]) -> list[dict]:
    """Deleting multiple skills in batches (independent sub-transactions and rollbacks for a single skill)."""
    if len(slugs) > 50:
        raise ValueError("Số lượng kỹ năng xóa hàng loạt không được vượt quá 50")
    results = []
    for slug in slugs:
        try:
            await delete_skill(db, slug=slug)
            results.append({"slug": slug, "success": True})
        except Exception as e:
            if hasattr(db, "rollback"):
                await db.rollback()
            results.append({"slug": slug, "success": False, "error": str(e)})
    return results


async def update_skill_share_config(
    db: AsyncSession,
    *,
    slug: str,
    share_config: dict | None,
    operator: User,
) -> Skill:
    item = await get_manageable_skill_or_raise(db, operator, slug)
    _ensure_non_builtin(item)
    normalized = normalize_skill_share_config(
        share_config,
        operator_uid=operator.uid,
        source_type=item.source_type,
        allowed_access_levels=set(get_allowed_skill_access_levels(operator)),
    )
    return await SkillRepository(db).update_share_config(item, share_config=normalized, updated_by=operator.uid)


async def update_skill_enabled(db: AsyncSession, *, slug: str, enabled: bool, operator: User) -> Skill:
    item = await get_manageable_skill_or_raise(db, operator, slug)
    return await SkillRepository(db).update_enabled(item, enabled=enabled, updated_by=operator.uid)


def list_builtin_skill_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for raw_spec in get_builtin_skill_specs():
        slug = str(getattr(raw_spec, "slug", "")).strip()
        source_dir = Path(str(getattr(raw_spec, "source_dir", ""))).resolve()
        configured_description = str(getattr(raw_spec, "description", "")).strip()
        version = str(getattr(raw_spec, "version", "1.0.0")).strip() or "1.0.0"
        configured_tools = normalize_string_list(getattr(raw_spec, "tool_dependencies", None))
        configured_mcps = normalize_string_list(getattr(raw_spec, "mcp_dependencies", None))
        configured_skills = normalize_string_list(getattr(raw_spec, "skill_dependencies", None))

        if not is_valid_skill_slug(slug):
            raise ValueError(f"Skill slug tích hợp không hợp lệ: {slug}")
        if not source_dir.exists() or not source_dir.is_dir():
            logger.warning(f"Skip non-existent built-in skill directories: {source_dir}")
            continue

        skill_md = source_dir / "SKILL.md"
        if not skill_md.exists():
            raise ValueError(f"Skill tích hợp thiếu SKILL.md: {source_dir}")

        content = skill_md.read_text(encoding="utf-8")
        parsed_slug, parsed_name, parsed_desc, meta = _parse_skill_markdown(content)
        if parsed_slug != slug:
            raise ValueError(f"frontmatter.slug của skill tích hợp phải bằng slug: {slug}")

        specs.append(
            {
                "slug": slug,
                "name": parsed_name,
                "description": configured_description or parsed_desc,
                "version": version,
                "tool_dependencies": configured_tools or normalize_string_list(meta.get("tool_dependencies")),
                "mcp_dependencies": configured_mcps or normalize_string_list(meta.get("mcp_dependencies")),
                "skill_dependencies": configured_skills or normalize_string_list(meta.get("skill_dependencies")),
                "content_hash": _compute_dir_hash(source_dir),
                "source_dir": source_dir,
            }
        )

    return specs


async def init_builtin_skills(db: AsyncSession, *, created_by: str = "system") -> list[Skill]:
    repo = SkillRepository(db)
    synced_items: list[Skill] = []

    for spec in list_builtin_skill_specs():
        slug = spec["slug"]
        existing = await repo.get_by_slug(slug)
        if existing and not is_builtin_skill(existing):
            raise ValueError(f"Skill tích hợp '{slug}' xung đột với skill không tích hợp đã tồn tại")

        target_dir = get_skills_root_dir() / slug
        _replace_skill_target(target_dir, Path(spec["source_dir"]))

        if existing:
            if existing.name != spec["name"] or existing.description != spec["description"]:
                await repo.update_metadata(
                    existing,
                    name=spec["name"],
                    description=spec["description"],
                    updated_by=created_by,
                )
            if (
                normalize_string_list(existing.tool_dependencies or []) != spec["tool_dependencies"]
                or normalize_string_list(existing.mcp_dependencies or []) != spec["mcp_dependencies"]
                or normalize_string_list(existing.skill_dependencies or []) != spec["skill_dependencies"]
            ):
                await repo.update_dependencies(
                    existing,
                    tool_dependencies=spec["tool_dependencies"],
                    mcp_dependencies=spec["mcp_dependencies"],
                    skill_dependencies=spec["skill_dependencies"],
                    updated_by=created_by,
                )
            synced_items.append(
                await repo.update_builtin_install(
                    existing,
                    version=spec["version"],
                    content_hash=spec["content_hash"],
                    updated_by=created_by,
                )
            )
            continue

        synced_items.append(
            await repo.create(
                slug=slug,
                name=spec["name"],
                description=spec["description"],
                source_type="builtin",
                tool_dependencies=spec["tool_dependencies"],
                mcp_dependencies=spec["mcp_dependencies"],
                skill_dependencies=spec["skill_dependencies"],
                dir_path=_build_builtin_skill_dir_path(slug),
                share_config=BUILTIN_SKILL_SHARE_CONFIG.copy(),
                enabled=True,
                version=spec["version"],
                content_hash=spec["content_hash"],
                created_by=created_by or BUILTIN_SKILL_OPERATOR,
            )
        )

    return synced_items
