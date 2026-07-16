"""
Công cụ tính toán các chỉ số đánh giá RAG
# Bao gồm: Retrieval (Recall, F1, MRR, NDCG), LLM Judge (Accuracy, Groundedness, Coherence) và OCR (CER, WER)
"""

import textwrap
from typing import Any

import json_repair

from yuxi.utils import logger


class RetrievalMetrics:
    """Tính toán các chỉ số đánh giá tìm kiếm (Retrieval)"""

    @staticmethod
    def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Tính Precision@K"""
        if not retrieved_ids[:k]:
            return 0.0
        retrieved_set = set(retrieved_ids[:k])
        relevant_set = set(relevant_ids)
        return len(retrieved_set & relevant_set) / k

    @staticmethod
    def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Tính Recall@K"""
        if not relevant_ids:
            return 0.0
        retrieved_set = set(retrieved_ids[:k])
        relevant_set = set(relevant_ids)
        return len(retrieved_set & relevant_set) / len(relevant_set)

    @staticmethod
    def f1_score_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Tính F1@K"""
        precision = RetrievalMetrics.precision_at_k(retrieved_ids, relevant_ids, k)
        recall = RetrievalMetrics.recall_at_k(retrieved_ids, relevant_ids, k)
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    @staticmethod
    def mrr_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Tính MRR@K (Mean Reciprocal Rank)"""
        relevant_set = set(relevant_ids)
        for i, doc_id in enumerate(retrieved_ids[:k]):
            if doc_id in relevant_set:
                return 1.0 / (i + 1)
        return 0.0

    @staticmethod
    def ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Tính NDCG@K"""
        import math

        relevant_set = set(relevant_ids)
        dcg = 0.0
        for i, doc_id in enumerate(retrieved_ids[:k]):
            if doc_id in relevant_set:
                dcg += 1.0 / math.log2(i + 2)
        idcg = 0.0
        for i in range(min(k, len(relevant_set))):
            idcg += 1.0 / math.log2(i + 2)

        if idcg == 0.0:
            return 0.0
        return dcg / idcg


class AnswerMetrics:
    """Tính toán các chỉ số đánh giá câu trả lời (Answer Metrics)"""

    @staticmethod
    async def judge_correctness(
        query: str, generated_answer: str, gold_answer: str, judge_llm: Any, context: str = ""
    ) -> dict[str, Any]:
        """
        Sử dụng LLM-as-Judge để đánh giá đa chiều câu trả lời (Accuracy, Groundedness, Coherence).
        """
        if not generated_answer:
            return {
                "accuracy": 0.0,
                "groundedness": 0.0,
                "coherence": 0.0,
                "score": 0.0,
                "reasoning": "Không có câu trả lời được sinh ra",
            }
        if not gold_answer:
            return {
                "accuracy": 0.0,
                "groundedness": 0.0,
                "coherence": 0.0,
                "score": 0.0,
                "reasoning": "Không có câu trả lời mẫu",
            }

        prompt = textwrap.dedent(f"""Bạn là một giám khảo công bằng. Hãy đánh giá câu trả lời do AI sinh ra dựa trên thang điểm từ 1-10 cho các tiêu chí sau:

            Câu hỏi: {query}
            
            Ngữ cảnh tham chiếu (Context):
            {context if context else "Không cung cấp ngữ cảnh"}

            Câu trả lời chuẩn (Standard Answer):
            {gold_answer}

            Câu trả lời của AI:
            {generated_answer}

            Hãy đánh giá 3 tiêu chí sau trên thang điểm từ 1-10:
            1. Accuracy: Câu trả lời của AI có chính xác về mặt dữ kiện so với câu trả lời chuẩn không?
            2. Groundedness: Câu trả lời của AI có dựa hoàn toàn vào Ngữ cảnh tham chiếu không? (Bị trừ điểm nếu bịa đặt thêm thông tin)
            3. Coherence: Câu trả lời có mạch lạc, logic và tự nhiên không?

            Chỉ trả về JSON theo định dạng sau (không bao gồm Markdown hay bất kỳ văn bản nào khác):
            {{
                "accuracy": <1-10>,
                "groundedness": <1-10>,
                "coherence": <1-10>,
                "reasoning": "<Giải thích ngắn gọn lý do đánh giá>"
            }}
            """)
        try:
            response = await judge_llm.call(prompt, stream=False)
            content = response.content.strip()

            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json_repair.loads(content)

            accuracy = float(result.get("accuracy", 0.0)) / 10.0 if result.get("accuracy") else 0.0
            groundedness = float(result.get("groundedness", 0.0)) / 10.0 if result.get("groundedness") else 0.0
            coherence = float(result.get("coherence", 0.0)) / 10.0 if result.get("coherence") else 0.0

            return {
                "accuracy": accuracy,
                "groundedness": groundedness,
                "coherence": coherence,
                "score": accuracy,
                "reasoning": result.get("reasoning", ""),
            }
        except Exception as e:
            logger.error(f"LLM đánh giá thất bại: {e}")
            return {
                "accuracy": 0.0,
                "groundedness": 0.0,
                "coherence": 0.0,
                "score": 0.0,
                "reasoning": f"Lỗi trong quá trình đánh giá: {str(e)}",
            }


class EvaluationMetricsCalculator:
    """Bộ tính toán tổng hợp các chỉ số đánh giá"""

    @staticmethod
    def calculate_retrieval_metrics(
        retrieved_chunks: list[dict[str, Any]], gold_chunk_ids: list[str], k_values: list[int] = [1, 3, 5, 10]
    ) -> dict[str, float]:
        """Tính toán các chỉ số tìm kiếm (Recall, F1, MRR, NDCG)"""
        if not retrieved_chunks or not gold_chunk_ids:
            return {}

        retrieved_ids = []
        for chunk in retrieved_chunks:
            chunk_id = chunk.get("chunk_id") or chunk.get("metadata", {}).get("chunk_id")
            retrieved_ids.append(str(chunk_id) if chunk_id else "")

        metrics = {}
        for k in k_values:
            metrics[f"recall@{k}"] = RetrievalMetrics.recall_at_k(retrieved_ids, gold_chunk_ids, k)
            metrics[f"f1@{k}"] = RetrievalMetrics.f1_score_at_k(retrieved_ids, gold_chunk_ids, k)
            metrics[f"mrr@{k}"] = RetrievalMetrics.mrr_at_k(retrieved_ids, gold_chunk_ids, k)
            metrics[f"ndcg@{k}"] = RetrievalMetrics.ndcg_at_k(retrieved_ids, gold_chunk_ids, k)

        return metrics

    @staticmethod
    async def calculate_answer_metrics(
        query: str, generated_answer: str, gold_answer: str, judge_llm: Any = None, context: str = ""
    ) -> dict[str, Any]:
        """Tính toán các chỉ số câu trả lời (LLM-as-Judge)"""
        if not judge_llm:
            return {}

        return await AnswerMetrics.judge_correctness(query, generated_answer, gold_answer, judge_llm, context)

    @staticmethod
    def calculate_overall_score(
        retrieval_metrics_list: list[dict[str, float]], answer_metrics_list: list[dict[str, Any]]
    ) -> float | None:
        """Điểm tổng hợp: Dùng Accuracy nếu có, nếu không thì dùng NDCG@10 hoặc Recall@10."""
        if answer_metrics_list:
            scores = [m.get("accuracy", m.get("score", 0.0)) for m in answer_metrics_list]
            return sum(scores) / len(scores) if scores else None

        ndcgs = [m["ndcg@10"] for m in retrieval_metrics_list if m and "ndcg@10" in m]
        if ndcgs:
            return sum(ndcgs) / len(ndcgs)

        recalls = [m["recall@10"] for m in retrieval_metrics_list if m and "recall@10" in m]
        return sum(recalls) / len(recalls) if recalls else None


class OCRMetrics:
    """Tính toán các chỉ số lỗi cho OCR"""

    @staticmethod
    def calculate_cer_wer(reference_text: str, generated_text: str) -> dict[str, float]:
        """Tính toán CER (Character Error Rate) và WER (Word Error Rate) bằng thuật toán Levenshtein"""

        def levenshtein_distance(s1: list, s2: list) -> int:
            if len(s1) < len(s2):
                return levenshtein_distance(s2, s1)
            if len(s2) == 0:
                return len(s1)
            previous_row = range(len(s2) + 1)
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row
            return previous_row[-1]

        # Calculate CER
        cer_distance = levenshtein_distance(list(reference_text), list(generated_text))
        cer = cer_distance / max(len(reference_text), 1)

        # Calculate WER
        ref_words = reference_text.split()
        gen_words = generated_text.split()
        wer_distance = levenshtein_distance(ref_words, gen_words)
        wer = wer_distance / max(len(ref_words), 1)

        return {"cer": cer, "wer": wer}
