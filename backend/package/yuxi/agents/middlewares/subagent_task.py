from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any

from deepagents import SubagentTransformer as DeepAgentsSubagentTransformer
from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware.types import AgentMiddleware, ContextT, ModelRequest, ModelResponse, ResponseT
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import Command

from yuxi.repositories.agent_repository import AgentRepository
from yuxi.repositories.agent_run_repository import TERMINAL_RUN_STATUSES
from yuxi.repositories.user_repository import UserRepository
from yuxi.services.input_message_service import build_chat_input_message
from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import Agent

YUXI_SUBAGENTS_STREAM_KEY = "yuxi_subagents"


def _subagent_run_service_module():
    from yuxi.services import subagent_run_service

    return subagent_run_service


def _async_only_tool(*, name: str, coroutine: Callable[..., Awaitable[Any]], description: str) -> StructuredTool:
    """Công cụ sub-agent chạy nền chỉ thực thi trong luồng bất đồng bộ; chỉ khai báo coroutine, các lệnh gọi đồng bộ sẽ bị lỗi trực tiếp bởi LangChain."""
    return StructuredTool.from_function(name=name, coroutine=coroutine, description=description, infer_schema=True)


class YuxiSubagentTransformer(DeepAgentsSubagentTransformer):
    def init(self) -> dict[str, Any]:
        return {YUXI_SUBAGENTS_STREAM_KEY: self._log}


TASK_SYSTEM_PROMPT = """## `task` (Công cụ giao nhiệm vụ cho sub-agent)

Bạn có thể sử dụng công cụ `task` để giao các nhiệm vụ phụ phức tạp và độc lập cho sub-agent đã được cấu hình xử lý. Sub-agent chỉ trả về kết quả cuối cùng, bạn không thể thấy các bước trung gian của nó.
Kết quả công cụ sẽ bao gồm ID thread của sub-agent. Khi cần tiếp tục cùng một nhiệm vụ phụ sau này, hãy truyền ID đó làm `thread_id` quay lại `task`.

Nguyên tắc sử dụng:
- Sử dụng khi nhiệm vụ đủ phức tạp, có thể hoàn thành độc lập hoặc cần cô lập ngữ cảnh.
- Nhiều nhiệm vụ phụ không phụ thuộc lẫn nhau có thể gọi đồng thời nhiều `task`.
- Truyền `thread_id` từ kết quả trước đó khi tiếp tục một nhiệm vụ sub-agent hiện có; không điền `thread_id` cho nhiệm vụ mới.
- Không gọi đồng thời cùng một `thread_id` để tránh nhiều yêu cầu tiếp tục ghi vào cùng một thread con cùng lúc.
- Không ủy thác cho các câu hỏi đơn giản hoặc chỉ cần một lượng nhỏ cuộc gọi công cụ trực tiếp.
- Khi gọi, phải chọn một `subagent_slug` khả dụng bên dưới và viết rõ mục tiêu, ngữ cảnh và kết quả mong muốn trong `description`.
- Không gọi gián tiếp sub-agent qua shell, curl, HTTP API hoặc dòng lệnh; phải sử dụng công cụ `task` khi cần sub-agent.

Sub-agent chạy nền (background subagent):
- Đối với các nhiệm vụ dài hạn hoặc nhiều nhiệm vụ có thể chạy song song, hãy ưu tiên sử dụng `subagent_start`, nó sẽ trả về ngay lập tức `run_id` và `thread_id`, cho phép agent cha tiếp tục làm việc.
- Tiếp theo, sử dụng `subagent_status` để truy vấn trạng thái, `subagent_events` để đọc các sự kiện gia tăng,
  `subagent_cancel` để hủy bỏ, và `subagent_await` để chờ đợi khi thực sự cần kết quả.
- `thread_id` là ID ngữ cảnh dài hạn của sub-agent; cùng một `thread_id` sau khi hoàn thành có thể tiếp tục tạo lượt chạy (run) mới.
  Nếu luồng đó đã có run đang hoạt động, hệ thống sẽ trả về trạng thái bận (busy) chứ không âm thầm xếp hàng.
- Đối với các nhiệm vụ ngắn hạn mà agent cha bắt buộc phải phụ thuộc ngay vào kết quả, hãy tiếp tục sử dụng `task`.

Available subagent slugs:

{available_agents}"""

