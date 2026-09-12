"""Unit tests for Project persistence path helpers and service validation."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from yuxi.services.project_service import MAX_PROJECT_NAME_LENGTH, _normalize_project_name
from yuxi.workspace.paths import (
    normalize_linked_workdir_path,
    normalize_managed_workdir_path,
    normalize_workdir_path,
)
from yuxi.workspace.workdir import Workdir


def test_normalize_workdir_path_accepts_relative_posix():
    assert normalize_workdir_path("projects/abc") == "projects/abc"
    assert normalize_workdir_path("  docs/nested/file.md ") == "docs/nested/file.md"
    assert normalize_workdir_path("a/b/c") == "a/b/c"


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("", "empty"),
        ("   ", "blank"),
        ("/absolute/path", "absolute"),
        ("C:\\\\windows", "windows drive"),
        ("a//b", "empty component"),
        ("a/../b", "parent traversal"),
        ("./a", "current component"),
    ],
)
def test_normalize_workdir_path_rejects_invalid(raw, reason):
    with pytest.raises(ValueError):
        normalize_workdir_path(raw)


def test_normalize_linked_workdir_path_delegates_to_relative_rules():
    assert normalize_linked_workdir_path("linked/dir") == "linked/dir"
    with pytest.raises(ValueError):
        normalize_linked_workdir_path("/etc")


def test_normalize_managed_workdir_path_accepts_projects_uuid():
    value = "projects/123e4567-e89b-12d3-a456-426614174000"
    assert normalize_managed_workdir_path(value) == value


@pytest.mark.parametrize(
    "raw",
    [
        "not-projects/123e4567-e89b-12d3-a456-426614174000",
        "projects",
        "projects/not-a-uuid",
        "projects/uuid/extra",
        "/projects/123e4567-e89b-12d3-a456-426614174000",
    ],
)
def test_normalize_managed_workdir_path_rejects_invalid(raw):
    with pytest.raises(ValueError):
        normalize_managed_workdir_path(raw)


def test_workdir_open_existing_raises_for_missing_directory(tmp_path, monkeypatch):
    from yuxi.agents.backends.sandbox import paths as sandbox_paths
    import yuxi.workspace.workdir as workdir_module

    monkeypatch.setattr(sandbox_paths, "global_user_data_dir", lambda uid: tmp_path / uid)
    monkeypatch.setattr(workdir_module, "global_user_data_dir", lambda uid: tmp_path / uid)

    with pytest.raises(FileNotFoundError):
        Workdir.open_existing("user1", "missing/dir")

    # Creating the directory makes the same path openable
    (tmp_path / "user1" / "existing").mkdir(parents=True)
    workdir = Workdir.open_existing("user1", "existing")
    assert workdir.workdir_path == "existing"


def test_normalize_project_name_strips_and_validates():
    assert _normalize_project_name("  My Project  ", required=False) == "My Project"
    assert _normalize_project_name(None, required=False) is None

    with pytest.raises(HTTPException) as exc:
        _normalize_project_name("   ", required=True)
    assert exc.value.status_code == 422

    with pytest.raises(HTTPException) as exc:
        _normalize_project_name("x" * (MAX_PROJECT_NAME_LENGTH + 1), required=False)
    assert exc.value.status_code == 422