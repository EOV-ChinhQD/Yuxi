"""文档解析领域包。"""

# Import lười (PEP 562): tránh kéo toàn bộ unified/OCR service vào mọi tiến trình
# chỉ vì chạm vào package parser (contract: fresh-import không khởi tạo knowledge runtime).
from importlib import import_module


def __getattr__(name: str):
    if name == "Parser":
        return getattr(import_module("yuxi.knowledge.parser.unified"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted({*globals(), "Parser"})