TASK_TOOL_DESCRIPTION = """Launch a configured Yuxi subagent to handle an isolated task.

Available subagent slugs:
{available_agents}

Use `subagent_slug` to select one available subagent and put the full task brief in `description`.
Omit `thread_id` for a new task. To continue a previous subagent task, pass the child thread ID returned by
that prior task result as `thread_id`.
Do not call subagents through shell, curl, HTTP APIs, or command-line indirection."""

SUBAGENT_START_DESCRIPTION = """Start a configured Yuxi subagent asynchronously.

Returns a child thread ID for future continuation and a run ID for status/events/cancel/result checks.
Use this for long-running or parallelizable subagent work. If `thread_id` is provided, it continues that subagent
thread when no active run is currently writing to it."""

SUBAGENT_STATUS_DESCRIPTION = """Check a subagent run status by run_id.

Returns the current run status, a compact progress summary with the latest 3 readable messages, and the final result
when the run has reached a terminal status."""

SUBAGENT_EVENTS_DESCRIPTION = """Read recent events for a subagent run by run_id and Redis stream cursor."""

SUBAGENT_CANCEL_DESCRIPTION = """Cancel a running subagent run by run_id."""

SUBAGENT_AWAIT_DESCRIPTION = """Wait for a subagent run to finish and return its final result."""

TASK_DESCRIPTION_ARG = (
    "Mô tả nhiệm vụ cần sub-agent hoàn thành độc lập, bao gồm ngữ cảnh cần thiết và kết quả mong muốn."
)
SUBAGENT_SLUG_ARG = (
    "Định danh (slug) của sub-agent cần gọi, phải là một trong những loại khả dụng được liệt kê trong mô tả công cụ."
)
TASK_THREAD_ID_ARG = "Tùy chọn. ID thread của sub-agent hiện có muốn tiếp tục, thường đến từ kết quả công cụ task trước đó; không điền cho nhiệm vụ mới."
ASYNC_THREAD_ID_ARG = "Tùy chọn. ID thread của sub-agent nền muốn tiếp tục, đến từ thread_id do subagent_start trả về trước đó; không điền cho nhiệm vụ mới."
SUBAGENT_RUN_ID_ARG = "ID chạy (run ID) của sub-agent, được trả về bởi subagent_start."
SUBAGENT_AFTER_SEQ_ARG = "Tùy chọn. Con trỏ dòng sự kiện (stream cursor), truyền 0-0 cho lần đọc đầu tiên; các lần sau truyền last_seq trả về lần trước."
SUBAGENT_EVENT_LIMIT_ARG = "Tùy chọn. Số lượng sự kiện cần đọc, phạm vi từ 1-50."


async def create_subagent_task_middleware(parent_context) -> YuxiSubAgentMiddleware | None:
    """Dựa trên ngữ cảnh của agent cha để tải các sub-agent khả dụng, và tạo middleware task khi có các mục khả dụng."""
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
                agent = await repo.get_visible_by_slug(slug=slug, user=user, kind="subagent")
                if agent:
                    subagents.append(agent)
        else:
            subagents = await repo.list_visible_subagents(user=user)

    if not subagents:
        return None
    return YuxiSubAgentMiddleware(parent_context=parent_context, subagents=subagents)


