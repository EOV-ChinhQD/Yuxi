from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from deepagents import SubagentTransformer as DeepAgentsSubagentTransformer
from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware.types import AgentMiddleware, ContextT, ModelRequest, ModelResponse, ResponseT
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import Command

from yuxi.agents.context import build_agent_input_context
from yuxi.repositories.agent_repository import SUB_AGENT_BACKEND_ID, AgentRepository
from yuxi.repositories.agent_run_repository import AgentRunRepository
from yuxi.repositories.user_repository import UserRepository
from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import Agent
from yuxi.utils.datetime_utils import utc_isoformat
from yuxi.utils.subagent_thread_utils import make_child_thread_id

_CHILD_STATE_INHERIT_KEYS: frozenset[str] = frozenset()
_TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled", "interrupted"}
YUXI_SUBAGENTS_STREAM_KEY = "yuxi_subagents"

TASK_SYSTEM_PROMPT = """## `task` (Công cụ giao nhiệm vụ cho sub-agent)

Bạn có thể sử dụng công cụ `task` để giao các nhiệm vụ phụ phức tạp và độc lập cho sub-agent đã được cấu hình xử lý. Sub-agent chỉ trả về kết quả cuối cùng, bạn không thể thấy các bước trung gian của nó.
Kết quả công cụ sẽ bao gồm ID thread của sub-agent. Khi cần tiếp tục cùng một nhiệm vụ phụ sau này, hãy truyền ID đó làm `thread_id` quay lại `task`.

Nguyên tắc sử dụng:
- Sử dụng khi nhiệm vụ đủ phức tạp, có thể hoàn thành độc lập hoặc cần cô lập ngữ cảnh.
- Nhiều nhiệm vụ phụ không phụ thuộc lẫn nhau có thể gọi đồng thời nhiều `task`.
- Truyền `thread_id` từ kết quả trước đó khi tiếp tục một nhiệm vụ sub-agent hiện có; không điền `thread_id` cho nhiệm vụ mới.
- Không gọi đồng thời cùng một `thread_id` để tránh nhiều yêu cầu tiếp tục ghi vào cùng một thread con cùng lúc.
- Không ủy thác cho các câu hỏi đơn giản hoặc chỉ cần một lượng nhỏ cuộc gọi công cụ trực tiếp.
- Khi gọi, phải chọn một `subagent_type` khả dụng bên dưới và viết rõ mục tiêu, ngữ cảnh và kết quả mong muốn trong `description`.
- Không gọi gián tiếp sub-agent qua shell, curl, HTTP API hoặc dòng lệnh; phải sử dụng công cụ `task` khi cần sub-agent.

Available subagent types:

{available_agents}"""

TASK_TOOL_DESCRIPTION = """Launch a configured Yuxi subagent to handle an isolated task.

Available subagent types:
{available_agents}

Use `subagent_type` to select one available subagent and put the full task brief in `description`.
Omit `thread_id` for a new task. To continue a previous subagent task, pass the child thread ID returned by
that prior task result as `thread_id`.
Do not call subagents through shell, curl, HTTP APIs, or command-line indirection."""


TASK_DESCRIPTION_ARG = "Mô tả nhiệm vụ cần sub-agent hoàn thành độc lập, bao gồm ngữ cảnh cần thiết và kết quả mong muốn."
SUBAGENT_TYPE_ARG = "Định danh sub-agent cần gọi, phải là một trong những loại khả dụng được liệt kê trong mô tả công cụ."
THREAD_ID_ARG = "Tùy chọn. ID thread sub-agent hiện có muốn tiếp tục, phải đến từ kết quả công cụ task trước đó; không điền cho nhiệm vụ mới."


class YuxiSubagentTransformer(DeepAgentsSubagentTransformer):
    def init(self) -> dict[str, Any]:
        return {YUXI_SUBAGENTS_STREAM_KEY: self._log}


def _get_agent_backend(backend_id: str):
    from yuxi.agents.buildin import agent_manager

    return agent_manager.get_agent(backend_id)


