"""
RAG assessment indicator calculation tool
# Simplified version: Keep only Recall/F1 (retrieval) and LLM Judge (answer accuracy)
"""

import textwrap
from typing import Any

import json_repair

from yuxi.utils import logger


class RetrievalMetrics:
    """Search evaluation index calculation"""

    @staticmethod
    def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Calculate Precision@K"""
        if not retrieved_ids[:k]:
            return 0.0
        retrieved_set = set(retrieved_ids[:k])
        relevant_set = set(relevant_ids)
        return len(retrieved_set & relevant_set) / k

    @staticmethod
    def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Calculate Recall@K"""
        if not relevant_ids:
            return 0.0
        retrieved_set = set(retrieved_ids[:k])
        relevant_set = set(relevant_ids)
        return len(retrieved_set & relevant_set) / len(relevant_set)

    @staticmethod
    def f1_score_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
        """Calculate F1@K"""
        precision = RetrievalMetrics.precision_at_k(retrieved_ids, relevant_ids, k)
        recall = RetrievalMetrics.recall_at_k(retrieved_ids, relevant_ids, k)
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)


class AnswerMetrics:
    """Answer evaluation index calculation"""

    @staticmethod
    async def judge_correctness(query: str, generated_answer: str, gold_answer: str, judge_llm: Any) -> dict[str, Any]:
        """
        Use LLM to determine whether the generated answer is correct
        """
        if not generated_answer:
            return {"score": 0.0, "reasoning": "No answer generated"}
        if not gold_answer:
            return {"score": 0.0, "reasoning": "No reference answer"}

        prompt = textwrap.dedent(f"""You are a fair judge. Please evaluate the accuracy of the AI generated answer relative to the standard answer.

            question:{query}

            Standard answer:
            {gold_answer}

            AI generated answer:
            {generated_answer}

            Please determine whether AIgenerateofAnswer is not factually consistent with the standard Answerone.
            Ignore subtle differences in wording, punctuation or format.
            Focusing only on core facts is not accurate.

            Please return the following JSONFormatof results (do not bag other text, Markdown or comments):
            {{
                "score": 1.0,
                "reasoning": "Briefly explain the reasons for the judgment"
            }}
            score can only be 1.0 or 0.0。
            """)
        try:
            response = await judge_llm.call(prompt, stream=False)
            content = response.content.strip()

            # Try to clean up possible markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json_repair.loads(content)
            return {"score": float(result.get("score", 0.0)), "reasoning": result.get("reasoning", "")}
        except Exception as e:
            logger.error(f"LLM failure to judge: {e}")
            return {"score": 0.0, "reasoning": f"Error in judgment: {str(e)}"}


class EvaluationMetricsCalculator:
    """Comprehensive evaluation index calculator"""

    @staticmethod
    def calculate_retrieval_metrics(
        retrieved_chunks: list[dict[str, Any]], gold_chunk_ids: list[str], k_values: list[int] = [1, 3, 5, 10]
    ) -> dict[str, float]:
        """Calculate search index (Recall, F1)"""
        if not retrieved_chunks or not gold_chunk_ids:
            return {}

        # Extract ID
        retrieved_ids = []
        for chunk in retrieved_chunks:
            chunk_id = chunk.get("chunk_id") or chunk.get("metadata", {}).get("chunk_id")
            retrieved_ids.append(str(chunk_id) if chunk_id else "")

        metrics = {}
        for k in k_values:
            metrics[f"recall@{k}"] = RetrievalMetrics.recall_at_k(retrieved_ids, gold_chunk_ids, k)
            metrics[f"f1@{k}"] = RetrievalMetrics.f1_score_at_k(retrieved_ids, gold_chunk_ids, k)

        return metrics

    @staticmethod
    async def calculate_answer_metrics(
        query: str, generated_answer: str, gold_answer: str, judge_llm: Any = None
    ) -> dict[str, Any]:
        """Calculate answer index (LLM Judge)"""
        if not judge_llm:
            return {}

        return await AnswerMetrics.judge_correctness(query, generated_answer, gold_answer, judge_llm)

    @staticmethod
    def calculate_overall_score(
        retrieval_metrics_list: list[dict[str, float]], answer_metrics_list: list[dict[str, Any]]
    ) -> float | None:
        """Comprehensive score: If there is an answer accuracy rate, use accuracy rate, otherwise use recall rate.@10。"""
        if answer_metrics_list:
            scores = [m.get("score", 0.0) for m in answer_metrics_list]
            return sum(scores) / len(scores) if scores else None

        recalls = [m["recall@10"] for m in retrieval_metrics_list if m and "recall@10" in m]
        return sum(recalls) / len(recalls) if recalls else None
