import re
import json
import uuid
from typing import Any
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage, AnyMessage
from langgraph.runtime import Runtime
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRetryMiddleware, TodoListMiddleware

_GARBAGE_PREFIXES = ("portun", "leton", "iciary", "дажe", "дажe")
_BARE_JSON_TOOL_PATTERN = re.compile(
    r'\{[^{}]*"name"\s*:\s*"(?P<name>[^"]+)"[^{}]*"arguments"\s*:\s*(?P<args>\{[^{}]*\})[^{}]*\}',
    re.DOTALL
)

class OllamaToolCallParserMiddleware(AgentMiddleware):
    """Parses raw tool call strings from Ollama assistant messages.

    Handles three patterns:
    1. <tool_call>{"name": ..., "arguments": ...}</tool_call>  — XML wrapped
    2. {"name": ..., "arguments": {...}}                        — bare JSON object
    3. garbage_prefix<tool_call>...</tool_call>                 — garbage prefix before XML
    """

    @staticmethod
    def _try_parse_bare_tool_call(text: str) -> dict | None:
        """Return a tool_call dict if text is a standalone JSON tool call, else None."""
        stripped = text.strip()
        if not stripped.startswith("{") or not stripped.endswith("}"):
            return None
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "name" in data:
                return {
                    "name": data["name"],
                    "args": data.get("arguments") or data.get("parameters") or {},
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "type": "tool_call",
                }
        except Exception:
            pass
        return None

    @staticmethod
    def _strip_garbage(text: str) -> str:
        for prefix in _GARBAGE_PREFIXES:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
        return text

    @staticmethod
    def _extract_tool_calls(content: str) -> tuple[list, str]:
        """Return (tool_calls, cleaned_content) extracted from content string."""
        tool_calls: list[dict] = []
        cleaned = content

        # Pattern 1 — XML <tool_call>...</tool_call>
        if "<tool_call>" in content:
            for match in re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", content, re.DOTALL):
                try:
                    data = json.loads(match.strip())
                    tool_calls.append({
                        "name": data.get("name"),
                        "args": data.get("arguments", {}),
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "type": "tool_call",
                    })
                except Exception:
                    pass
            if tool_calls:
                cleaned = re.sub(r"<tool_call>.*?</tool_call>", "", content, flags=re.DOTALL).strip()
                cleaned = OllamaToolCallParserMiddleware._strip_garbage(cleaned)
                return tool_calls, cleaned

        # Pattern 2 — Entire content is a bare JSON tool call
        bare = OllamaToolCallParserMiddleware._try_parse_bare_tool_call(content.strip())
        if bare:
            return [bare], ""

        # Pattern 3 — JSON embedded in garbage text
        m = _BARE_JSON_TOOL_PATTERN.search(content)
        if m:
            try:
                data = json.loads(m.group(0))
                if "name" in data:
                    tool_calls.append({
                        "name": data["name"],
                        "args": data.get("arguments", {}),
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "type": "tool_call",
                    })
                    cleaned = (content[: m.start()] + content[m.end():]).strip()
                    cleaned = OllamaToolCallParserMiddleware._strip_garbage(cleaned)
                    return tool_calls, cleaned
            except Exception:
                pass

        return [], content

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        modified = False
        for msg in messages:
            if not isinstance(msg, AIMessage):
                continue
            if getattr(msg, "tool_calls", None):
                continue  # already parsed
            content = msg.content
            if not isinstance(content, str) or not content.strip():
                continue

            tool_calls, cleaned = self._extract_tool_calls(content)
            if tool_calls:
                msg.tool_calls = tool_calls
                msg.content = cleaned
                modified = True

        if modified:
            from langgraph.types import Overwrite
            return {"messages": Overwrite(messages)}
        return None

    async def awrap_model_call(self, request, handler):
        response = await handler(request)
        if not response or not getattr(response, "result", None):
            return response

        for msg in response.result:
            if not isinstance(msg, AIMessage):
                continue
            if getattr(msg, "tool_calls", None):
                continue  # already parsed by model
            content = msg.content
            if not isinstance(content, str) or not content.strip():
                continue

            tool_calls, cleaned = self._extract_tool_calls(content)
            if tool_calls:
                msg.tool_calls = tool_calls
                msg.content = cleaned

        return response


