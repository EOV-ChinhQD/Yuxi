#!/usr/bin/env python3
"""Small trace-first executor used by the AgentKit benchmark harness."""

from __future__ import annotations

import inspect
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


class DecisionProvider(Protocol):
    async def decide(
        self, task: Mapping[str, Any], tools: list[dict[str, Any]]
    ) -> dict[str, Any]: ...


@dataclass
class AgentKitTrace:
    task_id: str
    decision: str | None = None
    selected_tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    tool_result: Any = None
    final_answer: str | None = None
    error: str | None = None
    recovery_attempted: bool = False
    latency_ms: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "decision": self.decision,
            "selected_tool": self.selected_tool,
            "arguments": self.arguments,
            "tool_result": self.tool_result,
            "final_answer": self.final_answer,
            "error": self.error,
            "recovery_attempted": self.recovery_attempted,
            "latency_ms": self.latency_ms,
        }


class AgentKitExecutor:
    def __init__(
        self,
        tools: list[dict[str, Any]],
        handlers: Mapping[str, Callable[..., Any]] | None = None,
    ) -> None:
        self.tools = tools
        self.tool_names = {tool["name"] for tool in tools}
        self.handlers = dict(handlers or {})

    async def run(
        self, task: Mapping[str, Any], provider: DecisionProvider
    ) -> AgentKitTrace:
        started = time.perf_counter()
        trace = AgentKitTrace(task_id=str(task["task_id"]))
        decision = await provider.decide(task, self.tools)
        trace.decision = decision.get("decision")
        trace.selected_tool = decision.get("tool_name")
        trace.arguments = decision.get("arguments") or {}
        trace.final_answer = decision.get("final_answer")

        if trace.decision != "tool_call":
            trace.latency_ms = (time.perf_counter() - started) * 1000
            return trace
        if trace.selected_tool not in self.tool_names:
            trace.error = f"Unknown tool: {trace.selected_tool}"
            trace.latency_ms = (time.perf_counter() - started) * 1000
            return trace

        tool = next(tool for tool in self.tools if tool["name"] == trace.selected_tool)
        required = tool.get("parameters", {}).get("required", [])
        missing = [name for name in required if name not in trace.arguments]
        if missing:
            trace.error = f"Missing required arguments: {', '.join(missing)}"
            trace.latency_ms = (time.perf_counter() - started) * 1000
            return trace

        handler = self.handlers.get(trace.selected_tool)
        if handler is None:
            trace.error = f"No handler bound for tool: {trace.selected_tool}"
            trace.latency_ms = (time.perf_counter() - started) * 1000
            return trace
        try:
            result = handler(**trace.arguments)
            trace.tool_result = await result if inspect.isawaitable(result) else result
        except Exception as error:
            trace.error = f"{type(error).__name__}: {error}"
        trace.latency_ms = (time.perf_counter() - started) * 1000
        return trace
