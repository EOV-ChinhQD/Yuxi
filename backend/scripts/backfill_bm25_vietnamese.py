import asyncio
import sys
import logging
from pymilvus import utility, Collection

from yuxi.knowledge.implementations.milvus import MilvusKB, _tokenize_vietnamese
from yuxi.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill_bm25")

async def backfill_kb(kb_id: str):
    logger.info(f"Starting backfill for KB: {kb_id}")
    kb = MilvusKB()
    
    # 1. Get current Milvus collection
    collection_name = kb._get_collection_name(kb_id)
    if not utility.has_collection(collection_name, using=kb.connection_alias):
        logger.warning(f"Milvus collection {collection_name} does not exist. Skipping.")
        return
        
    old_collection = Collection(collection_name, using=kb.connection_alias)
    
    # Check if it already has raw_content field
    fields = [f.name for f in old_collection.schema.fields]
    if "raw_content" in fields:
        logger.info(f"Collection {collection_name} already has 'raw_content' field. No migration needed.")
        return

    logger.info(f"Loading existing entities from old Milvus collection: {collection_name}")
    old_collection.load()
    
    # Query all records from Milvus. Limit to a large number (e.g. 16384)
    # Milvus requires an expression for query, we use "id != ''" since id is VARCHAR
    iterator = old_collection.query(
        expr="id != ''",
        output_fields=["id", "content", "chunk_id", "file_id", "chunk_index", "embedding"]
    )
    
    if not iterator:
        logger.info("No records found in Milvus collection.")
        return
        
    logger.info(f"Found {len(iterator)} records to migrate.")
    
    # 2. Extract database metadata to recreate
    meta = kb.databases_meta.get(kb_id)
    if not meta:
        logger.error(f"KB metadata not found for {kb_id}")
        return
        
    embedding_info = meta.get("embedding_model_spec")
    
    # 3. Drop the old collection
    logger.info(f"Dropping old Milvus collection: {collection_name}")
    old_collection.release()
    utility.drop_collection(collection_name, using=kb.connection_alias)
    
    # 4. Create new collection with raw_content schema
    logger.info(f"Creating new Milvus collection with updated schema: {collection_name}")
    new_collection = kb._create_new_collection(collection_name, embedding_info, kb_id)
    
    # 5. Prepare and insert migrated data
    batch_size = 200
    for i in range(0, len(iterator), batch_size):
        batch = iterator[i : i + batch_size]
        
        ids = [item["id"] for item in batch]
        contents = [item["content"] for item in batch]
        tokenized_contents = [_tokenize_vietnamese(c) for c in contents]
        chunk_ids = [item["chunk_id"] for item in batch]
        file_ids = [item["file_id"] for item in batch]
        chunk_indexes = [item["chunk_index"] for item in batch]
        embeddings = [item["embedding"] for item in batch]
        raw_contents = contents # The old collection's content is raw text
        
        entities = [
            ids,
            tokenized_contents,
            chunk_ids,
            file_ids,
            chunk_indexes,
            embeddings,
            raw_contents,
        ]
        
        logger.info(f"Inserting batch {i // batch_size + 1}/{-(-len(iterator) // batch_size)}")
        new_collection.insert(entities)
        
    new_collection.flush()
    # Create indexes again (handled in _create_new_collection but call load to ensure it's queryable)
    new_collection.load()
    logger.info(f"Successfully migrated {len(iterator)} records for KB: {kb_id}")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python backfill_bm25_vietnamese.py <kb_id>")
        sys.exit(1)
    kb_id = sys.argv[1]
    await backfill_kb(kb_id)

if __name__ == "__main__":
    asyncio.run(main())