class YuxiSubAgentMiddleware(AgentMiddleware[Any, ContextT, ResponseT]):
    def __init__(self, *, parent_context, subagents: list[Agent]) -> None:
        super().__init__()
        self.parent_context = parent_context
        self.subagents = {agent.slug: agent for agent in subagents}
        available_agents = "\n".join(f"- {agent.slug}: {agent.description or agent.name}" for agent in subagents)
        self.system_prompt = TASK_SYSTEM_PROMPT.format(available_agents=available_agents)
        self.tools = [self._build_task_tool(available_agents), *self._build_async_subagent_tools(available_agents)]
        self.subagent_names = frozenset(self.subagents)
        self.transformers = [lambda scope: YuxiSubagentTransformer(scope, subagent_names=self.subagent_names)]

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

    def _build_task_tool(self, available_agents: str) -> StructuredTool:
        """Xây dựng công cụ task: khởi chạy sub-agent rồi chặn chờ kết quả cuối cùng."""

        async def atask(
            description: Annotated[str, TASK_DESCRIPTION_ARG],
            subagent_slug: Annotated[str, SUBAGENT_SLUG_ARG],
            runtime: ToolRuntime,
            thread_id: Annotated[str | None, TASK_THREAD_ID_ARG] = None,
        ) -> str | Command:
            started, error = await self._start_subagent(
                description=description,
                subagent_slug=subagent_slug,
                runtime=runtime,
                thread_id=thread_id,
                error_prefix="Không thể gọi sub-agent",
            )
            if error is not None:
                return error

            # Chặn agent cha cho đến khi sub run kết thúc rồi mới đọc kết quả; nếu run thất bại thì result chứa thông tin lỗi
            parent_runtime = started.parent_runtime
            subagent_service = _subagent_run_service_module()
            try:
                from yuxi.services.agent_run_service import AgentRunWaitTimeout, await_agent_run_result

                result = await await_agent_run_result(run_id=started.result.run.id, current_uid=parent_runtime.uid)
                run = await self._get_verified_subagent_run(
                    run_id=started.result.run.id,
                    uid=parent_runtime.uid,
                    created_by_run_id=parent_runtime.created_by_run_id,
                )
            except AgentRunWaitTimeout as exc:
                try:
                    run = await self._get_verified_subagent_run(
                        run_id=started.result.run.id,
                        uid=parent_runtime.uid,
                        created_by_run_id=parent_runtime.created_by_run_id,
                    )
                except ValueError as verify_exc:
                    return str(verify_exc)
                subagent_run = subagent_service.serialize_subagent_run_state(run)
                return _task_wait_timeout_response(exc.result, runtime.tool_call_id, subagent_run)
            except ValueError as exc:
                return str(exc)

            subagent_run = subagent_service.serialize_subagent_run_state(run)
            return _task_result_response(result, runtime.tool_call_id, subagent_run)

        return _async_only_tool(
            name="task",
            coroutine=atask,
            description=TASK_TOOL_DESCRIPTION.format(available_agents=available_agents),
        )

    def _build_async_subagent_tools(self, available_agents: str) -> list[StructuredTool]:
        """Xây dựng các công cụ vòng đời sub-agent chạy nền: start/status/events/cancel/await."""

        async def asubagent_start(
            description: Annotated[str, TASK_DESCRIPTION_ARG],
            subagent_slug: Annotated[str, SUBAGENT_SLUG_ARG],
            runtime: ToolRuntime,
            thread_id: Annotated[str | None, ASYNC_THREAD_ID_ARG] = None,
        ) -> str | Command:
            started, error = await self._start_subagent(
                description=description,
                subagent_slug=subagent_slug,
                runtime=runtime,
                thread_id=thread_id,
                error_prefix="Không thể khởi chạy sub-agent",
            )
            if error is not None:
                return error

            result, agent_item = started.result, started.agent_item
            subagent_service = _subagent_run_service_module()
            payload = {
                "status": "started" if result.created else "existing",
                "run_id": result.run.id,
                "thread_id": result.relation.child_thread_id,
                "subagent_slug": subagent_slug,
                "subagent_name": agent_item.name,
                "created_by_run_id": result.run.created_by_run_id,
                "run_status": result.run.status,
                "continuing": result.continuing,
                "subagent_thread_relation_id": result.relation.id,
                **subagent_service.subagent_run_urls(result.run.id),
            }
            subagent_run = subagent_service.serialize_subagent_run_state(result.run)
            return _json_tool_command(payload, runtime.tool_call_id, subagent_run=subagent_run)

        async def asubagent_status(
            run_id: Annotated[str, SUBAGENT_RUN_ID_ARG],
            runtime: ToolRuntime,
        ) -> str | Command:
            from yuxi.services.agent_run_service import get_agent_run_progress, get_agent_run_result

            parent_runtime, runtime_error = self._require_async_parent_runtime("Không thể truy vấn sub-agent")
            if runtime_error:
                return runtime_error
            try:
                run = await self._get_verified_subagent_run(
                    uid=parent_runtime.uid,
                    created_by_run_id=parent_runtime.created_by_run_id,
                    run_id=run_id,
                )

                # Nếu run đã kết thúc, đọc kết quả cuối cùng; nếu chưa thì result giữ nguyên None
                result = None
                if run.status in TERMINAL_RUN_STATUSES:
                    async with pg_manager.get_async_session_context() as db:
                        result = await get_agent_run_result(run_id=run.id, current_uid=parent_runtime.uid, db=db)

            except ValueError as exc:
                return str(exc)

            subagent_service = _subagent_run_service_module()
            payload = {
                "status": run.status,
                "run_id": run.id,
                "thread_id": run.conversation_thread_id,
                "subagent_slug": run.agent_slug,
                "error": run.error_message,
                "progress": await get_agent_run_progress(run.id),
                **subagent_service.subagent_run_urls(run.id),
            }
            if result:
                payload["result"] = result
            subagent_run = subagent_service.serialize_subagent_run_state(run)
            return _json_tool_command(payload, runtime.tool_call_id, subagent_run=subagent_run)

        async def asubagent_events(
            run_id: Annotated[str, SUBAGENT_RUN_ID_ARG],
            runtime: ToolRuntime,
            after_seq: Annotated[str, SUBAGENT_AFTER_SEQ_ARG] = "0-0",
            limit: Annotated[int, SUBAGENT_EVENT_LIMIT_ARG] = 20,
        ) -> str | Command:
            from yuxi.services.run_queue_service import list_run_stream_events, normalize_after_seq

            parent_runtime, runtime_error = self._require_async_parent_runtime("Không thể đọc sự kiện sub-agent")
            if runtime_error:
                return runtime_error
            try:
                await self._get_verified_subagent_run(
                    run_id=run_id,
                    uid=parent_runtime.uid,
                    created_by_run_id=parent_runtime.created_by_run_id,
                )  # Xác thực quyền sở hữu sub-agent
            except ValueError as exc:
                return str(exc)

            normalized_after_seq = normalize_after_seq(after_seq)
            event_limit = min(50, max(1, int(limit or 20)))
            events = await list_run_stream_events(run_id, after_seq=normalized_after_seq, limit=event_limit)
            payload = {
                "status": "ok",
                "run_id": run_id,
                "after_seq": normalized_after_seq,
                "last_seq": str(events[-1]["seq"]) if events else normalized_after_seq,
                "events": events,
            }
            return _json_tool_command(payload, runtime.tool_call_id)

        async def asubagent_cancel(
            run_id: Annotated[str, SUBAGENT_RUN_ID_ARG],
            runtime: ToolRuntime,
        ) -> str | Command:
            from yuxi.services.agent_run_service import request_cancel_agent_run

            parent_runtime, runtime_error = self._require_async_parent_runtime("Không thể hủy sub-agent")
            if runtime_error:
                return runtime_error
            try:
                await self._get_verified_subagent_run(
                    run_id=run_id,
                    uid=parent_runtime.uid,
                    created_by_run_id=parent_runtime.created_by_run_id,
                )  # Xác thực quyền sở hữu sub-agent

                # Hủy lượt chạy sub-agent, trả về trạng thái run mới nhất
                async with pg_manager.get_async_session_context() as db:
                    run = await request_cancel_agent_run(run_id=run_id, current_uid=parent_runtime.uid, db=db)

            except ValueError as exc:
                return str(exc)

            subagent_service = _subagent_run_service_module()
            payload = {
                "status": run.status,
                "run_id": run.id,
                "thread_id": run.conversation_thread_id,
                **subagent_service.subagent_run_urls(run.id),
            }
            subagent_run = subagent_service.serialize_subagent_run_state(run)
            return _json_tool_command(payload, runtime.tool_call_id, subagent_run=subagent_run)

        async def asubagent_await(
            run_id: Annotated[str, SUBAGENT_RUN_ID_ARG],
            runtime: ToolRuntime,
        ) -> str | Command:
            from yuxi.services.agent_run_service import AgentRunWaitTimeout, await_agent_run_result

            parent_runtime, runtime_error = self._require_async_parent_runtime("Không thể chờ sub-agent")
            if runtime_error:
                return runtime_error
            wait_timed_out = False
            try:
                # Xác thực quyền sở hữu run trước khi chờ, tránh chờ trái phép tác vụ con khác
                await self._get_verified_subagent_run(
                    run_id=run_id,
                    uid=parent_runtime.uid,
                    created_by_run_id=parent_runtime.created_by_run_id,
                )
                # Sau khi chờ xong, đọc lại trạng thái run đã xác thực mới nhất
                result = await await_agent_run_result(run_id=run_id, current_uid=parent_runtime.uid)
                run = await self._get_verified_subagent_run(
                    run_id=run_id,
                    uid=parent_runtime.uid,
                    created_by_run_id=parent_runtime.created_by_run_id,
                )
            except AgentRunWaitTimeout as exc:
                wait_timed_out = True
                result = exc.result
                try:
                    run = await self._get_verified_subagent_run(
                        run_id=run_id,
                        uid=parent_runtime.uid,
                        created_by_run_id=parent_runtime.created_by_run_id,
                    )
                except ValueError as verify_exc:
                    return str(verify_exc)
            except ValueError as exc:
                return str(exc)

            subagent_service = _subagent_run_service_module()
            payload = {
                "status": run.status,
                "run_id": run.id,
                "thread_id": run.conversation_thread_id,
                "result": result,
            }
            if wait_timed_out:
                payload["wait_timed_out"] = True
                payload["message"] = (
                    "Sub-agent vẫn đang chạy, chờ kết quả cuối cùng đã hết thời gian; vui lòng truy vấn lại sau."
                )
            subagent_run = subagent_service.serialize_subagent_run_state(run)
            return _json_tool_command(payload, runtime.tool_call_id, subagent_run=subagent_run)

        return [
            _async_only_tool(
                name="subagent_start",
                coroutine=asubagent_start,
                description=SUBAGENT_START_DESCRIPTION + "\n\nAvailable subagent slugs:\n" + available_agents,
            ),
            _async_only_tool(
                name="subagent_status",
                coroutine=asubagent_status,
                description=SUBAGENT_STATUS_DESCRIPTION,
            ),
            _async_only_tool(
                name="subagent_events",
                coroutine=asubagent_events,
                description=SUBAGENT_EVENTS_DESCRIPTION,
            ),
            _async_only_tool(
                name="subagent_cancel",
                coroutine=asubagent_cancel,
                description=SUBAGENT_CANCEL_DESCRIPTION,
            ),
            _async_only_tool(
                name="subagent_await",
                coroutine=asubagent_await,
                description=SUBAGENT_AWAIT_DESCRIPTION,
            ),
        ]

    def _parent_runtime(self) -> _ParentRuntime:
        """Trích xuất thông tin parent run tối thiểu cần thiết cho sub-agent từ context của agent cha."""
        parent_thread_id = str(getattr(self.parent_context, "parent_thread_id", None) or self.parent_context.thread_id)
        file_thread_id = str(getattr(self.parent_context, "file_thread_id", None) or parent_thread_id)
        uid = str(getattr(self.parent_context, "uid", "") or "").strip()
        created_by_run_id = str(getattr(self.parent_context, "run_id", "") or "").strip()
        return _ParentRuntime(
            file_thread_id=file_thread_id,
            uid=uid,
            created_by_run_id=created_by_run_id,
        )

    def _require_async_parent_runtime(self, error_prefix: str) -> tuple[_ParentRuntime, str | None]:
        """Xác thực context parent run mà công cụ sub-agent nền phải phụ thuộc."""
        parent_runtime = self._parent_runtime()
        if not parent_runtime.uid:
            return parent_runtime, f"{error_prefix}: runtime hiện tại thiếu uid"
        if not parent_runtime.created_by_run_id:
            return parent_runtime, f"{error_prefix}: runtime hiện tại thiếu parent run ID"
        return parent_runtime, None

    async def _start_subagent(
        self,
        *,
        description: str,
        subagent_slug: str,
        runtime: ToolRuntime,
        thread_id: str | None,
        error_prefix: str,
    ) -> tuple[_StartedSubagent | None, str | Command | None]:
        """Xác thực và khởi chạy (hoặc tiếp tục) sub-agent run nền; thành công trả về kết quả khởi động, thất bại trả về phản hồi lỗi trực tiếp."""
        if subagent_slug not in self.subagents:
            allowed = ", ".join(f"`{slug}`" for slug in self.subagents)
            return None, f"Không thể gọi sub-agent {subagent_slug}, các sub-agent khả dụng chỉ có: {allowed}"
        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for subagent invocation")

        parent_runtime, runtime_error = self._require_async_parent_runtime(error_prefix)
        if runtime_error:
            return None, runtime_error

        agent_item = self.subagents[subagent_slug]
        input_message = build_chat_input_message(description)
        subagent_service = _subagent_run_service_module()
        try:
            async with pg_manager.get_async_session_context() as db:
                result = await subagent_service.SubagentRunService(db).start(
                    uid=parent_runtime.uid,
                    created_by_run_id=parent_runtime.created_by_run_id,
                    agent_item=agent_item,
                    input_message=input_message,
                    tool_call_id=runtime.tool_call_id,
                    requested_thread_id=thread_id,
                    file_thread_id=parent_runtime.file_thread_id,
                    model_spec=self._subagent_model_override(agent_item),
                )
        except subagent_service.SubagentRunBusy as exc:
            return None, _json_tool_command(exc.to_payload(), runtime.tool_call_id)
        except ValueError as exc:
            return None, str(exc)
        return _StartedSubagent(result=result, parent_runtime=parent_runtime, agent_item=agent_item), None

    def _subagent_model_override(self, agent_item: Agent) -> str | None:
        """Khi sub-agent không cấu hình mô-đun rõ ràng, kế thừa mô hình hiện tại của agent cha."""
        config_context = (
            (agent_item.config_json or {}).get("context") if isinstance(agent_item.config_json, dict) else None
        )
        configured_model = ""
        if isinstance(config_context, dict):
            configured_model = str(config_context.get("model") or "").strip()
        if configured_model:
            return None
        return str(getattr(self.parent_context, "model", None) or "").strip() or None

    async def _get_verified_subagent_run(self, *, run_id: str, uid: str, created_by_run_id: str):
        """Trước khi gọi công cụ, xác thực quyền sở hữu của run con theo phạm vi run cha."""
        subagent_service = _subagent_run_service_module()
        async with pg_manager.get_async_session_context() as db:
            return await subagent_service.SubagentRunService(db).get_run_for_creator(
                uid=uid,
                created_by_run_id=created_by_run_id,
                run_id=run_id,
            )


