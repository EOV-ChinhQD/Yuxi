"""Steer middleware for the main session."""

from langchain.agents.middleware import AgentMiddleware, hook_config


class SteerMiddleware(AgentMiddleware):
    """End the current Run at the safe lifecycle boundary so the queue can run Steer first."""

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state, runtime):  # noqa: ARG002
        return await self._jump_if_steer_requested(runtime)

    @hook_config(can_jump_to=["end"])
    async def aafter_model(self, state, runtime):
        """Fallback for tool-free model turns so Steer is not missed after the last check."""
        if _last_message_has_tool_calls(state):
            return None
        return await self._jump_if_steer_requested(runtime)

    async def _jump_if_steer_requested(self, runtime):
        from yuxi.services.agent_request_queue_service import should_end_run_for_steer

        run_id = getattr(runtime.context, "run_id", None)
        if not run_id or not await should_end_run_for_steer(run_id):
            return None
        return {"jump_to": "end"}


def _last_message_has_tool_calls(state) -> bool:
    """Check whether the last model message still needs tool execution to avoid skipping a tool batch."""
    messages = state.get("messages") if isinstance(state, dict) else None
    if not messages:
        return False
    last_message = messages[-1]
    if isinstance(last_message, dict):
        return bool(last_message.get("tool_calls"))
    return bool(getattr(last_message, "tool_calls", None))
