import hashlib
import json
import logging
from yuxi.storage.postgres.manager import pg_manager
from sqlalchemy import text

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """
    Caches embedding vectors in Postgres to prevent redundant GPU calls.
    Uses an md5 hash of the text + model_name as the key.
    """

    @staticmethod
    def _generate_key(content: str, model_name: str) -> str:
        key_str = f"{model_name}::{content}"
        return hashlib.md5(key_str.encode("utf-8")).hexdigest()

    @classmethod
    async def get_embeddings(cls, contents: list[str], model_name: str) -> list[list[float] | None]:
        """Fetch embeddings for a list of contents. Returns None for cache misses."""
        keys = [cls._generate_key(c, model_name) for c in contents]

        # This requires an embedding_cache table in Postgres.
        # CREATE TABLE IF NOT EXISTS embedding_cache (
        #     hash_key VARCHAR(64) PRIMARY KEY,
        #     embedding JSONB,
        #     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        # );

        try:
            async with pg_manager.get_async_session_context() as session:
                result = await session.execute(
                    text("SELECT hash_key, embedding FROM embedding_cache WHERE hash_key = ANY(:keys)"), {"keys": keys}
                )
                cache_map = {row.hash_key: row.embedding for row in result.all()}

                return [cache_map.get(k) for k in keys]
        except Exception as e:
            # If table doesn't exist or DB error, fail gracefully and act as complete cache miss
            logger.warning(f"Failed to fetch from embedding_cache: {e}")
            return [None] * len(contents)

    @classmethod
    async def set_embeddings(cls, contents: list[str], embeddings: list[list[float]], model_name: str) -> None:
        """Store embeddings in cache."""
        if not contents or not embeddings or len(contents) != len(embeddings):
            return

        records = []
        for content, embedding in zip(contents, embeddings):
            records.append({"hash_key": cls._generate_key(content, model_name), "embedding": json.dumps(embedding)})

        try:
            async with pg_manager.get_async_session_context() as session:
                # Upsert using raw SQL
                stmt = text("""
                    INSERT INTO embedding_cache (hash_key, embedding)
                    VALUES (:hash_key, CAST(:embedding AS jsonb))
                    ON CONFLICT (hash_key) DO NOTHING
                """)
                for record in records:
                    await session.execute(stmt, record)
        except Exception as e:
            logger.warning(f"Failed to write to embedding_cache: {e}")
