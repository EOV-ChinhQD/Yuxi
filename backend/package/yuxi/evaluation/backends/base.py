from __future__ import annotations
from typing import Any, Protocol, runtime_checkable
from yuxi.evaluation.config.query_options import QueryOptions


@runtime_checkable
class RetrieverBackend(Protocol):
    """
    Protocol định nghĩa giao diện chung cho các bộ truy xuất (Backend) phục vụ kiểm thử và đánh giá.
    Giúp cô lập logic chạy thực nghiệm (Stages) khỏi việc gọi trực tiếp đến cơ sở dữ liệu Milvus/Postgres
    hoặc logic production.
    """

    async def query(self, query_text: str, kb_id: str, options: QueryOptions) -> list[dict[str, Any]]:
        """
        Thực hiện truy vấn tài liệu.

        Args:
            query_text: Nội dung câu truy vấn.
            kb_id: Mã cơ sở tri thức cần truy vấn.
            options: Đối tượng QueryOptions chứa cấu hình tham số.

        Returns:
            Danh sách các chunk tìm được dạng dict, đồng nhất với cấu trúc chunk của Milvus:
            [
                {
                    "content": "nội dung chunk...",
                    "chunk_id": "chunk_xxx",
                    "file_id": "file_yyy",
                    "score": 0.85,
                    "stage1_score": 0.80, # nếu qua Reranker Stage 1
                    "rerank_score": 0.90, # nếu qua Reranker Stage 2
                }
            ]
        """
        ...
