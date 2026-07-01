"""Agent evaluation run service.

This service intentionally does not implement dataset storage or judging. It
creates a normal conversation-backed AgentRun, blocks until it finishes, and
returns the run's final result by reusing the shared agent_run base capability.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.repositories.agent_repository import AgentRepository
from yuxi.repositories.conversation_repository import ConversationRepository
from yuxi.services.agent_run_service import await_agent_run_result, create_agent_run_view
from yuxi.storage.postgres.models_business import User

EVALUATION_SOURCE = "agent_evaluation"
EVALUATION_FIELDS = ("dataset_name", "dataset_item_id", "experiment_name")
MAX_REQUEST_ID_LENGTH = 64


def _normalize_evaluation(evaluation: dict[str, Any] | None) -> dict[str, str]:
    """Only known evaluation fields are retained and converted into non-empty strings with whitespace removed."""
    if not isinstance(evaluation, dict):
        return {}

    normalized: dict[str, str] = {}
    for key in EVALUATION_FIELDS:
        value = evaluation.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            normalized[key] = text
    return normalized


def _normalize_request_id(meta: dict[str, Any] | None) -> str:
    """Returns the request_id with whitespace trimmed and length verified; by default a new UUID is generated."""
    raw_request_id = (meta or {}).get("request_id")
    if raw_request_id is None or not str(raw_request_id).strip():
        return str(uuid.uuid4())

    request_id = str(raw_request_id).strip()
    if len(request_id) > MAX_REQUEST_ID_LENGTH:
        raise HTTPException(status_code=422, detail=f"request_id không được vượt quá {MAX_REQUEST_ID_LENGTH} ký tự")
    return request_id


async def run_agent_eval(
    *,
    query: str,
    agent_slug: str,
    evaluation: dict[str, Any] | None,
    meta: dict[str, Any] | None,
    image_content: str | None,
    model_spec: str | None,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any]:
    """Create Evaluate AgentRun, block until the end of the run and return the final result.

    The caller of Evaluate only cares about the final output, so it does not perform SSE streaming encapsulation: it can be directly reused after building run.
    ``await_agent_run_result`` waits for the run to terminate and returns the result. Note that this will block HTTP requests until
    The operation ends (no intermediate bytes), and the idle timeout needs to be relaxed accordingly for long operations on the gateway link.
    """
    agent_slug = agent_slug.strip()
    if not agent_slug:
        raise HTTPException(status_code=422, detail="agent_slug không được để trống")
    if not query:
        raise HTTPException(status_code=422, detail="query không được để trống")

    agent_item = await AgentRepository(db).get_visible_by_slug(slug=agent_slug, user=current_user)
    if not agent_item:
        raise HTTPException(status_code=404, detail="Agent không tồn tại")

    evaluation_metadata = _normalize_evaluation(evaluation)
    request_id = _normalize_request_id(meta)
    thread_id = str(uuid.uuid4())

    await ConversationRepository(db).create_conversation(
        uid=str(current_user.uid),
        agent_id=agent_item.slug,
        title="Agent Evaluation Run",
        thread_id=thread_id,
        metadata={
            "source": EVALUATION_SOURCE,
            "evaluation": evaluation_metadata,
        },
    )

    run_meta = {
        "request_id": request_id,
        "source": EVALUATION_SOURCE,
        "evaluation": evaluation_metadata,
        "attachment_file_ids": (meta or {}).get("attachment_file_ids") or [],
    }
    run_response = await create_agent_run_view(
        query=query,
        agent_id=agent_item.slug,
        thread_id=thread_id,
        meta=run_meta,
        image_content=image_content,
        current_uid=str(current_user.uid),
        db=db,
        model_spec=model_spec,
    )
    return await await_agent_run_result(run_id=run_response["run_id"], current_uid=str(current_user.uid))
