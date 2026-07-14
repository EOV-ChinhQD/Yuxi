import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from yuxi.knowledge.implementations.milvus import MilvusKB


class DummyHit:
    def __init__(self, id, distance):
        self.id = id
        self.distance = distance
        self.entity = MagicMock()
        # Mock entity get to return chunk metadata
        self.entity.get.side_effect = lambda field: {
            "chunk_id": f"chunk_{id}",
            "file_id": f"file_{id}",
            "chunk_index": id,
            "raw_content": f"nội dung chunk {id}"
        }.get(field)


@pytest.mark.asyncio
async def test_reranker_stage2_only_no_prefilter(monkeypatch):
    # Setup MilvusKB with mock collection
    kb = object.__new__(MilvusKB)
    kb.databases_meta = {
        "kb-1": {
            "embedding_model_spec": "dummy-embed",
            "metric_type": "COSINE"
        }
    }
    
    mock_collection = MagicMock()
    monkeypatch.setattr(kb, "_get_milvus_collection", AsyncMock(return_value=mock_collection))
    monkeypatch.setattr(kb, "_get_embedding_function", lambda model, sync: MagicMock())
    monkeypatch.setattr(kb, "_hydrate_chunk_sources", AsyncMock())
    
    # Mock search results returning 50 hits
    dummy_hits = [DummyHit(i, 0.5) for i in range(50)]
    
    async def mock_run_query_io(func, *args, **kwargs):
        if args and isinstance(args[0], list) and all(isinstance(x, str) for x in args[0]):
            return [[0.1] * 768]
        return [dummy_hits]
        
    monkeypatch.setattr("yuxi.knowledge.implementations.milvus._run_milvus_query_io", mock_run_query_io)
    
    # Mock Stage 2 Reranker
    mock_reranker = AsyncMock()
    # Return scores for all 50 chunks
    mock_reranker.acompute_score.return_value = [0.8] * 50
    mock_reranker.aclose = AsyncMock()
    
    mock_get_reranker = MagicMock(return_value=mock_reranker)
    monkeypatch.setattr("yuxi.models.rerank.get_reranker", mock_get_reranker)
    
    # Call aquery
    query_params = {
        "use_reranker": True,
        "reranker_model": "provider:heavy-model",
        "final_top_k": 5,
        "recall_top_k": 50,
        "enable_stage1_prefilter": False # Mặc định tắt lọc thô để tránh regression
    }
    
    result = await kb.aquery("câu hỏi", "kb-1", **query_params)
    
    # Assertions
    assert len(result) == 5
    # Reranker 2 should receive all 50 chunks
    called_args = mock_reranker.acompute_score.call_args[0][0]
    assert called_args[0] == "câu hỏi"
    assert len(called_args[1]) == 50 # 50 documents passed to Stage 2
    assert mock_reranker.aclose.called


