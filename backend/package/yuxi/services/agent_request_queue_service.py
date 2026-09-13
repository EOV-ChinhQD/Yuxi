"""Agent request queue service.

Full transactional logic for request intake, FIFO dispatch, cancellation, and
recovery scans. Never calls agent_run_service private functions.
``recover_pending_dispatches`` manages its own sessions and only calls
``enqueue_agent_run`` after commit.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.repositories.agent_run_repository import AgentRunRepository
from yuxi.repositories.agent_run_request_repository import AgentRunRequestRepository
from yuxi.repositories.conversation_repository import ConversationRepository
from yuxi.services.agent_run_service import (
    create_agent_run_input_message,
    enqueue_agent_run,
    resolve_agent_run_config,
)
from yuxi.services.input_message_service import AgentRunInputMessage
from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import AgentRun, AgentRunRequest, Message
from yuxi.utils.datetime_utils import utc_now_naive
from yuxi.utils.logging_config import logger
from yuxi.utils.sse_utils import (
    SSE_HEARTBEAT_SECONDS,
    SSE_MAX_CONNECTION_MINUTES,
    SSE_POLL_INTERVAL_SECONDS,
    format_heartbeat,
    format_sse,
)

SUPPORTED_QUEUE_POLICIES = ("enqueue", "reject", "steer")
NOT_IMPLEMENTED_QUEUE_POLICIES = ("guided", "bridge")

# ponytail: Tool approval timeout (30 mins) to prevent thread queue deadlocks
TOOL_APPROVAL_TIMEOUT_SECONDS = 1800

# Request lifecycle states.
REQUEST_STATUS_QUEUED = "queued"
REQUEST_STATUS_DISPATCHED = "dispatched"
REQUEST_STATUS_CANCELLED = "cancelled"
REQUEST_STATUS_REJECTED = "rejected"
REQUEST_STATUS_FAILED = "failed"
REQUEST_TERMINAL_STATUSES = frozenset({REQUEST_STATUS_CANCELLED, REQUEST_STATUS_REJECTED, REQUEST_STATUS_FAILED})

# Message delivery states aligned with messages.delivery_status.
DELIVERY_STATUS_QUEUED = "queued"
DELIVERY_STATUS_DISPATCHED = "dispatched"
DELIVERY_STATUS_COMPLETE = "complete"
DELIVERY_STATUS_REJECTED = "rejected"
DELIVERY_STATUS_FAILED = "failed"
DELIVERY_STATUS_CANCELLED = "cancelled"

# AgentRun terminal status → Message.delivery_status. ``interrupted`` is excluded:
# interrupted requests never truly finish, so the original delivery_status is kept
# for the UI to distinguish completed vs interrupted.
RUN_STATUS_TO_DELIVERY_STATUS: dict[str, str] = {
    "completed": DELIVERY_STATUS_COMPLETE,
    "failed": DELIVERY_STATUS_FAILED,
    "cancelled": DELIVERY_STATUS_CANCELLED,
}


@dataclass(frozen=True)
class IntakeResult:
    """Intake decision result."""

    request_id: str
    status: str  # queued / dispatched / rejected
    queue_policy: str
    message_id: int | None
    thread_id: str
    run_id: str | None = None
    # FIFO queue position; None when not queued (dispatched/rejected/existing).
    queue_position: int | None = None


@dataclass(frozen=True)
class DispatchResult:
    """One pre-commit FIFO head-dispatch result."""

    request_id: str
    run_id: str


def validate_queue_policy(queue_policy: str) -> str:
    """Validate queue_policy, returning 422 for unimplemented policies."""
    if queue_policy in NOT_IMPLEMENTED_QUEUE_POLICIES:
        raise HTTPException(
            status_code=422,
            detail=f"queue_policy '{queue_policy}' not implemented yet",
        )
    if queue_policy not in SUPPORTED_QUEUE_POLICIES:
        raise HTTPException(status_code=422, detail=f"Unsupported queue_policy: {queue_policy}")
    return queue_policy


async def intake_request(
    *,
    db: AsyncSession,
    request_id: str,
    uid: str,
    agent_slug: str,
    thread_id: str,
    source: str = "chat",
    channel: str = "web",
    external_id: str | None = None,
    origin_metadata: dict | None = None,
    queue_policy: str = "enqueue",
    input_message: AgentRunInputMessage,
    agent_item: Any,
    agent_backend: Any,
    model_spec: str | None = None,
    tool_approval_mode: str | None = None,
    meta: dict | None = None,
) -> IntakeResult:
    """Create request + Message and attempt immediate dispatch.

    All flushes complete inside the caller transaction; no commit here.
    Returns IntakeResult: includes run_id when dispatched (caller must commit,
    then enqueue ARQ).
    """
    policy = validate_queue_policy(queue_policy)
    if policy == "steer" and source not in {"chat", "channel"}:
        raise HTTPException(status_code=422, detail="queue_policy 'steer' only supports main Chat/Channel sessions")
    meta = meta or {}
    uid_str = str(uid)
    repo = AgentRunRequestRepository(db)

    async def existing_intake_result() -> IntakeResult | None:
        """Idempotent: return the existing request/run view when request_id exists, else None."""
        existing = await repo.get_by_request_id(request_id)
        if not existing:
            return None
        return await _build_existing_intake_result(
            repo=repo,
            request=existing,
            uid=uid_str,
            agent_slug=agent_slug,
            thread_id=thread_id,
            source=source,
            channel=channel,
            external_id=external_id,
            queue_policy=policy,
        )

    if result := await existing_intake_result():
        return result

    conversation = await _get_thread_conversation(
        db=db,
        uid=uid_str,
        agent_slug=agent_slug,
        thread_id=thread_id,
        lock=True,
    )
    if result := await existing_intake_result():
        return result
    existing_requests = await repo.list_queued(
        uid=uid_str,
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
    )
    existing_head = existing_requests[0] if existing_requests else None
    active_run = await AgentRunRepository(db).get_active_run_by_thread_for_user(
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
        uid=uid_str,
    )
    latest_run = await AgentRunRepository(db).get_latest_chat_or_resume_run(
        uid=uid_str,
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
    )
    if latest_run is not None and latest_run.status == "interrupted":
        raise _queue_conflict("run_interrupted", "Thread is currently waiting for user response or approval")
    if policy == "steer" and active_run is not None and not await _is_steerable_message_run(db=db, run=active_run):
        raise _queue_conflict("run_not_steerable", "Current run does not support steering")
    if policy == "steer" and await repo.get_pending_steer(
        uid=uid_str,
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
    ):
        raise _queue_conflict("steer_already_pending", "Thread already has a pending steer request")

    # reject means "refuse unless the request immediately becomes and dispatches as FIFO head".
    reject_without_immediate_dispatch = policy == "reject" and (active_run is not None or existing_head is not None)
    if reject_without_immediate_dispatch:
        request_status = REQUEST_STATUS_REJECTED
        delivery_status = DELIVERY_STATUS_REJECTED
        input_payload = {}
    else:
        request_status = REQUEST_STATUS_QUEUED
        delivery_status = DELIVERY_STATUS_QUEUED
        resolved_model_spec, resolved_tool_approval_mode = resolve_agent_run_config(
            model_spec, tool_approval_mode, agent_item, agent_backend
        )
        input_payload = {
            "model_spec": resolved_model_spec,
            "tool_approval_mode": resolved_tool_approval_mode,
        }

    run_input_message = input_message.with_metadata(
        _build_message_metadata(request_id=request_id, source=source, input_message=input_message, meta=meta)
    )
    try:
        async with db.begin_nested():
            persisted_message = await create_agent_run_input_message(
                db=db,
                conversation_id=conversation.id,
                request_id=request_id,
                input_message=run_input_message,
                delivery_status=delivery_status,
            )
            persisted_request = await repo.create(
                request_id=request_id,
                uid=uid_str,
                agent_slug=agent_slug,
                conversation_thread_id=thread_id,
                source=source,
                channel=channel,
                external_id=external_id,
                origin_metadata=origin_metadata,
                queue_policy=policy,
                input_message_id=persisted_message.id,
                input_payload=input_payload,
                status=request_status,
            )
    except IntegrityError:
        if result := await existing_intake_result():
            return result
        raise

    if not reject_without_immediate_dispatch:
        dispatched = await _dispatch_ready_head(
            db=db,
            uid=uid_str,
            agent_slug=agent_slug,
            thread_id=thread_id,
            conversation_id=conversation.id,
            expected_request_id=request_id if policy == "reject" else None,
        )
        if dispatched and dispatched.request_id == request_id:
            return IntakeResult(
                request_id=request_id,
                status=REQUEST_STATUS_DISPATCHED,
                queue_policy=policy,
                message_id=persisted_message.id,
                thread_id=thread_id,
                run_id=dispatched.run_id,
            )

        if policy == "reject":
            persisted_request.status = REQUEST_STATUS_REJECTED
            persisted_request.input_payload = {}
            persisted_request.updated_at = utc_now_naive()
            persisted_message.delivery_status = DELIVERY_STATUS_REJECTED
            await db.flush()
            return IntakeResult(
                request_id=request_id,
                status=REQUEST_STATUS_REJECTED,
                queue_policy=policy,
                message_id=persisted_message.id,
                thread_id=thread_id,
            )

    if reject_without_immediate_dispatch:
        return IntakeResult(
            request_id=request_id,
            status=REQUEST_STATUS_REJECTED,
            queue_policy=policy,
            message_id=persisted_message.id,
            thread_id=thread_id,
        )

    return IntakeResult(
        request_id=request_id,
        status=REQUEST_STATUS_QUEUED,
        queue_policy=policy,
        message_id=persisted_message.id,
        thread_id=thread_id,
        queue_position=await repo.get_queue_position(request_id),
    )


async def steer_queued_request(
    *,
    request_id: str,
    current_uid: str,
    db: AsyncSession,
) -> IntakeResult:
    """Promote a regular queued Chat request to the next Steer to execute."""
    repo = AgentRunRequestRepository(db)
    existing = await repo.get_by_request_id(request_id)
    if existing is None or existing.uid != str(current_uid):
        raise HTTPException(status_code=404, detail={"code": "request_not_found", "message": "Request not found"})

    await _get_thread_conversation(
        db=db,
        uid=existing.uid,
        agent_slug=existing.agent_slug,
        thread_id=existing.conversation_thread_id,
        lock=True,
    )
    request = await repo.lock_by_request_id(request_id)
    if request is None or request.uid != str(current_uid):
        raise HTTPException(status_code=404, detail={"code": "request_not_found", "message": "Request not found"})
    if request.queue_policy == "steer" and request.status == REQUEST_STATUS_QUEUED:
        return await _build_existing_intake_result(
            repo=repo,
            request=request,
            uid=request.uid,
            agent_slug=request.agent_slug,
            thread_id=request.conversation_thread_id,
            source=request.source,
            channel=request.channel,
            external_id=request.external_id,
            queue_policy="steer",
        )
    if request.status != REQUEST_STATUS_QUEUED or request.queue_policy != "enqueue" or request.source != "chat":
        raise _queue_conflict("request_not_queued", "Only regular queued Chat requests can be promoted to steer")

    pending_steer = await repo.get_pending_steer(
        uid=request.uid,
        agent_slug=request.agent_slug,
        conversation_thread_id=request.conversation_thread_id,
    )
    if pending_steer and pending_steer.request_id != request_id:
        raise _queue_conflict("steer_already_pending", "Thread already has a pending steer request")

    active_run = await AgentRunRepository(db).get_active_run_by_thread_for_user(
        uid=request.uid,
        agent_slug=request.agent_slug,
        conversation_thread_id=request.conversation_thread_id,
    )
    if active_run is None or not await _is_steerable_message_run(db=db, run=active_run):
        raise _queue_conflict("run_not_steerable", "Current run does not support steering")

    request.queue_policy = "steer"
    request.updated_at = utc_now_naive()
    await db.flush()
    return IntakeResult(
        request_id=request.request_id,
        status=request.status,
        queue_policy=request.queue_policy,
        message_id=request.input_message_id,
        thread_id=request.conversation_thread_id,
        queue_position=1,
    )


async def should_end_run_for_steer(run_id: str) -> bool:
    """Decide whether the current Chat Run should yield to a Steer before model calls."""
    async with pg_manager.get_async_session_context() as db:
        run = await AgentRunRepository(db).get_run(run_id)
        if run is None or not await _is_steerable_message_run(db=db, run=run):
            return False
        request = await AgentRunRequestRepository(db).get_pending_steer(
            uid=run.uid,
            agent_slug=run.agent_slug,
            conversation_thread_id=run.conversation_thread_id,
        )
        return request is not None


async def finalize_intake(*, db: AsyncSession, intake: IntakeResult) -> None:
    """Caller commits after intake_request and conditionally enqueues the dispatched run into ARQ."""
    dispatch = (
        DispatchResult(request_id=intake.request_id, run_id=intake.run_id)
        if intake.status == REQUEST_STATUS_DISPATCHED and intake.run_id
        else None
    )
    await finalize_dispatch(db=db, dispatch=dispatch)


async def finalize_dispatch(*, db: AsyncSession, dispatch: DispatchResult | None) -> None:
    """Commit the current transaction; only deliver the created run to ARQ after commit."""
    await db.commit()
    if dispatch:
        await enqueue_agent_run(dispatch.run_id)


async def dispatch_next_request(
    *,
    uid: str,
    agent_slug: str,
    thread_id: str,
) -> str | None:
    """Dispatch the thread head request. Manages its own session, delivers to ARQ after commit.

    Called for next-request dispatch after run completion and by recovery scans.
    """
    run_id = None
    async with pg_manager.get_async_session_context() as db:
        conversation = await ConversationRepository(db).lock_conversation_by_thread_id(thread_id)
        if not _conversation_matches(conversation, uid=uid, agent_slug=agent_slug):
            return None
        active_run = await AgentRunRepository(db).get_active_run_by_thread_for_user(
            uid=str(uid),
            agent_slug=agent_slug,
            conversation_thread_id=thread_id,
        )
        if active_run:
            if active_run.status == "pending":
                run_id = active_run.id
        else:
            dispatch = await _dispatch_ready_head(
                db=db,
                uid=str(uid),
                agent_slug=agent_slug,
                thread_id=thread_id,
                conversation_id=conversation.id,
            )
            if dispatch:
                run_id = dispatch.run_id

    if run_id:
        await enqueue_agent_run(run_id)
        return run_id
    return None


async def recover_pending_dispatches() -> None:
    """Recover pending dispatches and auto-cancel interrupted runs past due (30 minutes)."""
    # Specialized optimization: use advisory lock to prevent duplicate dispatch on multi-worker deploys.
    async with pg_manager.get_async_session_context() as db:
        try:
            await db.execute(select(1).where(False))  # dummy to ensure session
            # Use pg_try_advisory_xact_lock to avoid blocking concurrent recoveries
            locked = await db.execute(
                __import__("sqlalchemy").text("SELECT pg_try_advisory_xact_lock(hashtextextended('queue-recover', 0))")
            )
            if not locked.scalar():
                logger.info("Queue recovery skipped: another worker holds advisory lock")
                return
        except Exception:
            pass

        # 1. Auto-expire interrupted runs older than TOOL_APPROVAL_TIMEOUT_SECONDS
        now = utc_now_naive()
        interrupted_result = await db.execute(select(AgentRun).where(AgentRun.status == "interrupted"))
        interrupted_runs = interrupted_result.scalars().all()
        for expired_run in interrupted_runs:
            run_time = expired_run.updated_at or expired_run.created_at
            if run_time and (now - run_time).total_seconds() >= TOOL_APPROVAL_TIMEOUT_SECONDS:
                logger.warning(
                    f"Auto-expiring interrupted run {expired_run.id} on thread {expired_run.conversation_thread_id} "
                    f"after {TOOL_APPROVAL_TIMEOUT_SECONDS}s timeout"
                )
                expired_run.status = "cancelled"
                expired_run.error_type = "approval_timeout"
                expired_run.error_message = "Tool approval timed out after 30 minutes"
                expired_run.finished_at = now
                db.add(expired_run)
        await db.commit()

        # 2. Collect scopes to dispatch
        pending_result = await db.execute(
            select(AgentRun.uid, AgentRun.agent_slug, AgentRun.conversation_thread_id).where(
                AgentRun.status == "pending"
            )
        )
        scopes_result = await db.execute(
            select(
                AgentRunRequest.uid,
                AgentRunRequest.agent_slug,
                AgentRunRequest.conversation_thread_id,
            )
            .where(AgentRunRequest.status == REQUEST_STATUS_QUEUED)
            .distinct()
        )
        scopes = {tuple(row) for row in pending_result.all()}
        scopes.update(tuple(row) for row in scopes_result.all())

    recovered = await asyncio.gather(
        *(
            dispatch_next_request(uid=uid, agent_slug=agent_slug, thread_id=thread_id)
            for uid, agent_slug, thread_id in scopes
        )
    )
    for run_id in recovered:
        if run_id:
            logger.info(f"Recovered pending run or queue: {run_id}")


async def cancel_queued_request(
    *,
    request_id: str,
    current_uid: str,
    db: AsyncSession,
) -> str:
    """Cancel a queued request; dispatched requests cannot be cancelled.

    Returns the final status string. Missing or foreign requests return 404.
    Lock the Conversation first, then decide the final request status after
    ``SELECT ... FOR UPDATE``; Steer refuses cancellation while a run is active
    to avoid racing Middleware safety points.
    """
    repo = AgentRunRequestRepository(db)
    existing = await repo.get_by_request_id(request_id)
    if existing is None or existing.uid != str(current_uid):
        raise HTTPException(status_code=404, detail="Request not found")

    await _get_thread_conversation(
        db=db,
        uid=existing.uid,
        agent_slug=existing.agent_slug,
        thread_id=existing.conversation_thread_id,
        lock=True,
    )

    request = await repo.lock_by_request_id(request_id)
    if request is None or request.uid != str(current_uid):
        raise HTTPException(status_code=404, detail="Request not found")
    if request.status == REQUEST_STATUS_DISPATCHED:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "request_already_dispatched",
                "message": "Request already dispatched; cancel the active run via the run cancellation endpoint",
                "run_id": request.dispatched_run_id,
            },
        )
    if request.status in REQUEST_TERMINAL_STATUSES:
        return request.status
    if request.queue_policy == "steer":
        active_run = await AgentRunRepository(db).get_active_run_by_thread_for_user(
            uid=request.uid,
            agent_slug=request.agent_slug,
            conversation_thread_id=request.conversation_thread_id,
        )
        if active_run is not None:
            raise _queue_conflict(
                "steer_in_progress", "Steer is waiting for the active run to finish and cannot be cancelled yet"
            )
    request.status = REQUEST_STATUS_CANCELLED
    request.updated_at = utc_now_naive()
    await db.flush()
    return REQUEST_STATUS_CANCELLED


async def get_request(*, db: AsyncSession, request_id: str, uid: str) -> dict | None:
    """Look up a request by request_id (with uid ownership check)."""
    repo = AgentRunRequestRepository(db)
    request = await repo.get_by_request_id(request_id)
    if not request or request.uid != str(uid):
        return None
    return request.to_dict()


async def get_thread_queue_snapshot(*, db: AsyncSession, uid: str, agent_slug: str, thread_id: str) -> dict:
    """Read queue requests with a minimal state projection."""
    await _get_thread_conversation(db=db, uid=uid, agent_slug=agent_slug, thread_id=thread_id)
    repo = AgentRunRequestRepository(db)
    items = await repo.list_queued(uid=str(uid), agent_slug=agent_slug, conversation_thread_id=thread_id)

    message_ids = [request.input_message_id for request in items if request.input_message_id is not None]
    contents: dict[int, str] = {}
    if message_ids:
        result = await db.execute(select(Message.id, Message.content).where(Message.id.in_(message_ids)))
        contents = {row[0]: row[1] for row in result.all()}

    requests = []
    for position, request in enumerate(items, start=1):
        data = request.to_dict()
        if request.input_message_id is not None:
            data["content"] = contents.get(request.input_message_id, "")
        data["queue_position"] = position
        requests.append(data)
    status, metadata = await _get_queue_state(
        db=db,
        uid=str(uid),
        agent_slug=agent_slug,
        thread_id=thread_id,
        head=items[0] if items else None,
    )
    return {"requests": requests, "queue": {"status": status, **metadata}}


async def continue_thread_queue(
    *,
    db: AsyncSession,
    uid: str,
    agent_slug: str,
    thread_id: str,
) -> DispatchResult:
    """Confirm paused state and dispatch the FIFO head within one transaction."""
    conversation = await _get_thread_conversation(
        db=db,
        uid=uid,
        agent_slug=agent_slug,
        thread_id=thread_id,
        lock=True,
    )
    repo = AgentRunRequestRepository(db)
    head = await repo.get_queue_head(
        uid=str(uid),
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
    )
    if not head:
        raise _queue_conflict("queue_empty", "Queue is empty")

    status, _ = await _get_queue_state(
        db=db,
        uid=str(uid),
        agent_slug=agent_slug,
        thread_id=thread_id,
        head=head,
    )
    if status == "running":
        raise _queue_conflict("run_active", "Thread already has an active run")
    if status == "interrupted":
        raise _queue_conflict("run_interrupted", "Thread is waiting for user response or approval")
    if status != "paused":
        raise _queue_conflict("queue_not_paused", "Queue does not need manual resume")

    dispatched = await _dispatch_locked_head(
        db=db,
        head=head,
        uid=str(uid),
        agent_slug=agent_slug,
        thread_id=thread_id,
        conversation_id=conversation.id,
    )
    if dispatched:
        return dispatched

    active_run = await AgentRunRepository(db).get_active_run_by_thread_for_user(
        uid=str(uid),
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
    )
    if active_run:
        raise _queue_conflict("run_active", "Thread already has an active run")
    raise _queue_conflict("queue_not_paused", "Queue state has changed")


async def stream_request_events(
    *,
    request_id: str,
    uid: str,
    db_session_factory,
) -> AsyncIterator[str]:
    """Request SSE: emit queued heartbeats and position changes; end with run_created on dispatch."""
    started_at = utc_now_naive()
    last_heartbeat_ts = started_at
    last_position = -1

    try:
        while True:
            async with db_session_factory() as db:
                repo = AgentRunRequestRepository(db)
                request = await repo.get_by_request_id(request_id)
                if not request or request.uid != str(uid):
                    yield format_sse({"request_id": request_id, "message": "Request not found"}, event="error")
                    return

                if request.status == REQUEST_STATUS_DISPATCHED:
                    yield format_sse(
                        {
                            "request_id": request_id,
                            "run_id": request.dispatched_run_id,
                            "stream_url": f"/api/agent/runs/{request.dispatched_run_id}/events",
                        },
                        event="run_created",
                    )
                    return

                if request.status in REQUEST_TERMINAL_STATUSES:
                    yield format_sse(
                        {"request_id": request_id, "status": request.status},
                        event=request.status,
                    )
                    return

                # queued: locate position with a COUNT query (O(1)), report only on change
                position = await repo.get_queue_position_for(request)
                if position != last_position:
                    last_position = position
                    yield format_sse(
                        {"request_id": request_id, "status": REQUEST_STATUS_QUEUED, "position": position},
                        event=REQUEST_STATUS_QUEUED,
                    )

            now = utc_now_naive()
            if (now - last_heartbeat_ts).total_seconds() >= SSE_HEARTBEAT_SECONDS:
                yield format_heartbeat()
                last_heartbeat_ts = now

            if (now - started_at).total_seconds() >= SSE_MAX_CONNECTION_MINUTES * 60:
                return

            await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        return


def _queue_conflict(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=409, detail={"code": code, "message": message})


async def _build_existing_intake_result(
    *,
    repo: AgentRunRequestRepository,
    request: AgentRunRequest,
    uid: str,
    agent_slug: str,
    thread_id: str,
    source: str,
    channel: str,
    external_id: str | None,
    queue_policy: str,
) -> IntakeResult:
    expected_scope = (str(uid), agent_slug, thread_id, source, channel, external_id, queue_policy)
    actual_scope = (
        request.uid,
        request.agent_slug,
        request.conversation_thread_id,
        request.source,
        request.channel,
        request.external_id,
        request.queue_policy,
    )
    if actual_scope != expected_scope:
        raise _queue_conflict("request_id_conflict", "request_id already used by another request scope")
    return IntakeResult(
        request_id=request.request_id,
        status=request.status,
        queue_policy=request.queue_policy,
        message_id=request.input_message_id,
        thread_id=request.conversation_thread_id,
        run_id=request.dispatched_run_id,
        queue_position=await repo.get_queue_position(request.request_id)
        if request.status == REQUEST_STATUS_QUEUED
        else None,
    )


def _build_message_metadata(
    *, request_id: str, source: str, input_message: AgentRunInputMessage, meta: dict
) -> dict[str, Any]:
    """Build Message.extra_metadata: request_id + source + raw_message + extra context."""
    metadata: dict[str, Any] = {"request_id": request_id}
    if source:
        metadata["source"] = source
    if channel := meta.get("channel"):
        metadata["channel"] = channel
    if raw_message := input_message.raw_message():
        metadata["raw_message"] = raw_message
    if attachment_file_ids := meta.get("attachment_file_ids"):
        metadata["attachment_file_ids"] = attachment_file_ids
    if isinstance(meta.get("agent_invocation_meta"), dict):
        metadata["agent_invocation_meta"] = meta["agent_invocation_meta"]
    if meta.get("tool_approval_mode") is not None:
        metadata["tool_approval_mode"] = meta["tool_approval_mode"]
    return metadata


async def _is_steerable_message_run(*, db: AsyncSession, run: AgentRun) -> bool:
    """Confirm the Run is running and comes from a Steer-capable message entry."""
    if run.status != "running" or run.run_type != "chat":
        return False
    request = await AgentRunRequestRepository(db).get_by_request_id(run.request_id)
    return request is not None and request.source in {"chat", "channel"}


async def _get_thread_conversation(
    *,
    db: AsyncSession,
    uid: str,
    agent_slug: str,
    thread_id: str,
    lock: bool = False,
):
    repo = ConversationRepository(db)
    conversation = (
        await repo.lock_conversation_by_thread_id(thread_id)
        if lock
        else await repo.get_conversation_by_thread_id(thread_id)
    )
    if _conversation_matches(conversation, uid=uid, agent_slug=agent_slug):
        return conversation
    raise HTTPException(status_code=404, detail="Conversation thread not found")


def _conversation_matches(conversation, *, uid: str, agent_slug: str) -> bool:
    """Thread ownership check: exists, not deleted, owned by current user and agent."""
    return (
        conversation is not None
        and conversation.uid == str(uid)
        and conversation.status != "deleted"
        and conversation.agent_id == agent_slug
    )


async def _get_queue_state(
    *,
    db: AsyncSession,
    uid: str,
    agent_slug: str,
    thread_id: str,
    head: AgentRunRequest | None,
) -> tuple[str, dict]:
    """Derive queue state from the head, the active run, and the latest top-level run."""
    if head is None:
        return "idle", {"paused_reason": None, "blocking_run_id": None, "can_continue": False}

    run_repo = AgentRunRepository(db)
    active_run = await run_repo.get_active_run_by_thread_for_user(
        uid=str(uid), agent_slug=agent_slug, conversation_thread_id=thread_id
    )
    if active_run:
        return "running", {"paused_reason": None, "blocking_run_id": None, "can_continue": False}

    latest_run = await run_repo.get_latest_chat_or_resume_run(
        uid=str(uid), agent_slug=agent_slug, conversation_thread_id=thread_id
    )
    if latest_run and latest_run.status == "interrupted":
        return "interrupted", {
            "paused_reason": None,
            "blocking_run_id": latest_run.id,
            "can_continue": False,
        }

    if latest_run and latest_run.status in {"failed", "cancelled"} and latest_run.finished_at is None:
        raise RuntimeError(f"Terminal run {latest_run.id} is missing finished_at")

    if latest_run and latest_run.status in {"failed", "cancelled"} and head.created_at <= latest_run.finished_at:
        return "paused", {
            "paused_reason": latest_run.status,
            "blocking_run_id": latest_run.id,
            "can_continue": True,
        }

    return "ready", {"paused_reason": None, "blocking_run_id": None, "can_continue": False}


async def _dispatch_ready_head(
    *,
    db: AsyncSession,
    uid: str,
    agent_slug: str,
    thread_id: str,
    conversation_id: int,
    expected_request_id: str | None = None,
) -> DispatchResult | None:
    """Dispatch the FIFO head only in ready state."""
    repo = AgentRunRequestRepository(db)
    head = await repo.get_queue_head(
        uid=uid,
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
    )
    if not head:
        return None
    if expected_request_id is not None and head.request_id != expected_request_id:
        return None
    status, _ = await _get_queue_state(
        db=db,
        uid=uid,
        agent_slug=agent_slug,
        thread_id=thread_id,
        head=head,
    )
    if status != "ready":
        return None
    return await _dispatch_locked_head(
        db=db,
        head=head,
        uid=uid,
        agent_slug=agent_slug,
        thread_id=thread_id,
        conversation_id=conversation_id,
    )


async def _dispatch_locked_head(
    *,
    db: AsyncSession,
    head: AgentRunRequest,
    uid: str,
    agent_slug: str,
    thread_id: str,
    conversation_id: int,
) -> DispatchResult | None:
    """Convert the locked queued head into an AgentRun without committing."""
    repo = AgentRunRequestRepository(db)
    run_repo = AgentRunRepository(db)
    run_id = str(uuid.uuid4())
    try:
        async with db.begin_nested():
            await run_repo.create_run(
                run_id=run_id,
                conversation_thread_id=thread_id,
                agent_slug=agent_slug,
                uid=uid,
                request_id=head.request_id,
                input_payload=head.input_payload or {},
                source=head.source,
                channel=head.channel,
                external_id=head.external_id,
                origin_metadata=head.origin_metadata,
                conversation_id=conversation_id,
                run_type="chat",
                input_message_id=head.input_message_id,
            )
            msg = await db.get(Message, head.input_message_id)
            if msg:
                msg.run_id = run_id
                msg.delivery_status = DELIVERY_STATUS_DISPATCHED
            await db.flush()
            await repo.mark_dispatched(head.request_id, run_id=run_id)
    except IntegrityError as exc:
        cause = getattr(exc.orig, "__cause__", None)
        constraint_name = getattr(exc.orig, "constraint_name", None) or getattr(cause, "constraint_name", None)
        if constraint_name != "uq_agent_runs_one_active_per_thread":
            raise
        logger.info(f"Dispatch conflict for request {head.request_id}, keeping queued")
        return None

    return DispatchResult(request_id=head.request_id, run_id=run_id)