from yuxi.agents import BaseAgent, load_chat_model, resolve_chat_model_spec
from yuxi.agents.backends import create_agent_filesystem_middleware
from yuxi.agents.context import (
    DEFAULT_SUMMARY_KEEP_MESSAGES,
    DEFAULT_SUMMARY_THRESHOLD_K,
    DEFAULT_SUMMARY_TOOL_RESULT_TOKEN_LIMIT,
    DEFAULT_TOOL_RESULT_EVICTION_K_TOKENS,
    DEFAULT_YUXI_SUMMARY_PROMPT,
    prepare_agent_runtime_context,
)
from yuxi.agents.middlewares import (
    TokenUsageMiddleware,
    create_summary_middleware,
    save_attachments_to_fs,
)
from yuxi.agents.middlewares.skills import SkillsMiddleware
from yuxi.agents.middlewares.subagent_task import create_subagent_task_middleware
from yuxi.agents.toolkits.service import resolve_configured_runtime_tools

from .context import ChatBotContext
from .prompt import TODO_MID_PROMPT, build_prompt_with_context
from .state import ChatBotState


async def _build_middlewares(context):
    """
    Build a list of middlewares.
    """
    summary_trigger_tokens = getattr(context, "summary_threshold", DEFAULT_SUMMARY_THRESHOLD_K) * 1024
    summary_keep_messages = getattr(context, "summary_keep_messages", DEFAULT_SUMMARY_KEEP_MESSAGES)
    summary_prompt = getattr(context, "summary_prompt", None) or DEFAULT_YUXI_SUMMARY_PROMPT
    summary_tool_result_token_limit = getattr(
        context,
        "summary_tool_result_token_limit",
        DEFAULT_SUMMARY_TOOL_RESULT_TOKEN_LIMIT,
    )
    model_spec = resolve_chat_model_spec(context.model)
    summary_middleware = create_summary_middleware(
        model=load_chat_model(fully_specified_name=model_spec),
        trigger=("tokens", summary_trigger_tokens),
        keep=("messages", summary_keep_messages),
        summary_prompt=summary_prompt,
        trim_tokens_to_summarize=4000,
        tool_result_offload_token_limit=summary_tool_result_token_limit,
    )

    middlewares = [
        create_agent_filesystem_middleware(
            getattr(context, "tool_token_limit", DEFAULT_TOOL_RESULT_EVICTION_K_TOKENS) * 1024,
            context=context,
        ),
        save_attachments_to_fs,
        SkillsMiddleware(),
    ]
    subagent_middleware = await create_subagent_task_middleware(context)
    if subagent_middleware:
        middlewares.append(subagent_middleware)
    middlewares.extend(
        [
            OllamaToolCallParserMiddleware(),
            summary_middleware,
            TodoListMiddleware(system_prompt=TODO_MID_PROMPT),
            PatchToolCallsMiddleware(),
            ModelRetryMiddleware(max_retries=getattr(context, "model_retry_times", 2)),
            TokenUsageMiddleware(),
        ]
    )
    return middlewares


class ChatbotAgent(BaseAgent):
    name = "Chatbot"
    description = "Basic dialogue robot, can answer questions, can enable required tools in the configuration."
    capabilities = ["file_upload", "files"]
    context_schema = ChatBotContext

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def get_graph(self, context=None, **kwargs):

        context = await prepare_agent_runtime_context(
            context or self.context_schema(),
            context_schema=self.context_schema,
        )

        # Cập nhật context.system_prompt để middleware context_aware_prompt không ghi đè mất prompt này
        context.system_prompt = await build_prompt_with_context(context)

        model_spec = resolve_chat_model_spec(context.model)
        resolved_tools = await resolve_configured_runtime_tools(context)
        is_test = any(str(kb.get("name") or "").startswith("TEST_RAG_PIPELINE_") for kb in getattr(context, "_visible_knowledge_bases", []))
        if is_test:
            resolved_tools = [t for t in resolved_tools if t.name not in ("ask_user_question", "install_skill", "list_kbs")]

        graph = create_agent(
            model=load_chat_model(fully_specified_name=model_spec),
            tools=resolved_tools,
            system_prompt=context.system_prompt,
            middleware=await _build_middlewares(context),
            state_schema=ChatBotState,
            checkpointer=await self._get_checkpointer(),
        )

        return graph


def main():
    pass


if __name__ == "__main__":
    main()
    # asyncio.run(main())
