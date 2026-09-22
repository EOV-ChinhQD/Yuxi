#!/usr/bin/env python3
"""Validate agent benchmark contracts before model-backed tool-call scoring."""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def parse_tool(value: str) -> dict:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return ast.literal_eval(value)


def parse_expected(value: str) -> dict | None:
    if value in {"cannot_answer", "None", "none", "null"}:
        return None
    match = re.search(r"\{.*\}", value, re.DOTALL)
    if not match:
        raise ValueError(f"Cannot parse expected tool call: {value[:120]}")
    return json.loads(match.group(0))


def validate(path: Path, dataset: str) -> dict:
    rows = load_jsonl(path)
    invalid = []
    expected_tool_names = Counter()
    decision_counts = Counter()
    for row in rows:
        try:
            tools = [parse_tool(tool) for tool in row["tools"]]
            tool_names = {tool["name"] for tool in tools}
            if dataset == "when2call":
                expected = row["expected_tool_call"]
                if expected not in {"cannot_answer", "tool_call", "request_for_info"}:
                    raise ValueError(f"unknown When2Call decision: {expected}")
                if row.get("decision") != expected:
                    raise ValueError("decision does not match expected decision")
                decision_counts[expected] += 1
                continue
            expected = parse_expected(row["expected_tool_call"])
            if expected is not None:
                expected_tool_names[expected["name"]] += 1
                if expected["name"] not in tool_names:
                    raise ValueError(
                        f"expected tool {expected['name']} is not declared"
                    )
                if not isinstance(expected.get("arguments"), dict):
                    raise ValueError("expected arguments must be an object")
            decision_counts[str(row.get("decision"))] += 1
        except Exception as error:
            invalid.append({"sample_id": row.get("sample_id"), "error": str(error)})
    return {
        "dataset": dataset,
        "records": len(rows),
        "valid_records": len(rows) - len(invalid),
        "invalid_records": len(invalid),
        "decision_counts": dict(decision_counts),
        "expected_tool_names": dict(expected_tool_names),
        "errors": invalid[:20],
        "status": "ready_for_model_scoring" if not invalid else "invalid",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vietnamese", type=Path, required=True)
    parser.add_argument("--when2call", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "benchmark": "agent_contract_validation",
        "datasets": [
            validate(args.vietnamese, "vietnamese-function-calling"),
            validate(args.when2call, "when2call"),
        ],
        "model_score": None,
        "note": "This validates benchmark schemas and gold tool references; it does not score a model.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
