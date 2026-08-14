from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from yuxi.agents.state import BaseState


class SubAgentRunState(TypedDict, total=False):
    id: str
    run_id: str
    subagent_slug: str
    subagent_name: str
    child_thread_id: str
    description: str
    status: Literal["pending", "running", "completed", "failed", "cancel_requested", "cancelled", "interrupted"]
    created_at: str
    completed_at: str
    error: str | None
    artifacts: list[str]
    events_url: str
    result_url: str


def merge_subagent_runs(
    existing: list[SubAgentRunState] | None,
    new: list[SubAgentRunState] | None,
) -> list[SubAgentRunState]:
    """LangGraph state reducer: Hợp nhất gia tăng bản tóm tắt chạy của Subagent do Agent cha ghi nhận.

    `run_id` là danh tính của một lần thực thi Subagent thực tế. Chỉ `run_id` giống nhau mới cập nhật cùng một bản ghi;
    Các bản ghi gia tăng không có `run_id` sẽ được thêm trực tiếp vào cuối danh sách, không sử dụng ID gọi công cụ hoặc ID luồng con để khớp trạng thái cũ.
    """
    if existing is None:
        return list(new or [])
    if new is None:
        return existing

    merged_items = []
    run_id_map = {}

    for item in existing:
        item_copy = dict(item)
        run_id = item_copy.get("run_id")
        if run_id:
            run_id_map[run_id] = item_copy
        merged_items.append(item_copy)

    for item in new:
        run_id = item.get("run_id")
        if run_id and run_id in run_id_map:
            run_id_map[run_id].update(item)
        else:
            item_copy = dict(item)
            merged_items.append(item_copy)
            if run_id:
                run_id_map[run_id] = item_copy

    return merged_items


class ChatBotState(BaseState):
    subagent_runs: Annotated[list[SubAgentRunState], merge_subagent_runs]
