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


def parse_call(raw: str) -> list[dict] | None:
    decoder = json.JSONDecoder()
    starts = [index for index, char in enumerate(raw) if char in "[{" ]
    if not starts:
        return None
    first_start = starts[0]
    try:
        first, first_end = decoder.raw_decode(raw[first_start:])
    except json.JSONDecodeError:
        first = None
        first_end = 0
    if isinstance(first, list) and all(isinstance(item, dict) and item.get("name") for item in first):
        values = list(first)
    elif isinstance(first, dict) and first.get("name"):
        values = [first]
        offset = first_start + first_end
        for index in range(offset, len(raw)):
            if raw[index] != "{":
                continue
            try:
                value, _ = decoder.raw_decode(raw[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get("name"):
                values.append(value)
    else:
        return None
    return [
        {"name": item["name"], "arguments": item.get("arguments") or {}}
        for item in values
    ]


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


def score_call(calls: list[dict] | None, ground_truth: list[dict]) -> tuple[bool, bool]:
    if not calls:
        return False, False
    expected_calls = [
        {"name": name, "arguments": arguments}
        for expected_call in ground_truth
        for name, arguments in expected_call.items()
    ]
    if len(calls) == 1 and len(expected_calls) > 1:
        call = calls[0]
        if isinstance(call["arguments"], list):
            calls = [
                {"name": call["name"], "arguments": arguments}
                for arguments in call["arguments"]
            ]
        elif isinstance(call["arguments"], dict):
            count = len(expected_calls)
            values = call["arguments"]
            expanded = []
            for index in range(count):
                arguments = {
                    key: value[index] if isinstance(value, list) and len(value) == count else value
                    for key, value in values.items()
                }
                expanded.append({"name": call["name"], "arguments": arguments})
            calls = expanded
    if len(calls) != len(expected_calls):
        return False, False
    unmatched = list(expected_calls)
    argument_match = True
    for call in calls:
        match = next((item for item in unmatched if item["name"] == call["name"]), None)
        if match is None:
            return False, False
        unmatched.remove(match)
        argument_match = argument_match and argument_matches(call["arguments"], match["arguments"])
    return True, argument_match


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