def _final_assistant_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            text = message.text.rstrip() if message.text else ""
            if text:
                return text
    return "Sub-agent đã hoàn thành nhiệm vụ nhưng không trả về kết quả văn bản."


def _result_artifacts(result: dict[str, Any]) -> list[str]:
    artifacts = result.get("artifacts")
    return list(artifacts) if isinstance(artifacts, list) else []


def _preview_text(text: str, limit: int = 500) -> str:
    return text if len(text) <= limit else f"{text[:limit]}..."


def _tool_result_with_thread_id(child_thread_id: str, content: str) -> str:
    return f"> ID thread sub-agent: {child_thread_id}\n\n---\n\n{content}"


def _new_child_thread_id(
    requested_thread_id: str | None,
    *,
    parent_thread_id: str,
    agent_slug: str,
    tool_call_id: str,
) -> tuple[str, bool]:
    requested_thread_id = str(requested_thread_id or "").strip()
    if requested_thread_id:
        return requested_thread_id, True
    return make_child_thread_id(parent_thread_id, agent_slug, tool_call_id), False


def _subagent_request_id(parent_run_id: str, child_thread_id: str, tool_call_id: str, agent_slug: str) -> str:
    digest = hashlib.sha256(f"{parent_run_id}:{child_thread_id}:{tool_call_id}:{agent_slug}".encode()).hexdigest()
    return f"subagent:{digest[:48]}"


def _with_run_payload(subagent_run: dict[str, Any], run) -> dict[str, Any]:
    if not run:
        return subagent_run
    return {**subagent_run, **_agent_run_state_payload(run)}


def _completed_tool_response(result: dict[str, Any], tool_call_id: str, subagent_run: dict[str, Any]) -> Command:
    final_text = _final_assistant_text(result.get("messages") or [])
    artifacts = _result_artifacts(result)
    subagent_run = {
        **subagent_run,
        "status": "completed",
        "completed_at": utc_isoformat(),
        "result_preview": _preview_text(final_text),
        "error": None,
        "artifacts": artifacts,
    }
    tool_result = _tool_result_with_thread_id(subagent_run["child_thread_id"], final_text)
    update: dict[str, Any] = {"messages": [ToolMessage(tool_result, tool_call_id=tool_call_id)]}
    if artifacts:
        update["artifacts"] = artifacts
    update["subagent_runs"] = [subagent_run]
    return Command(update=update)


def _reused_run_response(run, tool_call_id: str, subagent_run: dict[str, Any]) -> Command:
    status = str(getattr(run, "status", "") or "unknown")
    if status == "completed":
        message = "Nhiệm vụ sub-agent đã hoàn thành, không thực hiện lại."
    elif status in _TERMINAL_RUN_STATUSES:
        error_message = str(getattr(run, "error_message", "") or "")
        message = f"Nhiệm vụ sub-agent đã kết thúc, trạng thái: {status}. {error_message}".strip()
    else:
        message = f"Nhiệm vụ sub-agent đã tồn tại, trạng thái hiện tại: {status}, không gửi lại."

    subagent_run = {
        **subagent_run,
        **_agent_run_state_payload(run),
        "status": status,
        "result_preview": _preview_text(message),
    }
    tool_message = ToolMessage(
        _tool_result_with_thread_id(subagent_run["child_thread_id"], message),
        tool_call_id=tool_call_id,
    )
    return Command(update={"messages": [tool_message], "subagent_runs": [subagent_run]})


def _agent_run_state_payload(run) -> dict[str, Any]:
    payload = {
        "run_id": run.id,
        "status": run.status,
        "parent_agent_run_id": run.parent_agent_run_id,
        "created_at": utc_isoformat(run.created_at) if run.created_at else None,
        "completed_at": utc_isoformat(run.finished_at) if run.finished_at else None,
        "error": run.error_message,
    }
    return {key: value for key, value in payload.items() if value is not None}


