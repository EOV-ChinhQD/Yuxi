"""知识库领域包。"""

# Nhánh ours nhập `knowledge_base` trực tiếp từ package này; giữ re-export
# để tương thích với runtime singleton đã được upstream tách ra yuxi.knowledge.runtime.
from yuxi.knowledge.runtime import knowledge_base

__all__ = ["knowledge_base"]
