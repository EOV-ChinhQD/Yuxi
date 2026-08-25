from __future__ import annotations

import uuid
from pathlib import PurePosixPath

from yuxi.agents.backends.sandbox.paths import global_user_data_dir

WORKDIR_PROJECTS_DIR_NAME = "projects"


def _as_posix_relative(raw: str, *, label: str) -> PurePosixPath:
    """Validate and return a safe relative POSIX path from user input."""
    if not raw:
        raise ValueError(f"{label} is required")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or "\\" in raw or "://" in raw:
        raise ValueError(f"{label} must be a relative POSIX path")
    if any(part in {"", ".", ".."} for part in raw.split("/")):
        raise ValueError(f"{label} contains invalid path components")
    return pure


def normalize_workdir_path(workdir_path: str) -> str:
    """Normalize a database UserWorkspace-relative Workdir path."""
    return _as_posix_relative(str(workdir_path or "").strip(), label="workdir_path").as_posix()


def normalize_linked_workdir_path(workdir_path: str) -> str:
    """Normalize a user-selected linked Workdir (workspace root enforced by relative-path rules)."""
    return normalize_workdir_path(workdir_path)


def normalize_managed_workdir_path(workdir_path: str) -> str:
    """Normalize a server-managed ``projects/<uuid>`` Workdir path."""
    raw = str(workdir_path or "").strip()
    pure = _as_posix_relative(raw, label="managed workdir_path")
    if len(pure.parts) != 2 or pure.parts[0] != WORKDIR_PROJECTS_DIR_NAME:
        raise ValueError("managed workdir_path must use projects/<uuid>")
    try:
        workdir_id = uuid.UUID(pure.parts[1])
    except ValueError as exc:
        raise ValueError("managed workdir_path must use projects/<uuid>") from exc
    return f"{WORKDIR_PROJECTS_DIR_NAME}/{workdir_id}"


def ensure_managed_workdir_exists(uid: str, workdir_path: str) -> None:
    """Create a managed ``projects/<uuid>`` directory under the user's shared workspace if missing."""
    normalized = normalize_managed_workdir_path(workdir_path)
    target_dir = global_user_data_dir(uid) / normalized
    target_dir.mkdir(parents=True, exist_ok=True)
