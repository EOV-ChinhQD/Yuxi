"""Workdir entry used by Project persistence.

Adapted from upstream ``yuxi.workspace.workdir``; scoped to existence validation
over the fork's shared user-data directory. The heavy fd-based filesystem layer
of upstream is intentionally not ported.
"""

from __future__ import annotations


from yuxi.agents.backends.sandbox.paths import global_user_data_dir
from yuxi.workspace.paths import normalize_workdir_path


class Workdir:
    """A user workspace directory bound to a Project."""

    def __init__(self, uid: str, workdir_path: str) -> None:
        self.uid = str(uid)
        self.workdir_path = normalize_workdir_path(workdir_path)
        self.root = global_user_data_dir(self.uid)
        self.absolute = self.root / self.workdir_path
        # Specialized guard: ensure absolute stays within user root and no symlink escape
        try:
            resolved_root = self.root.resolve()
            resolved_abs = self.absolute.resolve() if self.absolute.exists() else self.absolute
            # Check no symlink in path components before existence
            if self.absolute.is_symlink():
                raise PermissionError(f"workdir path is a symlink: {self.absolute}")
            if resolved_root not in resolved_abs.parents and resolved_abs != resolved_root:
                # For non-existing path, check parent containment
                parent = resolved_abs.parent if not self.absolute.exists() else resolved_abs
                if resolved_root not in parent.parents and parent != resolved_root:
                    raise PermissionError(f"workdir escapes user workspace: {workdir_path}")
        except PermissionError:
            raise
        except Exception:
            pass

    @staticmethod
    def open_existing(uid: str, workdir_path: str) -> Workdir:
        """Open a Workdir that must already exist on disk."""
        workdir = Workdir(uid, workdir_path)
        if workdir.absolute.is_symlink():
            raise PermissionError(f"workdir is a symlink: {workdir.absolute}")
        if not workdir.absolute.is_dir():
            raise FileNotFoundError(f"directory not found: {workdir.absolute}")
        return workdir

    @staticmethod
    def open_or_create(uid: str, workdir_path: str) -> Workdir:
        """Open a Workdir, creating it when missing."""
        workdir = Workdir(uid, workdir_path)
        if workdir.absolute.is_symlink():
            raise PermissionError(f"workdir is a symlink: {workdir.absolute}")
        workdir.absolute.mkdir(parents=True, exist_ok=True)
        return workdir

    def __fspath__(self) -> str:
        return str(self.absolute)
