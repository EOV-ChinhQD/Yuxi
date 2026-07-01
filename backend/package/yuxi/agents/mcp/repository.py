"""MCP Server data access layer - Repository"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import MCPServer


class MCPServerRepository:
    """
    MCP servers repository
    """

    async def get_by_slug(self, slug: str) -> MCPServer | None:
        """Get MCP server by slug"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(MCPServer).where(MCPServer.slug == slug))
            return result.scalar_one_or_none()

    async def list(self) -> list[MCPServer]:
        """Get all MCP servers"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(MCPServer))
            return list(result.scalars().all())

    async def list_enabled(self) -> list[MCPServer]:
        """Get enabled MCP servers"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(MCPServer).where(MCPServer.enabled == 1))
            return list(result.scalars().all())

    async def create(self, data: dict[str, Any]) -> MCPServer:
        """Create MCP server"""
        async with pg_manager.get_async_session_context() as session:
            server = MCPServer(**data)
            session.add(server)
        return server

    async def update(self, slug: str, data: dict[str, Any]) -> MCPServer | None:
        """Update MCP server"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(MCPServer).where(MCPServer.slug == slug))
            server = result.scalar_one_or_none()
            if server is None:
                return None
            for key, value in data.items():
                if key != "slug":
                    setattr(server, key, value)
        return server

    async def delete(self, slug: str) -> bool:
        """Delete MCP server"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(MCPServer).where(MCPServer.slug == slug))
            server = result.scalar_one_or_none()
            if server is None:
                return False
            await session.delete(server)
        return True

    async def upsert(self, data: dict[str, Any]) -> MCPServer:
        """Insert or update MCP server"""
        slug = data.get("slug")
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(MCPServer).where(MCPServer.slug == slug))
            existing = result.scalar_one_or_none()
            if existing is None:
                server = MCPServer(**data)
                session.add(server)
            else:
                for key, value in data.items():
                    if key != "slug":
                        setattr(existing, key, value)
                server = existing
        return server

    async def exists_by_slug(self, slug: str) -> bool:
        """Check if MCP server exists by slug"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(MCPServer.id).where(MCPServer.slug == slug))
            return result.scalar_one_or_none() is not None
