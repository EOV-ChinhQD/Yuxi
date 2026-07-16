"""Subagent run orchestration service.

This module owns parent/child agent-thread relationships. It decides whether a
task starts a new child thread or continues an existing one, records the
``SubagentThread`` relation and builds the subagent-only runtime payload.

It deliberately delegates durable run mechanics to ``agent_run_service``:
request id idempotency, active-run conflict checks, input message persistence,
AgentRun row creation and queue enqueueing all stay in the shared AgentRun
lifecycle boundary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import yuxi.services.agent_run_service as agent_run_service
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.repositories.agent_run_repository import AgentRunRepository
from yuxi.repositories.conversation_repository import ConversationRepository
from yuxi.repositories.subagent_thread_repository import SubagentThreadRepository
from yuxi.services.input_message_service import AgentRunInputMessage
from yuxi.storage.postgres.models_business import Agent, AgentRun, SubagentThread
from yuxi.utils.datetime_utils import utc_isoformat
from yuxi.utils.hash_utils import hash_id, subagent_child_thread_id


@dataclass(frozen=True)
class SubagentStartResult:
    run: AgentRun
    created: bool
    continuing: bool
    relation: SubagentThread


@dataclass(frozen=True)
class SubagentRunBusy(Exception):
    thread_id: str
    active_run_id: str | None
    active_run_status: str | None
    message: str | None

    def to_payload(self) -> dict:
        return {
            "status": "busy",
            "thread_id": self.thread_id,
            "active_run_id": self.active_run_id,
            "active_run_status": self.active_run_status,
            "message": self.message,
        }


def subagent_run_urls(run_id: str) -> dict[str, str]:
    """Tạo URL luồng sự kiện và kết quả tra cứu của sub-agent run."""
    return {
        "events_url": f"/api/agent/runs/{run_id}/events",
        "result_url": f"/api/agent/runs/{run_id}/result",
    }


def serialize_subagent_run_state(run: AgentRun) -> dict:
    """Serialize tóm tắt sub-agent run dùng cho trạng thái của agent cha.

    Mô tả nhiệm vụ không lưu dư thừa ở đây: nguồn duy nhất là tham số của lời gọi `task` trong hội thoại cha;
    frontend panel sẽ điền theo tool_call_id khi hiển thị.
    """
    payload = run.input_payload
    if not isinstance(payload, dict):
        raise ValueError("subagent run thiếu input_payload")
    runtime = payload.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("subagent run thiếu runtime")
    tool_call_id = str(runtime.get("tool_call_id") or "").strip()
    if not tool_call_id:
        raise ValueError("subagent run thiếu tool_call_id")

    state = {
        "id": tool_call_id,
        "run_id": run.id,
        "subagent_slug": run.agent_slug,
        "subagent_name": runtime.get("subagent_name"),
        "child_thread_id": run.conversation_thread_id,
        "status": run.status,
        "created_at": utc_isoformat(run.created_at) if run.created_at else None,
        "completed_at": utc_isoformat(run.finished_at) if run.finished_at else None,
        "error": run.error_message,
        **subagent_run_urls(run.id),
    }
    return {key: value for key, value in state.items() if value is not None}


class SubagentRunService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.run_repo = AgentRunRepository(db)
        self.conv_repo = ConversationRepository(db)
        self.thread_repo = SubagentThreadRepository(db)

    async def start(
        self,
        *,
        uid: str,
        created_by_run_id: str,
        agent_item: Agent,
        input_message: AgentRunInputMessage,
        tool_call_id: str,
        requested_thread_id: str | None = None,
        file_thread_id: str | None = None,
        model_spec: str | None = None,
    ) -> SubagentStartResult:
        """Khởi động hoặc tiếp tục một sub-agent run nền, và đưa vào hàng đợi worker khi tạo mới."""

        creator_run = await self.run_repo.get_run_for_user(created_by_run_id, uid)
        if not creator_run:
            raise ValueError("Run cha không tồn tại")
        if getattr(creator_run, "run_type", None) == "subagent":
            raise ValueError("Sub-agent không thể tạo sub-agent")

        child_thread_id = str(requested_thread_id or "").strip()
        continuing = bool(child_thread_id)  # True = tiếp tục thread sub-agent hiện có, False = tạo thread mới
        if not child_thread_id:
            child_thread_id = subagent_child_thread_id(
                creator_run.conversation_thread_id,
                agent_item.slug,
                tool_call_id,
            )

        # 1. Đảm bảo child thread có conversation tương ứng, tạo conversation subagent nếu cần
        # 2. Đảm bảo quan hệ thread cha-con tồn tại, tạo bản ghi SubagentThread nếu cần; relation là nguồn gốc thread của sub run nền
        relation = await self._ensure_thread_relation(
            child_thread_id=child_thread_id,
            uid=uid,
            agent_item=agent_item,
            creator_run=creator_run,
            continuing=continuing,
        )

        # Tạo bản ghi cơ sở dữ liệu
        request_id = hash_id("req:", f"{creator_run.id}:{child_thread_id}:{tool_call_id}")
        try:
            run, created = await self._create_run_record(
                input_message=input_message,
                request_id=request_id,
                current_uid=uid,
                model_spec=model_spec,
                creator_run=creator_run,
                relation=relation,
                tool_call_id=tool_call_id,
                file_thread_id=file_thread_id,
            )
        except HTTPException as exc:
            detail = exc.detail
            if exc.status_code == 409 and isinstance(detail, dict) and detail.get("code") == "run_busy":
                raise SubagentRunBusy(
                    thread_id=str(detail.get("thread_id") or child_thread_id),
                    active_run_id=detail.get("active_run_id"),
                    active_run_status=detail.get("active_run_status"),
                    message=detail.get("message"),
                ) from exc
            raise ValueError(detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)) from exc

        # Đưa vào hàng đợi worker sau khi tạo thành công; không lặp lại khi idempotency đã có run.
        if created:
            await self.db.commit()
            await agent_run_service.enqueue_agent_run(run.id)

        return SubagentStartResult(
            run=run,
            created=created,
            continuing=continuing,
            relation=relation,
        )

    async def get_run_for_creator(self, *, uid: str, created_by_run_id: str, run_id: str) -> AgentRun:
        """Lấy sub-agent run trong phạm vi run cha, tránh tool truy cập nhiệm vụ sub của hội thoại khác."""
        run = await self.run_repo.get_subagent_run_for_creator(
            uid=uid,
            created_by_run_id=created_by_run_id,
            run_id=run_id,
        )
        if not run:
            raise ValueError("Sub-agent run không tồn tại hoặc không thuộc run cha hiện tại")
        return run

    async def _create_run_record(
        self,
        *,
        input_message: AgentRunInputMessage,
        request_id: str,
        current_uid: str,
        model_spec: str | None,
        creator_run: AgentRun,
        relation: SubagentThread,
        tool_call_id: str,
        file_thread_id: str | None,
    ) -> tuple[Any, bool]:
        """Tạo sub-agent run nền và lưu tin nhắn đầu vào đã chuẩn hóa làm input của run."""
        if not input_message.content:
            raise HTTPException(status_code=422, detail="input_message không được để trống")

        scope = await agent_run_service.prepare_agent_run_creation_scope(
            agent_slug=relation.subagent_slug,
            conversation_thread_id=relation.child_thread_id,
            request_id=request_id,
            current_uid=current_uid,
            db=self.db,
            run_type="subagent",
            agent_kind="subagent",
            created_by_run_id=creator_run.id,
            subagent_thread_relation_id=relation.id,
        )
        if relation.child_conversation_id != scope.conversation.id:
            raise HTTPException(status_code=409, detail="subagent thread relation không khớp với lượt chạy này")
        if scope.existing_run:
            return scope.existing_run, False

        if creator_run.conversation_id != relation.parent_conversation_id:
            raise HTTPException(status_code=409, detail="subagent thread relation không khớp với lượt chạy này")

        resolved_model_spec = agent_run_service.resolve_agent_run_model_spec(
            model_spec,
            scope.agent_item,
            scope.agent_backend,
        )
        runtime_payload = {
            "tool_call_id": tool_call_id,
            "subagent_name": scope.agent_item.name,
            "parent_thread_id": creator_run.conversation_thread_id,
            "file_thread_id": file_thread_id or creator_run.conversation_thread_id,
            "skills_thread_id": relation.child_thread_id,
        }
        input_payload = {
            "model_spec": resolved_model_spec,
            "runtime": {key: value for key, value in runtime_payload.items() if value is not None},
        }
        subagent_input_message = input_message.with_metadata(
            {
                "request_id": request_id,
                "source": "subagent",
                "raw_message": input_message.raw_message(),
            }
        )
        persisted_input_message = await agent_run_service.create_agent_run_input_message(
            db=self.db,
            conversation_id=scope.conversation.id,
            request_id=request_id,
            input_message=subagent_input_message,
        )
        return await agent_run_service.persist_agent_run_record(
            agent_slug=relation.subagent_slug,
            conversation_thread_id=relation.child_thread_id,
            current_uid=current_uid,
            db=self.db,
            request_id=request_id,
            conversation_id=scope.conversation.id,
            run_type="subagent",
            input_payload=input_payload,
            persisted_input_message=persisted_input_message,
            created_by_run_id=creator_run.id,
            subagent_thread_relation_id=relation.id,
        )

    async def _ensure_child_conversation(
        self,
        *,
        child_thread_id: str,
        uid: str,
        agent_item: Agent,
        creator_run: AgentRun,
    ):
        """Đảm bảo child thread có conversation tương ứng; thread mới sẽ tạo hội thoại được đánh dấu là subagent."""
        conversation = await self.conv_repo.get_conversation_by_thread_id(child_thread_id)
        if conversation:
            if conversation.uid != str(uid) or conversation.status == "deleted":
                raise ValueError("Thread sub-agent không tồn tại")
            if conversation.status != "subagent":
                raise ValueError(f"Thread sub-agent {child_thread_id} đã bị hội thoại thường chiếm dụng")
            if conversation.agent_id != agent_item.slug:
                raise ValueError(f"Thread sub-agent {child_thread_id} thuộc agent {conversation.agent_id}")
            return conversation

        conversation = await self.conv_repo.add_conversation(
            uid=uid,
            agent_id=agent_item.slug,
            title=f"SubAgent: {agent_item.name}",
            thread_id=child_thread_id,
            metadata={
                "source": "subagent",
                "parent_thread_id": creator_run.conversation_thread_id,
                "created_by_run_id": creator_run.id,
                "parent_conversation_id": creator_run.conversation_id,
                "subagent_slug": agent_item.slug,
            },
        )
        conversation.status = "subagent"
        await self.db.flush()
        return conversation

    def _validate_thread_relation(
        self,
        relation: SubagentThread,
        *,
        child_thread_id: str,
        agent_item: Agent,
        creator_run: AgentRun,
    ) -> None:
        """Kiểm tra quan hệ thread con hiện có vẫn thuộc hội thoại cha và sub-agent hiện tại."""
        if relation.parent_conversation_id != creator_run.conversation_id:
            raise ValueError(f"Thread sub-agent {child_thread_id}: thread không thuộc hội thoại hiện tại")
        if relation.subagent_slug != agent_item.slug:
            raise ValueError(
                f"Thread sub-agent {child_thread_id} thuộc sub-agent {relation.subagent_slug or 'không xác định'}"
            )

    async def _ensure_thread_relation(
        self,
        *,
        child_thread_id: str,
        uid: str,
        agent_item: Agent,
        creator_run: AgentRun,
        continuing: bool,
    ) -> SubagentThread:
        """Lấy hoặc tạo quan hệ thread cha-con; relation là nguồn gốc thread của sub run nền."""
        existing = await self.thread_repo.get_by_child_thread_for_user(child_thread_id, uid)
        if existing:
            self._validate_thread_relation(
                existing,
                child_thread_id=child_thread_id,
                agent_item=agent_item,
                creator_run=creator_run,
            )
            return existing
        if continuing:
            raise ValueError(
                f"Không thể tiếp tục thread sub-agent {child_thread_id}: không tìm thấy bản ghi run tương ứng trong hội thoại hiện tại"
            )
        if creator_run.conversation_id is None:
            raise ValueError("Run cha thiếu conversation_id, không thể tạo quan hệ thread sub-agent")

        child_conversation = await self._ensure_child_conversation(
            child_thread_id=child_thread_id,
            uid=uid,
            agent_item=agent_item,
            creator_run=creator_run,
        )
        return await self.thread_repo.create(
            uid=uid,
            parent_conversation_id=creator_run.conversation_id,
            child_conversation_id=child_conversation.id,
            child_thread_id=child_thread_id,
            subagent_slug=agent_item.slug,
            created_by_run_id=creator_run.id,
        )
