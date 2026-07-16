from __future__ import annotations
import math
from typing import Any
from yuxi.evaluation.backends.base import RetrieverBackend
from yuxi.evaluation.config.query_options import QueryOptions


class MemoryVectorBackend(RetrieverBackend):
    """
    Mock Vector & BM25 database chạy trực tiếp trên bộ nhớ (In-memory).
    Tính toán Cosine Similarity bằng tần suất từ (Bag-of-Words) thuần túy.
    Hỗ trợ mô phỏng đầy đủ Reranking Stage 1 & Stage 2 để phục vụ Integration Test.
    """

    def __init__(self, corpus: list[dict[str, Any]]):
        """
        Khởi tạo backend với tập văn bản thô (Corpus).

        Args:
            corpus: Danh sách các chunk có dạng:
                [
                    {"chunk_id": "chunk_1", "content": "Văn bản mẫu số 1", "file_id": "file_1"},
                    ...
                ]
        """
        self.corpus = corpus

    def _tokenize(self, text: str) -> list[str]:
        # Tách từ đơn giản và chuẩn hóa về viết thường
        import re

        words = re.findall(r"\w+", text.lower())
        return words

    def _compute_cosine_similarity(self, query: str, doc: str) -> float:
        q_tokens = self._tokenize(query)
        d_tokens = self._tokenize(doc)

        if not q_tokens or not d_tokens:
            return 0.0

        # Tính toán tần suất từ (tf)
        q_tf = {}
        for t in q_tokens:
            q_tf[t] = q_tf.get(t, 0) + 1

        d_tf = {}
        for t in d_tokens:
            d_tf[t] = d_tf.get(t, 0) + 1

        # Tích vô hướng (dot product)
        dot_product = 0.0
        for token, count in q_tf.items():
            if token in d_tf:
                dot_product += count * d_tf[token]

        # Độ dài vector
        q_len = math.sqrt(sum(c * c for c in q_tf.values()))
        d_len = math.sqrt(sum(c * c for c in d_tf.values()))

        if q_len == 0.0 or d_len == 0.0:
            return 0.0

        return dot_product / (q_len * d_len)

    async def query(self, query_text: str, kb_id: str, options: QueryOptions) -> list[dict[str, Any]]:
        results = []

        # 1. Tính toán điểm thô (Cosine Similarity)
        for doc in self.corpus:
            similarity = self._compute_cosine_similarity(query_text, doc["content"])
            if similarity < options.similarity_threshold:
                continue

            results.append(
                {
                    "chunk_id": doc["chunk_id"],
                    "content": doc["content"],
                    "file_id": doc.get("file_id", "unknown"),
                    "score": similarity,
                }
            )

        # Sắp xếp theo score giảm dần
        results.sort(key=lambda x: x["score"], reverse=True)

        # Giả định số lượng lấy từ Milvus (recall_top_k) trước khi Rerank
        limit = options.recall_top_k if options.use_reranker else options.final_top_k
        results = results[:limit]

        # 2. Mô phỏng Reranker Stage 1 & Stage 2 nếu được cấu hình
        if options.use_reranker:
            # Stage 1: Prefilter
            if options.enable_stage1_prefilter or options.stage1_reranker_model:
                for chunk in results:
                    # Tạo độ lệch giả lập (Deterministic Perturbation dựa trên ký tự cuối cùng của chunk_id)
                    hash_val = sum(ord(c) for c in chunk["chunk_id"]) % 10
                    # Tinh chỉnh nhẹ điểm số để mô phỏng reranking
                    chunk["stage1_score"] = float(min(1.0, max(0.0, chunk["score"] * 0.9 + (hash_val / 100.0))))

                results.sort(key=lambda x: x.get("stage1_score", 0.0), reverse=True)
                results = results[: options.stage1_top_k]

            # Stage 2: Rerank chính
            if options.reranker_model:
                for chunk in results:
                    # Tạo độ lệch giả lập khác cho Stage 2
                    hash_val = sum(ord(c) for c in chunk["chunk_id"]) % 7
                    chunk["rerank_score"] = float(min(1.0, max(0.0, chunk["score"] * 0.8 + (hash_val / 50.0))))

                results.sort(key=lambda x: x.get("rerank_score", x.get("score", 0.0)), reverse=True)

        # Trả về tối đa final_top_k kết quả
        return results[: options.final_top_k]
