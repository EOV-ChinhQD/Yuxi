"""Plain-text Channel message entrypoint.

Channel is responsible only for transforming message envelopes into unified Run submission commands;
a few control commands are processed before standard message submission to prevent status queries
or approval decisions from being incorrectly queued into the Agent Request queue.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.repositories.agent_run_repository import AgentRunRepository
from yuxi.services.agent_run_service import create_agent_run_view
from yuxi.services.channel_command_service import parse_slash_command
from yuxi.services.chat_service import get_agent_state_view
from yuxi.services.input_message_service import build_chat_input_message
from yuxi.services.run_submission_service import RunOrigin, RunSubmissionCommand, submit_run_command
from yuxi.storage.postgres.models_business import User
from yuxi.utils.hash_utils import hash_id

from server.utils.auth_middleware import get_db, get_required_user

agent_invocation_channel_router = APIRouter(prefix="/agent-invocation/channel", tags=["agent-invocation"])


class ChannelTextMessage(BaseModel):
    """Channel plain-text message body."""

    type: Literal["text"] = "text"
    text: str = Field(..., min_length=1, description="Plain text message")


class ChannelMessageRequest(BaseModel):
    """Channel message envelope carrying source account, thread, and idempotency identifiers."""

    channel: str = Field("cli", max_length=32, description="Channel name")
    account_id: str = Field("default", description="Channel account identifier")
    chat_id: str | None = Field(None, description="Channel-side chat identifier")
    thread_id: str | None = Field(None, description="Optional Yuxi Thread ID")
    sender_id: str | None = Field(None, description="Channel-side sender identifier")
    message_id: str | None = Field(None, max_length=128, description="Channel-side message ID")
    request_id: str | None = Field(None, description="Request idempotency ID")
    agent_slug: str = Field(..., description="Target agent slug")
    message: ChannelTextMessage
    queue_policy: Literal["enqueue", "reject", "steer"] = "steer"


@agent_invocation_channel_router.post("/messages")
async def receive_channel_message(
    payload: ChannelMessageRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """Handle plain-text Channel message or minimal slash command."""
    channel = _normalize_required(payload.channel, "channel")
    account_id = _normalize_required(payload.account_id, "account_id")
    agent_slug = _normalize_required(payload.agent_slug, "agent_slug")
    thread_id = _resolve_thread_id(
        uid=str(current_user.uid),
        channel=channel,
        account_id=account_id,
        chat_id=payload.chat_id,
        requested_thread_id=payload.thread_id,
    )
    message_text = payload.message.text.strip()
    if not message_text:
        raise HTTPException(status_code=422, detail="text cannot be empty")
    raw_request_id = str(payload.request_id or "").strip()
    external_id = str(payload.message_id or "").strip() or raw_request_id or str(uuid.uuid4())
    request_id = raw_request_id or hash_id(
        "channel_request_",
        f"{current_user.uid}:{channel}:{account_id}:{payload.chat_id or thread_id}:{external_id}",
        length=64,
    )
    if len(request_id) > 64:
        raise HTTPException(status_code=422, detail="request_id cannot exceed 64 characters")
    origin_metadata = {
        key: value
        for key, value in {
            "account_id": account_id,
            "chat_id": payload.chat_id,
            "sender_id": payload.sender_id,
        }.items()
        if value
    }

    try:
        command = parse_slash_command(message_text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if command is not None:
        if command.name == "state":
            _require_no_args(command.name, command.args)
            state = await get_agent_state_view(
                thread_id=thread_id,
                current_user=current_user,
                db=db,
                include_messages=False,
            )
            return {"kind": "command", "command": "state", "thread_id": thread_id, "state": state}
        if command.name == "approve":
            _require_no_args(command.name, command.args)
            return await _approve_latest_run(
                agent_slug=agent_slug,
                thread_id=thread_id,
                request_id=request_id,
                external_id=external_id,
                channel=channel,
                origin_metadata=origin_metadata,
                current_user=current_user,
                db=db,
            )
        raise HTTPException(status_code=422, detail=f"Unsupported slash command: /{command.name}")

    latest_run = await AgentRunRepository(db).get_latest_chat_or_resume_run(
        uid=str(current_user.uid),
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
    )
    if latest_run and latest_run.status == "interrupted" and latest_run.error_type != "human_approval_required":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ask_user_question_unsupported",
                "message": "Current thread is waiting for user response; Channel does not currently support ask_user_question",
            },
        )

    result = await submit_run_command(
        command=RunSubmissionCommand(
            agent_slug=agent_slug,
            thread_id=thread_id,
            request_id=request_id,
            input_message=build_chat_input_message(message_text),
            origin=RunOrigin(
                source="channel",
                channel=channel,
                external_id=external_id,
                metadata=origin_metadata,
            ),
            request_metadata={"message_type": "text"},
            queue_policy=payload.queue_policy,
            create_conversation=True,
            conversation_title=f"{channel} Channel Run",
        ),
        current_user=current_user,
        db=db,
    )
    result["kind"] = "run"
    result["channel"] = channel
    return result


async def _approve_latest_run(
    *,
    agent_slug: str,
    thread_id: str,
    request_id: str,
    external_id: str,
    channel: str,
    origin_metadata: dict[str, str],
    current_user: User,
    db: AsyncSession,
) -> dict:
    """Approve currently pending tool calls, reusing resume run with same request_id if available."""
    run_repo = AgentRunRepository(db)
    existing_run = await run_repo.get_run_by_request_id(request_id)
    latest_run = await run_repo.get_latest_chat_or_resume_run(
        uid=str(current_user.uid),
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
    )
    if existing_run:
        if (
            existing_run.uid != str(current_user.uid)
            or existing_run.agent_slug != agent_slug
            or existing_run.conversation_thread_id != thread_id
            or existing_run.run_type != "resume"
            or not existing_run.created_by_run_id
            or latest_run is None
            or latest_run.id != existing_run.id
        ):
            raise HTTPException(status_code=409, detail="request_id conflict")
        parent_run_id = existing_run.created_by_run_id
    else:
        if not latest_run or latest_run.status != "interrupted":
            raise HTTPException(
                status_code=409,
                detail={"code": "no_pending_approval", "message": "No runs pending approval"},
            )
        if latest_run.error_type != "human_approval_required":
            raise HTTPException(
                status_code=409,
                detail={"code": "ask_user_question_unsupported", "message": "Current interrupt is not a tool approval and is not supported"},
            )
        parent_run_id = latest_run.id

    result = await create_agent_run_view(
        input_message=None,
        agent_slug=agent_slug,
        thread_id=thread_id,
        meta={"request_id": request_id, "source": "channel", "channel": channel},
        current_uid=str(current_user.uid),
        db=db,
        resume={"decisions": [{"type": "approve"}]},
        created_by_run_id=parent_run_id,
        source="channel",
        channel=channel,
        external_id=external_id,
        origin_metadata=origin_metadata,
    )
    return {"kind": "command", "command": "approve", "thread_id": thread_id, "run": result}


def _resolve_thread_id(
    *,
    uid: str,
    channel: str,
    account_id: str,
    chat_id: str | None,
    requested_thread_id: str | None,
) -> str:
    """Resolve stable Yuxi Thread ID from explicit thread or channel session information."""
    if requested_thread_id and requested_thread_id.strip():
        return requested_thread_id.strip()
    if not chat_id or not chat_id.strip():
        raise HTTPException(status_code=422, detail="At least one of thread_id or chat_id must be provided")
    return hash_id("channel_", f"{uid}:{channel}:{account_id}:{chat_id.strip()}", length=64)


def _normalize_required(value: str | None, field_name: str) -> str:
    """Validate and normalize required string field."""
    normalized = str(value or "").strip()
    if not normalized:
        raise HTTPException(status_code=422, detail=f"{field_name} cannot be empty")
    return normalized


def _require_no_args(name: str, args: tuple[str, ...]) -> None:
    """Reject slash commands with unexpected arguments."""
    if args:
        raise HTTPException(status_code=422, detail=f"/{name} does not accept arguments")