@dataclass(frozen=True)
class _ParentRuntime:
    file_thread_id: str
    uid: str
    created_by_run_id: str


@dataclass(frozen=True)
class _StartedSubagent:
    """Kết quả của _start_subagent: các thành phần khởi chạy run con và ngữ cảnh chạy của agent cha mà nó phụ thuộc."""

    result: Any  # SubagentStartResult
    parent_runtime: _ParentRuntime
    agent_item: Agent


def _task_result_response(result: dict[str, Any], tool_call_id: str, subagent_run: dict[str, Any]) -> Command:
    """Chuyển đổi kết quả cuối cùng của run sub-agent chạy nền thành kết quả công cụ task đồng bộ."""
    output = str(result.get("output") or "").strip()
    error = result.get("error") if isinstance(result.get("error"), dict) else None
    if not output and error:
        output = str(error.get("message") or "Sub-agent chạy thất bại")
    if not output:
        output = "Sub-agent đã hoàn thành nhiệm vụ nhưng không trả về kết quả văn bản."

    tool_result = _tool_result_with_thread_id(subagent_run["child_thread_id"], output)
    return Command(
        update={"messages": [ToolMessage(tool_result, tool_call_id=tool_call_id)], "subagent_runs": [subagent_run]}
    )


def _task_wait_timeout_response(result: dict[str, Any], tool_call_id: str, subagent_run: dict[str, Any]) -> Command:
    """Khi thời gian chờ đợi task đồng bộ đạt đến giới hạn tối đa, thông báo rõ ràng cho agent cha rằng run con vẫn chưa kết thúc."""
    status = str(result.get("status") or subagent_run.get("status") or "running")
    run_id = str(result.get("agent_run_id") or subagent_run["run_id"])
    output = (
        f"Sub-agent vẫn đang chạy (status: {status}), chưa trả về kết quả văn bản cuối cùng.\n"
        f"run_id: {run_id}\n"
        "Vui lòng sử dụng subagent_status hoặc subagent_await để truy vấn kết quả sau; không xem kết quả hiện tại là nhiệm vụ đã hoàn thành."
    )
    tool_result = _tool_result_with_thread_id(subagent_run["child_thread_id"], output)
    return Command(
        update={"messages": [ToolMessage(tool_result, tool_call_id=tool_call_id)], "subagent_runs": [subagent_run]}
    )


def _json_tool_command(
    payload: dict[str, Any],
    tool_call_id: str,
    *,
    subagent_run: dict[str, Any] | None = None,
) -> Command:
    """Đóng gói kết quả cấu trúc của công cụ sub-agent chạy nền vào ToolMessage."""
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    update: dict[str, Any] = {"messages": [ToolMessage(content, tool_call_id=tool_call_id)]}
    if subagent_run is not None:
        update["subagent_runs"] = [subagent_run]
    return Command(update=update)


def _tool_result_with_thread_id(child_thread_id: str, content: str) -> str:
    """Đặt ID thread con vào kết quả công cụ, thuận tiện cho việc tiếp tục cùng một nhiệm vụ phụ sau này."""
    return f"> ID thread sub-agent: {child_thread_id}\n\n---\n\n{content}"
