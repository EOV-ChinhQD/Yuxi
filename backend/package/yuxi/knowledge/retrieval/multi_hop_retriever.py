import re
import json
import asyncio
from typing import Any
import json_repair

from yuxi.utils import logger
from yuxi.models import select_model
from yuxi.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from yuxi.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from yuxi.knowledge.graphs.milvus_graph_vector_store import MilvusGraphVectorStore
from yuxi.models.embed import select_embedding_model

_MULTI_HOP_PATTERNS = re.compile(
    r"\b(so sánh|khác nhau|khác biệt|giống nhau|tương đồng|"
    r"đồng thời|cả hai|cả .+ và|giữa .+ và|"
    r"máy .+ và máy|hệ thống .+ và hệ thống|thiết bị .+ và thiết bị)\b",
    re.IGNORECASE,
)

_SINGLE_HOP_EXCLUDE = re.compile(
    r"\b(một|duy nhất|chỉ|riêng)\b",
    re.IGNORECASE,
)


def _heuristic_is_multi_hop(question: str) -> bool:
    """Kiểm tra nhanh bằng regex trước khi gọi LLM."""
    if _SINGLE_HOP_EXCLUDE.search(question) and not _MULTI_HOP_PATTERNS.search(question):
        return False
    return bool(_MULTI_HOP_PATTERNS.search(question))


async def detect_and_decompose(question: str, llm_model_spec: str) -> tuple[bool, list[str]]:
    """
    Phát hiện multi-hop và phân rã câu hỏi thành sub-queries.
    Returns: (is_multi_hop, sub_queries)
    """
    if not _heuristic_is_multi_hop(question):
        logger.debug(f"[MultiHop] Heuristic: single-hop — '{question[:60]}'")
        return False, []

    logger.info("[MultiHop] Heuristic triggered, calling LLM decomposer...")

    prompt = f"""Phân tích câu hỏi sau và trả về JSON. Không giải thích thêm.

Multi-hop = câu hỏi SO SÁNH hoặc hỏi về ÍT NHẤT 2 thực thể/thiết bị/quy trình khác nhau.
Single-hop = câu hỏi về 1 chủ đề duy nhất.

Câu hỏi: {question}

Trả về JSON:
{{
  "is_multi_hop": true/false,
  "reason": "lý do ngắn",
  "sub_queries": ["câu hỏi con 1 tự lập đầy đủ", "câu hỏi con 2 tự lập đầy đủ"]
}}

Lưu ý: nếu is_multi_hop=false thì sub_queries=[]. Tối đa 3 sub_queries.
"""

    try:
        model = select_model(model_spec=llm_model_spec)
        response = await asyncio.wait_for(model.call(prompt), timeout=15.0)
        raw = response.content.strip()

        # Tìm JSON trong output
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            logger.warning("[MultiHop] LLM did not return valid JSON, fallback to single-hop")
            return False, []

        data = json.loads(match.group())
        is_multi = bool(data.get("is_multi_hop", False))
        sub_queries = [q.strip() for q in data.get("sub_queries", []) if q.strip()]

        logger.info(f"[MultiHop] is_multi_hop={is_multi} | reason={data.get('reason', '')} | sub_queries={sub_queries}")

        if not is_multi or len(sub_queries) < 2:
            return False, []

        return True, sub_queries[:3]  # Tối đa 3 sub-queries

    except TimeoutError:
        logger.warning("[MultiHop] LLM decomposer timeout — fallback to single-hop")
        return False, []
    except Exception as e:
        logger.warning(f"[MultiHop] Decompose error: {e} — fallback to single-hop")
        return False, []


async def multi_hop_retrieve_labeled(sub_queries: list[str], retriever: Any, **kwargs) -> dict[str, Any]:
    """
    Chạy retriever song song cho từng sub-query và gộp kết quả có gắn nhãn nguồn.
    """

    async def _retrieve_one(sub_q: str) -> list[dict[str, Any]]:
        try:
            res = await retriever(sub_q, **kwargs)
            chunks = res.get("results", [])
            # Gắn nhãn nguồn vào đầu content để Agent dễ so sánh
            for c in chunks:
                if "content" in c:
                    c["content"] = f"[Nguồn tin cho câu hỏi con: {sub_q}]\n{c['content']}"
            return chunks
        except Exception as e:
            logger.error(f"[MultiHop] Retrieve failed for '{sub_q}': {e}")
            return []

    tasks = [_retrieve_one(q) for q in sub_queries]
    results = await asyncio.gather(*tasks)

    # Gộp & loại bỏ trùng lặp dựa trên chunk_id hoặc content
    seen_ids = set()
    merged_results = []

    for chunk_list in results:
        for chunk in chunk_list:
            cid = chunk.get("chunk_id") or chunk.get("content", "")[:50]
            if cid not in seen_ids:
                seen_ids.add(cid)
                merged_results.append(chunk)

    logger.info(f"[MultiHop] Merged {len(merged_results)} unique chunks from {len(sub_queries)} sub-queries")

    return {"results": merged_results}


