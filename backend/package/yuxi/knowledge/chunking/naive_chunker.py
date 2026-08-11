from typing import Any
from yuxi.knowledge.chunking.base import BaseChunker, ChunkResult, ChunkMetadata, ChunkingResult
from yuxi.knowledge.chunking.ragflow_like.parsers.general import chunk_markdown
from yuxi.knowledge.chunking.ragflow_like import nlp


class NaiveChunker(BaseChunker):
    """Adapter wrapping the legacy parser (general.py) into the BaseChunker interface."""

    def chunk(self, markdown: str, config: dict[str, Any] | None = None) -> ChunkingResult:
        config = config or {}
        text_chunks = chunk_markdown(markdown, config)

        results = []
        for c in text_chunks:
            token_count = nlp.count_tokens(c)
            results.append(ChunkResult(content=c, metadata=ChunkMetadata(), token_count=token_count))
        return ChunkingResult(chunks=results, strategy="naive", quality="GOOD")
