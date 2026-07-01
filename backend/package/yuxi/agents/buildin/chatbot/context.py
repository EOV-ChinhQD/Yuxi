from dataclasses import dataclass, field

from yuxi.agents.context import BaseContext


@dataclass(kw_only=True)
class ChatBotContext(BaseContext):
    subagents: list[str] | None = field(
        default=None,
        metadata={
            "name": "Sub-agents",
            "options": [],
            "description": "Optional list of subagents, empty means enabling all subagents visible to the current user.",
            "type": "list",
            "kind": "subagents",
        },
    )
