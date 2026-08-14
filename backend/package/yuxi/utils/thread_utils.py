from __future__ import annotations

from collections.abc import Mapping


def extract_thread_id(value: object, fallback: str | None = None) -> str | None:
    """Trích xuất thread_id từ cấu trúc sự kiện đã chuẩn hóa.

    Chỉ đọc đối tượng hiện tại và một tầng trường container ổn định, tránh việc quét đệ quy nhận nhầm các cấu trúc nội bộ chưa chuẩn hóa làm căn cứ định tuyến.
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
