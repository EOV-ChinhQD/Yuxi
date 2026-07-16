import asyncio
import os
import sys

# Đảm bảo import path đúng
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yuxi.storage.postgres.manager import pg_manager
from yuxi.core.queue import RAGWorker
from yuxi.utils.logging_config import logger


async def handle_extract_knowledge(payload: dict) -> None:
    kb_id = payload["kb_id"]
    file_id = payload["file_id"]
    chunk_id = payload["chunk_id"]
    content = payload["content"]

    logger.info(f"RAG Worker received EXTRACT_KNOWLEDGE job for chunk {chunk_id}")

    from yuxi.knowledge import knowledge_base
    from yuxi.knowledge.graphs.extractors.event import LLMEventExtractor
    from yuxi.knowledge.graphs.entity_resolver import EntityResolver
    from yuxi.repositories.knowledge_graph_repository import KnowledgeGraphRepository
    from yuxi.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
    from yuxi.knowledge.graphs.milvus_graph_vector_store import MilvusGraphVectorStore
    from yuxi.utils import hashstr

    # 1. Khởi tạo kết nối database và lấy cấu hình KB
    kb_instance = await knowledge_base._get_kb_for_database(kb_id)
    db_meta = kb_instance.databases_meta.get(kb_id) or {}
    model_spec = db_meta.get("llm_model_spec") or "gemini-1.5-flash"
    embedding_model_spec = db_meta.get("embedding_model_spec") or "text-embedding-004"

    # 2. Truy vấn metadata của chunk từ database
    chunk_repo = KnowledgeChunkRepository()
    chunk_obj = await chunk_repo.get_by_chunk_id(chunk_id)
    if not chunk_obj:
        raise ValueError(f"Chunk {chunk_id} not found in database")

    chunk_metadata = {
        "title": db_meta.get("name") or "Document",
        "heading": " > ".join(chunk_obj.heading_path) if chunk_obj.heading_path else "",
    }

    # 3. Trích xuất sự kiện và thực thể bằng LLM
    extractor = LLMEventExtractor(options={"model_spec": model_spec})
    extraction_result = await extractor.extract(content, chunk_metadata=chunk_metadata)

    # 4. Chuẩn bị thực thể thô và chạy Entity Resolution (Canonical Naming & Aliases)
    raw_entities = extraction_result.get("entities") or []
    raw_entities_records = []
    from yuxi.knowledge.graphs.graph_utils import compute_entity_id, normalize_entity_name

    for raw_ent in raw_entities:
        label = raw_ent.get("type") or "Entity"
        name = raw_ent.get("name") or ""
        norm_name = normalize_entity_name(name)
        ent_id = compute_entity_id(kb_id, norm_name, label)
        raw_entities_records.append(
            {
                "entity_id": ent_id,
                "text": name,
                "label": label,
                "attributes": [raw_ent.get("description") or ""],
            }
        )

    resolver = EntityResolver()
    resolved_entities = await resolver.resolve_entities(kb_id, raw_entities_records)

    # 5. Dựng bản ghi Sự kiện (Event)
    event_id = hashstr(f"{kb_id}:event:{chunk_id}", length=32)
    raw_event = extraction_result.get("event") or {}

    event_entities = []
    for entity in resolved_entities:
        event_entities.append(
            {
                "entity_id": entity["entity_id"],
                "weight": 1.0,
                "relation_type": "MENTIONS",
            }
        )

    event_record = {
        "event_id": event_id,
        "title": raw_event.get("title") or (content[:50] if content else "Event"),
        "summary": raw_event.get("summary") or "",
        "content": raw_event.get("content") or content,
        "category": raw_event.get("category") or "general",
        "keywords": raw_event.get("keywords") or [],
        "level": 0,
        "rank": chunk_obj.chunk_index,
        "entities": event_entities,
        "event_version": "v1.0",
        "status": "ready",
    }

    # 6. Ghi thông tin Sự kiện & Thực thể vào PostgreSQL
    graph_repo = KnowledgeGraphRepository()
    await graph_repo.upsert_chunk_graph(
        kb_id=kb_id,
        file_id=file_id,
        chunk_id=chunk_id,
        entities=resolved_entities,
        triples=[],
    )
    await graph_repo.upsert_chunk_events(
        kb_id=kb_id,
        file_id=file_id,
        chunk_id=chunk_id,
        events=[event_record],
    )

    # 7. Nhúng vector và lưu trữ vào Milvus Graph Vector Store
    graph_vector_store = MilvusGraphVectorStore()
    await graph_vector_store.insert_missing_graph_records(
        kb_id=kb_id,
        embedding_model_spec=embedding_model_spec,
        entities=resolved_entities,
        triples=[],
        events=[event_record],
    )

    # 8. Đánh dấu chunk đã hoàn tất trích xuất đồ thị
    await chunk_repo.mark_graph_indexed(
        chunk_id,
        ent_ids=[entity["entity_id"] for entity in resolved_entities],
    )
    logger.info(f"Successfully processed and stored Event & Entity resolution for chunk {chunk_id}")


async def start_worker() -> None:
    # Khởi tạo kết nối DB
    pg_manager.initialize()

    worker = RAGWorker()
    worker.register_handler("EXTRACT_KNOWLEDGE", handle_extract_knowledge)

    try:
        await worker.start()
    except asyncio.CancelledError:
        worker.stop()


if __name__ == "__main__":
    asyncio.run(start_worker())
