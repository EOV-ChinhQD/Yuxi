import os


class FeatureManager:
    """Quản lý các feature flags cho kiến trúc Hybrid Semantic Event RAG."""

    _overrides: dict[str, bool] = {}

    STRUCTURAL_CHUNKING = "ENABLE_STRUCTURAL_CHUNKING"
    EVENT_EXTRACTION = "ENABLE_EVENT_EXTRACTION"
    VLM_CAPTIONING = "ENABLE_VLM_CAPTIONING"
    SQL_MULTIHOP = "ENABLE_SQL_MULTIHOP"

    @classmethod
    def is_enabled(cls, flag: str) -> bool:
        if flag in cls._overrides:
            return cls._overrides[flag]
        return os.getenv(flag, "false").lower() in ("true", "1", "yes")

    @classmethod
    def override(cls, flag: str, value: bool) -> None:
        """Cho phép override giá trị flag trong unit/integration tests."""
        cls._overrides[flag] = value

    @classmethod
    def reset_overrides(cls) -> None:
        cls._overrides.clear()
