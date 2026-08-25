"""Application configuration module."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import tomli
import tomli_w
from pydantic import BaseModel, Field, PrivateAttr

from yuxi.config import cache as runtime_cache
from yuxi.knowledge.parser.registry import PROCESSOR_TYPES
from yuxi.utils.logging_config import logger

READONLY_CONFIG_FIELDS = frozenset({"save_dir"})
DEFAULT_OCR_ENGINE = "rapid_ocr"
DEFAULT_OCR_POLICY = "auto"


def _normalize_ocr_policy(value: Any) -> str:
    policy = str(value or "").strip().lower() or DEFAULT_OCR_POLICY
    if policy not in ("auto", "enable", "disable"):
        raise ValueError(f"Unsupported OCR policy: {policy}")
    return policy


def _get_available_ocr_engines() -> set[str]:
    return {"disable", *PROCESSOR_TYPES}


def _normalize_default_ocr_engine(value: Any) -> str:
    engine = str(value or "").strip() or DEFAULT_OCR_ENGINE
    if engine not in _get_available_ocr_engines():
        raise ValueError(f"Engine OCR mặc định không được hỗ trợ: {engine}")
    return engine


class Config(BaseModel):
    """Application configuration class.

    `save_dir` The configuration file location is only determined at startup and cannot be modified during runtime. The administrator writes first when saving the configuration
    `base.toml`, and then write the fields that can be synchronized at runtime into the Redis snapshot (`yuxi:runtime_config`）。
    Other processes use `start_runtime_sync()` where the started background thread periodically pulls the snapshot to refresh the memory value.
    """

    save_dir: str = Field(default="saves", description="Thư mục lưu trữ", exclude=True)
    enable_content_guard: bool = Field(default=False, description="Bật kiểm duyệt nội dung")
    enable_content_guard_llm: bool = Field(default=False, description="Bật kiểm duyệt nội dung LLM")
    default_model: str = Field(
        default="gemini_compatible:gemini-2.5-flash",
        description="Mô hình trò chuyện mặc định",
    )
    fast_model: str = Field(
        default="gemini_compatible:gemini-2.5-flash",
        description="Mô hình phản hồi nhanh",
    )
    embed_model: str = Field(
        default="gemini_compatible:text-embedding-004",
        description="Mô hình Embedding mặc định",
    )
    reranker: str = Field(
        default="siliconflow-cn:Pro/BAAI/bge-reranker-v2-m3",
        description="Mô hình Re-Ranker mặc định",
    )
    content_guard_llm_model: str = Field(
        default="gemini_compatible:gemini-2.5-flash",
        description="Mô hình LLM kiểm duyệt nội dung",
    )
    default_ocr_engine: str = Field(default=DEFAULT_OCR_ENGINE, description="Engine phân tích OCR mặc định")
    ocr_policy: str = Field(default=DEFAULT_OCR_POLICY, description="OCR policy for PDF parsing: auto/enable/disable")
    allow_external_ocr: bool = Field(
        default=False, description="Allow cloud-based OCR engines in the PDF fallback chain"
    )

    max_nli_claims: int = Field(default=8, description="Số lượng claim tối đa đưa vào NLI verifier để kiểm tra.")
    nli_max_concurrency: int = Field(default=3, description="Số lượng kết nối NLI tối đa chạy đồng thời (Semaphore).")

    _config_file: Path | None = PrivateAttr(default=None)
    _runtime_sync_thread: Any = PrivateAttr(default=None)

    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    def __init__(self, **data):
        super().__init__(**data)
        self._setup_paths()
        self._load_user_config()
        self._handle_environment()

    def _setup_paths(self) -> None:
        self._config_file = Path(self.save_dir) / "config" / "base.toml"
        self._config_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_user_config(self) -> None:
        if not self._config_file or not self._config_file.exists():
            logger.info(f"Config file not found, using defaults: {self._config_file}")
            return

        logger.info(f"Loading config from {self._config_file}")
        try:
            with open(self._config_file, "rb") as f:
                user_config = tomli.load(f)

            for key, value in user_config.items():
                if key in READONLY_CONFIG_FIELDS:
                    logger.warning(f"Readonly config key ignored: {key}")
                elif key in type(self).model_fields:
                    try:
                        setattr(self, key, self._normalize_config_value(key, value))
                    except ValueError as exc:
                        logger.warning(f"Invalid config key ignored: {key} ({exc})")
                else:
                    logger.warning(f"Unknown config key: {key}")

        except Exception as e:
            logger.error(f"Failed to load config from {self._config_file}: {e}")

    def _handle_environment(self) -> None:
        # Cấu hình NLI grounding và chính sách OCR của nhánh ours; sandbox đã chuyển sang đọc biến môi trường trực tiếp
        self.max_nli_claims = int(os.getenv("MAX_NLI_CLAIMS") or self.max_nli_claims or 8)
        self.nli_max_concurrency = int(os.getenv("NLI_MAX_CONCURRENCY") or self.nli_max_concurrency or 3)
        self.ocr_policy = os.getenv("OCR_POLICY") or self.ocr_policy or DEFAULT_OCR_POLICY
        self.allow_external_ocr = (os.getenv("ALLOW_EXTERNAL_OCR") or str(self.allow_external_ocr)).lower() in (
            "true",
            "1",
            "yes",
        )

    def start_runtime_sync(self, interval: float = runtime_cache.RUNTIME_CONFIG_SYNC_INTERVAL_SECONDS) -> None:
        """Start a background thread to periodically synchronize the runtime configuration from Redis. Multiple calls only start once."""
        self._runtime_sync_thread = runtime_cache.start_runtime_sync(
            self,
            self._runtime_sync_thread,
            interval=interval,
        )

    def refresh(self) -> None:
        """Refresh public configuration fields to memory from a Redis snapshot; keep current values ​​when Redis is unavailable or there is no snapshot."""
        runtime_cache.refresh_runtime_config(self)

    def save(self) -> None:
        if not self._config_file:
            logger.warning("Config file path not set")
            return

        logger.info(f"Saving config to {self._config_file}")
        user_modified = {}
        for field_name, field_info in type(self).model_fields.items():
            if field_info.exclude:
                continue
            current_value = getattr(self, field_name)
            if current_value != field_info.default:
                user_modified[field_name] = current_value

        try:
            with open(self._config_file, "wb") as f:
                tomli_w.dump(user_modified, f)
            logger.info(f"Config saved to {self._config_file}")
            runtime_cache.save_runtime_config(self)
        except Exception as e:
            logger.error(f"Failed to save config to {self._config_file}: {e}")

    def dump_config(self) -> dict[str, Any]:
        config_dict = self.model_dump()
        fields_info = {}
        for field_name, field_info in Config.model_fields.items():
            if field_info.exclude:
                continue
            fields_info[field_name] = {
                "des": field_info.description,
                "default": field_info.default,
                "type": field_info.annotation.__name__
                if hasattr(field_info.annotation, "__name__")
                else str(field_info.annotation),
                "exclude": field_info.exclude if hasattr(field_info, "exclude") else False,
            }
        config_dict["_config_items"] = fields_info
        return config_dict

    def update(self, other: dict[str, Any]) -> None:
        for key, value in other.items():
            if self.can_update(key):
                self.set_value(key, value)
            elif key in READONLY_CONFIG_FIELDS:
                logger.warning(f"Readonly config key ignored: {key}")
            else:
                logger.warning(f"Unknown config key: {key}")

    def can_update(self, key: object) -> bool:
        return isinstance(key, str) and key in type(self).model_fields and key not in READONLY_CONFIG_FIELDS

    def set_value(self, key: str, value: Any) -> None:
        if not self.can_update(key):
            raise ValueError(f"Mục cấu hình không thể sửa đổi: {key}")
        setattr(self, key, self._normalize_config_value(key, value))

    def _normalize_config_value(self, key: str, value: Any) -> Any:
        if key == "default_ocr_engine":
            return _normalize_default_ocr_engine(value)
        if key == "ocr_policy":
            return _normalize_ocr_policy(value)
        if key == "allow_external_ocr":
            return str(value).lower() in ("true", "1", "yes")
        return value


config = Config()
