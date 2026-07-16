from __future__ import annotations
from typing import Any, TYPE_CHECKING
from yuxi.evaluation.backends.base import RetrieverBackend
from yuxi.evaluation.config.query_options import QueryOptions
from yuxi.evaluation.datasets.loader import DatasetLoader, EvaluationDataset
from yuxi.evaluation.stages.base import EvaluationStage, ReportSchema, calculate_bootstrap_ci
from yuxi.knowledge.eval.metrics import RetrievalMetrics
from yuxi.utils import logger

if TYPE_CHECKING:
    from yuxi.evaluation.runner import EvaluationRunner, QueryResult


class RerankingStage(EvaluationStage):
    """
    Stage 5: Reranking.
    Đo lường sự thay đổi chất lượng qua các tầng xếp hạng lại (Reranking).
    Thực hiện so sánh 3 mốc baselines thô/tinh để đánh giá chính xác tác động của Reranker.
    """

    def __init__(self, backend: RetrieverBackend):
        self.backend = backend
        self.dataset: EvaluationDataset | None = None
        self.manifest: dict[str, Any] | None = None
        self.options: QueryOptions | None = None

        # Ba runner chạy ba cấu hình truy xuất khác nhau
        self.pre_runner: EvaluationRunner | None = None
        self.post1_runner: EvaluationRunner | None = None
        self.final_runner: EvaluationRunner | None = None

        self.calculated_metrics: dict[str, Any] = {}
        self.kb_id: str = "default_kb"

    def prepare(self, dataset_path: str, manifest: dict[str, Any]) -> None:
        self.dataset = DatasetLoader.load_from_jsonl(dataset_path)
        self.manifest = manifest
        self.kb_id = manifest.get("kb_id", "default_kb")

        # 1. Cấu hình Final (đầy đủ hai giai đoạn reranker)
        options_dict = {}
        retriever_str = manifest.get("retriever", "hybrid").lower()
        if "hybrid" in retriever_str:
            options_dict["search_mode"] = "hybrid"
        elif "keyword" in retriever_str:
            options_dict["search_mode"] = "keyword"
        else:
            options_dict["search_mode"] = "vector"

        reranker_str = manifest.get("reranker")
        if reranker_str:
            options_dict["use_reranker"] = True
            options_dict["reranker_model"] = reranker_str

        for field_name in QueryOptions.model_fields:
            if field_name in manifest:
                options_dict[field_name] = manifest[field_name]

        self.options = QueryOptions(**options_dict)

        # 2. Khởi tạo runners
        from yuxi.evaluation.runner import EvaluationRunner

        self.pre_runner = EvaluationRunner(self.backend)
        self.final_runner = EvaluationRunner(self.backend)

        # Chỉ chạy runner Stage 1 nếu cấu hình Stage 1 rerank thực sự được bật
        if self.options.stage1_reranker_model or self.options.enable_stage1_prefilter:
            self.post1_runner = EvaluationRunner(self.backend)
        else:
            self.post1_runner = None

    async def run(self) -> None:
        if not self.dataset or not self.options:
            raise ValueError("Stage chưa được chuẩn bị (gọi prepare()).")

        timeout = float(self.manifest.get("timeout", 15.0)) if self.manifest else 15.0

        # --- 1. Chạy Pre-Rerank (Tắt toàn bộ Reranker) ---
        pre_options = self.options.model_copy(update={"use_reranker": False})
        logger.info("[Stage 5 Reranking] Đang chạy đánh giá Pre-Rerank...")
        await self.pre_runner.run_dataset(self.dataset, self.kb_id, pre_options, timeout=timeout)

        # --- 2. Chạy Post-Stage 1 (Nếu bật lọc thô Stage 1 và bỏ Stage 2) ---
        if self.post1_runner:
            post1_options = self.options.model_copy(
                update={
                    "use_reranker": True,
                    "reranker_model": None,  # Bỏ qua Stage 2
                }
            )
            logger.info("[Stage 5 Reranking] Đang chạy đánh giá Post-Stage1...")
            await self.post1_runner.run_dataset(self.dataset, self.kb_id, post1_options, timeout=timeout)

        # --- 3. Chạy Final (Đầy đủ cả 2 giai đoạn) ---
        logger.info("[Stage 5 Reranking] Đang chạy đánh giá Final Rerank...")
        await self.final_runner.run_dataset(self.dataset, self.kb_id, self.options, timeout=timeout)

    def _evaluate_results(self, results: list[QueryResult]) -> dict[str, list[float]]:
        scores = {"recall@1": [], "recall@3": [], "recall@5": [], "recall@10": [], "ndcg@10": [], "mrr@10": []}
        for result in results:
            if not result.success or not result.retrieved_chunks:
                for k in scores:
                    scores[k].append(0.0)
                continue

            retrieved_ids = [
                str(chunk.get("chunk_id") or chunk.get("metadata", {}).get("chunk_id"))
                for chunk in result.retrieved_chunks
            ]
            gold_ids = [str(gid) for gid in result.gold_chunk_ids]

            scores["recall@1"].append(RetrievalMetrics.recall_at_k(retrieved_ids, gold_ids, 1))
            scores["recall@3"].append(RetrievalMetrics.recall_at_k(retrieved_ids, gold_ids, 3))
            scores["recall@5"].append(RetrievalMetrics.recall_at_k(retrieved_ids, gold_ids, 5))
            scores["recall@10"].append(RetrievalMetrics.recall_at_k(retrieved_ids, gold_ids, 10))
            scores["ndcg@10"].append(RetrievalMetrics.ndcg_at_k(retrieved_ids, gold_ids, 10))
            scores["mrr@10"].append(RetrievalMetrics.mrr_at_k(retrieved_ids, gold_ids, 10))

        return scores

    async def evaluate(self) -> dict[str, Any]:
        if not self.final_runner or not self.final_runner.results:
            return {}

        final_metrics = {}

        # 1. Tính toán metrics cho Pre-Rerank
        pre_scores = self._evaluate_results(self.pre_runner.results)
        for metric, scores in pre_scores.items():
            mean_val, lower, upper = calculate_bootstrap_ci(scores)
            final_metrics[f"pre_rerank_{metric}"] = mean_val
            final_metrics[f"pre_rerank_{metric}_ci"] = [lower, upper]

        # 2. Tính toán metrics cho Post-Stage1 (nếu có)
        if self.post1_runner and self.post1_runner.results:
            post1_scores = self._evaluate_results(self.post1_runner.results)
            for metric, scores in post1_scores.items():
                mean_val, lower, upper = calculate_bootstrap_ci(scores)
                final_metrics[f"post_stage1_{metric}"] = mean_val
                final_metrics[f"post_stage1_{metric}_ci"] = [lower, upper]

        # 3. Tính toán metrics cho Final Rerank
        final_scores = self._evaluate_results(self.final_runner.results)
        for metric, scores in final_scores.items():
            mean_val, lower, upper = calculate_bootstrap_ci(scores)
            final_metrics[f"final_{metric}"] = mean_val
            final_metrics[f"final_{metric}_ci"] = [lower, upper]
            # Giữ lại metric gốc không có tiền tố để tương thích ngược với runner/baseline
            final_metrics[metric] = mean_val
            final_metrics[f"{metric}_ci"] = [lower, upper]

        self.calculated_metrics = final_metrics
        return final_metrics

    def report(self) -> ReportSchema:
        schema = ReportSchema(metrics=self.calculated_metrics, performance={}, cost={}, reliability={}, regression={})
        # Sử dụng stats của final_runner làm đại diện cho hiệu năng thực tế của Reranking pipeline
        if self.final_runner:
            schema = self.final_runner.patch_report(schema)

        return schema
