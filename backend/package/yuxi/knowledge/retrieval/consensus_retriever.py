import asyncio
import time
import hashlib
from typing import List, Dict, Set, Any, Optional
from collections import defaultdict
from yuxi.utils import logger
from yuxi.models import select_model
from yuxi.storage.neo4j import neo4j_read, safe_neo4j_label
from yuxi.knowledge.graphs.milvus_graph_vector_store import MilvusGraphVectorStore
from yuxi.knowledge.graphs.milvus_graph_service import MilvusGraphService

# In-memory keyword cache: {md5(query): (keywords_str, expire_timestamp)}
_keyword_cache: Dict[str, tuple] = {}
_KEYWORD_CACHE_TTL = 3600  # 60 phút

_RELATION_KEYWORDS = {
    "liên quan đến", "ảnh hưởng bởi", "dẫn đến", "kết nối với",
    "related to", "influenced by", "leads to", "connected to"
}

def _get_cached_keywords(query: str) -> Optional[str]:
    key = hashlib.md5(query.encode()).hexdigest()
    if key in _keyword_cache:
        kw, expire = _keyword_cache[key]
        if time.time() < expire:
            return kw
        del _keyword_cache[key]
    return None

def _set_cached_keywords(query: str, keywords: str):
    key = hashlib.md5(query.encode()).hexdigest()
    _keyword_cache[key] = (keywords, time.time() + _KEYWORD_CACHE_TTL)

def _normalize_map(score_map: Dict[str, float]) -> Dict[str, float]:
    if not score_map:
        return {}
    min_val = min(score_map.values())
    max_val = max(score_map.values())
    if max_val == min_val:
        return {k: 1.0 for k in score_map.keys()}
    return {k: (v - min_val) / (max_val - min_val) for k, v in score_map.items()}

