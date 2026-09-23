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


def _load_tools(raw_tools: list[str]) -> list[dict]:
    return [json.loads(tool) for tool in raw_tools]


def _parse_relevance_gate(content: str, known_names: set[str]) -> list[str] | None:
    try:
        start = content.find("{")
        payload = json.loads(content[start:] if start >= 0 else content)
    except (TypeError, json.JSONDecodeError):
        return None
    names = payload.get("relevant_tool_names")
    if not isinstance(names, list):
        return None
    return [name for name in names if isinstance(name, str) and name in known_names]


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
        started = time.perf_counter()
        tool_records = _load_tools(row["tools"])
        tool_by_name = {tool["name"]: tool for tool in tool_records}
        gate_status = {"enabled": args.relevance_gate, "selected_tools": None}
        candidate_tools = tool_records
        if args.relevance_gate:
            gate_prompt = (
                'Return only JSON: {"relevant_tool_names":["..."]}. '
                "Select tools that can actually fulfill the user's request based on the tool description and "
                "argument semantics. Do not select a tool because a word merely overlaps. A food-only tool is not "
                "relevant to changing a beverage; a tool requiring an unavailable resource is not relevant. "
                "Keep a tool if the request is in its domain even when a required argument is missing, because the "
                "next decision may need request_for_info. Return an empty list when no tool is relevant.\n"
                f"User request: {row['input_text']}\nAvailable tools: "
                f"{json.dumps(tool_records, ensure_ascii=False)}"
            )
            if tracker.allow():
                try:
                    gate_response = await asyncio.wait_for(
                        model.call(gate_prompt, stream=False), timeout=args.timeout
                    )
                    tracker.record(True, len(gate_prompt), len(gate_response.content or ""))
                    selected_names = _parse_relevance_gate(gate_response.content or "", set(tool_by_name))
                    if selected_names is not None:
                        candidate_tools = [tool_by_name[name] for name in selected_names]
                        gate_status["selected_tools"] = selected_names
                    else:
                        gate_status["status"] = "invalid_output_fallback_all_tools"
                except Exception as error:
                    tracker.record(False, len(gate_prompt))
                    gate_status["status"] = f"error_fallback_all_tools:{type(error).__name__}"
            else:
                break
        tools = json.dumps(candidate_tools, ensure_ascii=False)
        if args.relevance_gate and not candidate_tools:
            prediction = {"decision": "cannot_answer", "tool_name": None}
        else:
            if not tracker.allow():
                break
            prompt = (
                'Return only JSON: {"decision":"cannot_answer|request_for_info|tool_call",'
                '"tool_name":null|string}.\n'
                "Use cannot_answer when no available tool is relevant. Use request_for_info "
                "when a relevant tool exists but at least one required argument is missing. Use tool_call only "
                "when a relevant tool exists and all required arguments are present. Do not call a tool merely "
                "because its name looks related; inspect its description and required parameters.\n"
                f"User request: {row['input_text']}\nAvailable relevant tools: {tools}"
            )
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
                "relevance_gate": gate_status,
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
    parser.add_argument("--relevance-gate", action=argparse.BooleanOptionalAction, default=True)
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
