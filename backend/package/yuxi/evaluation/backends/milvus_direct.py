from __future__ import annotations
from typing import Any
from yuxi.evaluation.backends.base import RetrieverBackend
from yuxi.evaluation.config.query_options import QueryOptions
from yuxi.knowledge import knowledge_base
from yuxi.knowledge.implementations.milvus import MilvusKB


class MilvusDirectBackend(RetrieverBackend):
    """
    Backend gọi trực tiếp đến lớp MilvusKB (`_query_factual`).
    Bỏ qua toàn bộ tầng định tuyến (Semantic Router), Multi-hop, Graph RAG và Agent.
    Phù hợp cho Stage 3 để đo lường thuần túy chất lượng Embedding/Vector.
    """

    async def query(self, query_text: str, kb_id: str, options: QueryOptions) -> list[dict[str, Any]]:
        kb_instance = await knowledge_base._get_kb_for_database(kb_id)
        if not isinstance(kb_instance, MilvusKB):
            raise ValueError(f"Cơ sở dữ liệu {kb_id} không thuộc loại MilvusKB (kiểu hiện tại: {type(kb_instance)})")

        # Gọi trực tiếp truy xuất tầng factual thô (Dense/Sparse/Hybrid) của Milvus
        return await kb_instance._query_factual(
            query_text=query_text, kb_id=kb_id, agent_call=False, **options.to_dict()
        )
