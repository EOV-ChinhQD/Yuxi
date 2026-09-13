import os
from pathlib import Path

_raw_prefix = os.getenv("SANDBOX_VIRTUAL_PATH_PREFIX")
VIRTUAL_PATH_PREFIX = (_raw_prefix.strip() if _raw_prefix else "/home/gem/user-data") or "/home/gem/user-data"
if not VIRTUAL_PATH_PREFIX.startswith("/"):
    VIRTUAL_PATH_PREFIX = f"/{VIRTUAL_PATH_PREFIX}"
WORKSPACE_DIR_NAME = "workspace"
WORKSPACE_AGENTS_DIR_NAME = "agents"
WORKSPACE_AGENT_CONTEXT_FILES = {
    "AGENTS.md": "# AGENTS\n\nDưới đây là các yêu cầu và quy định ràng buộc hành vi của Agent\n",
    "USER.md": "# USER\n\nDưới đây là thông tin và ngữ cảnh liên quan về người dùng\n",
    "MEMORY.md": "# MEMORY\n\nDưới đây là các thông tin và bài học Agent cần ghi nhớ lâu dài\n",
}
UPLOADS_DIR_NAME = "uploads"
OUTPUTS_DIR_NAME = "outputs"
LARGE_TOOL_RESULTS_DIR_NAME = "large_tool_results"
CONVERSATION_HISTORY_DIR_NAME = "conversation_history"
VIRTUAL_SKILLS_PATH = "/home/gem/skills"

VIRTUAL_PATH_WORKSPACE = (Path(VIRTUAL_PATH_PREFIX) / WORKSPACE_DIR_NAME).as_posix()
VIRTUAL_PATH_WORKSPACE_SKILLS = (Path(VIRTUAL_PATH_WORKSPACE) / WORKSPACE_AGENTS_DIR_NAME / "skills").as_posix()
VIRTUAL_PATH_UPLOADS = (Path(VIRTUAL_PATH_PREFIX) / UPLOADS_DIR_NAME).as_posix()
VIRTUAL_PATH_OUTPUTS = (Path(VIRTUAL_PATH_PREFIX) / OUTPUTS_DIR_NAME).as_posix()
VIRTUAL_PATH_LARGE_TOOL_RESULTS = (Path(VIRTUAL_PATH_OUTPUTS) / LARGE_TOOL_RESULTS_DIR_NAME).as_posix()
VIRTUAL_PATH_CONVERSATION_HISTORY = (Path(VIRTUAL_PATH_OUTPUTS) / CONVERSATION_HISTORY_DIR_NAME).as_posix()


def ensure_within_root(path: Path, root: Path, *, error_message: str) -> Path:
    """Ensure the resolved path is within the root directory, otherwise reject out-of-bounds access."""
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        raise ValueError(error_message) from None
    return path


__all__ = [
    "VIRTUAL_PATH_PREFIX",
    "WORKSPACE_DIR_NAME",
    "WORKSPACE_AGENTS_DIR_NAME",
    "WORKSPACE_AGENT_CONTEXT_FILES",
    "UPLOADS_DIR_NAME",
    "OUTPUTS_DIR_NAME",
    "LARGE_TOOL_RESULTS_DIR_NAME",
    "CONVERSATION_HISTORY_DIR_NAME",
    "VIRTUAL_PATH_WORKSPACE",
    "VIRTUAL_PATH_WORKSPACE_SKILLS",
    "VIRTUAL_PATH_UPLOADS",
    "VIRTUAL_PATH_OUTPUTS",
    "VIRTUAL_PATH_LARGE_TOOL_RESULTS",
    "VIRTUAL_PATH_CONVERSATION_HISTORY",
    "VIRTUAL_SKILLS_PATH",
    "ensure_within_root",
]
