"""Agent Call HTTP protocol adapter.

This module handles request/response format, synchronous waiting, and OpenAI-compatible
response assembly for Agent Calls; Conversation, Request, and Run creation are handled by ``submit_run_command``.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.services.agent_run_service import (
    AgentRunWaitTimeout,
    await_agent_run_result,
    get_agent_run_result,
    get_agent_run_view,
)
from yuxi.services.input_message_service import (
    AgentRunInputMessage,
    build_chat_input_message_from_openai_content,
)
from yuxi.services.run_submission_service import RunOrigin, RunSubmissionCommand, submit_run_command
from yuxi.storage.postgres.models_business import User
from yuxi.utils.hash_utils import hash_id

from server.utils.auth_middleware import get_db, get_required_user

agent_invocation_call_router = APIRouter(prefix="/agent-invocation/agent-call", tags=["agent-invocation"])

MAX_REQUEST_ID_LENGTH = 64


class AgentCallRunCreate(BaseModel):
    """Agent Call creation request, compatible with OpenAI-style message input."""

    agent_slug: str = Field(..., description="Agent slug to invoke")
    messages: list[dict[str, Any]] = Field(..., description="List of messages, last user message used as input")
    stream: bool = Field(False, description="Streaming not yet supported, passing true returns 422")
    agent_call_meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Agent Call metadata; cannot override Agent runtime context via context",
    )
    thread_id: str | None = Field(None, description="Optional conversation thread ID; auto-generated if omitted")
    request_id: str | None = Field(None, description="Optional request idempotency ID; auto-generated if omitted")
    model_spec: str | None = Field(None, description="Optional model spec override")
    tool_approval_mode: str | None = Field(None, description="Optional tool approval mode override")
    async_mode: bool = Field(False, description="Whether to create run and immediately return run_id")
    queue_policy: str | None = Field(None, description="Queue policy; defaults to enqueue for async, reject for sync")


class AgentCallRunResultRequest(BaseModel):
    """Agent Call result query request."""

    run_id: str = Field(..., description="AgentRun ID")
    agent_slug: str | None = Field(None, description="Optional agent slug to verify run ownership")


@agent_invocation_call_router.post("/runs")
async def create_agent_call_run(
    payload: AgentCallRunCreate,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """Create Agent Call, optionally waiting for final result based on async_mode."""
    agent_slug = _normalize_required_text(payload.agent_slug, field_name="agent_slug")
    if payload.stream:
        raise HTTPException(status_code=422, detail="agent-call does not support stream=true yet")

    input_message = _extract_input_message(payload.messages)
    request_id = _normalize_request_id(payload.request_id)
    _validate_agent_call_meta(payload.agent_call_meta)
    queue_policy = str(payload.queue_policy or ("enqueue" if payload.async_mode else "reject")).strip()
    if not payload.async_mode and queue_policy != "reject":
        raise HTTPException(status_code=422, detail="Synchronous agent-call only supports queue_policy=reject")

    run_response = await submit_run_command(
        command=RunSubmissionCommand(
            agent_slug=agent_slug,
            thread_id=str(payload.thread_id or "").strip()
            or _invocation_thread_id(current_user.uid, agent_slug, request_id),
            request_id=request_id,
            input_message=input_message,
            origin=RunOrigin(
                source="agent_call",
                channel="api",
                external_id=request_id,
                metadata={"agent_invocation_meta": dict(payload.agent_call_meta or {})}
                if payload.agent_call_meta
                else {},
            ),
            request_metadata={"request_id": request_id},
            model_spec=payload.model_spec,
            tool_approval_mode=payload.tool_approval_mode,
            queue_policy=queue_policy,
            create_conversation=True,
            conversation_title="Agent Call Run",
        ),
        current_user=current_user,
        db=db,
    )

    if payload.async_mode:
        if not run_response.get("run_id"):
            return run_response
        return _build_agent_call_response(
            {
                "run_id": run_response["run_id"],
                "agent_slug": agent_slug,
                "thread_id": run_response["thread_id"],
                "status": run_response["status"],
                "request_id": run_response["request_id"],
                "output": "",
            }
        )

    if run_response["status"] == "rejected":
        return run_response
    try:
        result = await await_agent_run_result(run_id=run_response["run_id"], current_uid=str(current_user.uid))
    except AgentRunWaitTimeout as exc:
        raise HTTPException(
            status_code=504,
            detail={"message": "Run is still in progress, waiting for final result timed out", "run": exc.result},
        ) from exc
    return _build_agent_call_response(result)


@agent_invocation_call_router.post("/runs/result")
async def get_agent_call_run_result(
    payload: AgentCallRunResultRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve OpenAI-compatible result of an Agent Call Run."""
    run_id = str(payload.run_id or "").strip()
    if not run_id:
        raise HTTPException(status_code=422, detail="run_id cannot be empty")
    run_view = await get_agent_run_view(run_id=run_id, current_uid=str(current_user.uid), db=db)
    run = run_view["run"]
    expected_agent_slug = str(payload.agent_slug or "").strip()
    if expected_agent_slug and run.get("agent_slug") != expected_agent_slug:
        raise HTTPException(status_code=409, detail="run_id does not match agent_slug")
    result = await get_agent_run_result(run_id=run_id, current_uid=str(current_user.uid), db=db)
    return _build_agent_call_response(result)


