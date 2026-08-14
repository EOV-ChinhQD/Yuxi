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
    agent_slug: str = Field(..., description="Slug của Agent cần gọi")
    messages: list[dict[str, Any]] = Field(..., description="Danh sách tin nhắn, lấy tin nhắn user cuối cùng làm đầu vào")
    stream: bool = Field(False, description="Tạm thời chưa hỗ trợ stream, truyền true sẽ trả về lỗi 422")
    agent_call_meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata của Agent Call; không cho phép ghi đè ngữ cảnh chạy của Agent qua context",
    )
    thread_id: str | None = Field(None, description="ID luồng hội thoại tùy chọn, nếu không truyền sẽ tự động tạo luồng tạm")
    request_id: str | None = Field(None, description="ID idempotent của yêu cầu tùy chọn, nếu không truyền sẽ tự động sinh")
    model_spec: str | None = Field(None, description="Ghi đè mô hình tùy chọn")
    async_mode: bool = Field(False, description="Chỉ tạo run và trả về run_id ngay lập tức hay không")


class AgentCallRunResultRequest(BaseModel):
    run_id: str = Field(..., description="ID của AgentRun")
    agent_slug: str | None = Field(None, description="Tùy chọn, dùng để kiểm tra quyền sở hữu run khi truyền vào")


class AgentEvaluationContext(BaseModel):
    dataset_name: str | None = Field(None, description="Tên dataset trên Langfuse")
    dataset_item_id: str | None = Field(None, description="ID item trong dataset Langfuse")
    experiment_name: str | None = Field(None, description="Tên experiment/run trên Langfuse")


class AgentEvalRunCreate(BaseModel):
    query: str = Field(..., description="Dữ liệu đầu vào của mẫu đánh giá")
    agent_slug: str = Field(..., description="Slug của Agent cần chạy")
    evaluation: AgentEvaluationContext = Field(default_factory=AgentEvaluationContext, description="Ngữ cảnh đánh giá")
    meta: dict = Field(default_factory=dict, description="Tùy chọn, thông tin truy vết yêu cầu, ví dụ request_id, attachment_file_ids")
    image_content: str | None = Field(None, description="Tùy chọn, nội dung ảnh định dạng base64")
    model_spec: str | None = Field(None, description="Tùy chọn, ghi đè mô hình cấp hội thoại, ưu tiên cao hơn cấu hình Agent")
    include_trajectory_summary: bool = Field(False, description="Có trả về bản tóm tắt quỹ đạo gọi công cụ gọn nhẹ hay không")


@agent_invocation_router.post("/agent-call/runs")
async def create_agent_call_run(
    payload: AgentCallRunCreate,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """Tạo run gọi Agent từ hệ thống bên ngoài, và quyết định có chờ kết quả cuối cùng theo async_mode hay không."""
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
    """Đọc cấu trúc kết quả tương thích chuẩn OpenAI của run gọi Agent bên ngoài."""
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
    """Chạy một mẫu đánh giá Agent CLI/Langfuse và chặn chờ kết quả đầu ra cuối cùng."""
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
