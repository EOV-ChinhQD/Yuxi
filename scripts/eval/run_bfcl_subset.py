#!/usr/bin/env python3
"""Run a small model-backed BFCL adapter with exact tool/argument scoring."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from pathlib import Path

from usage_tracker import UsageTracker
from yuxi.models.chat import select_model


def question_text(row: dict) -> str:
    return "\n".join(
        message.get("content", "")
        for turn in row["question"]
        for message in turn
        if message.get("role") == "user"
    )


def parse_call(raw: str) -> dict | None:
    candidates = re.findall(r"\{.*\}", raw, re.DOTALL)
    for candidate in reversed(candidates):
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("name"):
            return {"name": value["name"], "arguments": value.get("arguments") or {}}
    return None


def argument_matches(actual: dict, expected: dict) -> bool:
    if not set(actual).issubset(expected):
        return False
    for key, allowed in expected.items():
        if key not in actual:
            if "" in allowed:
                continue
            return False
        if actual[key] not in allowed:
            return False
    return True


def score_call(call: dict | None, ground_truth: list[dict]) -> tuple[bool, bool]:
    if not call:
        return False, False
    for expected_call in ground_truth:
        for name, expected_arguments in expected_call.items():
            if call["name"] == name:
                return True, argument_matches(call["arguments"], expected_arguments)
    return False, False


async def run(args: argparse.Namespace) -> dict:
    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    model = select_model(args.model, temperature=0, max_tokens=args.max_tokens)
    tracker = UsageTracker(max_calls=args.max_calls, log_path=args.usage_log)
    samples = []
    for row in rows[: args.sample_size or None]:
        if not tracker.allow():
            break
        tools = json.dumps(row["function"], ensure_ascii=False)
        prompt = (
            "You are a function-calling evaluator. Return only one JSON object with exactly "
            '`name` and `arguments` keys. Do not add markdown or explanation.\n\n'
            f"Available functions:\n{tools}\n\nUser request:\n{question_text(row)}"
        )
        started = time.perf_counter()
        raw = ""
        error = None
        try:
            response = await asyncio.wait_for(model.call(prompt, stream=False), timeout=args.timeout)
            raw = (response.content or "").strip()
            tracker.record(True, len(prompt), len(raw))
        except Exception as exc:
            error = repr(exc)
            tracker.record(False, len(prompt))
        call = parse_call(raw)
        tool_match, argument_match = score_call(call, row["ground_truth"])
        samples.append(
            {
                "id": row["id"],
                "raw_output": raw,
                "parsed_call": call,
                "tool_match": tool_match,
                "argument_exact_match": argument_match,
                "error": error,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )
    n = len(samples)
    result = {
        "benchmark": "bfcl-yuxi-adapter",
        "category": args.category,
        "model": args.model,
        "sample_size": n,
        "usage": tracker.summary(),
        "summary": {
            "tool_selection_accuracy": sum(s["tool_match"] for s in samples) / n if n else 0.0,
            "argument_exact_match": sum(s["argument_exact_match"] for s in samples) / n if n else 0.0,
            "call_error_rate": sum(bool(s["error"]) for s in samples) / n if n else 0.0,
        },
        "samples": samples,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sample_size": n, "usage": result["usage"], "summary": result["summary"]}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--category", default="simple_python")
    parser.add_argument("--model", default="ollama:qwen2.5:7b")
    parser.add_argument("--sample-size", type=int, default=0)
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--usage-log", type=Path, default=None)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
