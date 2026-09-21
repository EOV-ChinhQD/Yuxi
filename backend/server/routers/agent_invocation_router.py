from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.services.agent_invocation_service import (
    create_agent_call_run_view,
    create_agent_eval_run_view,
    get_agent_call_run_result_view,
)
from yuxi.storage.postgres.models_business import User

from server.utils.auth_middleware import get_db, get_required_user

agent_invocation_router = APIRouter(prefix="/agent-invocation", tags=["agent-invocation"])


class AgentCallRunCreate(BaseModel):
    agent_slug: str = Field(..., description="Agent slug to invoke")
    messages: list[dict[str, Any]] = Field(..., description="， user ")
    stream: bool = Field(False, description="， true  422")
    agent_call_meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Agent Call ； context  Agent ",
    )
    thread_id: str | None = Field(None, description=" ID，")
    request_id: str | None = Field(None, description=" ID，")
    model_spec: str | None = Field(None, description="")
    async_mode: bool = Field(False, description=" run_id")


class AgentCallRunResultRequest(BaseModel):
    run_id: str = Field(..., description="AgentRun ID")
    agent_slug: str | None = Field(None, description="， run ")


class AgentEvaluationContext(BaseModel):
    dataset_name: str | None = Field(None, description="Langfuse dataset ")
    dataset_item_id: str | None = Field(None, description="Langfuse dataset item ID")
    experiment_name: str | None = Field(None, description="Langfuse experiment/run ")


class AgentEvalRunCreate(BaseModel):
    query: str = Field(..., description="")
    agent_slug: str = Field(..., description=" slug")
    evaluation: AgentEvaluationContext = Field(default_factory=AgentEvaluationContext, description="")
    meta: dict = Field(default_factory=dict, description="，， request_id、attachment_file_ids")
    image_content: str | None = Field(None, description="，base64 ")
    model_spec: str | None = Field(None, description="，，")
    include_trajectory_summary: bool = Field(False, description="")


@agent_invocation_router.post("/agent-call/runs")
async def create_agent_call_run(
    payload: AgentCallRunCreate,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """[cleaned]  Agent  [cleaned]  run， [cleaned]  async_mode  [cleaned] 。"""
    return await create_agent_call_run_view(
        agent_slug=payload.agent_slug,
        messages=payload.messages,
        agent_call_meta=payload.agent_call_meta,
        requested_thread_id=payload.thread_id,
        request_id=payload.request_id,
        model_spec=payload.model_spec,
        async_mode=payload.async_mode,
        stream=payload.stream,
        current_user=current_user,
        db=db,
    )


@agent_invocation_router.post("/agent-call/runs/result")
async def get_agent_call_run_result(
    payload: AgentCallRunResultRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """[cleaned]  Agent  [cleaned]  run  [cleaned]  OpenAI-compatible  [cleaned] 。"""
    return await get_agent_call_run_result_view(
        run_id=payload.run_id,
        agent_slug=payload.agent_slug,
        current_uid=str(current_user.uid),
        db=db,
    )


@agent_invocation_router.post("/eval/runs")
async def create_agent_eval_run(
    payload: AgentEvalRunCreate,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """[cleaned]  CLI/Langfuse Agent  [cleaned] ， [cleaned] 。"""
    return await create_agent_eval_run_view(
        query=payload.query,
        agent_slug=payload.agent_slug,
        evaluation=payload.evaluation.model_dump(exclude_none=True),
        meta=dict(payload.meta or {}),
        image_content=payload.image_content,
        model_spec=payload.model_spec,
        include_trajectory_summary=payload.include_trajectory_summary,
        current_user=current_user,
        db=db,
    )
