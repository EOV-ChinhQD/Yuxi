from typing import Any
from yuxi.knowledge.chunking.base import BaseChunker, ChunkResult, ChunkMetadata
from yuxi.knowledge.chunking.ragflow_like.parsers.general import chunk_markdown
from yuxi.knowledge.chunking.ragflow_like import nlp


class NaiveChunker(BaseChunker):
    """Adapter: wrap parser cũ (general.py) vào BaseChunker interface."""

    def chunk(self, markdown: str, config: dict[str, Any] | None = None) -> list[ChunkResult]:
        config = config or {}
        text_chunks = chunk_markdown(markdown, config)

        results = []
        for c in text_chunks:
            token_count = nlp.count_tokens(c)
            results.append(ChunkResult(content=c, metadata=ChunkMetadata(), token_count=token_count))
        return results
