from __future__ import annotations
import asyncio
from typing import Any
import pytest
from yuxi.evaluation.backends.base import RetrieverBackend
from yuxi.evaluation.config.query_options import QueryOptions
from yuxi.evaluation.datasets.loader import EvaluationDataset, DatasetItem, DatasetMetadata
from yuxi.evaluation.runner import EvaluationRunner
from yuxi.evaluation.stages.stage4_retrieval import RetrievalPipelineStage
from yuxi.evaluation.stages.base import ReportSchema


class MockRetrieverBackend(RetrieverBackend):
    def __init__(self, mode: str = "normal"):
        self.mode = mode

    async def query(
        self, query_text: str, kb_id: str, options: QueryOptions
    ) -> list[dict[str, Any]]:
        if self.mode == "timeout" and "timeout" in query_text:
            # Mô phỏng quá thời gian chạy
            await asyncio.sleep(2.0)
            return []
        elif self.mode == "error" and "error" in query_text:
            # Mô phỏng lỗi hệ thống
            raise RuntimeError("Lỗi truy vấn CSDL")
        elif query_text == "empty":
            return []
            
        # Trả về kết quả bình thường
        return [
            {"chunk_id": "chunk_1", "content": "Nội dung 1", "score": 0.9},
            {"chunk_id": "chunk_2", "content": "Nội dung 2", "score": 0.8},
        ]


@pytest.mark.asyncio
async def test_runner_partial_failures():
    # Dataset gồm 3 câu hỏi: 1 thành công, 1 timeout, 1 lỗi
    dataset = EvaluationDataset(
        metadata=DatasetMetadata(name="Test partial failures"),
        items=[
            DatasetItem(query="normal query", gold_chunk_ids=["chunk_1"]),
            DatasetItem(query="timeout query", gold_chunk_ids=["chunk_2"]),
            DatasetItem(query="error query", gold_chunk_ids=["chunk_1"]),
        ]
    )
    
    # Mock backend hỗ trợ cả lỗi lẫn timeout
    backend = MockRetrieverBackend(mode="timeout")
    # Ghi đè phương thức query để mô phỏng cả 3 trạng thái tùy theo query_text
    async def custom_query(query_text: str, kb_id: str, options: QueryOptions):
        if "timeout" in query_text:
            await asyncio.sleep(1.0)
            return []
        elif "error" in query_text:
            raise RuntimeError("Database connection lost")
        return [{"chunk_id": "chunk_1", "content": "Nội dung 1", "score": 0.9}]
        
    backend.query = custom_query
    
    runner = EvaluationRunner(backend)
    options = QueryOptions()
    
    # Thiết lập timeout cực ngắn (0.2s) để kích hoạt TimeoutError
    results = await runner.run_dataset(dataset, "kb_test", options, timeout=0.2)
    
    assert len(results) == 3
    
    # 1. Kiểm tra query thành công
    assert results[0].success is True
    assert len(results[0].retrieved_chunks) == 1
    assert results[0].error_message is None
    
    # 2. Kiểm tra query bị timeout
    assert results[1].success is False
    assert len(results[1].retrieved_chunks) == 0
    assert "Timeout" in results[1].error_message
    
    # 3. Kiểm tra query bị lỗi
    assert results[2].success is False
    assert len(results[2].retrieved_chunks) == 0
    assert "Database connection lost" in results[2].error_message
    
    # 4. Kiểm tra độ tin cậy thu được
    stats = runner.reliability_stats
    assert stats["total_queries"] == 3
    assert stats["success_count"] == 1
    assert stats["failure_count"] == 2
    assert stats["timeout_count"] == 1
    # Tỉ lệ thành công 1/3 = 33.3%
    assert abs(stats["success_rate"] - 0.333) < 0.01
    
    # 5. Kiểm tra tính điểm chất lượng tích hợp thông qua Stage 4
    stage = RetrievalPipelineStage(backend)
    stage.runner = runner
    stage.manifest = {}
    
    metrics = await stage.evaluate()
    # Vì chỉ có 1 query thành công tìm thấy chunk_1 (gold_ids của query 1 là chunk_1 -> recall=1)
    # 2 query còn lại nhận 0 điểm -> Recall trung bình = (1 + 0 + 0) / 3 = 0.333
    assert abs(metrics["recall@1"] - 0.333) < 0.01
    # Kiểm tra có CI đi kèm
    assert "recall@1_ci" in metrics
    assert len(metrics["recall@1_ci"]) == 2
    assert metrics["recall@1_ci"][0] <= metrics["recall@1"] <= metrics["recall@1_ci"][1]


@pytest.mark.asyncio
async def test_retrieval_stage_confusion_matrix():
    from yuxi.evaluation.datasets.loader import EvaluationDataset, DatasetItem, DatasetMetadata
    from yuxi.evaluation.runner import QueryResult
    
    dataset = EvaluationDataset(
        metadata=DatasetMetadata(name="Test router confusion matrix"),
        items=[
            DatasetItem(query="Query 1", gold_chunk_ids=["chunk_1"], gold_intent="CHIT_CHAT"),
            DatasetItem(query="Query 2", gold_chunk_ids=["chunk_2"], gold_intent="EXACT_MATCH"),
            DatasetItem(query="Query 3", gold_chunk_ids=["chunk_1"], gold_intent="SUMMARIZATION"),
        ]
    )
    
    # Mock backend to return system routing headers
    class MockRouterBackend(RetrieverBackend):
        async def query(self, query_text: str, kb_id: str, options: QueryOptions):
            if "Query 1" in query_text:
                intent = "CHIT_CHAT"
            elif "Query 2" in query_text:
                intent = "EXACT_MATCH"
            else:
                intent = "NAIVE_SEARCH"  # Wrong classification (Expected SUMMARIZATION)
            return [
                {
                    "chunk_id": "system_routing_header",
                    "content": f"🤖 **Bộ định tuyến RAG Yuxi**\n* **Ý định**: `{intent}`\n* **Chiến lược**: `FactStrategy`",
                    "score": 1.0,
                },
                {"chunk_id": "chunk_1", "content": "Nội dung 1", "score": 0.9},
            ]

    backend = MockRouterBackend()
    runner = EvaluationRunner(backend)
    options = QueryOptions()
    
    await runner.run_dataset(dataset, "kb_test", options)
    
    stage = RetrievalPipelineStage(backend)
    stage.dataset = dataset
    stage.runner = runner
    stage.manifest = {}
    
    metrics = await stage.evaluate()
    
    assert "router_accuracy" in metrics
    # 2 correct (CHIT_CHAT, EXACT_MATCH), 1 incorrect (expected SUMMARIZATION, got NAIVE_SEARCH) -> 2/3 = 66.7%
    assert abs(metrics["router_accuracy"] - 0.666) < 0.01
    
    matrix = metrics["router_confusion_matrix"]
    assert matrix["CHIT_CHAT"]["CHIT_CHAT"] == 1
    assert matrix["EXACT_MATCH"]["EXACT_MATCH"] == 1
    assert matrix["SUMMARIZATION"]["NAIVE_SEARCH"] == 1

    report = stage.report()
    assert report.reliability["router_accuracy"] == metrics["router_accuracy"]
    assert "router_confusion_matrix" in report.reliability