class MultiHopRetriever:
    def __init__(
        self,
        kb_id: str,
        embedding_model_spec: str,
        llm_model_spec: str,
    ):
        self.kb_id = kb_id
        self.embedding_model_spec = embedding_model_spec
        self.llm_model_spec = llm_model_spec
        self.graph_repo = KnowledgeGraphRepository()
        self.chunk_repo = KnowledgeChunkRepository()
        self.vector_store = MilvusGraphVectorStore()

    async def _extract_named_entities(self, query: str) -> list[str]:
        prompt = f"""Bạn là một công cụ trích xuất thực thể chuyên nghiệp. Nhiệm vụ duy nhất của bạn là trích xuất tất cả các thực thể quan trọng (như tên riêng, sản phẩm, hệ thống, tổ chức, vị trí, thuật ngữ chuyên ngành) từ câu hỏi bên dưới.
Trả về kết quả dưới dạng JSON array chứa danh sách các chuỗi thực thể. KHÔNG giải thích.

Câu hỏi: {query}
Kết quả dạng JSON array:"""
        try:
            model = select_model(model_spec=self.llm_model_spec)
            response = await model.call(prompt)
            parsed = json_repair.loads(response.content.strip())
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception as e:
            logger.warning(f"[MultiHop] Failed to extract entities via LLM: {e}")
        return []

    async def _rerank_events_llm(self, query: str, candidates: list[dict[str, Any]], top_k: int) -> list[str]:
        if not candidates:
            return []
        prompt = f"""Hệ thống đang tìm kiếm các sự kiện hữu ích nhất để trả lời câu hỏi của người dùng.
Hãy chọn tối đa {top_k} ID sự kiện (event_id) hữu ích nhất để trả lời câu hỏi.
Trả về kết quả dạng JSON array duy nhất chứa danh sách các ID sự kiện được chọn. KHÔNG giải thích.

Câu hỏi: {query}

Danh sách sự kiện ứng viên:
{json.dumps([{"id": c["id"], "title": c["title"], "content": c["content"][:1000]} for c in candidates], ensure_ascii=False)}

Kết quả dạng JSON array chứa event_id:"""
        try:
            model = select_model(model_spec=self.llm_model_spec)
            response = await model.call(prompt)
            parsed = json_repair.loads(response.content.strip())
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception as e:
            logger.error(f"[MultiHop] Failed to rerank events via LLM: {e}")
        return [c["id"] for c in candidates[:top_k]]

    async def retrieve(
        self,
        query: str,
        *,
        search_mode: str = "normal",  # normal hoặc fast
        max_hops: int = 2,
        entity_top_k: int = 10,
        multi_top_k: int = 5,
        max_events: int = 15,
        rerank_top_k: int = 5,
    ) -> list[dict[str, Any]]:
        # 1. Thu hồi các thực thể (Entities)
        recalled_entity_ids = []
        if search_mode == "fast":
            entities = await self.graph_repo.search_entities_by_text(self.kb_id, query, limit=entity_top_k)
            recalled_entity_ids = [e["id"] for e in entities]
        else:
            query_entities = await self._extract_named_entities(query)
            logger.info(f"[MultiHop] Extracted entities: {query_entities}")
            if query_entities:
                exact_entities = await self.graph_repo.search_entities_by_name(self.kb_id, query_entities)
                recalled_entity_ids = [e["id"] for e in exact_entities]

                embed_model = select_embedding_model(self.embedding_model_spec)
                for ent_name in query_entities:
                    vector_entities = await self.vector_store.search_entities(
                        kb_id=self.kb_id,
                        query_text=ent_name,
                        embedding_model_spec=self.embedding_model_spec,
                        top_k=entity_top_k,
                    )
                    for ve in vector_entities:
                        if ve["id"] not in recalled_entity_ids:
                            recalled_entity_ids.append(ve["id"])

        # 2. Tìm kiếm các Seed Events (sự kiện hạt giống)
        entity_event_ids = []
        if recalled_entity_ids:
            entity_event_ids = await self.graph_repo.get_event_ids_by_entity_ids(self.kb_id, recalled_entity_ids)

        vector_events = await self.vector_store.search_events(
            kb_id=self.kb_id, query_text=query, embedding_model_spec=self.embedding_model_spec, top_k=multi_top_k
        )
        vector_event_ids = [ve["id"] for ve in vector_events]

        seed_event_ids = list(set(entity_event_ids + vector_event_ids))
        if not seed_event_ids:
            logger.info("[MultiHop] No seed events found, returning empty.")
            return []

        # 3. Mở rộng đa bước (Expand Hops)
        tracked_event_ids = set(seed_event_ids)
        tracked_entity_ids = set(recalled_entity_ids)

        current_events = await self.graph_repo.get_events_with_entity_ids(seed_event_ids)
        expanded_event_ids = list(seed_event_ids)

        for hop in range(max_hops):
            new_entity_ids = []
            for ev_id, ev_data in current_events.items():
                for ent_id in ev_data.get("entityIds", []):
                    if ent_id not in tracked_entity_ids:
                        new_entity_ids.append(ent_id)
                        tracked_entity_ids.add(ent_id)

            if not new_entity_ids:
                break

            new_event_ids = await self.graph_repo.get_event_ids_by_entity_ids(
                self.kb_id, new_entity_ids, exclude_event_ids=list(tracked_event_ids)
            )
            if not new_event_ids:
                break

            for ev_id in new_event_ids:
                tracked_event_ids.add(ev_id)
                expanded_event_ids.append(ev_id)

            current_events = await self.graph_repo.get_events_with_entity_ids(new_event_ids)

        # 4. Sắp xếp sơ bộ (Coarse Rank) bằng Vector similarity
        candidate_events = await self.graph_repo.get_events_by_ids(expanded_event_ids)
        if not candidate_events:
            return []

        milvus_matches = await self.vector_store.search_events(
            kb_id=self.kb_id, query_text=query, embedding_model_spec=self.embedding_model_spec, top_k=max_events
        )
        match_scores = {m["id"]: m["score"] for m in milvus_matches}

        coarse_ranked = []
        for ev in candidate_events:
            score = match_scores.get(ev["event_id"], 0.1)
            coarse_ranked.append(
                {
                    "id": ev["event_id"],
                    "title": ev["title"],
                    "content": ev["content"],
                    "summary": ev["summary"],
                    "score": score,
                }
            )

        coarse_ranked.sort(key=lambda x: x["score"], reverse=True)
        coarse_ranked = coarse_ranked[:max_events]

        # 5. Rerank bằng LLM
        selected_event_ids = await self._rerank_events_llm(query, coarse_ranked, top_k=rerank_top_k)

        # 6. Lấy chunks tương ứng với các Event được chọn
        from yuxi.storage.postgres.manager import pg_manager

        async with pg_manager.get_async_session_context() as session:
            from sqlalchemy import select
            from yuxi.storage.postgres.models_knowledge import KnowledgeGraphEvent, KnowledgeChunk

            stmt = (
                select(KnowledgeChunk, KnowledgeGraphEvent.event_id)
                .join(KnowledgeGraphEvent, KnowledgeGraphEvent.chunk_id == KnowledgeChunk.chunk_id)
                .where(KnowledgeGraphEvent.event_id.in_(selected_event_ids))
            )
            res = await session.execute(stmt)
            rows = res.all()

            results = []
            seen_chunks = set()
            for chunk_row, event_id in rows:
                if chunk_row.chunk_id in seen_chunks:
                    continue
                seen_chunks.add(chunk_row.chunk_id)
                idx = selected_event_ids.index(event_id) if event_id in selected_event_ids else 99
                results.append(
                    {
                        "chunk_id": chunk_row.chunk_id,
                        "content": chunk_row.content,
                        "score": 1.0 - (idx * 0.05),
                        "file_id": chunk_row.file_id,
                    }
                )
            return results
