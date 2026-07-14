import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from yuxi.utils.logging_config import logger
from yuxi.knowledge.retrieval.router import RouteType, SemanticRouter

class BaseRetrievalStrategy(ABC):
    @abstractmethod
    async def retrieve(self, query: str, kb_instance: Any, kb_id: str, **kwargs) -> List[Dict[str, Any]]:
        pass

class FactStrategy(BaseRetrievalStrategy):
    """Chiến lược Fact RAG: Tìm kiếm Vector kết hợp BM25 Keyword Search."""
    async def retrieve(self, query: str, kb_instance: Any, kb_id: str, **kwargs) -> List[Dict[str, Any]]:
        logger.info(f"[FactStrategy] Executing factual search for query: '{query[:60]}'")
        factual_kwargs = {**kwargs, "use_graph_retrieval": False}
        return await kb_instance._query_factual(query, kb_id, **factual_kwargs)

class SummaryStrategy(BaseRetrievalStrategy):
    """Chiến lược Summary RAG: Truy xuất sự kiện PostgreSQL + Vector Search."""
    async def retrieve(self, query: str, kb_instance: Any, kb_id: str, **kwargs) -> List[Dict[str, Any]]:
        logger.info(f"[SummaryStrategy] Executing summarization retrieval for query: '{query[:60]}'")
        from yuxi.storage.postgres.manager import pg_manager
        from sqlalchemy import select
        from yuxi.storage.postgres.models_knowledge import KnowledgeGraphEvent, KnowledgeChunk

        # 1. Truy vấn các chunks liên kết với các events có độ quan trọng/tin cậy cao
        event_chunks = []
        try:
            async with pg_manager.get_async_session_context() as session:
                stmt = (
                    select(KnowledgeChunk)
                    .join(KnowledgeGraphEvent, KnowledgeGraphEvent.chunk_id == KnowledgeChunk.chunk_id)
                    .where(KnowledgeGraphEvent.kb_id == kb_id)
                    .order_by(KnowledgeGraphEvent.importance.desc(), KnowledgeGraphEvent.confidence.desc())
                    .limit(20)
                )
                res = await session.execute(stmt)
                event_chunks = res.scalars().all()
        except Exception as e:
            logger.warning(f"[SummaryStrategy] Failed to query events from PostgreSQL: {e}")

        # 2. Tìm kiếm vector thông thường
        factual_kwargs = {**kwargs, "use_graph_retrieval": False}
        vector_chunks = await kb_instance._query_factual(query, kb_id, **factual_kwargs)

        # 3. Gộp và loại bỏ trùng lặp
        seen_ids = set()
        merged = []

        # Thêm chunk từ SQL events trước
        for record in event_chunks:
            if record.chunk_id not in seen_ids:
                seen_ids.add(record.chunk_id)
                merged.append(kb_instance._build_chunk_from_record(record, 0.9, score_field="score"))

        # Thêm chunk từ Vector search
        for chunk in vector_chunks:
            if chunk["chunk_id"] not in seen_ids:
                seen_ids.add(chunk["chunk_id"])
                merged.append(chunk)

        logger.info(f"[SummaryStrategy] Retrieved {len(merged)} chunks (SQL Events: {len(event_chunks)}, Vector: {len(vector_chunks)})")
        return merged

class CompareStrategy(BaseRetrievalStrategy):
    """Chiến lược Compare RAG: Phân rã câu hỏi song song và gắn nhãn nguồn tin."""
    async def retrieve(self, query: str, kb_instance: Any, kb_id: str, **kwargs) -> List[Dict[str, Any]]:
        logger.info(f"[CompareStrategy] Executing parallel compare retrieval for query: '{query[:60]}'")
        from yuxi.knowledge.retrieval.multi_hop_retriever import detect_and_decompose

        llm_model_spec = kb_instance.databases_meta[kb_id].get("llm_model_spec", "gpt-4o-mini")
        is_multi_hop, sub_queries = await detect_and_decompose(query, llm_model_spec)

        if not is_multi_hop or len(sub_queries) < 2:
            logger.info("[CompareStrategy] Decomposer failed or returned single query. Fallback to FactStrategy.")
            factual_kwargs = {**kwargs, "use_graph_retrieval": False}
            return await kb_instance._query_factual(query, kb_id, **factual_kwargs)

        # Truy xuất song song cho từng câu hỏi con
        async def fetch_one(sub_q: str) -> List[Dict[str, Any]]:
            try:
                factual_kwargs = {**kwargs, "use_graph_retrieval": False}
                chunks = await kb_instance._query_factual(sub_q, kb_id, **factual_kwargs)
                # Gắn nhãn nguồn vào content để Agent dễ đối chiếu
                for c in chunks:
                    prefix = f"[Nguồn tin cho câu hỏi con: {sub_q}]\n"
                    if "content" in c:
                        c["content"] = prefix + c["content"]
                    if "raw_content" in c:
                        c["raw_content"] = prefix + c["raw_content"]
                return chunks
            except Exception as e:
                logger.error(f"[CompareStrategy] Parallel fetch failed for sub-query '{sub_q}': {e}")
                return []

        logger.info(f"[CompareStrategy] Running parallel search for sub-queries: {sub_queries}")
        tasks = [fetch_one(sq) for sq in sub_queries]
        results = await asyncio.gather(*tasks)

        # Gộp kết quả
        seen_ids = set()
        merged = []
        for chunk_list in results:
            for chunk in chunk_list:
                cid = chunk["chunk_id"]
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    merged.append(chunk)

        logger.info(f"[CompareStrategy] Merged {len(merged)} chunks from parallel comparison")
        return merged

