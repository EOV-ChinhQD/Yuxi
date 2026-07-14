import pytest
from yuxi.storage.postgres.models_knowledge import KnowledgeChunk, KnowledgeGraphEntity, KnowledgeGraphEvent

def test_knowledge_chunk_new_fields():
    chunk = KnowledgeChunk(
        chunk_id="chunk_test_123",
        file_id="file_123",
        kb_id="kb_123",
        chunk_index=0,
        content="test content",
        chunk_version="v1.0",
        status="pending"
    )
    assert chunk.chunk_version == "v1.0"
    assert chunk.status == "pending"

def test_knowledge_graph_entity_new_fields():
    entity = KnowledgeGraphEntity(
        entity_id="entity_123",
        kb_id="kb_123",
        normalized_name="gpt-4",
        label="model",
        name="GPT-4",
        canonical_name="GPT-4",
        aliases=["GPT4", "GPT 4"]
    )
    assert entity.canonical_name == "GPT-4"
    assert entity.aliases == ["GPT4", "GPT 4"]

def test_knowledge_graph_event_new_fields():
    event = KnowledgeGraphEvent(
        event_id="event_123",
        kb_id="kb_123",
        file_id="file_123",
        chunk_id="chunk_123",
        title="Event Title",
        summary="Event Summary",
        content="Event Content",
        event_version="v1.0",
        status="pending",
        confidence=0.95,
        importance="high",
        event_type="process",
        temporal_info={"start_time": "2026-07-14T00:00:00Z"},
        event_embedding=[0.1, 0.2, 0.3]
    )
    assert event.event_version == "v1.0"
    assert event.status == "pending"
    assert event.confidence == 0.95
    assert event.importance == "high"
    assert event.event_type == "process"
    assert event.temporal_info == {"start_time": "2026-07-14T00:00:00Z"}
    assert event.event_embedding == [0.1, 0.2, 0.3]

def test_milvus_pg_record_mapping():
    from yuxi.knowledge.implementations.milvus import MilvusKB
    # Mock databases_meta or instantiate a minimal MilvusKB
    kb = MilvusKB(work_dir="/tmp")
    chunks = [
        {
            "chunk_id": "c1",
            "file_id": "f1",
            "chunk_index": 0,
            "content": "some text",
            "chunk_version": "v1.2",
            "status": "ready",
            "heading_path": ["H1", "H2"],
            "section_type": "text"
        }
    ]
    records = kb._build_chunk_pg_records("kb_123", chunks)
    assert len(records) == 1
    rec = records[0]
    assert rec["chunk_id"] == "c1"
    assert rec["file_id"] == "f1"
    assert rec["kb_id"] == "kb_123"
    assert rec["chunk_version"] == "v1.2"
    assert rec["status"] == "ready"
    assert rec["heading_path"] == ["H1", "H2"]
    assert rec["section_type"] == "text"

@pytest.mark.asyncio
async def test_incremental_indexing_logic():
    from yuxi.knowledge.implementations.milvus import MilvusKB
    from unittest.mock import AsyncMock, MagicMock, patch
    from yuxi.storage.postgres.models_knowledge import KnowledgeChunk

    kb = MilvusKB(work_dir="/tmp")

    # Mock existing chunks in Postgres
    old_chunk = KnowledgeChunk(
        chunk_id="old_c1",
        file_id="f1",
        content="existing text",
        chunk_index=0
    )
    
    mock_list_by_file_id = AsyncMock(return_value=[old_chunk])
    mock_insert_stores = AsyncMock()
    mock_embed_store = AsyncMock()
    
    # Mock Milvus collection
    collection = MagicMock()
    collection.query.return_value = [{"chunk_id": "old_c1", "embedding": [0.1, 0.2]}]

    # Define new chunks input (one matching existing, one new)
    new_chunks = [
        {
            "chunk_id": "new_c1",
            "file_id": "f1",
            "content": "existing text",  # Should reuse old_c1
        },
        {
            "chunk_id": "new_c2",
            "file_id": "f1",
            "content": "different text", # New chunk -> Needs embedding
        }
    ]

    embedding_fn = AsyncMock(return_value=[[0.3, 0.4]])

    with patch("yuxi.repositories.knowledge_chunk_repository.KnowledgeChunkRepository.list_by_file_id", mock_list_by_file_id), \
         patch("yuxi.storage.postgres.manager.PostgresManager.get_async_session_context"), \
         patch.object(kb, "_insert_chunks_to_stores", mock_insert_stores), \
         patch.object(kb, "_embed_and_store_chunks", mock_embed_store):
         
         await kb._incremental_index_file(
             kb_id="kb_123",
             file_id="f1",
             collection=collection,
             new_chunks=new_chunks,
             embedding_function=embedding_fn
         )

    # Reused chunks: should call _insert_chunks_to_stores with reused embedding
    assert mock_insert_stores.call_count == 1
    reused_args = mock_insert_stores.call_args[0]
    assert reused_args[0] == "kb_123"
    assert reused_args[1] == "f1"
    assert reused_args[3][0]["content"] == "existing text"
    assert reused_args[4] == [[0.1, 0.2]]

    # New chunks: should call _embed_and_store_chunks to create new embedding
    assert mock_embed_store.call_count == 1
    new_args = mock_embed_store.call_args[0]
    assert new_args[3][0]["content"] == "different text"


