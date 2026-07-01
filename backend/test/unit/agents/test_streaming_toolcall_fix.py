"""Regression test: streaming tool_call continues empty string name/id normalization to avoid the cumulative defects of LangGraph v3.

Background: v3 streaming accumulation is "post value coverage" for tool_call Field, part OpenAI compatible provider
(siliconflow, Alibaba Cloud Bailian, etc.) If you issue name/id as an empty string "" in the sequel, it will overwrite the first one of
True value (lost name / Lost id), resulting in tool results unable to be associated by tool_call_id.
`_normalize_tool_call_chunks` converts empty strings to None (aligned with OpenAI official) to avoid this.

This test uses fake streaming Model to deterministically reproduce the defect (no network/API key required) and verify that the repair is effective.
"""

import pytest
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_core.messages.tool import tool_call_chunk
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from yuxi.agents.models import _normalize_tool_call_chunks


@tool
def get_weather(city: str) -> str:
    """Query the weather in a specified city."""
    return f"{city} Sunny 25℃"


class _FakeSiliconFlowModel(BaseChatModel):
    """Simulating SiliconFlow flow: first piece with name+id, sequel name=''(empty string).

    `apply_fix=True` is called after the sequel is produced `_normalize_tool_call_chunks`，
    Forked `_ToolCallChunkFixChatOpenAI` normalization behavior.
    """

    apply_fix: bool = False
    call_count: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake-siliconflow"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        self.call_count += 1
        call_id = f"call_{self.call_count}"
        deltas = [
            tool_call_chunk(name="get_weather", args="", id=call_id, index=0),
            tool_call_chunk(name="", args='{"city": ', id=None, index=0),
            tool_call_chunk(name="", args='"Beijing"}', id=None, index=0),
        ]
        for delta in deltas:
            chunk = ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=[delta]))
            if self.apply_fix:
                _normalize_tool_call_chunks(chunk.message)
            yield chunk

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        raise NotImplementedError("Chỉ sử dụng cho bài test streaming")


async def _run_and_get_tool_calls(model: BaseChatModel) -> list[dict]:
    agent = create_agent(model=model, tools=[get_weather], checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "t"}, "recursion_limit": 4}
    graph_input = {"messages": [HumanMessage("Beijing weather?")]}
    try:
        run = await agent.astream_events(graph_input, config=config, version="v3")
        async for _ in run:
            pass
    except GraphRecursionError:
        pass  # Loss of name will lead to an infinite loop. Here we only take the tool_call that has fallen into state.
    state = await agent.aget_state(config)
    tool_calls: list[dict] = []
    for msg in state.values.get("messages", []):
        if msg.type == "ai" and msg.tool_calls:
            tool_calls.extend(msg.tool_calls)
    return tool_calls


def test_normalize_replaces_empty_string_with_none():
    msg = AIMessageChunk(
        content="",
        tool_call_chunks=[
            tool_call_chunk(name="", args="{}", id="", index=0),
            tool_call_chunk(name="foo", args="{}", id="abc", index=1),
        ],
    )
    _normalize_tool_call_chunks(msg)
    assert msg.tool_call_chunks[0]["name"] is None
    assert msg.tool_call_chunks[0]["id"] is None
    # Non-null values ​​remain unchanged
    assert msg.tool_call_chunks[1]["name"] == "foo"
    assert msg.tool_call_chunks[1]["id"] == "abc"


async def test_v3_loses_name_without_fix():
    """Control group: Reproduce upstream defects——When not normalized, the real name of tool_call accumulated by v3 is overwritten by an empty string."""
    tool_calls = await _run_and_get_tool_calls(_FakeSiliconFlowModel(apply_fix=False))
    assert tool_calls, "At least one tool_call should be accumulated"
    assert tool_calls[0]["name"] == "", "When not repaired, the real name of the first film should be overwritten by the empty string of the sequel."


async def test_v3_preserves_name_with_fix():
    """Repair group: tool_call accumulated in v3 after normalizing the empty string retains the complete name/id with parameters."""
    tool_calls = await _run_and_get_tool_calls(_FakeSiliconFlowModel(apply_fix=True))
    assert tool_calls, "At least one tool_call should be accumulated"
    assert all(tc["name"] == "get_weather" for tc in tool_calls)
    assert all(tc["id"] for tc in tool_calls)
    assert tool_calls[0]["args"] == {"city": "Beijing"}
