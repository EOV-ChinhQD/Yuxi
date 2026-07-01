from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from server.utils.auth_middleware import get_db, get_required_user
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.repositories.conversation_repository import ConversationRepository
from yuxi.services.mention_search_service import search_mention_files_in_index
from yuxi.storage.postgres.models_business import User

mention_router = APIRouter(prefix="/mention", tags=["mention"])


class MentionFileItem(BaseModel):
    """Kết quả tìm kiếm tệp được nhắc đến"""

    name: str
    path: str
    is_dir: bool
    source: str


@mention_router.get("/search", response_model=list[MentionFileItem])
async def search_mention_files(
    thread_id: str | None = Query(None, description="ID phiên hội thoại hiện tại; khi để trống chỉ tìm kiếm trong workspace của người dùng"),
    query: str = Query("", description="Từ khóa tìm kiếm"),
    sources: str | None = Query(None, description="Nguồn tìm kiếm: workspace, thread; để trống sẽ tự động chọn"),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """
    API tìm kiếm tệp được nhắc đến: Khi chưa tạo thread chỉ tìm kiếm trong workspace người dùng; khi đã có thread có thể tìm kiếm tệp trong cuộc hội thoại hiện tại.
    """
    uid = str(current_user.uid)
    effective_thread_id: str | None = None

    if thread_id:
        conv_repo = ConversationRepository(db)
        conversation = await conv_repo.get_conversation_by_thread_id(thread_id)
        if conversation:
            if conversation.uid != uid or conversation.status == "deleted":
                raise HTTPException(status_code=404, detail="Thread hội thoại không tồn tại")
            effective_thread_id = thread_id
        else:
            try:
                from yuxi.agents.backends.sandbox.paths import validate_thread_id

                validate_thread_id(thread_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Định dạng thread_id không hợp lệ")

    source_list = [item.strip() for item in sources.split(",")] if sources else None
    return await search_mention_files_in_index(
        thread_id=effective_thread_id,
        uid=uid,
        query=query,
        sources=source_list,
    )
