#!/usr/bin/env python3
"""Run a stratified When2Call decision benchmark with a local model."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from pathlib import Path

from yuxi.models.chat import select_model

from usage_tracker import UsageTracker


def _load_rows(path: Path, per_label: int) -> list[dict]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    selected = []
    for label in ("cannot_answer", "request_for_info", "tool_call"):
        selected.extend([row for row in rows if row["decision"] == label][:per_label])
    return selected


def _parse_prediction(content: str) -> dict:
    try:
        start = content.find("{")
        payload = json.loads(content[start:] if start >= 0 else content)
    except (TypeError, json.JSONDecodeError):
        return {"decision": "parse_error", "raw_output": content}
    return {
        "decision": payload.get("decision", "parse_error"),
        "tool_name": payload.get("tool_name"),
        "raw_output": content,
    }


async def run(args: argparse.Namespace) -> dict:
    rows = _load_rows(args.input, args.per_label)
    model_kwargs = {"temperature": 0, "max_tokens": args.max_tokens}
    if args.native_ollama:
        model_kwargs.update(native_ollama=True, think=False)
    model = select_model(args.model, **model_kwargs)
    tracker = UsageTracker(max_calls=args.max_calls, log_path=args.usage_log)
    results = []

    for row in rows:
        if not tracker.allow():
            break
        tools = json.dumps(
            [json.loads(tool) for tool in row["tools"]], ensure_ascii=False
        )
        prompt = (
            'Return only JSON: {"decision":"cannot_answer|request_for_info|tool_call",'
            '"tool_name":null|string}.\n'
            "Use cannot_answer when no available tool is relevant. Use request_for_info "
            "when a relevant tool exists but at least one required argument is missing. "
            "Use tool_call only when a relevant tool exists and all required arguments "
            "are present. Do not call a tool merely because its name looks related; "
            "inspect its description and required parameters.\n"
            f"User request: {row['input_text']}\nAvailable tools: {tools}"
        )
        started = time.perf_counter()
        try:
            response = await asyncio.wait_for(
                model.call(prompt, stream=False), timeout=args.timeout
            )
            tracker.record(True, len(prompt), len(response.content or ""))
            prediction = _parse_prediction(response.content or "")
        except Exception as error:
            tracker.record(False, len(prompt))
            prediction = {"decision": "error", "raw_output": repr(error)}
        expected = row["decision"]
        results.append(
            {
                "sample_id": row["sample_id"],
                "expected": expected,
                "predicted": {
                    key: value
                    for key, value in prediction.items()
                    if key != "raw_output"
                },
                "correct": prediction.get("decision") == expected,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "raw_output": prediction.get("raw_output", ""),
            }
        )

    tracker.write_log(
        "run_when2call_local.py",
        args.model,
        {"output": str(args.output), "sample_size": len(results)},
    )
    return {
        "benchmark": "when2call",
        "model": args.model,
        "sample_size": len(results),
        "usage": tracker.summary(),
        "class_counts": dict(Counter(row["expected"] for row in results)),
        "decision_accuracy": sum(row["correct"] for row in results) / len(results) if results else 0.0,
        "per_class_accuracy": {
            label: (sum(row["correct"] for row in results if row["expected"] == label)
            / sum(row["expected"] == label for row in results))
            if any(row["expected"] == label for row in results)
            else None
            for label in ("cannot_answer", "request_for_info", "tool_call")
        },
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="ollama:qwen3:8b")
    parser.add_argument("--per-label", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--usage-log", type=Path, default=None)
    parser.add_argument("--native-ollama", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "results"},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
