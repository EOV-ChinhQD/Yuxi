"""Project persistence repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.repositories.conversation_repository import INVOCATION_CONVERSATION_SOURCES
from yuxi.storage.postgres.models_business import Conversation, Project


class ProjectRepository:
    """Read/write Project business facts for the current user."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def add(self, project: Project) -> Project:
        """Add a Project and flush."""
        self.db.add(project)
        await self.db.flush()
        return project

    async def get_for_user(self, project_id: str, uid: str) -> Project | None:
        """Read a Project owned by a user."""
        return await self.db.scalar(select(Project).where(Project.id == project_id, Project.uid == str(uid)))

    async def get_by_idempotency_key(self, idempotency_key: str, uid: str) -> Project | None:
        """Read a Project by user and idempotency key."""
        return await self.db.scalar(
            select(Project).where(Project.uid == str(uid), Project.idempotency_key == idempotency_key)
        )

    async def list_selectable_for_user(self, uid: str) -> list[Project]:
        """List Projects the user can select."""
        result = await self.db.execute(
            select(Project)
            .where(Project.uid == str(uid), Project.selection_status == "selectable")
            .order_by(Project.updated_at.desc(), Project.id.desc())
        )
        return list(result.scalars().all())

    async def list_selectable_workdir_paths_for_user(self, uid: str) -> list[str]:
        """List the deduplicated Workdir paths of a user's selectable Projects."""
        result = await self.db.execute(
            select(Project.workdir_path)
            .where(Project.uid == str(uid), Project.selection_status == "selectable")
            .distinct()
        )
        return list(result.scalars().all())

    async def get_by_workdir_path(self, uid: str, workdir_path: str) -> Project | None:
        """Check duplicate linked workdir per user."""
        return await self.db.scalar(
            select(Project).where(Project.uid == str(uid), Project.workdir_path == workdir_path)
        )

    async def delete(self, project: Project) -> None:
        """Delete a Project."""
        await self.db.delete(project)
        await self.db.flush()

    async def count_bound_conversations(self, project_id: str, uid: str) -> int:
        """Count conversations bound to a project."""
        result = await self.db.execute(
            select(Conversation.id).where(Conversation.project_id == project_id, Conversation.uid == str(uid))
        )
        return len(result.scalars().all())

    async def list_history_candidates(
        self, uid: str, query: str | None = None, limit: int = 20, offset: int = 0
    ) -> tuple[list[tuple[Conversation, str]], bool]:
        """List historical conversations with DB-side filtering and pagination."""
        normalized = (query or "").strip().lower()
        stmt = (
            select(Conversation, Project.workdir_path)
            .join(Project, (Project.uid == Conversation.uid) & (Project.id == Conversation.project_id))
            .where(
                Conversation.uid == str(uid),
                Conversation.status == "active",
                (
                    Conversation.extra_metadata.is_(None)
                    | Conversation.extra_metadata["source"].as_string().is_(None)
                    | Conversation.extra_metadata["source"].as_string().notin_(INVOCATION_CONVERSATION_SOURCES)
                ),
            )
        )
        if normalized:
            stmt = stmt.where(
                (Conversation.title.ilike(f"%{normalized}%")) | (Conversation.agent_id.ilike(f"%{normalized}%"))
            )
        stmt = stmt.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).limit(limit + 1).offset(offset)
        result = await self.db.execute(stmt)
        rows = list(result.all())
        has_more = len(rows) > limit
        return rows[:limit], has_more
