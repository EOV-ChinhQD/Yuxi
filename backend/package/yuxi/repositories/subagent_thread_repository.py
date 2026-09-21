"""Subagent thread relation repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import SubagentThread


class SubagentThreadRepository:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_by_child_thread_for_user(self, child_thread_id: str, uid: str) -> SubagentThread | None:
        """Find parent-child thread relationships visible to current user by sub-thread ID."""
        result = await self.db.execute(
            select(SubagentThread).where(
                SubagentThread.child_thread_id == child_thread_id,
                SubagentThread.uid == str(uid),
            )
        )
        return result.scalar_one_or_none()

    async def get_for_user(self, relation_id: int, uid: str) -> SubagentThread | None:
        """Read subagent thread relationship for current user by primary key."""
        result = await self.db.execute(
            select(SubagentThread).where(
                SubagentThread.id == relation_id,
                SubagentThread.uid == str(uid),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_child_conversation_for_user(self, child_conversation_id: int, uid: str) -> SubagentThread | None:
        """Find parent-child relationship by sub-conversation ID to trace parent thread."""
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
        """Create parent-to-child conversation thread relationship record."""
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
