from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


class QueryOptions(BaseModel):
    """
    Cấu hình chi tiết tham số truy xuất (Retrieval) dùng cho cả MilvusDirect, Pipeline và các Stages đánh giá.
    Mục tiêu: Đảm bảo các tham số kiểm thử không bị trôi dạt (drift) so với các tham số chạy thực tế trong production.
    """

    # General Options
    use_graph_retrieval: bool = Field(default=False, description="Có sử dụng Graph RAG hay không")
    final_top_k: int = Field(default=10, description="Số lượng kết quả cuối cùng trả về")
    similarity_threshold: float = Field(default=0.2, description="Ngưỡng tương đồng tối thiểu để giữ lại chunk")
    include_distances: bool = Field(default=True, description="Có trả về khoảng cách/độ tương đồng trong kết quả")
    search_mode: Literal["vector", "keyword", "hybrid"] = Field(default="vector", description="Chế độ tìm kiếm")

    # Reranking Options
    use_reranker: bool = Field(default=False, description="Có sử dụng bộ xếp hạng lại (Reranker) hay không")
    recall_top_k: int = Field(default=50, description="Số lượng kết quả lấy từ Milvus trước khi đưa vào Rerank")
    file_name: str | None = Field(default=None, description="Tên tệp cụ thể để lọc truy xuất (nếu có)")

    # BM25 Options
    bm25_top_k: int = Field(default=10, description="Số lượng kết quả lấy từ BM25")
    bm25_drop_ratio_search: float = Field(default=0.0, description="Tỷ lệ bỏ từ khóa ít quan trọng khi BM25 search")

    # Hybrid Fusion Options
    vector_weight: float = Field(default=0.7, description="Trọng số của Vector Search khi kết hợp Hybrid")
    bm25_weight: float = Field(default=0.3, description="Trọng số của BM25 khi kết hợp Hybrid")
    hybrid_ranker: Literal["weighted", "rrf"] = Field(
        default="weighted", description="Loại ranker kết hợp: weighted hoặc rrf"
    )
    rrf_k: int = Field(default=60, description="Hằng số k của thuật toán RRF")

    # Graph / Consensus Options
    use_consensus_retrieval: bool = Field(default=True, description="Có sử dụng consensus để gộp kết quả đồ thị")
    consensus_weight_vector: float = Field(default=0.4, description="Trọng số của Naive Vector trong Consensus")
    consensus_weight_local: float = Field(default=0.25, description="Trọng số của Local Entity trong Consensus")
    consensus_weight_relation: float = Field(default=0.15, description="Trọng số của Relation trong Consensus")
    consensus_weight_event: float = Field(default=0.2, description="Trọng số của Event Multi-hop trong Consensus")
    graph_entity_top_k: int = Field(default=10, description="Số lượng entity lấy từ đồ thị")
    graph_triple_top_k: int = Field(default=10, description="Số lượng triple lấy từ đồ thị")
    graph_top_k: int = Field(default=20, description="Số lượng kết quả đồ thị tối đa")
    graph_max_nodes: int = Field(default=10000, description="Số lượng nút tối đa duyệt trong đồ thị")
    ppr_damping: float = Field(default=0.85, description="Hệ số damping PPR trong thuật toán đồ thị")
    graph_weight: float = Field(default=1.0, description="Trọng số kết hợp đồ thị (khi không dùng consensus)")

    # Two-Stage Rerank Model Options
    reranker_model: str | None = Field(default=None, description="Tên mô hình rerank chính (Stage 2)")
    stage1_reranker_model: str | None = Field(default=None, description="Tên mô hình rerank pre-filter (Stage 1)")
    stage1_top_k: int = Field(default=20, description="Số lượng chunk giữ lại sau Stage 1 pre-filter")
    enable_stage1_prefilter: bool = Field(default=False, description="Bật pre-filter Stage 1")

    def to_dict(self) -> dict[str, Any]:
        """Chuyển cấu hình thành dict loại bỏ các trường None để làm kwargs."""
        return {k: v for k, v in self.model_dump().items() if v is not None}
