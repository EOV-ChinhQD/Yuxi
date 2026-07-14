import pytest
from unittest.mock import MagicMock, AsyncMock

from yuxi.knowledge.implementations.milvus import _tokenize_vietnamese, MilvusKB


def test_tokenize_vietnamese():
    # Test that Vietnamese multi-syllable words are segmented with underscores
    original_text = "Tôi là khách hàng sử dụng hệ thống học máy"
    tokenized = _tokenize_vietnamese(original_text)
    
    # "khách hàng" -> "khách_hàng", "hệ thống" -> "hệ_thống"
    assert "khách_hàng" in tokenized
    assert "hệ_thống" in tokenized
    # Ensure it doesn't fail on empty or non-string inputs
    assert _tokenize_vietnamese("") == ""
    assert _tokenize_vietnamese(None) is None


@pytest.mark.asyncio
async def test_insert_chunks_to_stores_separates_bm25_and_raw_content():
    # Mock Milvus KB and Collection
    kb = object.__new__(MilvusKB)
    
    mock_collection = MagicMock()
    # Mock collection schema fields to pretend it supports raw_content
    mock_field_raw = MagicMock()
    mock_field_raw.name = "raw_content"
    mock_collection.schema.fields = [mock_field_raw]
    
    mock_collection.insert = MagicMock()
    
    chunks = [
        {
            "id": "c1",
            "chunk_id": "chunk_1",
            "content": "Tôi là khách hàng",
            "file_id": "f1",
            "chunk_index": 0
        }
    ]
    embeddings = [[0.1] * 768]
    
    # Mock repository
    mock_repo = MagicMock()
    mock_repo.batch_upsert = AsyncMock(return_value=None)
    
    # Patch repository creation inside implementation
    from unittest.mock import patch
    with patch("yuxi.knowledge.implementations.milvus.KnowledgeChunkRepository", return_value=mock_repo):
        await kb._insert_chunks_to_stores("kb1", "f1", mock_collection, chunks, embeddings)
        
    # Verify Milvus insert was called
    assert mock_collection.insert.called
    inserted_entities = mock_collection.insert.call_args[0][0]
    
    # entities list order:
    # 0: ids
    # 1: tokenized content (should have khách_hàng)
    # 2: chunk_id
    # 3: file_id
    # 4: chunk_index
    # 5: embeddings
    # 6: raw_content (should have original khách hàng)
    assert inserted_entities[1][0] == "Tôi là khách_hàng"
    assert inserted_entities[6][0] == "Tôi là khách hàng"