def _failed_tool_response(error: Exception, tool_call_id: str, subagent_run: dict[str, Any]) -> Command:
    error_text = str(error)
    message = f"Gọi sub-agent {subagent_run['subagent_type']} thất bại: {error_text}"
    tool_result = _tool_result_with_thread_id(subagent_run["child_thread_id"], message)
    update = {
        "messages": [ToolMessage(tool_result, tool_call_id=tool_call_id)],
        "subagent_runs": [
            {
                **subagent_run,
                "status": "failed",
                "completed_at": utc_isoformat(),
                "result_preview": _preview_text(message),
                "error": error_text,
                "artifacts": [],
            }
        ],
    }
    return Command(update=update)


def _state_for_child(
    description: str,
    runtime: ToolRuntime,
    *,
    parent_thread_id: str,
    file_thread_id: str,
    skills_thread_id: str,
    continuing: bool = False,
) -> dict[str, Any]:
    state = {} if continuing else {key: runtime.state[key] for key in _CHILD_STATE_INHERIT_KEYS if key in runtime.state}
    state.update(
        {
            "parent_thread_id": parent_thread_id,
            "file_thread_id": file_thread_id,
            "skills_thread_id": skills_thread_id,
        }
    )
    state["messages"] = [HumanMessage(content=description)]
    return state


