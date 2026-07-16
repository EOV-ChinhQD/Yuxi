from __future__ import annotations
import asyncio
import time
from typing import Any
from pydantic import BaseModel, Field
from yuxi.evaluation.backends.base import RetrieverBackend
from yuxi.evaluation.config.query_options import QueryOptions
from yuxi.evaluation.datasets.loader import EvaluationDataset
from yuxi.evaluation.stages.base import ReportSchema
from yuxi.utils import logger


class QueryResult(BaseModel):
    """Kết quả chi tiết của một câu truy vấn trong lượt chạy đánh giá."""

    query: str
    gold_chunk_ids: list[str]
    gold_intent: str | None = None
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    latency: float = 0.0
    success: bool = True
    error_message: str | None = None


class EvaluationRunner:
    """
    Bộ chạy thực nghiệm (Experiment Runner) trung tâm.
    Chịu trách nhiệm thực thi vòng lặp chạy dataset, quản lý timeout, xử lý lỗi (partial failures),
    đo lường hiệu năng và độ tin cậy.
    """

    def __init__(self, backend: RetrieverBackend):
        self.backend = backend
        self.results: list[QueryResult] = []
        self.performance_stats: dict[str, Any] = {}
        self.reliability_stats: dict[str, Any] = {}

    async def run_dataset(
        self,
        dataset: EvaluationDataset,
        kb_id: str,
        options: QueryOptions,
        timeout: float = 15.0,
    ) -> list[QueryResult]:
        """
        Thực thi truy vấn cho toàn bộ dataset với cơ chế xử lý lỗi và timeout.
        """
        self.results = []
        total_queries = len(dataset.items)
        success_count = 0
        total_latency = 0.0

        logger.info(f"Bắt đầu chạy thực nghiệm trên dataset '{dataset.metadata.name}' với {total_queries} queries.")

        for idx, item in enumerate(dataset.items, 1):
            start_time = time.time()
            try:
                # Thực thi truy vấn có giới hạn thời gian (timeout)
                retrieved = await asyncio.wait_for(self.backend.query(item.query, kb_id, options), timeout=timeout)
                latency = time.time() - start_time
                success_count += 1
                total_latency += latency

                self.results.append(
                    QueryResult(
                        query=item.query,
                        gold_chunk_ids=item.gold_chunk_ids,
                        gold_intent=getattr(item, "gold_intent", None),
                        retrieved_chunks=retrieved,
                        latency=latency,
                        success=True,
                    )
                )
            except TimeoutError:
                latency = time.time() - start_time
                total_latency += latency
                logger.warning(f"Query {idx}/{total_queries} bị Timeout ({timeout}s): '{item.query}'")
                self.results.append(
                    QueryResult(
                        query=item.query,
                        gold_chunk_ids=item.gold_chunk_ids,
                        gold_intent=getattr(item, "gold_intent", None),
                        retrieved_chunks=[],  # Timeout tính là 0 điểm
                        latency=latency,
                        success=False,
                        error_message=f"Timeout sau {timeout} giây",
                    )
                )
            except Exception as e:
                latency = time.time() - start_time
                total_latency += latency
                logger.error(f"Query {idx}/{total_queries} bị lỗi: '{item.query}'. Chi tiết: {e}")
                self.results.append(
                    QueryResult(
                        query=item.query,
                        gold_chunk_ids=item.gold_chunk_ids,
                        gold_intent=getattr(item, "gold_intent", None),
                        retrieved_chunks=[],  # Lỗi hệ thống tính là 0 điểm
                        latency=latency,
                        success=False,
                        error_message=str(e),
                    )
                )

        # Tính toán hiệu năng và độ tin cậy
        success_rate = success_count / total_queries if total_queries > 0 else 0.0
        avg_latency = total_latency / total_queries if total_queries > 0 else 0.0

        self.performance_stats = {
            "avg_latency": avg_latency,
            "total_latency": total_latency,
            "queries_per_second": total_queries / total_latency if total_latency > 0 else 0.0,
        }

        self.reliability_stats = {
            "success_rate": success_rate,
            "total_queries": total_queries,
            "success_count": success_count,
            "failure_count": total_queries - success_count,
            "timeout_count": sum(1 for r in self.results if r.error_message and "Timeout" in r.error_message),
        }

        logger.info(f"Hoàn thành chạy thực nghiệm. Success rate: {success_rate:.2%}, Avg Latency: {avg_latency:.3f}s")
        return self.results

    def patch_report(self, report: ReportSchema) -> ReportSchema:
        """Cập nhật các chỉ số hiệu năng và độ tin cậy thu được vào ReportSchema."""
        report.performance.update(self.performance_stats)
        report.reliability.update(self.reliability_stats)
        return report
