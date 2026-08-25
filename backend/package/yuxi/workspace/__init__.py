"""Workspace path and workdir helpers for Project persistence.

This is a thin adapter layer over the workspace infrastructure already owned by
the fork's sandbox path module (``yuxi.agents.backends.sandbox.paths``). It adds
the Project-specific path normalization helpers required by ``project_service``
without re-introducing the upstream fd-based workspace module.
"""

from yuxi.workspace.paths import (
    normalize_linked_workdir_path,
    normalize_managed_workdir_path,
    normalize_workdir_path,
)

__all__ = [
    "normalize_linked_workdir_path",
    "normalize_managed_workdir_path",
    "normalize_workdir_path",
]