class MultiHopStrategy(BaseRetrievalStrategy):
    """Chiến lược Multi-hop RAG: Entity Recall + Quan hệ SQL + Rerank."""
    async def retrieve(self, query: str, kb_instance: Any, kb_id: str, **kwargs) -> List[Dict[str, Any]]:
        logger.info(f"[MultiHopStrategy] Executing multi-hop relation retrieval for query: '{query[:60]}'")
        from yuxi.knowledge.retrieval.multi_hop_retriever import MultiHopRetriever

        llm_model_spec = kb_instance.databases_meta[kb_id].get("llm_model_spec", "gpt-4o-mini")
        embedding_model_spec = kb_instance.databases_meta[kb_id].get("embedding_model_spec")

        retriever = MultiHopRetriever(
            kb_id=kb_id,
            embedding_model_spec=embedding_model_spec,
            llm_model_spec=llm_model_spec
        )

        results = await retriever.retrieve(
            query,
            search_mode="normal",
            max_hops=2,
            rerank_top_k=int(kwargs.get("final_top_k", 10))
        )
        return results

class RetrievalDispatcher:
    """Bộ điều phối trung tâm Strategy Pattern định tuyến các chiến lược Retrieval."""
    
    def __init__(self):
        self._strategies = {
            "fact": FactStrategy(),
            "summary": SummaryStrategy(),
            "compare": CompareStrategy(),
            "multihop": MultiHopStrategy()
        }

    async def dispatch(self, query_text: str, kb_instance: Any, kb_id: str, **kwargs) -> List[Dict[str, Any]]:
        llm_model_spec = kb_instance.databases_meta.get(kb_id, {}).get("llm_model_spec", "gpt-4o-mini")
        
        # Tự động fallback sang mô hình khả dụng nếu gpt-4o-mini không có sẵn
        from yuxi.models.providers.cache import model_cache
        if not model_cache.get_model_info(llm_model_spec):
            available = model_cache.get_all_specs("chat")
            if available:
                llm_model_spec = available[0].spec
        
        # 1. Định tuyến ý định
        route_type, route_details = await SemanticRouter.route(query_text, llm_model_spec=llm_model_spec)
        logger.info(f"[RetrievalDispatcher] Query: '{query_text[:60]}...' routed to: {route_type.value}")

        # 2. Ánh xạ sang chiến lược tìm kiếm
        if route_type in (RouteType.EXACT_MATCH, RouteType.NAIVE_SEARCH):
            strategy = self._strategies["fact"]
        elif route_type == RouteType.SUMMARIZATION:
            strategy = self._strategies["summary"]
        elif route_type == RouteType.MULTI_HOP:
            # Kiểm tra xem có chứa từ khóa so sánh/đối chiếu không
            is_compare = any(kw in query_text.lower() for kw in ["so sánh", "khác nhau", "khác biệt", "giống nhau", "tương đồng"])
            if is_compare:
                strategy = self._strategies["compare"]
            else:
                strategy = self._strategies["multihop"]
        else:
            # Fallback cho các nhãn phi-retrieval
            strategy = self._strategies["fact"]

        # 3. Thực thi chiến lược tìm kiếm
        results = await strategy.retrieve(query_text, kb_instance, kb_id, **kwargs)
        
        # 4. Tự động tiêm (inject) một system chunk chứa thông tin định tuyến (Hữu ích cho hiển thị trên UI)
        info_content = (
            f"🤖 **Bộ định tuyến RAG Yuxi**\n"
            f"* **Ý định**: `{route_type.value}`\n"
            f"* **Chiến lược**: `{strategy.__class__.__name__}`\n"
            f"* **Lý do**: {route_details.get('reasoning', 'Không rõ')}"
        )
        system_chunk = {
            "chunk_id": "system_routing_header",
            "content": info_content,
            "score": 1.0,
            "rerank_score": 1.0,
            "metadata": {
                "source": "Hệ thống RAG Yuxi",
                "file_id": "system"
            }
        }
        
        return [system_chunk] + results
