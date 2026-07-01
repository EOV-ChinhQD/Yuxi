from typing import Any

from yuxi.utils import logger

# Tool metadata cache
_metadata_cache: list[dict] = []


def _extract_tool_info(tool_obj) -> dict:
    """Extract basic information from tool_obj"""
    metadata = getattr(tool_obj, "metadata", {}) or {}
    info = {
        "slug": tool_obj.name,
        "name": metadata.get("name", tool_obj.name),  # The display name is first obtained from metadata
        "description": tool_obj.description,
        "metadata": metadata,
        "args": [],
    }

    if hasattr(tool_obj, "args_schema") and tool_obj.args_schema:
        schema = tool_obj.args_schema
        if hasattr(schema, "schema"):
            schema = schema.schema()
        for arg_name, arg_info in schema.get("properties", {}).items():
            info["args"].append(
                {
                    "name": arg_name,
                    "type": arg_info.get("type", ""),
                    "description": arg_info.get("description", ""),
                }
            )
    return info


def _ensure_metadata_loaded():
    """Lazy loading tool metadata (automatically triggered on first call)"""
    global _metadata_cache

    if _metadata_cache:  # Loaded
        return

    from yuxi.agents.toolkits.registry import (
        get_all_extra_metadata,
        get_all_tool_instances,
    )

    # Get all tool instances
    all_tools = get_all_tool_instances()
    extra_meta = get_all_extra_metadata()

    for tool in all_tools:
        tool_name = tool.name
        runtime_info = _extract_tool_info(tool)

        # Merge additional metadata
        if tool_name in extra_meta:
            extra = extra_meta[tool_name]
            runtime_info["category"] = extra.category
            runtime_info["tags"] = extra.tags
            runtime_info["config_guide"] = extra.config_guide
            # display_name has higher priority than tool.name
            if extra.display_name:
                runtime_info["name"] = extra.display_name
        else:
            # Not registered, set as default category
            runtime_info["category"] = "buildin"
            runtime_info["tags"] = []
            runtime_info["config_guide"] = ""

        _metadata_cache.append(runtime_info)

    logger.info(f"Tool service loaded {len(_metadata_cache)} tools (lazy load)")


def get_tool_metadata(category: str = None) -> list[dict]:
    """Get a list of tool metadata (lazy loading)"""
    _ensure_metadata_loaded()

    if category:
        return [t for t in _metadata_cache if t.get("category") == category]
    return _metadata_cache


def get_tool_instances_by_category(category: str) -> list[Any]:
    from yuxi.agents.toolkits.registry import get_all_extra_metadata, get_all_tool_instances

    extra_meta = get_all_extra_metadata()
    tools = []
    for tool in get_all_tool_instances():
        tool_meta = extra_meta.get(tool.name)
        tool_category = tool_meta.category if tool_meta else "buildin"
        if tool_category == category:
            tools.append(tool)
    return tools


async def resolve_configured_runtime_tools(context) -> list[Any]:
    from yuxi.agents.mcp.service import get_enabled_mcp_tools

    selected_tools = []
    selected_tool_names: set[str] = set()
    buildin_tools = {tool.name: tool for tool in get_tool_instances_by_category("buildin")}

    for tool_name in getattr(context, "tools", None) or []:
        if not isinstance(tool_name, str) or tool_name in selected_tool_names:
            continue
        tool = buildin_tools.get(tool_name)
        if tool is None:
            logger.warning(f"Configured buildin tool not found, skip: {tool_name}")
            continue
        selected_tools.append(tool)
        selected_tool_names.add(tool_name)

    selected_mcp_servers: set[str] = set()
    for server_name in getattr(context, "mcps", None) or []:
        if not isinstance(server_name, str) or server_name in selected_mcp_servers:
            continue
        selected_mcp_servers.add(server_name)
        try:
            mcp_tools = await get_enabled_mcp_tools(server_name)
        except Exception as e:
            logger.warning(f"Failed to load configured MCP tools '{server_name}': {e}")
            continue
        if not mcp_tools:
            logger.warning(f"Configured MCP unavailable, skip: {server_name}")
            continue
        for tool in mcp_tools:
            if tool.name in selected_tool_names:
                continue
            selected_tools.append(tool)
            selected_tool_names.add(tool.name)

    # Local tools that Skill depends on: must be registered with the basic tool into the ToolNode of create_agent before it can be executed.
    # Otherwise, although the model can initiate calls after the Skill is activated, the executor will still report "not a valid tool".
    # Visibility bound to the model by default is gated by the SkillsMiddleware activation state per Skill (keeps loading on demand).
    from yuxi.agents.middlewares.skills import resolve_skill_gated_tools

    for tool in resolve_skill_gated_tools(context):
        if tool.name in selected_tool_names:
            continue
        selected_tools.append(tool)
        selected_tool_names.add(tool.name)

    return selected_tools
