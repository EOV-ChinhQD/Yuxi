"""Subagent thread relation repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import SubagentThread


class SubagentThreadRepository:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_by_child_thread_for_user(self, child_thread_id: str, uid: str) -> SubagentThread | None:
        """Tìm kiếm quan hệ luồng cha - con người dùng có quyền xem theo ID luồng con."""
        result = await self.db.execute(
            select(SubagentThread).where(
                SubagentThread.child_thread_id == child_thread_id,
                SubagentThread.uid == str(uid),
            )
        )
        return result.scalar_one_or_none()

    async def get_for_user(self, relation_id: int, uid: str) -> SubagentThread | None:
        """Đọc quan hệ luồng của Subagent của người dùng hiện tại theo khóa chính của bản ghi quan hệ."""
        result = await self.db.execute(
            select(SubagentThread).where(
                SubagentThread.id == relation_id,
                SubagentThread.uid == str(uid),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_child_conversation_for_user(self, child_conversation_id: int, uid: str) -> SubagentThread | None:
        """Tìm kiếm quan hệ luồng cha - con theo ID cuộc hội thoại con, dùng để tra ngược luồng cha từ conversation."""
        result = await self.db.execute(
            select(SubagentThread).where(
                SubagentThread.child_conversation_id == child_conversation_id,
                SubagentThread.uid == str(uid),
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        uid: str,
        parent_conversation_id: int,
        child_conversation_id: int,
        child_thread_id: str,
        subagent_slug: str,
        created_by_run_id: str,
    ) -> SubagentThread:
        """Tạo một bản ghi quan hệ luồng từ cuộc hội thoại cha đến cuộc hội thoại con."""
        item = SubagentThread(
            uid=str(uid),
            parent_conversation_id=parent_conversation_id,
            child_conversation_id=child_conversation_id,
            child_thread_id=child_thread_id,
            subagent_slug=subagent_slug,
            created_by_run_id=created_by_run_id,
        )
        self.db.add(item)
        await self.db.flush()
        return item
