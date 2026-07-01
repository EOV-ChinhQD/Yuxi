from __future__ import annotations

from yuxi.agents.toolkits.registry import tool


def test_tool_decorator_sets_handle_tool_error():
    """Test passed @tool Whether the tool registered by the decorator automatically sets handle_tool_error to True"""

    @tool(
        category="test",
        display_name="Công cụ test",
        description="Đây là công cụ unit test",
    )
    def my_test_tool(arg: str) -> str:
        return f"hello {arg}"

    assert my_test_tool.name == "my_test_tool"
    assert my_test_tool.handle_tool_error is True
