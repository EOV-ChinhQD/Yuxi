from __future__ import annotations
import ast
import os
from yuxi.evaluation.config.query_options import QueryOptions


def test_query_options_sync():
    """
    Test chống trôi dạt cấu hình (Anti-Config-Drift).
    Sử dụng AST phân tích milvus.py để phát hiện bất kỳ trường kwargs nào được gọi qua `.get()`
    mà chưa được khai báo tương ứng trong QueryOptions.
    """
    # 1. Đường dẫn tới file milvus.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    milvus_path = os.path.abspath(
        os.path.join(
            current_dir,
            "../../../package/yuxi/knowledge/implementations/milvus.py"
        )
    )
    assert os.path.exists(milvus_path), f"Không tìm thấy milvus.py tại {milvus_path}"

    with open(milvus_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    extracted_keys: set[str] = set()

    # 2. Duyệt cây cú pháp AST tìm các lệnh gọi method `.get()` của dict kwargs, merged_kwargs, query_params
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get":
                value = func.value
                if isinstance(value, ast.Name) and value.id in {"kwargs", "merged_kwargs", "query_params"}:
                    if node.args:
                        first_arg = node.args[0]
                        # Hỗ trợ cả Python 3.8+ Constant và Python < 3.8 Str
                        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                            extracted_keys.add(first_arg.value)
                        elif isinstance(first_arg, ast.Str):
                            extracted_keys.add(first_arg.s)

    # 3. Danh sách các trường được định nghĩa trong QueryOptions
    query_options_fields = set(QueryOptions.model_fields.keys())

    # 4. Tập các từ khóa cấu hình cốt lõi bắt buộc phải khớp
    core_retrieval_keys = {
        "search_mode", "use_reranker", "recall_top_k", "final_top_k", "similarity_threshold",
        "include_distances", "bm25_top_k", "bm25_drop_ratio_search", "vector_weight", "bm25_weight",
        "hybrid_ranker", "rrf_k", "use_consensus_retrieval", "consensus_weight_vector",
        "consensus_weight_local", "consensus_weight_relation", "consensus_weight_event",
        "graph_entity_top_k", "graph_weight", "reranker_model", "stage1_reranker_model",
        "stage1_top_k", "enable_stage1_prefilter"
    }

    # Đảm bảo toàn bộ cấu hình cốt lõi có mặt trong QueryOptions
    missing_core = core_retrieval_keys - query_options_fields
    assert not missing_core, f"QueryOptions thiếu các trường cốt lõi bắt buộc: {missing_core}"

    # 5. Các khóa không liên quan đến cấu hình tìm kiếm hoặc có xử lý đặc biệt khác
    ignored_keys = {
        "file_name", "graph_build_config", "milvus_token", "milvus_uri", "milvus_db"
    }

    # 6. Kiểm tra đối chiếu tự động
    for key in extracted_keys:
        if key in ignored_keys:
            continue
        
        # Chỉ kiểm tra các khóa trông giống như tham số cấu hình retrieval
        is_retrieval_param = any(
            substring in key
            for substring in [
                "top_k", "threshold", "weight", "mode", "model",
                "ranker", "prefilter", "k", "include", "use"
            ]
        )
        if is_retrieval_param:
            assert key in query_options_fields, (
                f"Phát hiện trôi dạt cấu hình! File milvus.py sử dụng tham số '{key}' "
                f"nhưng QueryOptions chưa được khai báo trường này."
            )
