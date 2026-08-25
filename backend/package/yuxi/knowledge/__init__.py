"""知识库领域包。"""

# Nhánh ours từng nhập `knowledge_base` trực tiếp từ package này; giữ tương thích qua
# lazy import (PEP 562) để tránh vòng lặp: yuxi.config -> yuxi.knowledge.__init__ -> yuxi.config
# khi config chuẩn hóa engine OCR trong lúc khởi tạo.
from importlib import import_module


def __getattr__(name: str):
    if name == "knowledge_base":
        runtime = import_module("yuxi.knowledge.runtime")
        return getattr(runtime, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted({*globals(), "knowledge_base"})
