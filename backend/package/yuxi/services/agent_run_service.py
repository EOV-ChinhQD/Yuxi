"""AgentRun lifecycle service.

This module owns the durable ``AgentRun`` contract: validating the run scope,
persisting the input message, creating the run row, enqueueing worker execution,
streaming run events, loading final results and requesting cancellation.

Keep source-specific orchestration outside this file. Normal chat, external
invocation and subagent tools may all create AgentRun records, but each caller
should translate its own request shape into this module's public run APIs first.
The worker then executes every run through the same queue and ``chat_service``
runtime path, so this module must not depend on agent-call, evaluation or
subagent presentation details.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.agents.buildin import agent_manager
from yuxi.agents.models import resolve_chat_model_spec
from yuxi.models.providers.cache import model_cache
from yuxi.repositories.agent_repository import AgentRepository
from yuxi.repositories.agent_run_repository import TERMINAL_RUN_STATUSES, AgentRunRepository
from yuxi.repositories.conversation_repository import ConversationRepository
from yuxi.services.input_message_service import (
    AgentRunInputMessage,
    build_resume_input_message,
)
from yuxi.services.run_queue_service import (
    build_run_event_envelope,
    get_arq_pool,
    get_last_run_stream_seq,
    list_recent_run_stream_events,
    list_run_stream_events,
    normalize_after_seq,
    publish_cancel_signal,
)
from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import Message, User
from yuxi.utils.datetime_utils import utc_now_naive
from yuxi.utils.hash_utils import hash_id
from yuxi.utils.logging_config import logger

SSE_HEARTBEAT_SECONDS = int(os.getenv("RUN_SSE_HEARTBEAT_SECONDS", "15"))  # Thời gian SSE rảnh trước khi gửi heartbeat
SSE_MAX_CONNECTION_MINUTES = int(
    os.getenv("RUN_SSE_MAX_CONNECTION_MINUTES", "30")
)  # Thời gian tồn tại tối đa của kết nối SSE
SSE_POLL_INTERVAL_SECONDS = float(os.getenv("RUN_SSE_POLL_INTERVAL_SECONDS", "1.0"))  # Khoảng cách polling SSE
RUN_PROGRESS_RECENT_EVENT_SCAN_LIMIT = 100
RUN_PROGRESS_MESSAGE_LIMIT = 3
RUN_PROGRESS_CONTENT_MAX_CHARS = 800


def _resolve_agent_run_request_id(
    *,
    meta: dict,
    run_type: Literal["chat", "resume"],
    resume: object | None,
    created_by_run_id: str | None,
) -> str:
    raw_request_id = meta.get("request_id")
    if raw_request_id:
        return str(raw_request_id)
    if run_type == "resume":
        resume_key = json.dumps(resume, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hash_id("resume:", f"{created_by_run_id}:{resume_key}", length=64)
    return str(uuid.uuid4())


class AgentRunWaitTimeout(Exception):
    """Chờ kết thúc nhưng run chưa chuyển sang trạng thái cuối."""

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        status = str(result.get("status") or "unknown")
        run_id = str(result.get("agent_run_id") or result.get("run_id") or "")
        super().__init__(f"agent run {run_id} is still {status} after waiting")


def resolve_agent_run_model_spec(model_spec: str | None, agent_item, agent_backend) -> str:
    """Xác định model thực tế được dùng trong lượt run này: ghi đè rõ ràng ưu tiên nhất, sau đó đến model cấu hình, cuối cùng là model hệ thống."""
    normalized = model_spec.strip() if isinstance(model_spec, str) else None
    if normalized:
        info = model_cache.get_model_info(normalized)
        if not info or info.model_type != "chat":
            raise HTTPException(status_code=422, detail=f"Không tìm thấy mô hình chat khả dụng: '{normalized}'")
        return normalized

    context = agent_backend.context_schema()
    config_json = getattr(agent_item, "config_json", None) or {}
    config_context = config_json.get("context") if isinstance(config_json, dict) else {}
    if isinstance(config_context, dict):
        context.update_from_dict(config_context)

    return resolve_chat_model_spec(getattr(context, "model", None))


def _build_run_response(run) -> dict:
    return {
        "run_id": run.id,
        "thread_id": run.conversation_thread_id,
        "status": run.status,
        "request_id": run.request_id,
        "stream_url": f"/api/agent/runs/{run.id}/events",
    }


def _format_sse(data: dict, event: str, event_id: str | None = None) -> str:
    lines = [f"event: {event}", f"data: {json.dumps(data, ensure_ascii=False)}"]
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append("")
    return "\n".join(lines) + "\n"


def _format_heartbeat() -> str:
    return ": heartbeat\n\n"


def _compact_message_dict(message: dict) -> dict:
    compact = {
        key: message[key] for key in ("id", "role", "content", "type", "message_type") if message.get(key) is not None
    }
    extra_metadata = message.get("extra_metadata")
    if isinstance(extra_metadata, dict) and extra_metadata.get("attachments"):
        compact["extra_metadata"] = {"attachments": extra_metadata["attachments"]}
    return compact


def _compact_semantic_stream_event(stream_event: dict) -> dict:
    event_type = stream_event.get("type")
    if event_type == "message_delta":
        return {
            key: stream_event[key]
            for key in ("type", "message_id", "content", "reasoning_content", "additional_reasoning_content")
            if stream_event.get(key)
        }

    if event_type in {"tool_call", "tool_call_delta"}:
        compact = {
            key: stream_event[key]
            for key in ("type", "message_id", "tool_call_id", "name", "args", "args_delta")
            if stream_event.get(key) is not None and stream_event.get(key) != ""
        }
        if stream_event.get("index"):
            compact["index"] = stream_event["index"]
        return compact

    return {key: value for key, value in stream_event.items() if key not in {"thread_id", "namespace"}}


def _compact_tool_stream_event(event: dict) -> dict:
    compact = {key: event[key] for key in ("method",) if event.get(key)}
    data = event.get("data")
    if isinstance(data, dict):
        compact_data = {
            key: data[key]
            for key in ("event", "tool_call_id", "tool_name", "output", "error")
            if data.get(key) is not None and data.get(key) != ""
        }
        if compact_data:
            compact["data"] = compact_data
    return compact


def _compact_stream_chunk(chunk: dict) -> dict:
    compact = {
        key: chunk[key]
        for key in (
            "status",
            "run_id",
            "message",
            "error_type",
            "error_message",
            "retryable",
            "job_try",
            "questions",
            "interrupt_info",
            "source",
            "agent_state",
            "compression",
        )
        if chunk.get(key) is not None and chunk.get(key) != ""
    }
    if isinstance(chunk.get("msg"), dict):
        compact["msg"] = _compact_message_dict(chunk["msg"])
    if isinstance(chunk.get("stream_event"), dict):
        compact["stream_event"] = _compact_semantic_stream_event(chunk["stream_event"])
    if isinstance(chunk.get("event"), dict):
        compact["event"] = _compact_tool_stream_event(chunk["event"])
    return compact


def _request_id_from_chunk(chunk: object) -> str | None:
    if not isinstance(chunk, dict):
        return None
    request_id = chunk.get("request_id")
    if isinstance(request_id, str) and request_id:
        return request_id
    msg = chunk.get("msg")
    extra_metadata = msg.get("extra_metadata") if isinstance(msg, dict) else None
    if isinstance(extra_metadata, dict):
        request_id = extra_metadata.get("request_id")
        if isinstance(request_id, str) and request_id:
            return request_id
    return None


def _request_id_from_payload(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    request_id = payload.get("request_id")
    if isinstance(request_id, str) and request_id:
        return request_id
    request_id = _request_id_from_chunk(payload.get("chunk"))
    if request_id:
        return request_id
    items = payload.get("items")
    if isinstance(items, list):
        for item in items:
            request_id = _request_id_from_chunk(item)
            if request_id:
                return request_id
    return None


def _compact_run_event_payload(event_type: str, payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {}

    if event_type == "messages":
        compact: dict = {}
        if isinstance(payload.get("items"), list):
            compact["items"] = [
                _compact_stream_chunk(item) if isinstance(item, dict) else item for item in payload["items"]
            ]
        if isinstance(payload.get("chunk"), dict):
            compact["chunk"] = _compact_stream_chunk(payload["chunk"])
        return compact

    compact = {key: value for key, value in payload.items() if key not in {"chunk", "request_id"}}
    if isinstance(payload.get("chunk"), dict):
        compact["chunk"] = _compact_stream_chunk(payload["chunk"])
    return compact


def _is_empty_agent_state(agent_state: object) -> bool:
    if not isinstance(agent_state, dict):
        return False
    return all(not value for value in agent_state.values())


def _compact_run_event_envelope(envelope: dict) -> dict | None:
    event_type = str(envelope.get("event") or "")
    payload = envelope.get("payload")
    if event_type == "metadata":
        return None
    if event_type == "custom" and isinstance(payload, dict) and payload.get("name") == "yuxi.agent_state":
        state = payload.get("agent_state")
        chunk = payload.get("chunk") if isinstance(payload.get("chunk"), dict) else {}
        if _is_empty_agent_state(state) or _is_empty_agent_state(chunk.get("agent_state")):
            return None

    compact = {key: envelope[key] for key in ("run_id", "thread_id") if key in envelope}
    request_id = _request_id_from_payload(payload)
    if request_id:
        compact["request_id"] = request_id
    compact["payload"] = _compact_run_event_payload(event_type, payload)
    return compact


def _progress_message_from_chunk(chunk: dict, *, seq: str) -> dict | None:
    """Chuyển đổi một message chunk thành một mục tiến trình hiển thị trong status."""
    stream_event = chunk.get("stream_event")
    if not isinstance(stream_event, dict):
        return None
    stream_type = stream_event.get("type")
    message_id = str(stream_event.get("message_id") or "").strip()

    content = ""
    kind = ""
    if stream_type == "message_delta":
        content = (
            stream_event.get("content")
            or stream_event.get("reasoning_content")
            or stream_event.get("additional_reasoning_content")
            or ""
        )
        kind = "assistant_message" if stream_event.get("content") else "assistant_reasoning"
    elif stream_type in {"tool_call", "tool_call_delta"}:
        tool_name = str(stream_event.get("name") or stream_event.get("tool_call_id") or "công cụ").strip()
        content = f"Gọi công cụ {tool_name}" if stream_type == "tool_call" else f"Đang chuẩn bị công cụ {tool_name}"
        kind = stream_type
    else:
        return None

    content = str(content).strip()
    if not content:
        return None
    if len(content) > RUN_PROGRESS_CONTENT_MAX_CHARS:
        content = "..." + content[-RUN_PROGRESS_CONTENT_MAX_CHARS:]

    base = {"seq": seq}
    if message_id:
        base["message_id"] = message_id
    tool_call_id = str(stream_event.get("tool_call_id") or "").strip()
    if tool_call_id:
        base["tool_call_id"] = tool_call_id
    return {**base, "kind": kind, "content": content}


async def get_agent_run_progress(run_id: str, *, message_limit: int = RUN_PROGRESS_MESSAGE_LIMIT) -> dict:
    """Lấy snapshot tiến trình nhẹ để trả về khi polling status."""
    try:
        events = await list_recent_run_stream_events(run_id, limit=RUN_PROGRESS_RECENT_EVENT_SCAN_LIMIT)
    except Exception as e:
        logger.warning(f"Failed to read run progress events for run {run_id}: {e}")
        return {"last_seq": "0-0", "messages": []}

    last_seq = str(events[0]["seq"]) if events else "0-0"
    limit = max(1, int(message_limit or RUN_PROGRESS_MESSAGE_LIMIT))
    messages = []

    for event in events:
        envelope = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event.get("event_type") != "messages" and envelope.get("event") != "messages":
            continue
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            continue

        chunks = []
        if isinstance(payload.get("chunk"), dict):
            chunks.append(payload["chunk"])
        if isinstance(payload.get("items"), list):
            chunks.extend(item for item in payload["items"] if isinstance(item, dict))

        for chunk in reversed(chunks):
            message = _progress_message_from_chunk(chunk, seq=str(event.get("seq") or ""))
            if message:
                messages.append(message)
            if len(messages) >= limit:
                return {"last_seq": last_seq, "messages": list(reversed(messages))}

    return {"last_seq": last_seq, "messages": list(reversed(messages))}


async def create_agent_run_view(
    *,
    input_message: AgentRunInputMessage | None,
    agent_slug: str,
    thread_id: str,
    meta: dict,
    current_uid: str,
    db: AsyncSession,
    model_spec: str | None = None,
    resume: object | None = None,
    created_by_run_id: str | None = None,
) -> dict:
    """HTTP entry point tạo chat/resume run, nội dung đầu vào do Message chứa; run chỉ ghi nhận metadata thực thi."""
    meta = meta or {}
    if input_message is None and resume is None:
        raise HTTPException(status_code=422, detail="input_message hoặc resume không được để trống")

    run_type = "resume" if resume is not None else "chat"
    run_created_by_id = created_by_run_id if run_type == "resume" else None
    request_id = _resolve_agent_run_request_id(
        meta=meta,
        run_type=run_type,
        resume=resume,
        created_by_run_id=run_created_by_id,
    )

    scope = await prepare_agent_run_creation_scope(
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
        current_uid=current_uid,
        db=db,
        request_id=request_id,
        run_type=run_type,
        agent_kind="main",
        created_by_run_id=run_created_by_id,
    )
    if scope.existing_run:
        return _build_run_response(scope.existing_run)

    if run_type == "resume":
        resolved_model_spec = scope.parent_run.input_payload["model_spec"]
    else:
        resolved_model_spec = resolve_agent_run_model_spec(model_spec, scope.agent_item, scope.agent_backend)

    run_input_message = _prepare_run_input_message(
        run_type=run_type,
        input_message=input_message,
        resume=resume,
        request_id=request_id,
        model_spec=resolved_model_spec,
        meta=meta,
    )

    persisted_input_message = await create_agent_run_input_message(
        db=db,
        conversation_id=scope.conversation.id,
        request_id=request_id,
        input_message=run_input_message,
    )
    input_payload = {"model_spec": resolved_model_spec}

    run, created = await persist_agent_run_record(
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
        current_uid=current_uid,
        db=db,
        request_id=request_id,
        conversation_id=scope.conversation.id,
        run_type=run_type,
        input_payload=input_payload,
        persisted_input_message=persisted_input_message,
        created_by_run_id=run_created_by_id,
    )
    if created:
        await db.commit()
        await enqueue_agent_run(run.id)

    return _build_run_response(run)


@dataclass(frozen=True)
class AgentRunCreationScope:
    """Phạm vi database sau khi kiểm tra tiền điều kiện tạo run, tránh nhầm lẫn với Agent runtime context."""

    conversation: Any
    agent_item: Any
    agent_backend: Any
    existing_run: Any | None
    parent_run: Any | None = None


def _prepare_run_input_message(
    *,
    run_type: Literal["chat", "resume"],
    input_message: AgentRunInputMessage | None,
    resume: object | None,
    request_id: str,
    model_spec: str,
    meta: dict,
) -> AgentRunInputMessage:
    metadata: dict[str, Any] = {"request_id": request_id}
    if attachment_file_ids := (meta.get("attachment_file_ids") or []):
        metadata["attachment_file_ids"] = attachment_file_ids
    if source := meta.get("source"):
        metadata["source"] = source
    if isinstance(meta.get("agent_invocation_meta"), dict):
        metadata["agent_invocation_meta"] = meta["agent_invocation_meta"]
    if run_type == "chat":
        if input_message is None:
            raise HTTPException(status_code=422, detail="input_message không được để trống")
        if raw_message := input_message.raw_message():
            metadata["raw_message"] = raw_message
        return input_message.with_metadata(metadata)

    metadata["resume"] = resume
    metadata["source"] = "ask_user_question_resume"
    return build_resume_input_message(resume).with_metadata(metadata)


def _same_run_request_scope(
    run,
    *,
    uid: str,
    agent_slug: str,
    conversation_thread_id: str,
    run_type: str,
    created_by_run_id: str | None = None,
    subagent_thread_relation_id: int | None = None,
) -> bool:
    """Kiểm tra xem run được command thượng có thực sự thuộc cùng một yêu cầu tạo ngữ nghĩa hay không."""
    return (
        run.uid == str(uid)
        and run.agent_slug == agent_slug
        and run.conversation_thread_id == conversation_thread_id
        and run.run_type == run_type
        and run.created_by_run_id == created_by_run_id
        and getattr(run, "subagent_thread_relation_id", None) == subagent_thread_relation_id
    )


def _run_busy_exception(*, active_run, agent_slug: str, conversation_thread_id: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "run_busy",
            "message": "Luồng agent này đang chạy, vui lòng chờ, truy vấn hoặc hủy lượt chạy hiện tại trước khi tiếp tục",
            "active_run_id": active_run.id,
            "active_run_status": active_run.status,
            "agent_slug": agent_slug,
            "thread_id": conversation_thread_id,
        },
    )


async def create_agent_run_input_message(
    *,
    db: AsyncSession,
    conversation_id: int,
    request_id: str,
    input_message: AgentRunInputMessage,
) -> Message:
    """Lưu tin nhắn đầu vào trước; sau khi tạo run sẽ điền lại run_id, tránh Message foreign key trỏ vào run chưa tồn tại."""
    message = Message(
        conversation_id=conversation_id,
        role="user",
        content=input_message.content,
        message_type=input_message.message_type,
        image_content=input_message.image_content,
        request_id=request_id,
        delivery_status="complete",
        extra_metadata=input_message.extra_metadata,
    )
    db.add(message)
    await db.flush()
    return message


async def persist_agent_run_record(
    *,
    agent_slug: str,
    conversation_thread_id: str,
    current_uid: str,
    db: AsyncSession,
    request_id: str,
    conversation_id: int,
    run_type: str,
    input_payload: dict,
    persisted_input_message: Message,
    created_by_run_id: str | None = None,
    subagent_thread_relation_id: int | None = None,
) -> tuple[Any, bool]:
    """Ghi nhận một AgentRun và gắn với tin nhắn đầu vào đã tạo; trả về cờ tạo mới hay không."""
    run_id = str(uuid.uuid4())
    try:
        async with db.begin_nested():
            run = await AgentRunRepository(db).create_run(
                run_id=run_id,
                conversation_thread_id=conversation_thread_id,
                agent_slug=agent_slug,
                uid=str(current_uid),
                request_id=request_id,
                input_payload=input_payload,
                conversation_id=conversation_id,
                created_by_run_id=created_by_run_id,
                subagent_thread_relation_id=subagent_thread_relation_id,
                run_type=run_type,
                input_message_id=persisted_input_message.id,
            )
            persisted_input_message.run_id = run_id
            await db.flush()
    except IntegrityError:
        run_repo = AgentRunRepository(db)
        existing = await run_repo.get_run_by_request_id(request_id)
        if existing and _same_run_request_scope(
            existing,
            uid=str(current_uid),
            agent_slug=agent_slug,
            conversation_thread_id=conversation_thread_id,
            run_type=run_type,
            created_by_run_id=created_by_run_id,
            subagent_thread_relation_id=subagent_thread_relation_id,
        ):
            await db.delete(persisted_input_message)
            await db.flush()
            return existing, False
        active_run = await run_repo.get_active_run_by_thread_for_user(
            agent_slug=agent_slug,
            conversation_thread_id=conversation_thread_id,
            uid=str(current_uid),
        )
        if active_run:
            raise _run_busy_exception(
                active_run=active_run,
                agent_slug=agent_slug,
                conversation_thread_id=conversation_thread_id,
            )
        raise HTTPException(status_code=409, detail="Trùng lặp request_id")

    return run, True


async def prepare_agent_run_creation_scope(
    *,
    agent_slug: str,
    conversation_thread_id: str,
    current_uid: str,
    db: AsyncSession,
    request_id: str,
    run_type: Literal["chat", "resume", "subagent"],
    agent_kind: Literal["main", "subagent"],
    created_by_run_id: str | None = None,
    subagent_thread_relation_id: int | None = None,
) -> AgentRunCreationScope:
    """Kiểm tra điều kiện tạo run, tải hội thoại/agent/backend và trạng thái idempotency; từ chối ghi đồng thời vào cùng thread."""
    if not conversation_thread_id:
        raise HTTPException(status_code=422, detail="conversation_thread_id không được để trống")

    conversation = await ConversationRepository(db).get_conversation_by_thread_id(conversation_thread_id)
    if not conversation or conversation.uid != str(current_uid) or conversation.status == "deleted":
        raise HTTPException(status_code=404, detail="Thread đối thoại không tồn tại")
    if conversation.agent_id != agent_slug:
        raise HTTPException(status_code=409, detail="Thread hiện tại đã liên kết với agent khác, không thể chuyển đổi")

    user_result = await db.execute(select(User).where(User.uid == str(current_uid)))
    current_user = user_result.scalar_one_or_none()
    if not current_user:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")

    agent_repo = AgentRepository(db)
    agent_item = await agent_repo.get_visible_by_slug(slug=agent_slug, user=current_user, kind=agent_kind)
    if not agent_item:
        raise HTTPException(status_code=404, detail="Agent không tồn tại")

    agent_backend = agent_manager.get_agent(agent_item.backend_id)
    if not agent_backend:
        raise HTTPException(status_code=404, detail=f"Agent backend {agent_item.backend_id} không tồn tại")

    run_repo = AgentRunRepository(db)
    existing = await run_repo.get_run_by_request_id(request_id)
    if existing and existing.uid != str(current_uid):
        raise HTTPException(status_code=409, detail="Trùng lặp request_id")
    if existing and not _same_run_request_scope(
        existing,
        uid=str(current_uid),
        agent_slug=agent_slug,
        conversation_thread_id=conversation_thread_id,
        run_type=run_type,
        created_by_run_id=created_by_run_id,
        subagent_thread_relation_id=subagent_thread_relation_id,
    ):
        raise HTTPException(status_code=409, detail="Trùng lặp request_id")
    parent_run = None
    if run_type == "resume":
        if not created_by_run_id:
            raise HTTPException(status_code=422, detail="created_by_run_id không được để trống")
        if not existing:
            parent_run = await run_repo.get_run_for_user(created_by_run_id, str(current_uid))
            if not parent_run or parent_run.conversation_thread_id != conversation_thread_id:
                raise HTTPException(status_code=404, detail="Lượt chạy cần khôi phục không tồn tại")
            if parent_run.status != "interrupted":
                raise HTTPException(
                    status_code=409, detail="Chỉ lượt chạy bị ngắt (interrupted run) mới có thể khôi phục"
                )
            parent_payload = parent_run.input_payload
            if not isinstance(parent_payload, dict) or not parent_payload.get("model_spec"):
                raise HTTPException(status_code=409, detail="Lượt chạy cần khôi phục thiếu ảnh chụp mô hình")
    if not existing:
        active_run = await run_repo.get_active_run_by_thread_for_user(
            agent_slug=agent_slug,
            conversation_thread_id=conversation_thread_id,
            uid=str(current_uid),
        )
        if active_run:
            raise _run_busy_exception(
                active_run=active_run,
                agent_slug=agent_slug,
                conversation_thread_id=conversation_thread_id,
            )
    return AgentRunCreationScope(
        conversation=conversation,
        agent_item=agent_item,
        agent_backend=agent_backend,
        existing_run=existing,
        parent_run=parent_run,
    )


async def enqueue_agent_run(run_id: str) -> None:
    """Gửi run đã được lưu vào hàng đợi worker nền."""
    queue = await get_arq_pool()
    await queue.enqueue_job("process_agent_run", run_id, _job_id=f"run:{run_id}")


async def get_agent_run_view(*, run_id: str, current_uid: str, db: AsyncSession) -> dict:
    repo = AgentRunRepository(db)
    run = await repo.get_run_for_user(run_id, str(current_uid))
    if not run:
        raise HTTPException(status_code=404, detail="Lượt chạy không tồn tại")
    return {"run": run.to_dict()}


def _select_output_message(messages: list[Message], *, output_message_id: int | None) -> Message | None:
    """Ưu tiên dùng output message của run; nếu không có thì fallback sang tin nhắn assistant cuối cùng."""
    if output_message_id:
        for message in messages:
            if message.id == output_message_id and message.role == "assistant":
                return message

    for message in reversed(messages):
        if message.role == "assistant":
            return message
    return None


async def get_agent_run_result(*, run_id: str, current_uid: str, db: AsyncSession) -> dict:
    """Tải kết quả cuối cùng của một run (trạng thái/output/Langfuse trace/lỗi), dùng chung cho chat/eval/cron."""
    run = await AgentRunRepository(db).get_run_for_user(run_id, str(current_uid))
    if not run:
        return {
            "status": "failed",
            "agent_run_id": run_id,
            "output": "",
            "error": {"type": "run_not_found", "message": "Lượt chạy không tồn tại"},
        }

    messages: list[Message] = []
    if run.conversation_id:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == run.conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        messages = list(result.scalars().unique().all())

    output_message = _select_output_message(messages, output_message_id=run.output_message_id)
    output_metadata = (
        output_message.extra_metadata if output_message and isinstance(output_message.extra_metadata, dict) else {}
    )

    payload: dict[str, Any] = {
        "status": run.status,
        "output": output_message.content if output_message else "",
        "agent_slug": run.agent_slug,
        "thread_id": run.conversation_thread_id,
        "conversation_id": run.conversation_id,
        "agent_run_id": run.id,
        "request_id": run.request_id,
        "final_message_id": output_message.id if output_message else None,
        "langfuse_trace_id": output_metadata.get("langfuse_trace_id"),
    }
    if run.error_type or run.error_message:
        payload["error"] = {"type": run.error_type, "message": run.error_message}
    return payload


async def load_agent_run_result(*, run_id: str, current_uid: str) -> dict:
    """Mở phiên độc lập để đọc kết quả run, dùng khi phiên request hiện tại không còn khả dụng (kết thúc stream, gọi nền v.v.)."""
    async with pg_manager.get_async_session_context() as db:
        return await get_agent_run_result(run_id=run_id, current_uid=current_uid, db=db)


async def await_agent_run_result(*, run_id: str, current_uid: str) -> dict:
    """Chặn đợi đến khi run kết thúc và trả về kết quả cuối cùng, dùng cho cron và các lời gọi in-process.

    Tái sử dụng luồng sự kiện hữu hạn ``stream_agent_run_events``: nó tự nhiên kết thúc khi run kết thúc hoặc hết thời gian,
    nên đọc hết là đợi xong, không cần polling thêm. Giới hạn chờ kế thừa từ ``SSE_MAX_CONNECTION_MINUTES`` bên trong luồng.
    Nếu sau khi chờ xong run vẫn chưa ở trạng thái cuối, nêm ``AgentRunWaitTimeout`` để caller không xử lý trạng thái non-terminal như kết quả cuối.
    """
    async for _ in stream_agent_run_events(run_id=run_id, after_seq="0-0", current_uid=current_uid, verbose=False):
        pass
    result = await load_agent_run_result(run_id=run_id, current_uid=current_uid)
    if str(result.get("status") or "") not in TERMINAL_RUN_STATUSES:
        raise AgentRunWaitTimeout(result)
    return result


async def request_cancel_agent_run(
    *,
    run_id: str,
    current_uid: str,
    db: AsyncSession,
    cascade_children: bool = False,
):
    """Yêu cầu hủy một run, có thể đồng thời phát tín hiệu hủy đến các run con còn hoạt động."""
    repo = AgentRunRepository(db)
    run = await repo.get_run_for_user(run_id, str(current_uid))
    if not run:
        raise HTTPException(status_code=404, detail="Lượt chạy không tồn tại")

    # Khóa ghi FOR UPDATE phải tuần tự trên cùng phiên; các tín hiệu hủy không phụ thuộc nhau, phát đồng thời.
    cancelled_ids = []
    if cascade_children:
        child_runs = await repo.list_active_child_runs_for_user(run_id, str(current_uid))
        for child_run in child_runs:
            await repo.request_cancel(child_run.id)
            cancelled_ids.append(child_run.id)

    run = await repo.request_cancel(run_id)
    cancelled_ids.append(run_id)
    await db.commit()
    await asyncio.gather(*(publish_cancel_signal(cid) for cid in cancelled_ids))
    return run


async def cancel_agent_run_view(*, run_id: str, current_uid: str, db: AsyncSession) -> dict:
    """HTTP entry point hủy run: mặc định cascade hủy các run con còn hoạt động khi hủy cha."""
    run = await request_cancel_agent_run(run_id=run_id, current_uid=current_uid, db=db, cascade_children=True)
    return {"run": run.to_dict() if run else None}


async def stream_agent_run_events(
    *,
    run_id: str,
    after_seq: str,
    current_uid: str,
    verbose: bool = True,
) -> AsyncIterator[str]:
    """Phát luồng sự kiện run theo định dạng SSE; bổ sung sự kiện kết thúc dựa theo DB khi thiếu sự kiện terminal."""
    started_at = utc_now_naive()
    last_heartbeat_ts = started_at

    last_seq = normalize_after_seq(after_seq)

    try:
        while True:
            try:
                async with pg_manager.get_async_session_context() as db:
                    repo = AgentRunRepository(db)
                    run = await repo.get_run_for_user(run_id, str(current_uid))
                    if not run:
                        yield _format_sse({"run_id": run_id, "message": "Lượt chạy không tồn tại"}, event="error")
                        return
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Run SSE DB error for run {run_id}: {e}")
                yield _format_sse(
                    {
                        "run_id": run_id,
                        "message": "Dòng sự kiện chạy tạm thời không khả dụng, vui lòng kết nối lại",
                        "reason": "db_error",
                    },
                    event="error",
                )
                return

            try:
                events = await list_run_stream_events(run_id, after_seq=last_seq, limit=200)
            except Exception as e:
                logger.warning(f"Run SSE redis error for run {run_id}: {e}")
                yield _format_sse(
                    {
                        "run_id": run_id,
                        "message": "Luồng sự kiện run tạm thời không khả dụng, vui lòng kết nối lại",
                        "reason": "redis_error",
                    },
                    event="error",
                )
                return

            emitted_terminal = False
            for event in events:
                seq = str(event.get("seq") or "0-0")
                last_seq = seq
                event_type = event.get("event_type") or "message"
                envelope = event.get("payload") or {}
                if not verbose and isinstance(envelope, dict):
                    envelope = _compact_run_event_envelope(envelope)
                    if envelope is None:
                        continue
                yield _format_sse(envelope, event=event_type, event_id=seq)
                if event_type == "end":
                    emitted_terminal = True

            if emitted_terminal:
                return

            if run.status in TERMINAL_RUN_STATUSES and not events:
                terminal_seq = last_seq
                if terminal_seq in {"", "0-0"}:
                    terminal_seq = await get_last_run_stream_seq(run_id)
                if terminal_seq in {"", "0-0"}:
                    terminal_seq = None
                terminal_envelope = build_run_event_envelope(
                    run_id=run_id,
                    thread_id=run.conversation_thread_id,
                    event_type="end",
                    payload={"status": run.status, "request_id": run.request_id},
                    created_at=utc_now_naive().isoformat(),
                )
                if not verbose:
                    terminal_envelope = _compact_run_event_envelope(terminal_envelope)
                yield _format_sse(
                    terminal_envelope,
                    event="end",
                    event_id=terminal_seq,
                )
                return

            now = utc_now_naive()
            elapsed_seconds = (now - started_at).total_seconds()
            heartbeat_elapsed = (now - last_heartbeat_ts).total_seconds()
            if heartbeat_elapsed >= SSE_HEARTBEAT_SECONDS:
                yield _format_heartbeat()
                last_heartbeat_ts = now

            if elapsed_seconds >= SSE_MAX_CONNECTION_MINUTES * 60:
                return

            await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        return


async def get_active_run_by_thread(*, thread_id: str, current_uid: str, db: AsyncSession) -> dict:
    """Lấy run gần nhất mà frontend vẫn cần quan tâm trong thread hiện tại."""
    from yuxi.storage.postgres.models_business import AgentRun

    # Các run trong thread là tuần tự; run gần nhất đại diện cho trạng thái hiện tại của thread.
    # Run bị ngắt (interrupted) đã được trả lời sẽ bị resume run mới hơn thay thế, do đó sẽ không bị trả về như pending interrupt nữa.
    result = await db.execute(
        select(AgentRun)
        .where(
            AgentRun.conversation_thread_id == thread_id,
            AgentRun.uid == str(current_uid),
            AgentRun.run_type.in_(["chat", "resume"]),
        )
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run and run.status in ("pending", "running", "cancel_requested", "interrupted"):
        return {"run": run.to_dict()}
    return {"run": None}
