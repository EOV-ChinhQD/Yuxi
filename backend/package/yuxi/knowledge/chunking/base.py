from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChunkMetadata:
    """Metadata ngữ cảnh cho chunk — KHÔNG ghi vào raw text."""

    heading_path: list[str] = field(default_factory=list)  # ["H1 Title", "H2 Section"]
    section_type: str = ""  # "text", "table", "equation", "code"
    page_number: int | None = None
    depth: int = 0  # Heading depth in tree


@dataclass
class ChunkResult:
    """Output chuẩn hóa từ mọi Chunker."""

    content: str  # Raw text, KHÔNG chứa context prefix
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)
    token_count: int = 0


class BaseChunker(ABC):
    """Interface cho tất cả chunker implementations."""

    @abstractmethod
    def chunk(self, markdown: str, config: dict[str, Any] | None = None) -> list[ChunkResult]:
        """Cắt markdown thành danh sách chunks có metadata."""
        pass

    def build_context_prefix(self, meta: ChunkMetadata) -> str:
        """Build context string từ metadata — chỉ dùng khi embedding/retrieval."""
        if not meta.heading_path:
            return ""
        return "Context: " + " > ".join(meta.heading_path)
