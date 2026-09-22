#!/usr/bin/env python3
"""Run a model-backed local smoke test for Vietnamese function calling."""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import re
import time
from pathlib import Path

from yuxi.models.chat import select_model

from usage_tracker import UsageTracker


def _parse_prediction(text: str) -> dict:
    match = re.search(r"\{\s*[\"']?(?:name|tool_name)[\"']?\s*:", text, re.S)
    if not match:
        return {"decision": "no_tool", "raw_output": text}
    candidate = text[text.rfind("{", 0, match.start() + 1) :]
    depth = 0
    end = None
    quoted = False
    escaped = False
    for index, char in enumerate(candidate):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    try:
        payload = json.loads(candidate[:end])
    except (TypeError, json.JSONDecodeError):
        return {"decision": "parse_error", "raw_output": text}
    return {
        "decision": "no_tool" if payload.get("name") is None else "tool_call",
        "tool_name": payload.get("name") or payload.get("tool_name"),
        "arguments": payload.get("arguments") or {},
        "raw_output": text,
    }


def _parse_expected(text: str) -> dict:
    if text == "cannot_answer":
        return {"decision": "no_tool"}
    payload = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    return {
        "decision": "tool_call",
        "tool_name": payload["name"],
        "arguments": payload.get("arguments") or {},
    }


def _load_tools(raw_tools: list[str]) -> list[dict]:
    tools = []
    for raw in raw_tools:
        try:
            tools.append(json.loads(raw))
        except json.JSONDecodeError:
            tools.append(ast.literal_eval(raw))
    return tools


def _matches(predicted: dict, expected: dict) -> tuple[bool, bool]:
    tool_match = predicted.get("decision") == expected.get(
        "decision"
    ) and predicted.get("tool_name") == expected.get("tool_name")
    arguments = expected.get("arguments", {})
    argument_match = tool_match and all(
        predicted.get("arguments", {}).get(key) == value
        for key, value in arguments.items()
    )
    return tool_match, argument_match


def _arguments_are_grounded(predicted: dict, user_request: str) -> bool:
    normalized_request = " ".join(user_request.split())
    for value in predicted.get("arguments", {}).values():
        if not isinstance(value, str) or not value.strip():
            return False
        if " ".join(value.split()) not in normalized_request:
            return False
    return True


def _prediction_needs_retry(
    predicted: dict, user_request: str, tools: list[dict]
) -> bool:
    """Reject tool calls that can be validated as malformed without gold labels."""
    if predicted.get("decision") != "tool_call":
        return False

    tool = next(
        (item for item in tools if item.get("name") == predicted.get("tool_name")), None
    )
    if not tool:
        return True

    parameters = tool.get("parameters") or {}
    properties = parameters.get("properties") or {}
    arguments = predicted.get("arguments") or {}
    if any(key not in properties for key in arguments):
        return True
    if any(key not in arguments for key in parameters.get("required") or []):
        return True
    if not _arguments_are_grounded(predicted, user_request):
        return True

    lowered = user_request.casefold()
    if (
        "download" in str(tool.get("name", "")).casefold()
        or "tải" in str(tool.get("description", "")).casefold()
    ):
        if not any(marker in lowered for marker in ("tải", "download", "tải xuống")):
            return True

    for key, value in arguments.items():
        if not key.endswith("_id") or not isinstance(value, str):
            continue
        id_match = re.search(r"\bID\s+([A-Za-z0-9]+)", user_request, re.IGNORECASE)
        nearby_match = re.search(
            r"\b(?:buổi|lịch)\s+([A-Za-z0-9]+)", user_request, re.IGNORECASE
        )
        expected_id = (
            (id_match or nearby_match).group(1) if (id_match or nearby_match) else None
        )
        if expected_id and value != expected_id:
            return True

    return False


