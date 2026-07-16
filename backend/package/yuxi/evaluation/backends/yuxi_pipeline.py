from __future__ import annotations
from typing import Any
from yuxi.evaluation.backends.base import RetrieverBackend
from yuxi.evaluation.config.query_options import QueryOptions
from yuxi.knowledge import knowledge_base
from yuxi.knowledge.retrieval.dispatcher import RetrievalDispatcher


class YuxiPipelineBackend(RetrieverBackend):
    """
    Backend mô phỏng toàn bộ Pipeline truy xuất thực tế trong production.
    Định tuyến qua `RetrievalDispatcher` (Semantic Router, Multi-hop, Graph RAG, Rerankers).
    Phù hợp cho Stage 4 và Stage 5 để đo lường hiệu năng của toàn bộ hệ thống.
    """

    async def query(self, query_text: str, kb_id: str, options: QueryOptions) -> list[dict[str, Any]]:
        kb_instance = await knowledge_base._get_kb_for_database(kb_id)
        dispatcher = RetrievalDispatcher()

        # Gọi qua bộ điều phối trung tâm để chạy đúng luồng production
        return await dispatcher.dispatch(
            query_text=query_text, kb_instance=kb_instance, kb_id=kb_id, **options.to_dict()
        )