def _invocation_thread_id(uid: object, agent_slug: str, request_id: str) -> str:
    """Generate deterministic thread ID for Agent Calls without explicit thread."""
    return hash_id("invocation_", f"{uid}:{agent_slug}:{request_id}", length=64)


def _normalize_required_text(value: str | None, *, field_name: str) -> str:
    """Validate required text field, returning 422 if empty."""
    normalized = str(value or "").strip()
    if not normalized:
        raise HTTPException(status_code=422, detail=f"{field_name} cannot be empty")
    return normalized


def _normalize_request_id(value: str | None) -> str:
    """Generate or validate request idempotency ID."""
    if value is None or not str(value).strip():
        return str(uuid.uuid4())
    normalized = str(value).strip()
    if len(normalized) > MAX_REQUEST_ID_LENGTH:
        raise HTTPException(status_code=422, detail=f"request_id cannot exceed {MAX_REQUEST_ID_LENGTH} characters")
    return normalized


def _validate_agent_call_meta(meta: dict[str, Any]) -> None:
    """Reject metadata attempts to override explicit runtime context fields."""
    if isinstance(meta, dict) and "context" in meta:
        raise HTTPException(
            status_code=422,
            detail="agent_call_meta.context is not allowed to override Agent context; use model_spec to override model",
        )


def _extract_input_message(messages: list[dict[str, Any]]) -> AgentRunInputMessage:
    """Extract last user message from message list as run input."""
    if not messages:
        raise HTTPException(status_code=422, detail="messages cannot be empty")
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        try:
            return build_chat_input_message_from_openai_content(message.get("content"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise HTTPException(status_code=422, detail="messages must contain at least one user message")


def _normalize_usage(usage: object) -> dict[str, int] | None:
    """Normalize usage fields from various sources to OpenAI-compatible counts."""
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
    completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
    total = usage.get("total_tokens")
    prompt = prompt if isinstance(prompt, int) else 0
    completion = completion if isinstance(completion, int) else 0
    total = total if isinstance(total, int) else prompt + completion
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}


def _build_agent_call_response(result: dict[str, Any]) -> dict[str, Any]:
    """Assemble AgentRun result into Agent Call response format."""
    raw_status = str(result.get("status") or "unknown")
    status = "pending" if raw_status == "dispatched" else raw_status
    output = result.get("output") if isinstance(result.get("output"), str) else ""
    token_usage = result.get("token_usage")
    token_total = (
        token_usage.get("total") if isinstance(token_usage, dict) and token_usage.get("complete") is True else None
    )
    payload: dict[str, Any] = {
        "run_id": result.get("agent_run_id") or result.get("run_id"),
        "agent_slug": result.get("agent_slug"),
        "thread_id": result.get("thread_id"),
        "status": status,
        "request_id": result.get("request_id"),
        "output": output,
        "choices": [
            {
                "index": 0,
                "messages": [{"role": "assistant", "content": output}],
                "finish_reason": _finish_reason(status),
            }
        ],
        "usage": _normalize_usage(token_total),
    }
    if result.get("error"):
        payload["error"] = result["error"]
    return payload


def _finish_reason(status: str) -> str | None:
    """Determine OpenAI choices.finish_reason from run termination status."""
    if status == "completed":
        return "stop"
    if status in {"failed", "cancelled", "interrupted"}:
        return status
    return None
