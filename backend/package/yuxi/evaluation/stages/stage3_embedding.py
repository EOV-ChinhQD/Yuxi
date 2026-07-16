from __future__ import annotations
from typing import Any, TYPE_CHECKING
from yuxi.evaluation.backends.base import RetrieverBackend
from yuxi.evaluation.config.query_options import QueryOptions
from yuxi.evaluation.datasets.loader import DatasetLoader, EvaluationDataset
from yuxi.evaluation.stages.base import EvaluationStage, ReportSchema, calculate_bootstrap_ci
from yuxi.knowledge.eval.metrics import RetrievalMetrics

if TYPE_CHECKING:
    from yuxi.evaluation.runner import EvaluationRunner


class EmbeddingStage(EvaluationStage):
    """
    Stage 3: Embedding Quality.
    Đo lường sức mạnh biểu diễn ngữ nghĩa của mô hình nhúng (Embedding) trên Milvus.
    Bỏ qua Reranking và Graph RAG.
    """

    def __init__(self, backend: RetrieverBackend):
        self.backend = backend
        self.dataset: EvaluationDataset | None = None
        self.manifest: dict[str, Any] | None = None
        self.options: QueryOptions | None = None
        self.runner: EvaluationRunner | None = None
        self.calculated_metrics: dict[str, Any] = {}
        self.kb_id: str = "default_kb"

    def prepare(self, dataset_path: str, manifest: dict[str, Any]) -> None:
        self.dataset = DatasetLoader.load_from_jsonl(dataset_path)
        self.manifest = manifest

        # Tạo QueryOptions từ manifest
        options_dict = {}

        # Stage 3 đo lường thuần túy vector
        options_dict["search_mode"] = "vector"
        options_dict["use_reranker"] = False
        options_dict["use_graph_retrieval"] = False

        # Cho phép ghi đè từ manifest
        for field_name in QueryOptions.model_fields:
            if field_name in manifest:
                options_dict[field_name] = manifest[field_name]

        self.options = QueryOptions(**options_dict)
        self.kb_id = manifest.get("kb_id", "default_kb")
        from yuxi.evaluation.runner import EvaluationRunner

        self.runner = EvaluationRunner(self.backend)

    async def run(self) -> None:
        if not self.dataset or not self.options or not self.runner:
            raise ValueError("Stage chưa được gọi prepare() hoặc thiếu dữ liệu cấu hình.")

        timeout = float(self.manifest.get("timeout", 15.0)) if self.manifest else 15.0
        await self.runner.run_dataset(self.dataset, self.kb_id, self.options, timeout=timeout)

    async def evaluate(self) -> dict[str, Any]:
        if not self.runner or not self.runner.results:
            return {}

        all_scores = {
            "recall@1": [],
            "recall@3": [],
            "recall@5": [],
            "recall@10": [],
            "ndcg@10": [],
            "mrr@10": [],
        }

        for result in self.runner.results:
            if not result.success or not result.retrieved_chunks:
                # Failed/Timeout query nhận điểm 0 cho tất cả metrics
                for k in all_scores:
                    all_scores[k].append(0.0)
                continue

            retrieved_ids = [
                str(chunk.get("chunk_id") or chunk.get("metadata", {}).get("chunk_id"))
                for chunk in result.retrieved_chunks
            ]
            gold_ids = [str(gid) for gid in result.gold_chunk_ids]

            all_scores["recall@1"].append(RetrievalMetrics.recall_at_k(retrieved_ids, gold_ids, 1))
            all_scores["recall@3"].append(RetrievalMetrics.recall_at_k(retrieved_ids, gold_ids, 3))
            all_scores["recall@5"].append(RetrievalMetrics.recall_at_k(retrieved_ids, gold_ids, 5))
            all_scores["recall@10"].append(RetrievalMetrics.recall_at_k(retrieved_ids, gold_ids, 10))
            all_scores["ndcg@10"].append(RetrievalMetrics.ndcg_at_k(retrieved_ids, gold_ids, 10))
            all_scores["mrr@10"].append(RetrievalMetrics.mrr_at_k(retrieved_ids, gold_ids, 10))

        # Tính toán Mean & 95% Confidence Interval (ci)
        final_metrics = {}
        for metric_name, scores in all_scores.items():
            mean_val, lower, upper = calculate_bootstrap_ci(scores)
            final_metrics[metric_name] = mean_val
            final_metrics[f"{metric_name}_ci"] = [lower, upper]

        self.calculated_metrics = final_metrics
        return final_metrics

    def report(self) -> ReportSchema:
        schema = ReportSchema(metrics=self.calculated_metrics, performance={}, cost={}, reliability={}, regression={})
        if self.runner:
            schema = self.runner.patch_report(schema)

        return schema