@pytest.mark.asyncio
async def test_reranker_two_stage_success(monkeypatch):
    # Setup MilvusKB
    kb = object.__new__(MilvusKB)
    kb.databases_meta = {
        "kb-1": {
            "embedding_model_spec": "dummy-embed",
            "metric_type": "COSINE"
        }
    }
    
    mock_collection = MagicMock()
    monkeypatch.setattr(kb, "_get_milvus_collection", AsyncMock(return_value=mock_collection))
    monkeypatch.setattr(kb, "_get_embedding_function", lambda model, sync: MagicMock())
    monkeypatch.setattr(kb, "_hydrate_chunk_sources", AsyncMock())
    
    # Mock search results returning 50 hits
    dummy_hits = [DummyHit(i, 0.5) for i in range(50)]
    
    async def mock_run_query_io(func, *args, **kwargs):
        if args and isinstance(args[0], list) and all(isinstance(x, str) for x in args[0]):
            return [[0.1] * 768]
        return [dummy_hits]
        
    monkeypatch.setattr("yuxi.knowledge.implementations.milvus._run_milvus_query_io", mock_run_query_io)
    
    # Mock Rerankers
    mock_reranker_1 = AsyncMock()
    mock_reranker_1.acompute_score.return_value = [0.1 * i for i in range(50)] # Stage 1 scores
    mock_reranker_1.aclose = AsyncMock()
    
    mock_reranker_2 = AsyncMock()
    mock_reranker_2.acompute_score.return_value = [0.9] * 20 # Stage 2 scores for top 20
    mock_reranker_2.aclose = AsyncMock()
    
    def mock_get_reranker(model_id):
        if model_id == "provider:light-model":
            return mock_reranker_1
        elif model_id == "provider:heavy-model":
            return mock_reranker_2
        raise ValueError("Unknown model")
        
    monkeypatch.setattr("yuxi.models.rerank.get_reranker", mock_get_reranker)
    
    # Call aquery
    query_params = {
        "use_reranker": True,
        "stage1_reranker_model": "provider:light-model",
        "stage1_top_k": 20,
        "reranker_model": "provider:heavy-model",
        "final_top_k": 5,
        "recall_top_k": 50
    }
    
    result = await kb.aquery("câu hỏi", "kb-1", **query_params)
    
    # Assertions
    assert len(result) == 5
    # Reranker 1 should receive 50 chunks
    assert len(mock_reranker_1.acompute_score.call_args[0][0][1]) == 50
    # Reranker 2 should receive only 20 chunks (stage1_top_k)
    assert len(mock_reranker_2.acompute_score.call_args[0][0][1]) == 20


@pytest.mark.asyncio
async def test_reranker_stage1_fails_graceful_fallback(monkeypatch):
    kb = object.__new__(MilvusKB)
    kb.databases_meta = {
        "kb-1": {
            "embedding_model_spec": "dummy-embed",
            "metric_type": "COSINE"
        }
    }
    
    mock_collection = MagicMock()
    monkeypatch.setattr(kb, "_get_milvus_collection", AsyncMock(return_value=mock_collection))
    monkeypatch.setattr(kb, "_get_embedding_function", lambda model, sync: MagicMock())
    monkeypatch.setattr(kb, "_hydrate_chunk_sources", AsyncMock())
    
    dummy_hits = [DummyHit(i, 0.5) for i in range(50)]
    
    async def mock_run_query_io(func, *args, **kwargs):
        if args and isinstance(args[0], list) and all(isinstance(x, str) for x in args[0]):
            return [[0.1] * 768]
        return [dummy_hits]
        
    monkeypatch.setattr("yuxi.knowledge.implementations.milvus._run_milvus_query_io", mock_run_query_io)
    
    # Stage 1 throws error, Stage 2 succeeds
    mock_reranker_2 = AsyncMock()
    mock_reranker_2.acompute_score.return_value = [0.8] * 50
    mock_reranker_2.aclose = AsyncMock()
    
    def mock_get_reranker(model_id):
        if model_id == "provider:light-model":
            raise RuntimeError("Stage 1 service unavailable")
        return mock_reranker_2
        
    monkeypatch.setattr("yuxi.models.rerank.get_reranker", mock_get_reranker)
    
    query_params = {
        "use_reranker": True,
        "stage1_reranker_model": "provider:light-model",
        "stage1_top_k": 20,
        "reranker_model": "provider:heavy-model",
        "final_top_k": 5,
        "recall_top_k": 50
    }
    
    result = await kb.aquery("câu hỏi", "kb-1", **query_params)
    
    assert len(result) == 5
    # Since Stage 1 failed, all 50 chunks must have bypassed directly to Stage 2
    assert len(mock_reranker_2.acompute_score.call_args[0][0][1]) == 50