def _child_config(
    runtime: ToolRuntime,
    *,
    child_thread_id: str,
    uid: str,
    parent_thread_id: str,
    file_thread_id: str,
    skills_thread_id: str,
    subagent_type: str,
    run_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    parent_config = runtime.config or {}
    config: dict[str, Any] = {}
    if "callbacks" in parent_config:
        config["callbacks"] = parent_config["callbacks"]
    if "tags" in parent_config:
        config["tags"] = parent_config["tags"]
    parent_configurable = (
        parent_config.get("configurable") if isinstance(parent_config.get("configurable"), dict) else {}
    )
    parent_configurable = {
        key: value
        for key, value in parent_configurable.items()
        if not str(key).startswith(("checkpoint_", "__pregel_"))
    }
    config["configurable"] = {
        **parent_configurable,
        "thread_id": child_thread_id,
        "uid": uid,
        "parent_thread_id": parent_thread_id,
        "file_thread_id": file_thread_id,
        "skills_thread_id": skills_thread_id,
        "subagent_type": subagent_type,
        "subagent_thread_id": child_thread_id,
        "subagent_tool_call_id": runtime.tool_call_id,
        "run_id": run_id,
        "request_id": request_id,
        "ls_agent_type": "subagent",
    }
    config["recursion_limit"] = parent_config.get("recursion_limit", 300)
    return config


class YuxiSubAgentMiddleware(AgentMiddleware[Any, ContextT, ResponseT]):
    def __init__(self, *, parent_context, subagents: list[Agent]) -> None:
        super().__init__()
        self.parent_context = parent_context
        self.subagents = {agent.slug: agent for agent in subagents}
        available_agents = "\n".join(f"- {agent.slug}: {agent.description or agent.name}" for agent in subagents)
        self.system_prompt = TASK_SYSTEM_PROMPT.format(available_agents=available_agents)
        self.tools = [self._build_task_tool(available_agents)]
        self.subagent_names = frozenset(self.subagents)
        self.transformers = [lambda scope: YuxiSubagentTransformer(scope, subagent_names=self.subagent_names)]

    async def _create_subagent_run(
        self,
        *,
        child_thread_id: str,
        description: str,
        subagent_type: str,
        agent: Agent,
        uid: str,
        parent_thread_id: str,
        tool_call_id: str,
        continuing: bool,
    ):
        parent_run_id = str(getattr(self.parent_context, "run_id", "") or "").strip()
        if not parent_run_id:
            raise ValueError("Thiếu run_id của cha trong runtime hiện tại, không thể ghi nhận chạy sub-agent")

        async with pg_manager.get_async_session_context() as db:
            repo = AgentRunRepository(db)
            parent_run = await repo.get_run_for_user(parent_run_id, uid)
            if not parent_run:
                raise ValueError("Nhiệm vụ chạy của cha không tồn tại")

            if continuing:
                previous = await repo.get_latest_subagent_run_by_thread_for_user(child_thread_id, uid)
                if not previous or previous.conversation_id != parent_run.conversation_id:
                    raise ValueError(
                        f"Không thể tiếp tục thread sub-agent {child_thread_id}: Không tìm thấy bản ghi chạy sub-agent tương ứng trong hội thoại hiện tại"
                    )
                if previous.agent_id != subagent_type:
                    raise ValueError(
                        f"Không thể tiếp tục thread sub-agent {child_thread_id}: Thread này thuộc về sub-agent {previous.agent_id or 'không xác định'}"
                    )

            request_id = _subagent_request_id(parent_run_id, child_thread_id, tool_call_id, agent.slug)
            existing = await repo.get_run_by_request_id(request_id)
            if existing:
                return existing, False

            run = await repo.create_run(
                run_id=str(uuid.uuid4()),
                thread_id=child_thread_id,
                agent_id=subagent_type,
                uid=uid,
                request_id=request_id,
                conversation_id=parent_run.conversation_id,
                parent_agent_run_id=parent_run.id,
                run_type="subagent",
                checkpoint_thread_id=child_thread_id,
                input_payload={
                    "description": description,
                    "tool_call_id": tool_call_id,
                    "subagent_type": subagent_type,
                    "subagent_name": agent.name,
                    "parent_thread_id": parent_thread_id,
                    "child_thread_id": child_thread_id,
                    "continuing": continuing,
                },
            )
            return await repo.mark_running(run.id), True

    async def _set_subagent_run_status(
        self,
        run_id: str,
        status: str,
        *,
        error_type: str | None = None,
        error_message: str | None = None,
    ):
        async with pg_manager.get_async_session_context() as db:
            return await AgentRunRepository(db).set_terminal_status(
                run_id,
                status=status,
                error_type=error_type,
                error_message=error_message,
            )

    def _build_task_tool(self, available_agents: str) -> StructuredTool:
        def task(
            description: Annotated[str, TASK_DESCRIPTION_ARG],
            subagent_type: Annotated[str, SUBAGENT_TYPE_ARG],
            runtime: ToolRuntime,
            thread_id: Annotated[str | None, THREAD_ID_ARG] = None,
        ) -> str:
            return "task The tool only supports asynchronous calls"

        async def atask(
            description: Annotated[str, TASK_DESCRIPTION_ARG],
            subagent_type: Annotated[str, SUBAGENT_TYPE_ARG],
            runtime: ToolRuntime,
            thread_id: Annotated[str | None, THREAD_ID_ARG] = None,
        ) -> str | Command:
            if subagent_type not in self.subagents:
                allowed = ", ".join(f"`{slug}`" for slug in self.subagents)
                return f"Không thể gọi sub-agent {subagent_type}, các sub-agent khả dụng chỉ gồm: {allowed}"
            if not runtime.tool_call_id:
                raise ValueError("Tool call ID is required for subagent invocation")

            parent_thread_id = str(
                getattr(self.parent_context, "parent_thread_id", None) or self.parent_context.thread_id
            )
            file_thread_id = str(getattr(self.parent_context, "file_thread_id", None) or parent_thread_id)
            uid = str(getattr(self.parent_context, "uid", "") or "").strip()
            if not uid:
                return "Không thể gọi sub-agent: thiếu uid trong runtime hiện tại"

            agent = self.subagents[subagent_type]
            backend = _get_agent_backend(agent.backend_id)
            if not backend or agent.backend_id != SUB_AGENT_BACKEND_ID:
                return f"Không thể gọi sub-agent {subagent_type}: cấu hình backend không hợp lệ"

            child_thread_id, continuing = _new_child_thread_id(
                thread_id,
                parent_thread_id=parent_thread_id,
                agent_slug=agent.slug,
                tool_call_id=runtime.tool_call_id,
            )
            subagent_run = {
                "id": runtime.tool_call_id,
                "subagent_type": subagent_type,
                "subagent_name": agent.name,
                "child_thread_id": child_thread_id,
                "description": description,
                "created_at": utc_isoformat(),
            }

            try:
                run, is_new_run = await self._create_subagent_run(
                    child_thread_id=child_thread_id,
                    description=description,
                    subagent_type=subagent_type,
                    agent=agent,
                    uid=uid,
                    parent_thread_id=parent_thread_id,
                    tool_call_id=runtime.tool_call_id,
                    continuing=continuing,
                )
            except ValueError as exc:
                return str(exc)
            subagent_run = _with_run_payload(subagent_run, run)
            if not is_new_run:
                return _reused_run_response(run, runtime.tool_call_id, subagent_run)

            child_context = backend.context_schema()
            config_context = (agent.config_json or {}).get("context") if isinstance(agent.config_json, dict) else None
            child_input_context = await build_agent_input_context(
                config_context if isinstance(config_context, dict) else {},
                thread_id=child_thread_id,
                uid=uid,
                run_id=run.id,
                request_id=run.request_id,
            )
            if not str(child_input_context.get("model") or "").strip():
                parent_model = str(getattr(self.parent_context, "model", "") or "").strip()
                if parent_model:
                    child_input_context["model"] = parent_model
            child_context.update_from_dict(child_input_context)
            child_context.uid = uid
            child_context.thread_id = child_thread_id
            child_context.parent_thread_id = parent_thread_id
            child_context.file_thread_id = file_thread_id
            child_context.skills_thread_id = child_thread_id
            child_context.run_id = run.id
            child_context.request_id = run.request_id
            child_context.is_subagent_runtime = True

            try:
                graph = await backend.get_graph(context=child_context)
                result = await graph.ainvoke(
                    _state_for_child(
                        description,
                        runtime,
                        parent_thread_id=parent_thread_id,
                        file_thread_id=file_thread_id,
                        skills_thread_id=child_thread_id,
                        continuing=continuing,
                    ),
                    config=_child_config(
                        runtime,
                        child_thread_id=child_thread_id,
                        uid=uid,
                        parent_thread_id=parent_thread_id,
                        file_thread_id=file_thread_id,
                        skills_thread_id=child_thread_id,
                        subagent_type=subagent_type,
                        run_id=run.id,
                        request_id=run.request_id,
                    ),
                    context=child_context,
                )
            except asyncio.CancelledError:
                await self._set_subagent_run_status(run.id, "cancelled")
                raise
            except Exception as exc:
                failed_run = await self._set_subagent_run_status(
                    run.id,
                    "failed",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                return _failed_tool_response(exc, runtime.tool_call_id, _with_run_payload(subagent_run, failed_run))
            completed_run = await self._set_subagent_run_status(run.id, "completed")
            return _completed_tool_response(
                result, runtime.tool_call_id, _with_run_payload(subagent_run, completed_run)
            )

        return StructuredTool.from_function(
            name="task",
            func=task,
            coroutine=atask,
            description=TASK_TOOL_DESCRIPTION.format(available_agents=available_agents),
            infer_schema=True,
        )

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        return handler(
            request.override(system_message=append_to_system_message(request.system_message, self.system_prompt))
        )

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        return await handler(
            request.override(system_message=append_to_system_message(request.system_message, self.system_prompt))
        )


async def create_subagent_task_middleware(parent_context) -> YuxiSubAgentMiddleware | None:
    selected_slugs = [
        str(slug).strip() for slug in (getattr(parent_context, "subagents", None) or []) if str(slug).strip()
    ]
    uid = str(getattr(parent_context, "uid", "") or "").strip()
    if not uid:
        return None

    async with pg_manager.get_async_session_context() as db:
        user = await UserRepository().get_by_uid_with_db(db, uid)
        if user is None:
            return None
        repo = AgentRepository(db)
        if selected_slugs:
            subagents: list[Agent] = []
            seen: set[str] = set()
            for slug in selected_slugs:
                if slug in seen:
                    continue
                seen.add(slug)
                agent = await repo.get_visible_subagent_by_slug(slug=slug, user=user)
                if agent and agent.backend_id == SUB_AGENT_BACKEND_ID:
                    subagents.append(agent)
        else:
            subagents = [
                agent
                for agent in await repo.list_visible_subagents(user=user)
                if agent.backend_id == SUB_AGENT_BACKEND_ID
            ]

    if not subagents:
        return None
    return YuxiSubAgentMiddleware(parent_context=parent_context, subagents=subagents)
