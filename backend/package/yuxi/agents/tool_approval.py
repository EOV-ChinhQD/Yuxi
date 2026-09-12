from typing import Literal

from langchain.agents.middleware import HumanInTheLoopMiddleware

ToolApprovalMode = Literal["default", "always_trust"]

DEFAULT_TOOL_APPROVAL_MODE: ToolApprovalMode = "default"
TOOL_APPROVAL_MODES = frozenset({"default", "always_trust"})
# Sensitive backend tools intercepted/hidden under default approval mode.
SENSITIVE_BACKEND_TOOLS = frozenset({"write_file", "edit_file", "execute"})
TOOL_APPROVAL_INTERRUPT_ON = {
    tool_name: {"allowed_decisions": ["approve", "reject"]} for tool_name in SENSITIVE_BACKEND_TOOLS
}


def normalize_tool_approval_mode(value: object) -> ToolApprovalMode:
    mode = value.strip() if isinstance(value, str) else value
    if mode not in TOOL_APPROVAL_MODES:
        raise ValueError(f"Unsupported tool_approval_mode: {value}")
    return mode


def create_tool_approval_middleware(mode: ToolApprovalMode):
    if mode == "always_trust":
        return None
    return HumanInTheLoopMiddleware(interrupt_on=TOOL_APPROVAL_INTERRUPT_ON)
