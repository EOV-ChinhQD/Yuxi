from typing import Any
from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_knowledge import IndexManifest


class IndexManifestRepository:
    async def create(self, **kwargs: Any) -> IndexManifest:
        async with pg_manager.get_async_session_context() as session:
            manifest = IndexManifest(**kwargs)
            session.add(manifest)
            await session.commit()
            return manifest
