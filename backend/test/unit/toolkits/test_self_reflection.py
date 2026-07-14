import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from yuxi.agents.toolkits.kbs import tools
from yuxi.knowledge.retrieval.router import RouteType


async def _fake_visible_kbs(runtime):
    return [{"kb_id": "db-1", "name": "FAQ"}]


@pytest.mark.asyncio
async def test_self_reflection_retries_once_on_empty(monkeypatch):
    # Setup mock retrievers
    calls = []
    async def mock_retriever(query_text, **kwargs):
        calls.append(query_text)
        if query_text == "câu hỏi cũ":
            return {"results": []} # Empty on first attempt
        elif query_text == "câu hỏi đã viết lại":
            return {"results": [{"content": "kết quả tìm kiếm", "chunk_id": "1", "file_id": "f1", "chunk_index": 0}]}
        return {"results": []}

    manager = MagicMock()
    manager.get_retrievers.return_value = {
        "db-1": {
            "name": "FAQ",
            "retriever": mock_retriever,
            "metadata": {"kb_type": "milvus"},
        }
    }
    
    monkeypatch.setattr(tools, "_get_knowledge_base", lambda: manager)
    monkeypatch.setattr(tools, "_resolve_visible_knowledge_bases_for_query", _fake_visible_kbs)
    
    # Mock SemanticRouter to always return NAIVE_SEARCH
    mock_route = AsyncMock(return_value=(RouteType.NAIVE_SEARCH, {"confidence_score": 1.0}))
    monkeypatch.setattr("yuxi.knowledge.retrieval.router.SemanticRouter.route", mock_route)
    
    # Mock _rewrite_query helper to return a rewritten question
    mock_rewrite = AsyncMock(return_value="câu hỏi đã viết lại")
    monkeypatch.setattr(tools, "_rewrite_query", mock_rewrite)

    # Call query_kb
    query_kb_func = getattr(tools.query_kb, "coroutine", None) or getattr(tools.query_kb, "func")
    result = await query_kb_func(kb_id="db-1", query_text="câu hỏi cũ")
    
    # Assertions
    assert len(calls) == 2
    assert calls[0] == "câu hỏi cũ"
    assert calls[1] == "câu hỏi đã viết lại"
    assert result["results"][0]["content"] == "kết quả tìm kiếm"


@pytest.mark.asyncio
async def test_self_reflection_max_retry_attempts(monkeypatch):
    # Setup mock retriever to always return empty
    calls = []
    async def mock_retriever(query_text, **kwargs):
        calls.append(query_text)
        return {"results": []}

    manager = MagicMock()
    manager.get_retrievers.return_value = {
        "db-1": {
            "name": "FAQ",
            "retriever": mock_retriever,
            "metadata": {"kb_type": "milvus"},
        }
    }
    
    monkeypatch.setattr(tools, "_get_knowledge_base", lambda: manager)
    monkeypatch.setattr(tools, "_resolve_visible_knowledge_bases_for_query", _fake_visible_kbs)
    
    # Mock SemanticRouter to always return NAIVE_SEARCH
    mock_route = AsyncMock(return_value=(RouteType.NAIVE_SEARCH, {"confidence_score": 1.0}))
    monkeypatch.setattr("yuxi.knowledge.retrieval.router.SemanticRouter.route", mock_route)
    
    # Mock _rewrite_query helper to return a rewritten question
    mock_rewrite = AsyncMock(return_value="câu hỏi đã viết lại")
    monkeypatch.setattr(tools, "_rewrite_query", mock_rewrite)

    # Call query_kb
    query_kb_func = getattr(tools.query_kb, "coroutine", None) or getattr(tools.query_kb, "func")
    result = await query_kb_func(kb_id="db-1", query_text="câu hỏi cũ")
    
    # Assertions: Should only call 2 times total (Attempt 0, Attempt 1 retry, then stops)
    assert len(calls) == 2
    assert calls[0] == "câu hỏi cũ"
    assert calls[1] == "câu hỏi đã viết lại"
    assert len(result["results"]) == 0
