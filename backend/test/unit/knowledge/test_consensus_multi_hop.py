from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

from yuxi.knowledge.retrieval.multi_hop_retriever import MultiHopRetriever
from yuxi.knowledge.retrieval.consensus_retriever import ConsensusRetriever

@pytest.mark.asyncio
async def test_multi_hop_retriever():
    with patch("yuxi.knowledge.graphs.milvus_graph_vector_store.MilvusGraphVectorStore._init_connection"):
        retriever = MultiHopRetriever("test_kb", "test/embed", "test/llm")
    
    retriever._extract_named_entities = AsyncMock(return_value=["SAG", "Yuxi"])
    retriever._rerank_events_llm = AsyncMock(return_value=["ev1"])
    
    retriever.graph_repo.search_entities_by_name = AsyncMock(return_value=[{"id": "ent1", "name": "SAG"}])
    retriever.vector_store.search_entities = AsyncMock(return_value=[{"id": "ent2", "name": "Yuxi"}])
    retriever.graph_repo.get_event_ids_by_entity_ids = AsyncMock(return_value=["ev1"])
    retriever.vector_store.search_events = AsyncMock(return_value=[{"id": "ev1", "score": 0.9}])
    
    retriever.graph_repo.get_events_with_entity_ids = AsyncMock(return_value={
        "ev1": {"entityIds": ["ent1", "ent2"]}
    })
    retriever.graph_repo.get_events_by_ids = AsyncMock(return_value=[
        {
            "event_id": "ev1",
            "title": "SAG Integration",
            "content": "SAG is integrated into Yuxi.",
            "summary": "Summary",
            "category": "update",
            "keywords": [],
            "level": "info",
            "rank": 1,
        }
    ])
    
    mock_execute = AsyncMock()
    mock_chunk = MagicMock()
    mock_chunk.chunk_id = "chunk1"
    mock_chunk.content = "This chunk is about SAG integration."
    mock_chunk.file_id = "file1"
    mock_execute.return_value.all = MagicMock(return_value=[(mock_chunk, "ev1")])
    
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=MagicMock(execute=mock_execute))
    mock_context.__aexit__ = AsyncMock()
    
    mock_embed = MagicMock()
    mock_embed.encode = AsyncMock(return_value=[0.1] * 1024)
    
    with patch("yuxi.storage.postgres.manager.pg_manager.get_async_session_context", return_value=mock_context), \
         patch("yuxi.knowledge.retrieval.multi_hop_retriever.select_embedding_model", return_value=mock_embed):
        res = await retriever.retrieve("What is SAG?")
    assert len(res) == 1
    assert res[0]["chunk_id"] == "chunk1"
    assert res[0]["content"] == "This chunk is about SAG integration."

@pytest.mark.asyncio
async def test_consensus_retriever_with_multi_hop():
    retriever = ConsensusRetriever("test_kb", "test/embed", "test/llm")
    
    retriever._extract_keywords = AsyncMock(return_value="keywords")
    retriever._get_local_chunk_ids = AsyncMock(return_value={"chunk1": 1.0})
    retriever._get_relation_chunk_ids = AsyncMock(return_value={"chunk1": 0.5})
    
    with patch("yuxi.knowledge.retrieval.multi_hop_retriever.MultiHopRetriever.retrieve", new_callable=AsyncMock) as mock_retrieve, \
         patch("yuxi.knowledge.graphs.milvus_graph_vector_store.MilvusGraphVectorStore._init_connection"):
        mock_retrieve.return_value = [{"chunk_id": "chunk1", "score": 0.9}]
        
        retrieved_chunks = [{"chunk_id": "chunk1", "score": 0.8}]
        res = await retriever.consensus_search("What is SAG?", retrieved_chunks)
        assert len(res) == 1
        assert res[0] == "chunk1"
