from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from yuxi.services.graph_reconciliation_service import reconcile_neo4j_failed_chunks

@pytest.mark.asyncio
async def test_reconcile_neo4j_failed_chunks_no_failed():
    mock_repo = MagicMock()
    mock_repo.list_by_neo4j_status = AsyncMock(return_value=[])

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_context)
    mock_context.__aexit__ = AsyncMock()

    with patch("yuxi.storage.postgres.manager.pg_manager.get_async_session_context", return_value=mock_context), \
         patch("yuxi.services.graph_reconciliation_service.KnowledgeChunkRepository", return_value=mock_repo):
        res = await reconcile_neo4j_failed_chunks("test_kb")
    
    assert res == 0
    mock_repo.list_by_neo4j_status.assert_called_once_with("test_kb", "failed", limit=100)

@pytest.mark.asyncio
async def test_reconcile_neo4j_failed_chunks_sync_success():
    mock_chunk = MagicMock()
    mock_chunk.chunk_id = "chunk_1"
    mock_chunk.extraction_result = {"entities": []}

    mock_repo = MagicMock()
    mock_repo.list_by_neo4j_status = AsyncMock(return_value=[mock_chunk])
    mock_repo.update_neo4j_sync_status = AsyncMock()

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_context)
    mock_context.__aexit__ = AsyncMock()

    mock_graph_service = MagicMock()
    mock_graph_service.write_chunk_graph = MagicMock(return_value=([], [], True)) # Success!

    with patch("yuxi.storage.postgres.manager.pg_manager.get_async_session_context", return_value=mock_context), \
         patch("yuxi.services.graph_reconciliation_service.KnowledgeChunkRepository", return_value=mock_repo), \
         patch("yuxi.services.graph_reconciliation_service.MilvusGraphService", return_value=mock_graph_service):
        res = await reconcile_neo4j_failed_chunks("test_kb")
    
    assert res == 1
    mock_repo.update_neo4j_sync_status.assert_called_once_with("chunk_1", "synced")

@pytest.mark.asyncio
async def test_reconcile_neo4j_failed_chunks_sync_failed():
    mock_chunk = MagicMock()
    mock_chunk.chunk_id = "chunk_2"
    mock_chunk.extraction_result = {"entities": []}

    mock_repo = MagicMock()
    mock_repo.list_by_neo4j_status = AsyncMock(return_value=[mock_chunk])
    mock_repo.update_neo4j_sync_status = AsyncMock()

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_context)
    mock_context.__aexit__ = AsyncMock()

    mock_graph_service = MagicMock()
    mock_graph_service.write_chunk_graph = MagicMock(return_value=([], [], False)) # Failed!

    with patch("yuxi.storage.postgres.manager.pg_manager.get_async_session_context", return_value=mock_context), \
         patch("yuxi.services.graph_reconciliation_service.KnowledgeChunkRepository", return_value=mock_repo), \
         patch("yuxi.services.graph_reconciliation_service.MilvusGraphService", return_value=mock_graph_service):
        res = await reconcile_neo4j_failed_chunks("test_kb")
    
    assert res == 0
    mock_repo.update_neo4j_sync_status.assert_not_called()
