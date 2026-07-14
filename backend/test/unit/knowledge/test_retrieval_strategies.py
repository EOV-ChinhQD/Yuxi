import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from yuxi.knowledge.retrieval.router import RouteType
from yuxi.knowledge.retrieval.dispatcher import (
    RetrievalDispatcher,
    FactStrategy,
    SummaryStrategy,
    CompareStrategy,
    MultiHopStrategy
)
from yuxi.storage.postgres.models_knowledge import KnowledgeChunk

@pytest.mark.asyncio
async def test_fact_strategy():
    strategy = FactStrategy()
    mock_kb = MagicMock()
    mock_kb._query_factual = AsyncMock(return_value=[{"chunk_id": "chunk_1", "content": "hello"}])

    res = await strategy.retrieve("query", mock_kb, "kb_123", final_top_k=5)
    assert len(res) == 1
    assert res[0]["chunk_id"] == "chunk_1"
    mock_kb._query_factual.assert_called_once_with("query", "kb_123", final_top_k=5, use_graph_retrieval=False)

@pytest.mark.asyncio
async def test_summary_strategy():
    strategy = SummaryStrategy()
    mock_kb = MagicMock()
    mock_kb._query_factual = AsyncMock(return_value=[{"chunk_id": "chunk_2", "content": "vector content"}])
    mock_kb._build_chunk_from_record = MagicMock(return_value={"chunk_id": "chunk_1", "content": "event content", "score": 0.9})

    mock_chunk = KnowledgeChunk(chunk_id="chunk_1", content="event content")
    mock_execute = MagicMock()
    mock_execute.scalars.return_value.all.return_value = [mock_chunk]

    mock_session_ctx = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_execute)
    mock_session_ctx.__aenter__.return_value = mock_session

    with patch("yuxi.storage.postgres.manager.PostgresManager.get_async_session_context", return_value=mock_session_ctx):
        res = await strategy.retrieve("summary", mock_kb, "kb_123")

    assert len(res) == 2
    assert res[0]["chunk_id"] == "chunk_1"
    assert res[1]["chunk_id"] == "chunk_2"
    mock_kb._query_factual.assert_called_once_with("summary", "kb_123", use_graph_retrieval=False)

@pytest.mark.asyncio
async def test_compare_strategy():
    strategy = CompareStrategy()
    mock_kb = MagicMock()
    mock_kb._query_factual = AsyncMock(side_effect=lambda q, *args, **kwargs: [
        {"chunk_id": f"chunk_{q}", "content": f"content for {q}"}
    ])

    with patch("yuxi.knowledge.retrieval.multi_hop_retriever.detect_and_decompose", AsyncMock(return_value=(True, ["sub_A", "sub_B"]))):
        res = await strategy.retrieve("so sánh A và B", mock_kb, "kb_123")

    assert len(res) == 2
    assert res[0]["chunk_id"] == "chunk_sub_A"
    assert "Nguồn tin cho câu hỏi con: sub_A" in res[0]["content"]
    assert res[1]["chunk_id"] == "chunk_sub_B"
    assert "Nguồn tin cho câu hỏi con: sub_B" in res[1]["content"]

@pytest.mark.asyncio
async def test_multihop_strategy():
    strategy = MultiHopStrategy()
    mock_kb = MagicMock()
    mock_kb.databases_meta = {"kb_123": {"llm_model_spec": "gemini", "embedding_model_spec": "embed"}}

    mock_retrieve = AsyncMock(return_value=[{"chunk_id": "chunk_multihop"}])

    with patch("yuxi.knowledge.retrieval.multi_hop_retriever.MultiHopRetriever.retrieve", mock_retrieve):
        res = await strategy.retrieve("query", mock_kb, "kb_123", final_top_k=5)

    assert len(res) == 1
    assert res[0]["chunk_id"] == "chunk_multihop"
    mock_retrieve.assert_called_once_with("query", search_mode="normal", max_hops=2, rerank_top_k=5)

@pytest.mark.asyncio
async def test_retrieval_dispatcher_routing():
    dispatcher = RetrievalDispatcher()
    
    mock_kb = MagicMock()
    mock_kb.databases_meta = {"kb_123": {"llm_model_spec": "gemini", "embedding_model_spec": "embed"}}

    # Mock all strategies
    for name, strat in dispatcher._strategies.items():
        strat.retrieve = AsyncMock(return_value=[{"strategy": name}])

    # 1. EXACT_MATCH -> FactStrategy
    with patch("yuxi.knowledge.retrieval.router.SemanticRouter.route", AsyncMock(return_value=(RouteType.EXACT_MATCH, {}))):
        res = await dispatcher.dispatch("query", mock_kb, "kb_123")
        assert res[0]["chunk_id"] == "system_routing_header"
        assert res[1]["strategy"] == "fact"

    # 2. SUMMARIZATION -> SummaryStrategy
    with patch("yuxi.knowledge.retrieval.router.SemanticRouter.route", AsyncMock(return_value=(RouteType.SUMMARIZATION, {}))):
        res = await dispatcher.dispatch("query", mock_kb, "kb_123")
        assert res[0]["chunk_id"] == "system_routing_header"
        assert res[1]["strategy"] == "summary"

    # 3. MULTI_HOP with compare words -> CompareStrategy
    with patch("yuxi.knowledge.retrieval.router.SemanticRouter.route", AsyncMock(return_value=(RouteType.MULTI_HOP, {}))):
        res = await dispatcher.dispatch("so sánh A và B", mock_kb, "kb_123")
        assert res[0]["chunk_id"] == "system_routing_header"
        assert res[1]["strategy"] == "compare"

    # 4. MULTI_HOP without compare words -> MultiHopStrategy
    with patch("yuxi.knowledge.retrieval.router.SemanticRouter.route", AsyncMock(return_value=(RouteType.MULTI_HOP, {}))):
        res = await dispatcher.dispatch("quan hệ A và B là gì", mock_kb, "kb_123")
        assert res[0]["chunk_id"] == "system_routing_header"
        assert res[1]["strategy"] == "multihop"
