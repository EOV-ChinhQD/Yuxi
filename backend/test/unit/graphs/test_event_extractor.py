from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import pytest

import yuxi.knowledge.graphs.extractors.event as event_module
from yuxi.knowledge.graphs.extractors.event import LLMEventExtractor, benchmark_entity_types


def test_event_extractor_options():
    extractor = LLMEventExtractor({"model_spec": "test/model"})
    extractor.validate_options()

    with pytest.raises(ValueError, match="LLMEventExtractor cần model_spec"):
        LLMEventExtractor({}).validate_options()


@pytest.mark.asyncio
async def test_event_extractor_extract():
    extractor = LLMEventExtractor({"model_spec": "test/model"})
    
    mock_model = MagicMock()
    mock_model.call = AsyncMock(return_value=SimpleNamespace(content="""
    {
        "type": "response",
        "data": {
            "items": [
                {
                    "title": "SAG Release",
                    "summary": "SAG was released.",
                    "content": "SAG is next-generation RAG.",
                    "category": "release",
                    "keywords": ["SAG", "RAG"],
                    "entities": [
                        {"type": "product", "name": "SAG", "description": "a RAG system"}
                    ]
                }
            ]
        }
    }
    """))
    
    event_module.select_model = MagicMock(return_value=mock_model)
    
    res = await extractor.extract("some text", chunk_metadata={"title": "Doc", "heading": "Heading"})
    assert res["event"]["title"] == "SAG Release"
    assert res["event"]["category"] == "release"
    assert res["entities"][0]["name"] == "SAG"
