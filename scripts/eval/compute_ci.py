#!/usr/bin/env python3
"""Wilson 95% confidence intervals for benchmark rates (offline, no API calls).

Usage: python compute_ci.py <result.json>...  Prints rate ± CI for the known
result schemas (when2call, vietnamese-function-calling, e2e, nli).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    if not trials:
        return (0.0, 0.0)
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


def report(name: str, successes: int, trials: int) -> None:
    low, high = wilson(successes, trials)
    rate = successes / trials if trials else 0.0
    print(f"{name}: {rate:.4f} (n={trials}, 95% CI [{low:.4f}, {high:.4f}])")


def main() -> None:
    for path in (Path(arg) for arg in sys.argv[1:]):
        data = json.loads(path.read_text(encoding="utf-8"))
        print(f"== {path.name} ==")
        benchmark = data.get("benchmark", "")
        if benchmark == "when2call":
            for row in data["results"]:
                pass
            total = sum(1 for row in data["results"] if row["correct"])
            report("decision_accuracy", total, len(data["results"]))
            for label, value in data.get("per_class_accuracy", {}).items():
                if value is None:
                    continue
                rows = [row for row in data["results"] if row["expected"] == label]
                report(f"  {label}", sum(1 for row in rows if row["correct"]), len(rows))
        elif benchmark == "vietnamese-function-calling":
            report("tool_match", sum(1 for r in data["results"] if r["tool_match"]), len(data["results"]))
            report("exact_match", sum(1 for r in data["results"] if r["exact_match"]), len(data["results"]))
        elif benchmark == "uit-viquad-2-e2e":
            for arm, summary in data.get("summary", {}).items():
                n = summary["sample_size"]
                report(f"{arm} em", round(summary["em"] * n), n)
        elif benchmark == "viwikifc":
            for config, payload in data.get("configs", {}).items():
                samples = payload["samples"]
                report(
                    f"{config} accuracy",
                    sum(1 for s in samples if s["expected"] == s["predicted"]),
                    len(samples),
                )
        print()


if __name__ == "__main__":
    main()
