"""OCR engine selection, runtime configuration, and health checks."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.config.options import (
    mineru_ocr_host_opts,
    mineru_official_api_opts,
    paddleocr_api_opts,
    pp_structure_v3_ocr_host_opts,
)
from yuxi.knowledge.parser.factory import DocumentProcessorFactory
from yuxi.knowledge.parser.registry import PROCESSOR_TYPES, get_parser_metadata
from yuxi.knowledge.parser.unified import OCR_FILE_EXTENSIONS, parse_resolved_document
from yuxi.models.providers.service import get_model_provider_by_id, resolve_api_key


def get_ocr_options() -> dict[str, Any]:
    from yuxi import config

    return {
        "default_engine": config.default_ocr_engine,
        "engines": [{"engine_id": engine_id, **get_parser_metadata(engine_id)} for engine_id in PROCESSOR_TYPES],
    }


def resolve_ocr_engine_id(engine_id: str | None = None) -> str:
    from yuxi import config

    resolved = str(engine_id or config.default_ocr_engine).strip() or config.default_ocr_engine
    if resolved == "disable":
        return resolved
    if resolved not in PROCESSOR_TYPES:
        raise ValueError(f"Unsupported OCR engine: {resolved}")
    return resolved


async def resolve_ocr_task_params(
    params: dict[str, Any] | None = None,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    resolved = dict(params or {})
    engine_id = resolve_ocr_engine_id(resolved.get("ocr_engine"))
    resolved["ocr_engine"] = engine_id
    resolved.pop("ocr_engine_config", None)

    if engine_id == "disable":
        kwargs = {}
    elif db is None:
        from yuxi.storage.postgres.manager import pg_manager

        async with pg_manager.get_async_session_context() as session:
            kwargs = await _build_processor_kwargs(session, engine_id)
    else:
        kwargs = await _build_processor_kwargs(db, engine_id)

    resolved["_ocr_processor_kwargs"] = kwargs
    return resolved


async def parse_document(
    source: str,
    params: dict[str, Any] | None = None,
    db: AsyncSession | None = None,
) -> str:
    """Parse a file into Markdown with the current runtime configuration.

    This is the only document-parsing entry point business code should call. The
    function separates application-level config resolution from low-level file
    conversion: for OCR files such as PDFs and images, it first settles the final
    OCR engine, then resolves that engine's constructor params from the database
    Options, environment variables, or model providers; for plain text, Office,
    and table files, params pass through untouched to the unified parser.

    The low-level parser only receives a prepared ``ocr_engine`` and
    ``_ocr_processor_kwargs`` — it never queries the database nor cares where a
    config value came from. Callers must not invoke the internal parsing entry
    points in ``yuxi.knowledge.parser.unified`` directly, or they bypass database
    config, environment-variable fallback, and default OCR engine resolution.

    Args:
        source: Local file path or a system-supported MinIO file address.
        params: File parsing params. May include ``ocr_engine``, image storage
            location, and per-parser business params; the system default OCR
            engine applies when none is specified.
        db: Optional async database session. Callers with an existing transaction
            may pass one in for reuse; when omitted, a dedicated session is only
            created if OCR config resolution needs a database lookup.

    Returns:
        The parsed Markdown text.

    Raises:
        ValueError: Invalid OCR engine, OCR disabled for images, or unsupported file type.
        DocumentProcessorException: OCR or document parser execution failed.
        StorageError: MinIO file read failed.
    """

    resolved_params = params
    suffix = Path(source.split("?", 1)[0]).suffix.lower()
    if suffix in OCR_FILE_EXTENSIONS:
        resolved_params = await resolve_ocr_task_params(params, db)

    parsed = await parse_resolved_document(source=source, params=resolved_params)
    return parsed.markdown


async def check_all_ocr_health(db: AsyncSession) -> dict[str, Any]:
    """Check all OCR engines in parallel with the current effective config."""

    configured = []
    results = {}
    for engine_id in PROCESSOR_TYPES:
        try:
            kwargs = await _build_processor_kwargs(db, engine_id)
            configured.append((engine_id, kwargs))
        except Exception as exc:
            results[engine_id] = {"status": "error", "message": str(exc), "details": {}}

    async def check(engine_id: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        try:
            result = await asyncio.to_thread(DocumentProcessorFactory.check_health, engine_id, **kwargs)
        except Exception as exc:
            result = {"status": "error", "message": str(exc), "details": {}}
        return engine_id, result

    checked = await asyncio.gather(*(check(engine_id, kwargs) for engine_id, kwargs in configured))
    results.update(checked)
    return results


async def _build_processor_kwargs(db: AsyncSession, engine_id: str) -> dict[str, Any]:
    if engine_id == "mineru_ocr":
        opts = await mineru_ocr_host_opts.get(db)
        return {"server_url": opts["server_url"]} if opts["server_url"] else {}
    if engine_id == "mineru_official":
        opts = await mineru_official_api_opts.get(db)
        return {"api_key": opts["api_key"]} if opts["api_key"] else {}
    if engine_id == "pp_structure_v3_ocr":
        opts = await pp_structure_v3_ocr_host_opts.get(db)
        return {"server_url": opts["server_url"]} if opts["server_url"] else {}
    if engine_id == "deepseek_ocr":
        provider = await get_model_provider_by_id(db, "siliconflow-cn")
        api_key = resolve_api_key(provider) if provider and provider.is_enabled else None
        if not api_key:
            raise ValueError("siliconflow-cn model provider credentials unavailable")
        return {
            "api_key": api_key,
            "api_url": f"{provider.base_url.rstrip('/')}/chat/completions",
        }
    if engine_id in {"paddleocr_vl_1_6", "paddleocr_pp_ocrv6"}:
        opts = await paddleocr_api_opts.get(db)
        return {key: value for key, value in opts.items() if value}
    return {}