@pytest.mark.asyncio
async def test_reranker_stage2_fails_graceful_fallback(monkeypatch):
    kb = object.__new__(MilvusKB)
    kb.databases_meta = {
        "kb-1": {
            "embedding_model_spec": "dummy-embed",
            "metric_type": "COSINE"
        }
    }
    
    mock_collection = MagicMock()
    monkeypatch.setattr(kb, "_get_milvus_collection", AsyncMock(return_value=mock_collection))
    monkeypatch.setattr(kb, "_get_embedding_function", lambda model, sync: MagicMock())
    monkeypatch.setattr(kb, "_hydrate_chunk_sources", AsyncMock())
    
    dummy_hits = [DummyHit(i, 0.5) for i in range(50)]
    
    async def mock_run_query_io(func, *args, **kwargs):
        if args and isinstance(args[0], list) and all(isinstance(x, str) for x in args[0]):
            return [[0.1] * 768]
        return [dummy_hits]
        
    monkeypatch.setattr("yuxi.knowledge.implementations.milvus._run_milvus_query_io", mock_run_query_io)
    
    # Stage 1 succeeds, Stage 2 throws error
    mock_reranker_1 = AsyncMock()
    # Return descending scores so we know which are top 20
    mock_reranker_1.acompute_score.return_value = [0.9 - 0.01 * i for i in range(50)]
    mock_reranker_1.aclose = AsyncMock()
    
    def mock_get_reranker(model_id):
        if model_id == "provider:light-model":
            return mock_reranker_1
        raise RuntimeError("Stage 2 service unavailable")
        
    monkeypatch.setattr("yuxi.models.rerank.get_reranker", mock_get_reranker)
    
    query_params = {
        "use_reranker": True,
        "stage1_reranker_model": "provider:light-model",
        "stage1_top_k": 20,
        "reranker_model": "provider:heavy-model",
        "final_top_k": 5,
        "recall_top_k": 50
    }
    
    result = await kb.aquery("câu hỏi", "kb-1", **query_params)
    
    assert len(result) == 5
    # Since Stage 2 failed, we must fall back to Stage 1 top results
    # First chunk should have the highest stage1 score (0.9)
    assert result[0]["stage1_score"] == 0.9


@pytest.mark.asyncio
async def test_reranker_edge_case_small_recall(monkeypatch):
    kb = object.__new__(MilvusKB)
    kb.databases_meta = {
        "kb-1": {
            "embedding_model_spec": "dummy-embed",
            "metric_type": "COSINE"
        }
    }
    
    mock_collection = MagicMock()
    monkeypatch.setattr(kb, "_get_milvus_collection", AsyncMock(return_value=mock_collection))
    monkeypatch.setattr(kb, "_get_embedding_function", lambda model, sync: MagicMock())
    monkeypatch.setattr(kb, "_hydrate_chunk_sources", AsyncMock())
    
    # Only 15 chunks retrieved
    dummy_hits = [DummyHit(i, 0.5) for i in range(15)]
    
    async def mock_run_query_io(func, *args, **kwargs):
        if args and isinstance(args[0], list) and all(isinstance(x, str) for x in args[0]):
            return [[0.1] * 768]
        return [dummy_hits]
        
    monkeypatch.setattr("yuxi.knowledge.implementations.milvus._run_milvus_query_io", mock_run_query_io)
    
    mock_reranker_1 = AsyncMock()
    mock_reranker_1.aclose = AsyncMock()
    
    mock_reranker_2 = AsyncMock()
    mock_reranker_2.acompute_score.return_value = [0.8] * 15
    mock_reranker_2.aclose = AsyncMock()
    
    def mock_get_reranker(model_id):
        if model_id == "provider:light-model":
            return mock_reranker_1
        return mock_reranker_2
        
    monkeypatch.setattr("yuxi.models.rerank.get_reranker", mock_get_reranker)
    
    query_params = {
        "use_reranker": True,
        "stage1_reranker_model": "provider:light-model",
        "stage1_top_k": 20, # 20 > 15 recall
        "reranker_model": "provider:heavy-model",
        "final_top_k": 5,
        "recall_top_k": 15
    }
    
    result = await kb.aquery("câu hỏi", "kb-1", **query_params)
    
    assert len(result) == 5
    # Since 15 < 20, Stage 1 should be bypassed entirely, and Stage 2 receives all 15 chunks
    assert not mock_reranker_1.acompute_score.called
    assert len(mock_reranker_2.acompute_score.call_args[0][0][1]) == 15
