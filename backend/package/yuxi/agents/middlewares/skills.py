"""Skills middleware - Processing skills prompt word injection, dependency expansion, dynamic activation"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Annotated, Any, NotRequired, TypedDict

from deepagents.middleware._utils import append_to_system_message
from deepagents.middleware.skills import SKILLS_SYSTEM_PROMPT
from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.tools.tool_node import ToolCallRequest
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.agents.mcp.service import get_enabled_mcp_tools
from yuxi.agents.skills.repository import SkillRepository
from yuxi.agents.skills.service import is_valid_skill_slug, list_accessible_skills, normalize_string_list
from yuxi.agents.toolkits import get_all_tool_instances
from yuxi.storage.postgres.manager import pg_manager
from yuxi.utils.logging_config import logger

# =============================================================================
# type definition
# =============================================================================


class SkillPromptMetadata(TypedDict):
    name: str
    description: str
    path: str


class SkillDependencyNode(TypedDict):
    tools: list[str]
    mcps: list[str]
    skills: list[str]


# =============================================================================
# Runtime data loading function
# =============================================================================


async def _list_skills_from_db(db: AsyncSession | None = None, user=None) -> list:
    """Load skills list from database"""
    if db is not None:
        if user is not None:
            return await list_accessible_skills(db, user)
        repo = SkillRepository(db)
        return await repo.list_enabled()

    async with pg_manager.get_async_session_context() as session:
        if user is not None:
            return await list_accessible_skills(session, user)
        repo = SkillRepository(session)
        return await repo.list_enabled()


def build_prompt_metadata(skills: list) -> dict[str, SkillPromptMetadata]:
    return {
        item.slug: {
            "name": item.name,
            "description": item.description,
            "path": f"/home/gem/skills/{item.slug}/SKILL.md",
        }
        for item in skills
        if item.slug
    }


def build_dependency_map(skills: list) -> dict[str, SkillDependencyNode]:
    result: dict[str, SkillDependencyNode] = {}
    for item in skills:
        if not item.slug:
            continue
        result[item.slug] = {
            "tools": normalize_string_list(item.tool_dependencies or []),
            "mcps": normalize_string_list(item.mcp_dependencies or []),
            "skills": normalize_string_list(item.skill_dependencies or []),
        }
    return result


async def get_prompt_metadata(db: AsyncSession | None = None, user=None) -> dict[str, SkillPromptMetadata]:
    """Get prompt word metadata (load directly from database)"""
    return build_prompt_metadata(await _list_skills_from_db(db, user))


async def get_dependency_map(db: AsyncSession | None = None, user=None) -> dict[str, SkillDependencyNode]:
    """Get dependency mapping (load directly from database)"""
    return build_dependency_map(await _list_skills_from_db(db, user))


def expand_skill_closure(
    slugs: list[str] | None,
    dependency_map: dict[str, SkillDependencyNode],
) -> list[str]:
    """Expand the skills dependency closure and return a list containing all dependencies"""
    ordered_roots = normalize_string_list(slugs)
    if not ordered_roots:
        return []

    result: list[str] = []
    seen: set[str] = set()

    def dfs(slug: str, stack: set[str]) -> None:
        if slug in stack:
            logger.warning(f"Cycle detected in skill dependencies, skip: {' -> '.join([*stack, slug])}")
            return
        if slug in seen:
            return

        node = dependency_map.get(slug)
        if not node:
            logger.warning(f"Skill dependency target not found in DB, skip: {slug}")
            return

        seen.add(slug)
        result.append(slug)
        next_stack = set(stack)
        next_stack.add(slug)
        for dep in node.get("skills", []):
            dfs(dep, next_stack)

    for root in ordered_roots:
        dfs(root, set())
    return result


async def resolve_runtime_skills_for_context(context, *, db: AsyncSession | None = None, user=None) -> dict[str, Any]:
    skill_items = await _list_skills_from_db(db, user)
    dependency_map = build_dependency_map(skill_items)
    prompt_metadata = build_prompt_metadata(skill_items)
    available = set(dependency_map)
    selected = normalize_string_list(getattr(context, "skills", None))
    context_skills = [slug for slug in selected if slug in available]
    prompt_skills = expand_skill_closure(context_skills, dependency_map)
    return {
        "context_skills": context_skills,
        "prompt_skills": prompt_skills,
        "readable_skills": prompt_skills,
        "runtime_skill_metadata": prompt_metadata,
        "runtime_skill_dependency_map": dependency_map,
    }


def resolve_skill_gated_tools(context) -> list:
    """Parse all visible Skill dependencies of the current Agent of local tool instances.

    These tooldefaults are not bound to the Model (they are released by SkillsMiddleware after the corresponding Skill is activated).
    However, create_agent of ToolNode must be registered during the build period. If no, even if the Model initiates a call, the executor will
    Judged as "not a valid tool". The caller should exclude tools already in the basic tool set by themselves to avoid duplication of gating.
    """
    dependency_map = getattr(context, "_runtime_skill_dependency_map", {}) or {}
    readable_skills = getattr(context, "_readable_skills", []) or []
    tool_names: set[str] = set()
    for slug in readable_skills:
        node = dependency_map.get(slug) or {}
        tool_names.update(node.get("tools", []))
    if not tool_names:
        return []
    return [tool for tool in get_all_tool_instances() if tool.name in tool_names]


def _activated_skills_reducer(left: list[str] | None, right: list[str] | None) -> list[str]:
    """Merge activated_skills list"""
    merged: list[str] = []
    seen: set[str] = set()
    for group in (left or [], right or []):
        for value in group:
            if not isinstance(value, str):
                continue
            slug = value.strip()
            if not slug or slug in seen:
                continue
            seen.add(slug)
            merged.append(slug)
    return merged


class SkillsState(AgentState):
    """Skills Status definition"""

    activated_skills: NotRequired[Annotated[list[str], _activated_skills_reducer]]


class SkillsMiddleware(AgentMiddleware):
    """Skills middleware - Processing skills prompt word injection, dependency expansion, dynamic activation

    Responsibilities:
    - Skills Prompt word injection (load directly from database)
    - Dependency expansion (user configuration + dynamic activation)
    - tool/MCP dynamic loading
    """

    state_schema = SkillsState

    def __init__(
        self,
        *,
        skills_context_name: str = "skills",
        enable_skills_prompt: bool = True,
        skills_sources_for_prompt: list[str] | None = None,
    ):
        """initializationmiddleware

        Args:
            skills_context_name: skills list field name in context (default "skills"）
            enable_skills_prompt: Whether to enable skills prompt segment injection (default True)
            skills_sources_for_prompt: skills Source path (used for prompt word display, default ["/home/gem/skills/"]）
        """
        super().__init__()
        self.skills_context_name = skills_context_name
        self.enable_skills_prompt = enable_skills_prompt
        self.skills_sources_for_prompt = skills_sources_for_prompt or ["/home/gem/skills/"]

    async def awrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        """Wrapping model calls, handling skills prompt injection, dynamic activation and dependency expansion"""
        runtime_context = request.runtime.context

        if self.enable_skills_prompt:
            prompt_skills = getattr(runtime_context, "_prompt_skills", None)
            if isinstance(prompt_skills, list):
                prompt_skills = normalize_string_list(prompt_skills)
                if prompt_skills:
                    skills_meta = self._collect_prompt_metadata(prompt_skills, runtime_context)
                    skills_section = self._build_skills_section(skills_meta)
                    system_message = append_to_system_message(getattr(request, "system_message", None), skills_section)
                    request = request.override(system_message=system_message)

        state = request.state if isinstance(request.state, dict) else {}
        activated = state.get("activated_skills", []) or []
        if not isinstance(activated, list):
            activated = []

        readable_skills = self._get_readable_skills(runtime_context)
        activated = [slug for slug in normalize_string_list(activated) if slug in readable_skills]

        deps_bundle = self._build_dependency_bundle(activated, runtime_context)
        activated_tool_names = set(deps_bundle["tools"])

        # Gated: Dependent tools for inactive Skills are not visible to the model (keep loading on demand).
        # These tools have been registered into ToolNode by resolve_configured_runtime_tools during the build period. Elimination only affects model visibility and does not affect executability.
        # Exclude tools from the base toolset (such as present_artifacts), which are always visible and are not affected by Skill activation.
        gated_tool_names = self._resolve_gated_tool_names(runtime_context) - activated_tool_names
        model_tools = list(request.tools or [])
        if gated_tool_names:
            model_tools = [t for t in model_tools if t.name not in gated_tool_names]

        # Add dependent tools for activated Skills: local tools are bound to the model, and MCP tools are loaded on demand.
        enabled_tools = []
        if activated_tool_names:
            enabled_tools = [t for t in get_all_tool_instances() if t.name in activated_tool_names]
        if deps_bundle["mcps"]:
            enabled_tools.extend(
                await self._get_mcp_tools_from_context(runtime_context, extra_mcps=deps_bundle["mcps"])
            )

        existing_tool_names = {t.name for t in model_tools}
        for t in enabled_tools:
            if t.name not in existing_tool_names:
                model_tools.append(t)
                existing_tool_names.add(t.name)

        if gated_tool_names or enabled_tools:
            request = request.override(tools=model_tools)

        return await handler(request)

    def _resolve_gated_tool_names(self, runtime_context) -> set[str]:
        """A collection of tool names that all visible Skills depend on and do not belong to the basic tool set (i.e. tools that are "only released when the Skill is activated")."""
        dependency_map = self._get_runtime_dependency_map(runtime_context)
        readable_skills = self._get_readable_skills(runtime_context)
        base_tool_names = set(normalize_string_list(getattr(runtime_context, "tools", None)))
        gated: set[str] = set()
        for slug in readable_skills:
            gated.update(dependency_map.get(slug, {}).get("tools", []))
        return gated - base_tool_names

    def _build_dependency_bundle(self, activated_skills: list[str], runtime_context) -> dict[str, list[str]]:
        """Build dependency packages based on directly activated skills (excluding dependencies of closure expansion)"""
        dependency_map = self._get_runtime_dependency_map(runtime_context)

        tools: list[str] = []
        mcps: list[str] = []
        seen_tools: set[str] = set()
        seen_mcps: set[str] = set()

        for slug in activated_skills:
            dep = dependency_map.get(slug, {})
            for tool_name in dep.get("tools", []):
                if tool_name in seen_tools:
                    continue
                seen_tools.add(tool_name)
                tools.append(tool_name)
            for mcp_name in dep.get("mcps", []):
                if mcp_name in seen_mcps:
                    continue
                seen_mcps.add(mcp_name)
                mcps.append(mcp_name)

        return {"tools": tools, "mcps": mcps, "skills": activated_skills}

    def _collect_prompt_metadata(self, slugs: list[str], runtime_context) -> list[SkillPromptMetadata]:
        """Collect hint word metadata for specified slugs"""
        prompt_metadata = self._get_runtime_prompt_metadata(runtime_context)

        result: list[SkillPromptMetadata] = []
        seen: set[str] = set()

        for slug in slugs:
            if not isinstance(slug, str):
                continue
            normalized = slug.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)

            item = prompt_metadata.get(normalized)
            if not item:
                logger.debug(f"Skill slug not found in prompt metadata, skip: {normalized}")
                continue
            result.append(dict(item))

        return result

    async def _get_mcp_tools_from_context(
        self,
        context,
        *,
        extra_mcps: list[str] | None = None,
    ) -> list:
        """Get MCP tools list from context configuration"""
        import asyncio

        # MCP tool (parallel loading)
        mcps = getattr(context, "mcps", None) or []
        all_mcp_names: list[str] = []
        for server_name in mcps:
            if isinstance(server_name, str):
                all_mcp_names.append(server_name)
        for server_name in extra_mcps or []:
            if isinstance(server_name, str):
                all_mcp_names.append(server_name)

        # Remove duplicates
        unique_mcp_names = list(dict.fromkeys(all_mcp_names))

        async def load_mcp_tools(server_name: str) -> list:
            """Tools for loading a single MCP server"""
            try:
                mcp_tools = await get_enabled_mcp_tools(server_name)
                if not mcp_tools:
                    logger.warning(f"SkillsMiddleware: mcp dependency unavailable, skip: {server_name}")
                return mcp_tools
            except Exception as e:
                logger.warning(f"SkillsMiddleware: failed to load mcp dependency '{server_name}': {e}")
                return []

        # Load all MCP tools in parallel
        results = await asyncio.gather(*[load_mcp_tools(name) for name in unique_mcp_names])
        selected_tools = []
        for tools in results:
            selected_tools.extend(tools)

        return selected_tools

    def _process_tool_call_result(self, result: Any, request: ToolCallRequest) -> Any:
        """Process tool call results, check and process skill dynamic activation"""
        if request.tool_call.get("name") != "read_file":
            return result

        args = request.tool_call.get("args") or {}
        file_path = args.get("file_path") if isinstance(args, dict) else None
        slug = self._extract_skill_slug_from_skill_md_path(file_path)

        if not slug:
            return result

        if not self._is_visible_skill_slug(request, slug):
            logger.warning(f"SkillsMiddleware: deny skill activation for invisible slug: {slug}")
            return result

        logger.debug(f"SkillsMiddleware: activated skill by read_file: {slug}")
        return self._merge_activated_skill_update(result, slug)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ):
        """Wrap tool calls and handle dynamic activation of skills"""
        result = await handler(request)
        return self._process_tool_call_result(result, request)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ):
        """Synchronized version of tool call wrapper"""
        result = handler(request)
        return self._process_tool_call_result(result, request)

    def _extract_skill_slug_from_skill_md_path(self, file_path: Any) -> str | None:
        """Extract skill slug from file path"""
        if not isinstance(file_path, str):
            return None
        raw = file_path.strip()
        if not raw:
            return None
        pure = PurePosixPath(raw if raw.startswith("/") else f"/{raw}")
        parts = [p for p in pure.parts if p not in ("/", "")]
        slug: str | None = None
        if (
            len(parts) == 5
            and parts[0] == "home"
            and parts[1] == "gem"
            and parts[2] == "skills"
            and parts[4] == "SKILL.md"
        ):
            slug = parts[3]

        if not is_valid_skill_slug(slug):
            return None
        return slug

    def _get_readable_skills(self, runtime_context) -> set[str]:
        selected = getattr(runtime_context, "_readable_skills", [])
        return set(normalize_string_list(selected if isinstance(selected, list) else []))

    def _get_runtime_prompt_metadata(self, runtime_context) -> dict[str, SkillPromptMetadata]:
        metadata = getattr(runtime_context, "_runtime_skill_metadata", {})
        return metadata if isinstance(metadata, dict) else {}

    def _get_runtime_dependency_map(self, runtime_context) -> dict[str, SkillDependencyNode]:
        dependency_map = getattr(runtime_context, "_runtime_skill_dependency_map", {})
        return dependency_map if isinstance(dependency_map, dict) else {}

    def _is_visible_skill_slug(self, request: ToolCallRequest, slug: str) -> bool:
        """Check if slug is visible"""
        return slug in self._get_readable_skills(request.runtime.context)

    def _merge_activated_skill_update(self, result: Any, slug: str):
        """Merge dynamically activated skill updates"""
        from langchain_core.messages import ToolMessage

        if isinstance(result, Command):
            update = dict(result.update or {})
            current = update.get("activated_skills") or []
            update["activated_skills"] = _activated_skills_reducer(current, [slug])
            return Command(graph=result.graph, update=update, resume=result.resume, goto=result.goto)

        if isinstance(result, ToolMessage):
            return Command(update={"messages": [result], "activated_skills": [slug]})

        return result

    def _format_skills_locations(self, sources: list[str]) -> str:
        """Format skills location information"""
        locations = []
        for i, source_path in enumerate(sources):
            name = PurePosixPath(source_path.rstrip("/")).name.capitalize()
            suffix = " (higher priority)" if i == len(sources) - 1 else ""
            locations.append(f"**{name} Skills**: `{source_path}`{suffix}")
        return "\n".join(locations)

    def _format_skills_list(self, skills_meta: list[dict[str, str]]) -> str:
        """Format skills list"""
        if not skills_meta:
            return f"(No skills available yet. You can create skills in {' or '.join(self.skills_sources_for_prompt)})"

        lines = []
        for skill in skills_meta:
            lines.append(f"- **{skill['name']}**: {skill['description']}")
            lines.append(f"  -> Read `{skill['path']}` for full instructions")
        return "\n".join(lines)

    def _build_skills_section(self, skills_meta: list[dict[str, str]]) -> str:
        """Build skills prompt section"""
        skills_locations = self._format_skills_locations(self.skills_sources_for_prompt)
        skills_list = self._format_skills_list(skills_meta)
        return SKILLS_SYSTEM_PROMPT.format(
            skills_locations=skills_locations,
            skills_load_warnings="",
            skills_list=skills_list,
        )
