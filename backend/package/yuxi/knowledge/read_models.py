"""Internal read models shared by the knowledge base manager, callers, and type executors."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from yuxi.permissions import ResourcePermission


@dataclass(frozen=True, slots=True)
class KnowledgeBaseConfig:
    """Minimal config a knowledge base type implementation needs to run one operation."""

    kb_id: str
    kb_type: str
    embedding_model_spec: str | None = None
    query_params: dict[str, Any] = field(default_factory=dict)
    additional_params: dict[str, Any] = field(default_factory=dict)

    @property
    def query_options(self) -> dict[str, Any]:
        """Return the options from the persisted query params."""
        options = self.query_params.get("options")
        return options if isinstance(options, dict) else {}


@dataclass(frozen=True, slots=True)
class KnowledgeBaseSummary:
    """Internal summary shared by knowledge base listing, permission filtering, and resource selection."""

    kb_id: str
    name: str
    description: str | None
    kb_type: str
    embedding_model_spec: str | None
    llm_model_spec: str | None
    query_params: dict[str, Any]
    additional_params: dict[str, Any]
    share_config: dict[str, Any]
    created_by: str | None
    created_at: datetime | None
    file_count: int = 0
    folder_count: int = 0
    row_count: int = 0
    total_size: int = 0
    chunk_count: int = 0
    token_count: int = 0
    pending_parse_count: int = 0
    pending_index_count: int = 0
    processing_count: int = 0
    effective_permission: ResourcePermission | None = None

    @property
    def can_manage(self) -> bool:
        """Return whether the current caller has manage permission."""
        return self.effective_permission == ResourcePermission.MANAGE


@dataclass(frozen=True, slots=True)
class KnowledgeBaseDetail(KnowledgeBaseSummary):
    """Knowledge base detail read model, adding detail-page fields on top of the summary."""

    mindmap: dict[str, Any] | None = None
    sample_questions: tuple[str, ...] = ()
    files: dict[str, dict[str, Any]] | None = None
    files_truncated: bool = False
    files_page_size: int | None = None
