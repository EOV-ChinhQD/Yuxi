import asyncio
from typing import Any
from yuxi.utils.logging_config import logger
from yuxi.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from yuxi.knowledge.graphs.milvus_graph_service import MilvusGraphService
from yuxi.storage.postgres.manager import pg_manager

async def reconcile_neo4j_failed_chunks(kb_id: str, limit: int = 100) -> int:
    """
    Find chunks with neo4j_sync_status='failed', retry writing them to Neo4j.
    Returns the count of successfully synced chunks.
    """
    logger.info(f"[Reconciliation] Starting Neo4j sync reconciliation for KB {kb_id} (limit={limit})")
    
    async with pg_manager.get_async_session_context() as db:
        chunk_repo = KnowledgeChunkRepository(db)
        failed_chunks = await chunk_repo.list_by_neo4j_status(kb_id, "failed", limit=limit)
        
        if not failed_chunks:
            logger.info(f"[Reconciliation] No failed chunks found for KB {kb_id}")
            return 0
            
        logger.info(f"[Reconciliation] Found {len(failed_chunks)} failed chunks to reconcile")
        
        milvus_graph_service = MilvusGraphService()
        reconciled_count = 0
        
        for chunk in failed_chunks:
            if not chunk.extraction_result:
                logger.warning(f"[Reconciliation] Chunk {chunk.chunk_id} has no extraction_result, skipping")
                continue
                
            try:
                extraction_result = chunk.extraction_result
                # Determine if it is event-centric or entity-relation
                is_event = "event" in extraction_result
                
                if is_event:
                    entities, events, neo4j_success = await asyncio.to_thread(
                        milvus_graph_service.write_chunk_events,
                        kb_id,
                        chunk,
                        extraction_result,
                    )
                else:
                    entities, triples, neo4j_success = await asyncio.to_thread(
                        milvus_graph_service.write_chunk_graph,
                        kb_id,
                        chunk,
                        extraction_result,
                    )
                
                if neo4j_success:
                    await chunk_repo.update_neo4j_sync_status(chunk.chunk_id, "synced")
                    reconciled_count += 1
                    logger.info(f"[Reconciliation] Successfully synced chunk {chunk.chunk_id} to Neo4j")
                else:
                    logger.warning(f"[Reconciliation] Sync retry failed for chunk {chunk.chunk_id}")
                    
            except Exception as e:
                logger.error(f"[Reconciliation] Error during reconciliation for chunk {chunk.chunk_id}: {e}")
                
        return reconciled_count
