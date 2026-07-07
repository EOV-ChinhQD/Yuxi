from __future__ import annotations

from typing import Any

from .base import GraphExtractor
from .llm import LLMGraphExtractor
from .event import LLMEventExtractor


class GraphExtractorFactory:
    _registry: dict[str, type[GraphExtractor]] = {
        "llm": LLMGraphExtractor,
        "event_llm": LLMEventExtractor,
    }

    @classmethod
    def create(cls, extractor_type: str | None, options: dict[str, Any] | None = None) -> GraphExtractor:
        normalized_type = (extractor_type or "").lower()
        extractor_class = cls._registry.get(normalized_type)
        if not extractor_class:
            raise ValueError(f"Loại bộ trích xuất đồ thị không được hỗ trợ: {extractor_type}")
        extractor = extractor_class(options or {})
        extractor.validate_options()
        return extractor

    @classmethod
    def supported_types(cls) -> list[str]:
        return list(cls._registry.keys())
