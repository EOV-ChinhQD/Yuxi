import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from yuxi.storage.postgres.models_knowledge import KnowledgeGraphEntity, KnowledgeChunk
from yuxi.storage.postgres.models_business import FailedJob
from yuxi.knowledge.graphs.entity_resolver import EntityResolver
from yuxi.services.run_rag_worker import handle_extract_knowledge
from yuxi.core.queue import RAGWorker

@pytest.mark.asyncio
async def test_entity_resolver_aliases():
    resolver = EntityResolver()

    # Mock DB entities
    db_ent = KnowledgeGraphEntity(
        id=101,
        entity_id="ent_gpt4",
        kb_id="kb_123",
        name="GPT-4",
        normalized_name="gpt 4",
        canonical_name="GPT-4",
        aliases=["GPT-4", "GPT4"]
    )

    mock_execute = MagicMock()
    # Mock database returns existing entity
    mock_execute.return_value.scalars.return_value.all.return_value = [db_ent]

    raw_entities = [
        {"text": "GPT 4", "label": "Model", "entity_id": "ent_gpt4_alias"},
        {"text": "GPT-4", "label": "Model", "entity_id": "ent_gpt4_exact"},
        {"text": "New Entity", "label": "Concept", "entity_id": "ent_new"}
    ]

    with patch("yuxi.storage.postgres.manager.PostgresManager.get_async_session_context") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_execute.return_value)
        mock_session_ctx.return_value.__aenter__.return_value = mock_session

        resolved = await resolver.resolve_entities("kb_123", raw_entities)

    assert len(resolved) == 3
    # Check alias resolution
    assert resolved[0]["canonical_name"] == "GPT-4"
    assert "GPT 4" in resolved[0]["aliases"]
    assert "GPT-4" in resolved[0]["aliases"]

    # Check new entity
    assert resolved[2]["canonical_name"] == "New Entity"
    assert resolved[2]["aliases"] == ["New Entity"]

@pytest.mark.asyncio
async def test_handle_extract_knowledge():
    # Mock dependencies
    mock_kb = MagicMock()
    mock_kb.databases_meta = {"kb_123": {"llm_model_spec": "gemini", "embedding_model_spec": "embedding"}}
    mock_kb_instance = AsyncMock(return_value=mock_kb)
    
    mock_chunk = KnowledgeChunk(
        chunk_id="chunk_1",
        file_id="file_1",
        heading_path=["H1"],
        chunk_index=0
    )
    mock_get_chunk = AsyncMock(return_value=mock_chunk)
    
    # Mock LLM extractor output
    mock_extract = AsyncMock(return_value={
        "event": {
            "title": "My Event",
            "summary": "Short summary",
            "content": "Full content",
            "category": "tech",
            "keywords": ["ai"]
        },
        "entities": [
            {"name": "GPT-4", "type": "model", "description": "AI model"}
        ]
    })
    
    mock_upsert_graph = AsyncMock()
    mock_upsert_events = AsyncMock()
    mock_insert_vector = AsyncMock()
    mock_mark_indexed = AsyncMock()
    embedding_fn = AsyncMock(return_value=[[0.3, 0.4]])

    mock_execute = MagicMock()
    mock_execute.scalars.return_value.all.return_value = []
    
    mock_session_ctx = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_execute)
    mock_session_ctx.__aenter__.return_value = mock_session

    with patch("yuxi.knowledge.knowledge_base._get_kb_for_database", mock_kb_instance), \
         patch("yuxi.repositories.knowledge_chunk_repository.KnowledgeChunkRepository.get_by_chunk_id", mock_get_chunk), \
         patch("yuxi.knowledge.graphs.extractors.event.LLMEventExtractor.extract", mock_extract), \
         patch("yuxi.repositories.knowledge_graph_repository.KnowledgeGraphRepository.upsert_chunk_graph", mock_upsert_graph), \
         patch("yuxi.repositories.knowledge_graph_repository.KnowledgeGraphRepository.upsert_chunk_events", mock_upsert_events), \
         patch("yuxi.knowledge.graphs.milvus_graph_vector_store.MilvusGraphVectorStore.insert_missing_graph_records", mock_insert_vector), \
         patch("yuxi.repositories.knowledge_chunk_repository.KnowledgeChunkRepository.mark_graph_indexed", mock_mark_indexed), \
         patch("yuxi.storage.postgres.manager.PostgresManager.get_async_session_context", return_value=mock_session_ctx):
         
         await handle_extract_knowledge({
             "kb_id": "kb_123",
             "file_id": "file_1",
             "chunk_id": "chunk_1",
             "content": "some document chunk content"
         })

    # Assert correct calls
    mock_extract.assert_called_once()
    mock_upsert_graph.assert_called_once()
    mock_upsert_events.assert_called_once()
    mock_insert_vector.assert_called_once()
    mock_mark_indexed.assert_called_once()

    # Check entities argument passed to upsert_chunk_graph
    assert mock_upsert_graph.call_args[1]["entities"][0]["canonical_name"] == "GPT-4"
    assert mock_upsert_events.call_args[1]["events"][0]["title"] == "My Event"

@pytest.mark.asyncio
async def test_rag_worker_dlq():
    # Mock redis stream returns message but handler throws exception
    mock_redis = AsyncMock()
    mock_redis.xgroup_create.return_value = True
    
    call_count = 0
    async def mock_xreadgroup(*args, **kwargs):
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            return [("yuxi:rag:stream", [("msg_abc", {"event_type": b"EXTRACT_KNOWLEDGE", "payload": b'{"kb_id":"1"}'})])]
        else:
            await asyncio.sleep(0.1)
            return []

    mock_redis.xreadgroup = mock_xreadgroup
    
    # Mock get returns try count >= 3 to simulate max retries exceeded
    mock_redis.get.return_value = b"3"
    mock_redis.xack.return_value = 1

    async def mock_get_redis():
        return mock_redis

    worker = RAGWorker(max_retries=3)
    
    # Handlers that always throws exception
    failing_handler = AsyncMock(side_effect=ValueError("LLM extraction failed"))
    worker.register_handler("EXTRACT_KNOWLEDGE", failing_handler)

    mock_session_ctx = MagicMock()
    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # db.add is synchronous
    mock_session_ctx.__aenter__.return_value = mock_session

    with patch("yuxi.core.queue.get_async_redis_client", mock_get_redis), \
         patch("yuxi.storage.postgres.manager.PostgresManager.get_async_session_context", return_value=mock_session_ctx):
         
         task = asyncio.create_task(worker.start())
         await asyncio.sleep(0.3)
         worker.stop()
         task.cancel()
         await asyncio.gather(task, return_exceptions=True)

    # Check that failed job was recorded to DLQ database table
    assert mock_session.add.call_count == 1
    added_job = mock_session.add.call_args[0][0]
    assert isinstance(added_job, FailedJob)
    assert added_job.job_type == "EXTRACT_KNOWLEDGE"
    assert added_job.job_id == "msg_abc"
    assert added_job.error_type == "ValueError"
    assert added_job.error_message == "LLM extraction failed"
