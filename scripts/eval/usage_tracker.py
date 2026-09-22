#!/usr/bin/env python3
"""Local API-usage accounting for benchmark runners.

NVIDIA's API catalog no longer exposes a credit-balance endpoint; trial use is
rate-limited per account. This helper counts our own billable units (one count
per model.call attempt, which is exactly what RPM limits apply to) and enforces
an optional hard budget so a run can never overspend quota unattended.

Token counts are deliberately NOT estimated: GeneralResponse drops usage
metadata, and guessing tokens would produce dishonest numbers. Prompt and
completion character lengths are recorded for reference only.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path


class UsageTracker:
    def __init__(self, max_calls: int = 0, log_path: Path | None = None) -> None:
        self.max_calls = max_calls or 0
        self.log_path = log_path
        self.attempts = 0
        self.errors = 0
        self.prompt_chars = 0
        self.completion_chars = 0
        self.stopped_early = False

    def allow(self) -> bool:
        """Return True if another model call fits within budget."""
        if self.max_calls and self.attempts >= self.max_calls:
            self.stopped_early = True
            return False
        return True

    def record(self, ok: bool, prompt_chars: int = 0, completion_chars: int = 0) -> None:
        self.attempts += 1
        if not ok:
            self.errors += 1
        self.prompt_chars += prompt_chars
        self.completion_chars += completion_chars

    def summary(self) -> dict:
        return {
            "model_calls": self.attempts,
            "call_errors": self.errors,
            "max_calls_budget": self.max_calls,
            "stopped_early": self.stopped_early,
            "prompt_chars": self.prompt_chars,
            "completion_chars": self.completion_chars,
        }

    def write_log(self, script: str, model: str, extra: dict | None = None) -> None:
        if not self.log_path:
            return
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "script": script,
            "model": model,
            **self.summary(),
            **(extra or {}),
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