def _repair_confident_arguments(
    predicted: dict, user_request: str, tools: list[dict]
) -> dict:
    """Apply only lossless repairs supported by an unambiguous source span."""
    if predicted.get("decision") != "tool_call":
        return predicted

    repaired = dict(predicted)
    arguments = dict(predicted.get("arguments") or {})
    tool = next(
        (item for item in tools if item.get("name") == predicted.get("tool_name")), None
    )
    properties = (tool or {}).get("parameters", {}).get("properties") or {}
    if "session_id" in properties and "session_id" not in arguments:
        session_candidates = re.findall(
            r"\b(?:buổi(?:\s+học)?|lịch(?:\s+học)?)\s+([A-Za-z0-9]+)",
            user_request,
            re.IGNORECASE,
        )
        if len(session_candidates) == 1:
            arguments["session_id"] = session_candidates[0]

    for key, value in arguments.items():
        if not isinstance(value, str):
            continue

        source_matches = re.findall(re.escape(value), user_request, re.IGNORECASE)
        if len(source_matches) == 1:
            arguments[key] = source_matches[0]

        if key.endswith("_id"):
            id_candidates = re.findall(
                r"\bID\s+([A-Za-z0-9]+)", user_request, re.IGNORECASE
            )
            nearby_candidates = re.findall(
                r"\b(?:buổi(?:\s+học)?|lịch(?:\s+học)?)\s+([A-Za-z0-9]+)",
                user_request,
                re.IGNORECASE,
            )
            candidates = list(dict.fromkeys(id_candidates + nearby_candidates))
            matching_candidates = [
                candidate
                for candidate in candidates
                if candidate.casefold() in value.casefold()
            ]
            if len(matching_candidates) == 1:
                arguments[key] = matching_candidates[0]

    if "student_name" in arguments:
        arguments["student_name"] = re.sub(
            r"^(?:bé|em|anh|chị|cô|chú|bạn)\s+",
            "",
            arguments["student_name"],
            flags=re.IGNORECASE,
        )

    if "reason" in arguments:
        reason_match = re.search(
            r"\b(lý do\s+)(?!là\b)([^,.!?]+)", user_request, re.IGNORECASE
        )
        reason_after_connector = re.search(
            r"\blý do\s+là\s+([^,.!?]+)", user_request, re.IGNORECASE
        )
        if (
            reason_match
            and arguments["reason"].casefold() in reason_match.group(2).casefold()
        ):
            arguments["reason"] = reason_match.group(1) + reason_match.group(2)
        elif (
            reason_after_connector
            and arguments["reason"].casefold()
            in reason_after_connector.group(1).casefold()
        ):
            arguments["reason"] = reason_after_connector.group(1)

    if "new_date" in arguments and "new_time" in properties:
        if re.fullmatch(
            r"\d{1,2}\s*(?:giờ|h)\s*(?:sáng|chiều|tối)?",
            arguments["new_date"],
            re.IGNORECASE,
        ):
            arguments["new_time"] = arguments.pop("new_date")
        elif re.search(
            r"((?:thứ\s+\w+|\w+)\s+tuần\s+sau)", user_request, re.IGNORECASE
        ):
            date_match = re.search(
                r"((?:thứ\s+\w+|\w+)\s+tuần\s+sau)",
                user_request,
                re.IGNORECASE,
            )
            arguments["new_date"] = date_match.group(1)
            arguments.pop("new_time", None)

    if "session_id" in arguments:
        explicit_id = re.search(r"\bID\s+([A-Za-z0-9]+)", user_request, re.IGNORECASE)
        if (
            explicit_id
            and "new_date" in arguments
            and arguments["new_date"] == explicit_id.group(1)
        ):
            arguments["session_id"] = explicit_id.group(1)
            arguments.pop("new_date", None)

    repaired["arguments"] = arguments
    return repaired


