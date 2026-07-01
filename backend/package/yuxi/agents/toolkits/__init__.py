# toolkits package
# Trigger the @tool decorator execution of each module and automatically register tools
from . import buildin, debug

# Tool get function
from .kbs import get_common_kb_tools
from .registry import (
    ToolExtraMetadata,
    get_all_extra_metadata,
    get_all_tool_instances,
    get_extra_metadata,
    tool,
)

__all__ = [
    "get_extra_metadata",
    "get_all_extra_metadata",
    "get_all_tool_instances",
    "ToolExtraMetadata",
    "tool",
    "get_common_kb_tools",
    # Trigger the @tool decorator execution of each module and automatically register tools
    "buildin",
    "debug",
]
