from __future__ import annotations
import json
import os
import pytest
from typing import Any
from yuxi.evaluation import (
    MemoryVectorBackend,
    EmbeddingStage,
    RetrievalPipelineStage,
    RerankingStage,
    QueryOptions,
)


# Mini Corpus dùng cho In-memory Vector Search
MINI_CORPUS = [
    {
        "chunk_id": "c1",
        "file_id": "doc_rag",
        "content": "RAG viết tắt của Retrieval Augmented Generation là kỹ thuật tối ưu hóa câu trả lời của LLM bằng cơ sở tri thức.",
    },
    {
        "chunk_id": "c2",
        "file_id": "doc_rag",
        "content": "BM25 là thuật toán tìm kiếm từ khóa dựa trên tần suất xuất hiện và độ dài văn bản.",
    },
    {
        "chunk_id": "c3",
        "file_id": "doc_rerank",
        "content": "Reranker giúp sắp xếp lại các tài liệu truy xuất để đưa tài liệu phù hợp nhất lên hàng đầu.",
    },
    {
        "chunk_id": "c4",
        "file_id": "doc_embed",
        "content": "Mô hình nhúng Vector chuyển đổi từ ngữ và câu văn thành các chuỗi số biểu diễn ngữ nghĩa.",
    },
    {
        "chunk_id": "c5",
        "file_id": "doc_semantic",
        "content": "Semantic Router định tuyến ý định câu hỏi sang các luồng xử lý hoặc công cụ phù hợp.",
    },
]

# Mini Dataset với Golden Ground Truth Chunks
MINI_DATASET_CONTENT = """{"query": "RAG nghĩa là gì?", "gold_chunk_ids": ["c1"]}
{"query": "Thuật toán BM25 và từ khóa", "gold_chunk_ids": ["c2"]}
{"query": "Xếp hạng lại Reranker hoạt động thế nào?", "gold_chunk_ids": ["c3"]}
"""


@pytest.mark.asyncio
async def test_retrieval_stages_snapshot_regression(tmp_path):
    # 1. Tạo file dataset JSONL tạm thời
    dataset_file = tmp_path / "mini_dataset.jsonl"
    dataset_file.write_text(MINI_DATASET_CONTENT, encoding="utf-8")

    # 2. Khởi tạo In-memory Backend với Mini Corpus
    backend = MemoryVectorBackend(MINI_CORPUS)

    # 3. Định nghĩa cấu hình manifest thử nghiệm
    manifest = {
        "experiment_id": "INT_TEST_SNAPSHOT",
        "dataset": "mini_dataset",
        "embedding": {
            "provider": "mock",
            "model": "mock-emb",
        },
        "chunker": "mock-chunker",
        "retriever": "hybrid",
        "reranker": "mock-reranker",
        "llm": "mock-llm",
        "similarity_threshold": 0.05,
        "final_top_k": 3,
        "use_reranker": True,
        "reranker_model": "mock-reranker",
        "enable_stage1_prefilter": True,
        "stage1_top_k": 4,
    }

    # 4. Thực thi Stage 3 (Embedding)
    stage3 = EmbeddingStage(backend)
    stage3.prepare(str(dataset_file), manifest)
    await stage3.run()
    metrics3 = await stage3.evaluate()
    report3 = stage3.report()

    # 5. Thực thi Stage 4 (Retrieval Pipeline)
    stage4 = RetrievalPipelineStage(backend)
    stage4.prepare(str(dataset_file), manifest)
    await stage4.run()
    metrics4 = await stage4.evaluate()
    report4 = stage4.report()

    # 6. Thực thi Stage 5 (Reranking)
    stage5 = RerankingStage(backend)
    stage5.prepare(str(dataset_file), manifest)
    await stage5.run()
    metrics5 = await stage5.evaluate()
    report5 = stage5.report()

    # Thu thập tất cả các điểm chất lượng (lọc bỏ các trường Confidence Interval vì có thể biến động nhẹ)
    current_metrics = {
        "stage3": {k: v for k, v in metrics3.items() if not k.endswith("_ci")},
        "stage4": {k: v for k, v in metrics4.items() if not k.endswith("_ci")},
        "stage5": {k: v for k, v in metrics5.items() if not k.endswith("_ci")},
    }

    # Đường dẫn file snapshot
    current_dir = os.path.dirname(os.path.abspath(__file__))
    snapshot_path = os.path.join(current_dir, "retrieval_stages_snapshot.json")

    # 7. Snapshot Regression logic
    if not os.path.exists(snapshot_path):
        # Lần chạy đầu tiên: tạo file snapshot làm gốc
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(current_metrics, f, indent=4, ensure_ascii=False)
        pytest.skip(f"Chưa có file snapshot. Đã tạo snapshot mới tại {snapshot_path}. Vui lòng chạy lại test.")

    # Đọc snapshot gốc
    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot_metrics = json.load(f)

    # So sánh và assert độ lệch (tolerance = 0.01)
    tolerance = 0.01
    for stage_key in ["stage3", "stage4", "stage5"]:
        assert stage_key in snapshot_metrics, f"Thiếu {stage_key} trong snapshot gốc"
        for metric_key, expected_val in snapshot_metrics[stage_key].items():
            assert metric_key in current_metrics[stage_key], f"Thiếu metric '{metric_key}' trong kết quả chạy hiện tại"
            actual_val = current_metrics[stage_key][metric_key]
            
            diff = abs(actual_val - expected_val)
            assert diff <= tolerance, (
                f"Phát hiện suy thoái thuật toán RAG hoặc sai lệch chất lượng! "
                f"Stage: {stage_key}, Metric: {metric_key}. "
                f"Kỳ vọng: {expected_val}, Thực tế: {actual_val} (Lệch: {diff})"
            )
            
    # Kiểm chứng các trường độ tin cậy và hiệu năng cơ bản
    assert report4.reliability["success_rate"] == 1.0
    assert report4.reliability["total_queries"] == 3
    assert report5.reliability["success_rate"] == 1.0