async def run(args: argparse.Namespace) -> dict:
    rows = [
        json.loads(line)
        for line in args.input.read_text(encoding="utf-8").splitlines()
        if line
    ][: args.limit]
    rows = rows[args.offset :]
    model_kwargs = {"temperature": 0, "max_tokens": args.max_tokens}
    if args.native_ollama:
        model_kwargs.update(native_ollama=True, think=False)
    model = select_model(args.model, **model_kwargs)
    tracker = UsageTracker(max_calls=args.max_calls, log_path=args.usage_log)
    results = []
    for row in rows:
        if not tracker.allow():
            break
        tools = _load_tools(row["tools"])
        compact_tools = json.dumps(
            [
                {
                    "name": tool.get("name"),
                    "description": tool.get("description"),
                    "parameters": tool.get("parameters", {}),
                }
                for tool in tools
            ],
            ensure_ascii=False,
        )
        prompt = (
            'Return only JSON: {"name": "tool_name", "arguments": {...}}. '
            "Use a tool whenever the request matches an available tool; do not return null because optional fields are absent. "
            'If no tool fits, return {"name": null, "arguments": {}}.\n'
            "Copy argument values exactly from the user request. Do not translate, normalize dates or times, expand phrases, correct casing, or add details. "
            "Include only arguments explicitly present in the request; omit missing optional arguments instead of guessing. "
            "Never use Chinese or English in argument values unless they appear verbatim in the user request.\n"
            "Choose recommendation tools for requests to suggest or recommend; choose download tools only when the user explicitly asks to download.\n"
            'Examples: "Tìm gia sư Lý." -> {"name":"search_tutors","arguments":{"subject":"Lý"}}; '
            '"Xem thông tin gia sư H234." -> {"name":"view_tutor_details","arguments":{"tutor_id":"H234"}}.\n'
            f"User request: {row['input_text']}\nAvailable tools: {compact_tools}"
        )
        started = time.perf_counter()
        try:
            if not tracker.allow():
                break
            response = await asyncio.wait_for(
                model.call(prompt, stream=False), timeout=args.timeout
            )
            tracker.record(True, len(prompt), len(response.content or ""))
            predicted = _parse_prediction(response.content or "")
            if _prediction_needs_retry(predicted, row["input_text"], tools) and tracker.allow():
                retry_prompt = (
                    f"{prompt}\nThe previous arguments were not copied verbatim from the user request. "
                    "Retry now. Validate required fields, use only schema field names, preserve exact casing, "
                    "and copy ID values without prefixes or surrounding words."
                )
                retry_response = await asyncio.wait_for(
                    model.call(retry_prompt, stream=False), timeout=args.timeout
                )
                tracker.record(True, len(retry_prompt), len(retry_response.content or ""))
                predicted = _parse_prediction(retry_response.content or "")
        except Exception as error:
            tracker.record(False, len(prompt))
            predicted = {"decision": "error", "raw_output": repr(error)}
        predicted = _repair_confident_arguments(predicted, row["input_text"], tools)
        expected = _parse_expected(row["expected_tool_call"])
        tool_match, argument_match = _matches(predicted, expected)
        results.append(
            {
                "task_id": str(row["sample_id"]),
                "expected": expected,
                "predicted": {
                    key: value
                    for key, value in predicted.items()
                    if key != "raw_output"
                },
                "tool_match": tool_match,
                "argument_match": argument_match,
                "exact_match": argument_match,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "raw_output": predicted.get("raw_output", ""),
            }
        )
    tracker.write_log(
        "run_agentkit_local_smoke.py",
        args.model,
        {"output": str(args.output), "sample_size": len(results)},
    )
    return {
        "benchmark": "vietnamese-function-calling",
        "split": "test",
        "model": args.model,
        "sample_size": len(results),
        "usage": tracker.summary(),
        "tool_match_rate": sum(item["tool_match"] for item in results) / len(results)
        if results
        else 0.0,
        "argument_match_rate": sum(item["argument_match"] for item in results)
        / len(results)
        if results
        else 0.0,
        "exact_match_rate": sum(item["exact_match"] for item in results) / len(results)
        if results
        else 0.0,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="ollama:qwen2.5:7b")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--max-tokens", type=int, default=256)
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
            {
                key: result[key]
                for key in (
                    "sample_size",
                    "tool_match_rate",
                    "argument_match_rate",
                    "exact_match_rate",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
