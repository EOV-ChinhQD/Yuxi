from dataclasses import dataclass, field

from yuxi.agents.context import BaseContext


@dataclass(kw_only=True)
class SubAgentContext(BaseContext):
    parent_thread_id: str | None = field(
        default=None,
        metadata={"name": "Parent thread ID", "configurable": False, "hide": True},
    )
    file_thread_id: str | None = field(
        default=None,
        metadata={"name": "File thread ID", "configurable": False, "hide": True},
    )
    skills_thread_id: str | None = field(
        default=None,
        metadata={"name": "Skills thread ID", "configurable": False, "hide": True},
    )
    is_subagent_runtime: bool = field(
        default=False,
        metadata={"name": "Sub-agent runtime", "configurable": False, "hide": True},
    )