class ConsensusRetriever:
    def __init__(
        self, 
        kb_id: str, 
        embedding_model_spec: str, 
        llm_model_spec: str,
        w_naive: float = 0.4,
        w_local: float = 0.25,
        w_relation: float = 0.15,
        w_event: float = 0.2
    ):
        self.kb_id = kb_id
        self.embedding_model_spec = embedding_model_spec
        self.llm_model_spec = llm_model_spec
        self.w_naive = w_naive
        self.w_local = w_local
        self.w_relation = w_relation
        self.w_event = w_event
        self.graph_service = MilvusGraphService()

    def _detect_query_type(self, query: str) -> str:
        query_lower = query.lower()
        if any(kw in query_lower for kw in _RELATION_KEYWORDS):
            return "relational"
        return "factual"

    def _get_weights_for_query(self, query: str, base_weights: dict) -> dict:
        query_type = self._detect_query_type(query)
        if query_type == "relational":
            weights = {
                "w_naive": 0.25,
                "w_relation": 0.35,
                "w_local": 0.25,
                "w_event": 0.15
            }
            logger.info(f"[Consensus] Relational query detected, routing to relational weights: {weights}")
            return weights
        return base_weights

    async def _extract_keywords(self, query: str) -> str:
        cached = _get_cached_keywords(query)
        if cached:
            logger.info(f"[Consensus] Keyword cache HIT: '{cached[:60]}'")
            return cached

        keywords_template = """Bạn là một công cụ trích xuất thực thể. Nhiệm vụ duy nhất của bạn là xuất ra danh sách các danh từ/thực thể/chủ đề cốt lõi từ câu hỏi.
Yêu cầu:
- Chỉ output các từ khóa, mỗi từ khóa cách nhau bằng dấu phẩy.
- KHÔNG giải thích. KHÔNG viết lại câu hỏi hoặc lập luận.
Câu hỏi: '{query}'
Từ khóa:"""

        try:
            t0 = time.perf_counter()
            prompt = keywords_template.format(query=query)
            
            # Sử dụng select_model từ Yuxi để gọi LLM trích xuất keywords
            model = select_model(model_spec=self.llm_model_spec)
            response = await asyncio.wait_for(model.call(prompt), timeout=2.0)
            keyword_str = response.content.strip()
            
            ms = (time.perf_counter() - t0) * 1000
            logger.info(f"[Consensus][TIMING] keyword_extraction={ms:.0f}ms")

            if keyword_str and ":" in keyword_str and "{" not in keyword_str:
                keyword_str = keyword_str.split(":")[-1].strip()

            if keyword_str and len(keyword_str.strip()) > 0:
                logger.info(f"[Consensus] Extracted keywords: {keyword_str[:80]}")
                _set_cached_keywords(query, keyword_str)
                return keyword_str
        except asyncio.TimeoutError:
            logger.warning("[Consensus] Keyword extraction timed out after 2s, using raw query.")
        except Exception as ke:
            logger.warning(f"[Consensus] Keyword extraction failed, using raw query. Error: {ke}")

        return query

    async def _get_local_chunk_ids(
        self,
        keywords: str,
        top_k_entities: int = 10
    ) -> Dict[str, float]:
        try:
            t0 = time.perf_counter()
            vector_store = MilvusGraphVectorStore()
            entities = await vector_store.search_entities(
                kb_id=self.kb_id,
                query_text=keywords,
                embedding_model_spec=self.embedding_model_spec,
                top_k=top_k_entities
            )
            ms = (time.perf_counter() - t0) * 1000
            logger.info(f"[Consensus][TIMING] entity_vector_search={ms:.0f}ms, found={len(entities)}")

            if not entities:
                return {}

            chunk_scores = defaultdict(float)
            total_entities = len(entities)
            label = safe_neo4j_label(self.kb_id)

            entity_ids = [entity["id"] for entity in entities]
            entity_score_map = {entity["id"]: float(entity.get("score") or (total_entities - idx)) for idx, entity in enumerate(entities)}
            
            cypher = f"""
            MATCH (c:Chunk:MilvusKB:`{label}`)-[:MENTIONS]->(e:Entity:MilvusKB:`{label}`)
            WHERE e.entity_id IN $entity_ids
            RETURN e.entity_id AS entity_id, c.chunk_id AS chunk_id
            """
            
            t_neo = time.perf_counter()
            records = await asyncio.to_thread(neo4j_read, self.graph_service.driver, cypher, kb_id=self.kb_id, entity_ids=entity_ids)
            
            for record in records:
                ent_id = record["entity_id"]
                cid = record["chunk_id"]
                if cid:
                    chunk_scores[cid] += entity_score_map.get(ent_id, 1.0)

            logger.info(
                f"[Consensus][TIMING] entity_to_chunk_mapping={(time.perf_counter() - t_neo)*1000:.0f}ms "
                f"(Neo4j mapped chunks: {len(chunk_scores)})"
            )
            return dict(chunk_scores)
        except Exception as e:
            logger.error(f"[Consensus][Local] Error: {e}")
            return {}

    async def _get_relation_chunk_ids(
        self,
        keywords: str,
        top_k: int = 10
    ) -> Dict[str, float]:
        try:
            t0 = time.perf_counter()
            vector_store = MilvusGraphVectorStore()
            relations = await vector_store.search_triples(
                kb_id=self.kb_id,
                query_text=keywords,
                embedding_model_spec=self.embedding_model_spec,
                top_k=top_k
            )
            ms = (time.perf_counter() - t0) * 1000
            logger.info(f"[Consensus][TIMING] relation_vector_search={ms:.0f}ms, found={len(relations)}")

            if not relations:
                return {}

            chunk_scores = defaultdict(float)
            total_relations = len(relations)
            label = safe_neo4j_label(self.kb_id)

            triple_ids = [rel["id"] for rel in relations]
            relation_score_map = {rel["id"]: float(rel.get("score") or (total_relations - idx)) for idx, rel in enumerate(relations)}

            cypher = f"""
            MATCH (source:Entity:MilvusKB:`{label}`)-[r:RELATION]->(target:Entity:MilvusKB:`{label}`)
            WHERE r.triple_id IN $triple_ids
            RETURN r.triple_id AS triple_id, r.chunk_id AS chunk_id
            """

            t_neo = time.perf_counter()
            records = await asyncio.to_thread(neo4j_read, self.graph_service.driver, cypher, kb_id=self.kb_id, triple_ids=triple_ids)

            for record in records:
                triple_id = record["triple_id"]
                cid = record["chunk_id"]
                if cid:
                    chunk_scores[cid] += relation_score_map.get(triple_id, 1.0)

            logger.info(
                f"[Consensus][TIMING] relation_to_chunk_mapping={(time.perf_counter() - t_neo)*1000:.0f}ms "
                f"(Neo4j mapped chunks: {len(chunk_scores)})"
            )
            return dict(chunk_scores)
        except Exception as e:
            logger.error(f"[Consensus][Relation] Error: {e}")
            return {}

    async def consensus_search(
        self,
        query: str,
        retrieved_chunks: list[dict],
        top_k_each_method: int = 10,
        final_k: int = 10
    ) -> List[str]:
        """
        Chạy Consensus Search kết hợp Naive Vector, Local Entity, Relation, và Event Multi-hop.
        """
        from yuxi.services.langfuse_service import langfuse_span
        from yuxi.utils.logging_config import log_context

        trace_id = log_context.get().get("request_id")

        async with langfuse_span(
            trace_id=trace_id,
            span_name="ConsensusRetrieval",
            input_data={"query": query, "top_k_each_method": top_k_each_method, "final_k": final_k},
            metadata={"kb_id": self.kb_id}
        ) as span:
            t_start = time.perf_counter()

            # Bước 0: Trích xuất keywords
            keywords = await self._extract_keywords(query)

            # Bước 1: Tìm kiếm Local, Relation, và Event song song
            from yuxi.knowledge.retrieval.multi_hop_retriever import MultiHopRetriever
            event_retriever = MultiHopRetriever(self.kb_id, self.embedding_model_spec, self.llm_model_spec)

            async def safe_get_local():
                try:
                    return await asyncio.wait_for(
                        self._get_local_chunk_ids(keywords, top_k_entities=top_k_each_method),
                        timeout=3.0
                    )
                except Exception as e:
                    logger.warning(f"[Consensus] Local search failed or timed out: {e}")
                    return {}

            async def safe_get_relation():
                try:
                    return await asyncio.wait_for(
                        self._get_relation_chunk_ids(keywords, top_k=top_k_each_method),
                        timeout=3.0
                    )
                except Exception as e:
                    logger.warning(f"[Consensus] Relation search failed or timed out: {e}")
                    return {}

            async def safe_get_event():
                try:
                    return await asyncio.wait_for(
                        event_retriever.retrieve(query, search_mode="normal", max_hops=2, rerank_top_k=top_k_each_method),
                        timeout=3.0
                    )
                except Exception as e:
                    logger.warning(f"[Consensus] Event search failed or timed out: {e}")
                    return []

            local_map, relation_map, event_chunks = await asyncio.gather(
                safe_get_local(),
                safe_get_relation(),
                safe_get_event()
            )

            naive_map = {chunk["chunk_id"]: chunk["score"] for chunk in retrieved_chunks}
            event_map = {chunk["chunk_id"]: chunk["score"] for chunk in event_chunks}

            logger.info(
                f"[Consensus] Naive={len(naive_map)}, Local={len(local_map)}, Relation={len(relation_map)}, Event={len(event_map)} chunks"
            )

            # Thiết lập trọng số consensus
            base_weights = {
                "w_naive": self.w_naive,
                "w_local": self.w_local,
                "w_relation": self.w_relation,
                "w_event": self.w_event
            }
            weights = self._get_weights_for_query(query, base_weights)
            W_NAIVE = weights["w_naive"]
            W_LOCAL = weights["w_local"]
            W_RELATION = weights["w_relation"]
            W_EVENT = weights["w_event"]

            logger.info(f"[Consensus] Final weights used: Naive={W_NAIVE}, Local={W_LOCAL}, Relation={W_RELATION}, Event={W_EVENT}")

            if span:
                try:
                    span.update(metadata={
                        "naive_chunks": len(naive_map),
                        "local_chunks": len(local_map),
                        "relation_chunks": len(relation_map),
                        "event_chunks": len(event_map),
                        "keywords": keywords,
                        "query_type": self._detect_query_type(query),
                        "weights_used": weights,
                    })
                except Exception:
                    pass

            # Chuẩn hóa score maps
            naive_norm = _normalize_map(naive_map)
            local_norm = _normalize_map(local_map)
            relation_norm = _normalize_map(relation_map)
            event_norm = _normalize_map(event_map)

            all_ids = set(naive_map) | set(local_map) | set(relation_map) | set(event_map)
            chunk_scores: Dict[str, float] = {}
            gold_ids: Set[str] = set()
            silver_ids: Set[str] = set()

            for cid in all_ids:
                score = (
                    naive_norm.get(cid, 0.0) * W_NAIVE
                    + local_norm.get(cid, 0.0) * W_LOCAL
                    + relation_norm.get(cid, 0.0) * W_RELATION
                    + event_norm.get(cid, 0.0) * W_EVENT
                )
                sources_count = sum([
                    cid in naive_map,
                    cid in local_map,
                    cid in relation_map,
                    cid in event_map
                ])
                if sources_count == 4:
                    score += 0.3  # Platinum bonus
                    gold_ids.add(cid)
                elif sources_count >= 2:
                    silver_ids.add(cid)
                chunk_scores[cid] = score

            # Sắp xếp chunk IDs theo score Consensus
            sorted_ids = sorted(all_ids, key=lambda cid: chunk_scores[cid], reverse=True)
            
            logger.info(
                f"[Consensus] Gold={len(gold_ids)}, Silver={len(silver_ids)} | "
                f"Consensus search hoàn thành trong {(time.perf_counter() - t_start)*1000:.0f}ms"
            )
            return sorted_ids[:final_k]
