from __future__ import annotations

from collections.abc import Mapping


def extract_thread_id(value: object, fallback: str | None = None) -> str | None:
    """Extract thread_id from normalized event structure.

    Only read current object and one level of stable fields to prevent misrouting.
    """
    if not isinstance(value, Mapping):
        return fallback

    for source in (
        value,
        value.get("configurable"),
        value.get("metadata"),
        value.get("stream_event"),
        value.get("meta"),
    ):
        if not isinstance(source, Mapping):
            continue
        thread_id = source.get("thread_id")
        if isinstance(thread_id, str) and thread_id.strip():
            return thread_id.strip()

    return fallback
