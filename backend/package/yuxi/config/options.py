"""Generic option definitions, persistence, validation, and runtime resolution.

System code maintains `params`; administrators only edit `value`. This module
only supports controlled primitive fields — no arbitrary dynamic components or
executable protocols; OCR is just the first consumer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from pydantic import HttpUrl, TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import ConfigOption


@dataclass(frozen=True, slots=True)
class Option:
    """A generic option defined by code and read from the database on every access."""

    key: str
    name: str
    description: str
    params: dict[str, Any]

    async def get(self, db: AsyncSession | None = None) -> dict[str, Any]:
        if db is None:
            from yuxi.storage.postgres.manager import pg_manager

            async with pg_manager.get_async_session_context() as session:
                return await self.get(session)

        record = await get_option(db, self.key)
        if record is None:
            raise ValueError(f"Option does not exist: {self.key}")
        stored = dict(record.value or {})
        resolved = {}
        for field in _fields(record):
            field_key = field["key"]
            stored_value = stored.get(field_key)
            if field.get("type") == "list[str]" and field_key in stored:
                resolved[field_key] = stored[field_key]
                continue

            environment_value = os.getenv(field.get("environment", ""))
            resolved[field_key] = stored_value or environment_value or field.get("default")
        return resolved


mineru_ocr_host_opts = Option(
    key="mineru_ocr_host_opts",
    name="MinerU Service",
    description="Configure the self-hosted MinerU service address.",
    params={
        "fields": [
            {
                "key": "server_url",
                "label": "Service address",
                "type": "url",
                "environment": "MINERU_API_URI",
                "placeholder": "http://mineru-api:30001",
                "help": "Reads MINERU_API_URI when left empty.",
            }
        ]
    },
)

mineru_official_api_opts = Option(
    key="mineru_official_api_opts",
    name="MinerU Official",
    description="Configure the MinerU official cloud service credentials.",
    params={
        "fields": [
            {
                "key": "api_key",
                "label": "API Key",
                "type": "password",
                "environment": "MINERU_API_KEY",
                "sensitive": True,
                "help": "Reads MINERU_API_KEY when left empty; prefer environment variables.",
            }
        ]
    },
)

pp_structure_v3_ocr_host_opts = Option(
    key="pp_structure_v3_ocr_host_opts",
    name="PP-Structure-V3 Service",
    description="Configure the self-hosted PaddleX service address.",
    params={
        "fields": [
            {
                "key": "server_url",
                "label": "Service address",
                "type": "url",
                "environment": "PADDLEX_URI",
                "placeholder": "http://paddlex:8080",
                "help": "Reads PADDLEX_URI when left empty.",
            }
        ]
    },
)

paddleocr_api_opts = Option(
    key="paddleocr_api_opts",
    name="PaddleOCR API",
    description="Shared configuration for PaddleOCR-VL and PP-OCRv6.",
    params={
        "fields": [
            {
                "key": "api_url",
                "label": "API address",
                "type": "url",
                "environment": "PADDLEOCR_API_URL",
                "placeholder": "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs",
                "help": "Reads PADDLEOCR_API_URL when left empty.",
            },
            {
                "key": "api_token",
                "label": "Access Token",
                "type": "password",
                "environment": "PADDLEOCR_API_TOKEN",
                "sensitive": True,
                "help": "Reads PADDLEOCR_API_TOKEN when left empty; prefer environment variables.",
            },
        ]
    },
)

remote_skill_source_policy = Option(
    key="remote_skill_source_policy",
    name="Remote Skill Sources",
    description="Configure the source domains allowed for remote Skill installation.",
    params={
        "fields": [
            {
                "key": "allowed_hosts",
                "label": "Allowed source domains",
                "type": "list[str]",
                "default": ["github.com", "modelscope.cn"],
                "help": "Exact domain match only; saving an empty list disables remote installation.",
            }
        ]
    },
)

OPTION_DEFINITIONS = {
    option.key: option
    for option in (
        mineru_ocr_host_opts,
        mineru_official_api_opts,
        pp_structure_v3_ocr_host_opts,
        paddleocr_api_opts,
        remote_skill_source_policy,
    )
}

_URL_ADAPTER = TypeAdapter(HttpUrl)


async def ensure_options_in_db(db: AsyncSession) -> list[ConfigOption]:
    """Idempotently sync system definitions while preserving administrator-saved values."""

    existing = {record.key: record for record in await list_options(db)}
    synced = []
    for key, definition in OPTION_DEFINITIONS.items():
        record = existing.get(key)
        if record is None:
            record = ConfigOption(
                key=key,
                name=definition.name,
                description=definition.description,
                params=definition.params,
                value={},
                created_by="system",
                updated_by="system",
            )
            db.add(record)
        else:
            record.name = definition.name
            record.description = definition.description
            record.params = definition.params
        synced.append(record)
    await db.flush()
    return synced


async def list_options(db: AsyncSession) -> list[ConfigOption]:
    result = await db.execute(select(ConfigOption).order_by(ConfigOption.id.asc()))
    return list(result.scalars().all())


async def get_option(db: AsyncSession, key: str) -> ConfigOption | None:
    statement = select(ConfigOption).where(ConfigOption.key == key).execution_options(populate_existing=True)
    result = await db.execute(statement)
    return result.scalar_one_or_none()


def serialize_option(record: ConfigOption) -> dict[str, Any]:
    """Return the form definition and values; secrets only expose source and masked preview."""

    value = dict(record.value or {})
    sensitive_configured = {}
    sensitive_state = {}
    for field in _fields(record):
        if not field.get("sensitive"):
            continue
        field_key = field["key"]
        stored_value = str(value.get(field_key) or "")
        environment_value = os.getenv(field.get("environment", ""))
        if stored_value:
            state = {
                "source": "database",
                "configured": True,
                "preview": _mask_sensitive_value(stored_value),
            }
        elif environment_value:
            state = {"source": "environment", "configured": True, "preview": None}
        else:
            state = {"source": "none", "configured": False, "preview": None}
        sensitive_state[field_key] = state
        sensitive_configured[field_key] = state["configured"]
        value[field_key] = ""
    return {
        "key": record.key,
        "name": record.name,
        "description": record.description,
        "params": record.params or {},
        "value": value,
        "sensitive_configured": sensitive_configured,
        "sensitive_state": sensitive_state,
    }


async def update_option_value(
    db: AsyncSession,
    key: str,
    value: dict[str, Any],
    updated_by: str,
) -> ConfigOption | None:
    record = await get_option(db, key)
    if record is None:
        return None

    fields = {field["key"]: field for field in _fields(record)}
    unknown = set(value) - set(fields)
    if unknown:
        raise ValueError(f"Unknown option fields: {', '.join(sorted(unknown))}")

    updated = dict(record.value or {})
    for field_key, raw_value in value.items():
        field = fields[field_key]
        updated[field_key] = _normalize_value(field, raw_value)
    record.value = updated
    record.updated_by = updated_by
    await db.flush()
    return record


def _fields(record: ConfigOption) -> list[dict[str, Any]]:
    return list((record.params or {}).get("fields") or [])


def _normalize_value(field: dict[str, Any], value: Any) -> Any:
    if field.get("type") == "list[str]":
        if not isinstance(value, list):
            raise ValueError("Option value must be a list")
        if not all(isinstance(item, str) for item in value):
            raise ValueError("Option value must be a string list")
        return value

    normalized = str(value or "").strip()
    if field.get("type") == "url" and normalized:
        return str(_URL_ADAPTER.validate_python(normalized))
    return normalized


def _mask_sensitive_value(value: str) -> str:
    if len(value) == 1:
        return "*******"
    if len(value) <= 4:
        return f"{value[0]}*******{value[-1]}"
    return f"{value[:2]}*******{value[-2:]}"
