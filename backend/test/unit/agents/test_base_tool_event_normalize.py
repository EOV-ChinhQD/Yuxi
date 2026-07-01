from __future__ import annotations

from langchain_core.messages import ToolMessage
from langgraph.types import Command

from yuxi.agents.base import _json_safe, _normalize_tool_event_data


def _command_tool_finished(tool_call_id: str) -> dict:
    """Simulate write_todos / task tool for this type of tool that returns a Command-finished event."""
    tool_message = ToolMessage(
        content="Updated todo list to [{'content': 'step one', 'status': 'in_progress'}]",
        tool_call_id=tool_call_id,
    )
    command = Command(update={"todos": [{"content": "step one", "status": "in_progress"}], "messages": [tool_message]})
    return {"event": "tool-finished", "tool_call_id": tool_call_id, "output": command}


def test_command_tool_finished_extracts_tool_message_for_frontend_association():
    tool_call_id = "call_abc"
    data = _normalize_tool_event_data(_command_tool_finished(tool_call_id))
    safe = _json_safe(data)
    output = safe["output"]

    # The front end associates results by tool_call_id and requires output to be an object (dict), otherwise it will be discarded.
    assert isinstance(output, dict)
    assert output["tool_call_id"] == tool_call_id
    assert output["type"] == "tool"
    assert "step one" in output["content"]


def test_command_tool_finished_prefers_message_matching_tool_call_id():
    other = ToolMessage(content="Other tool results", tool_call_id="call_other")
    target = ToolMessage(content="target result", tool_call_id="call_target")
    data = {
        "event": "tool-finished",
        "tool_call_id": "call_target",
        "output": Command(update={"messages": [other, target]}),
    }

    output = _normalize_tool_event_data(data)["output"]
    assert isinstance(output, ToolMessage)
    assert output.tool_call_id == "call_target"
    assert output.content == "target result"


def test_regular_dict_output_is_left_untouched():
    data = {"event": "tool-finished", "tool_call_id": "call_x", "output": {"content": "plain", "type": "tool"}}
    assert _normalize_tool_event_data(data)["output"] == {"content": "plain", "type": "tool"}


def test_tool_started_event_is_left_untouched():
    data = {"event": "tool-started", "tool_call_id": "call_x", "output": None}
    assert _normalize_tool_event_data(data) is data


def test_command_without_tool_message_is_left_untouched():
    command = Command(update={"todos": [{"content": "No news", "status": "pending"}]})
    data = {"event": "tool-finished", "tool_call_id": "call_x", "output": command}
    assert _normalize_tool_event_data(data)["output"] is command
