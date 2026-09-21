import asyncio
import logging
from yuxi.storage.postgres.manager import pg_manager
from yuxi.knowledge.manager import KnowledgeBaseManager
from yuxi.storage.postgres.models_knowledge import KnowledgeChunk
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def run_reconciliation() -> None:
    logger.info("Starting Reconciliation Job for Milvus and Postgres")
    if not pg_manager._initialized:
        pg_manager.initialize()

    kb_manager = KnowledgeBaseManager(work_dir="saves")
    await kb_manager.initialize()

    # Iterate through all knowledge bases
    for kb_id in kb_manager.databases_meta.keys():
        logger.info(f"Reconciling KB: {kb_id}")
        kb_instance = await kb_manager._get_kb_for_database(kb_id)
        if not kb_instance or not hasattr(kb_instance, "_get_milvus_collection"):
            continue

        collection = await kb_instance._get_milvus_collection(kb_id)
        if not collection:
            continue

        # 1. Fetch all chunk_ids from PostgreSQL for this KB
        pg_chunk_ids = set()
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(KnowledgeChunk.chunk_id).where(KnowledgeChunk.kb_id == kb_id))
            for row in result.scalars():
                pg_chunk_ids.add(row)

        # 2. Fetch all chunk_ids from Milvus
        def _get_milvus_chunks():
            # Query all chunks for this KB
            # Milvus collection doesn't easily support fetching ALL without limit or iterating
            # Since the collection is per-KB in our architecture, we query all.
            # Workaround: query by file_ids or some criteria
            res = collection.query(expr="chunk_id != ''", output_fields=["chunk_id"])
            return {r["chunk_id"] for r in res}

        try:
            milvus_chunk_ids = await asyncio.to_thread(_get_milvus_chunks)
        except Exception as e:
            logger.error(f"Failed to query Milvus chunks for {kb_id}: {e}")
            continue

        # 3. Find Orphan Chunks in Milvus (In Milvus but not in PG)
        orphan_chunks = milvus_chunk_ids - pg_chunk_ids
        if orphan_chunks:
            logger.warning(f"Found {len(orphan_chunks)} orphan chunks in Milvus for KB {kb_id}")
            import json

            def _delete_orphans():
                expr = f"chunk_id in {json.dumps(list(orphan_chunks))}"
                collection.delete(expr)

            try:
                await asyncio.to_thread(_delete_orphans)
                logger.info(f"Deleted {len(orphan_chunks)} orphan chunks from Milvus")
            except Exception as e:
                logger.error(f"Failed to delete orphan chunks: {e}")

        # 4. Find Missing Chunks in Milvus (In PG but not in Milvus, where file is INDEXED)
        # We need to find the files that are marked as INDEXED but their chunks are missing in Milvus
        missing_chunks = pg_chunk_ids - milvus_chunk_ids
        if missing_chunks:
            logger.warning(f"Found {len(missing_chunks)} chunks in PG missing from Milvus for KB {kb_id}")
            # Mark the parent files of these missing chunks as ERROR_INDEXING or trigger a re-sync
            async with pg_manager.get_async_session_context() as session:
                result = await session.execute(
                    select(KnowledgeChunk.file_id).where(KnowledgeChunk.chunk_id.in_(missing_chunks)).distinct()
                )
                affected_files = result.scalars().all()
                for file_id in affected_files:
                    logger.info(f"Queueing re-sync for file {file_id} due to missing chunks in Milvus")
                    from yuxi.core.queue import QueueClient

                    await QueueClient.publish(
                        "SYNC_MILVUS_CHUNKS", {"kb_id": kb_id, "file_id": file_id, "operator_id": "reconciliation_job"}
                    )

    logger.info("Reconciliation Job Completed")


if __name__ == "__main__":
    asyncio.run(run_reconciliation())
