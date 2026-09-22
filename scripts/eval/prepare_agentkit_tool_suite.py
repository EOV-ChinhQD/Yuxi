#!/usr/bin/env python3
"""Export a source-locked AgentKit-style suite from Yuxi's registered tools."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SELECTED_TOOLS = (
    "query_kb",
    "query_keywords",
    "open_kb_document",
    "search_file",
    "ocr_parse_file",
)

TASKS = (
    {
        "task_id": "kb-query-001",
        "language": "vi",
        "input_text": "Tìm trong kho kiến thức câu trả lời về chính sách nghỉ phép.",
        "expected_decision": "tool_call",
        "expected_tool": "query_kb",
        "expected_arguments": {
            "kb_id": "<benchmark_kb_id>",
            "query_text": "chính sách nghỉ phép",
        },
        "category": "single_tool",
    },
    {
        "task_id": "kb-keyword-001",
        "language": "vi",
        "input_text": "Tìm chính xác mã lỗi ERR-401 trong kho tài liệu.",
        "expected_decision": "tool_call",
        "expected_tool": "query_keywords",
        "expected_arguments": {"kb_id": "<benchmark_kb_id>", "query_text": "ERR-401"},
        "category": "single_tool",
    },
    {
        "task_id": "file-search-001",
        "language": "vi",
        "input_text": "Tìm file có tên hợp đồng lao động trong kho kiến thức.",
        "expected_decision": "tool_call",
        "expected_tool": "search_file",
        "expected_arguments": {"query": "hợp đồng lao động", "offset": 0, "limit": 20},
        "category": "single_tool",
    },
    {
        "task_id": "document-open-001",
        "language": "vi",
        "input_text": "Mở file DOC-001 từ dòng 10 để đọc thêm ngữ cảnh.",
        "expected_decision": "tool_call",
        "expected_tool": "open_kb_document",
        "expected_arguments": {
            "kb_id": "<benchmark_kb_id>",
            "file_id": "DOC-001",
            "line": 10,
            "window_size": 20,
        },
        "category": "single_tool",
    },
    {
        "task_id": "ocr-parse-001",
        "language": "vi",
        "input_text": "Đọc nội dung OCR của file /home/gem/user-data/uploads/document.pdf.",
        "expected_decision": "tool_call",
        "expected_tool": "ocr_parse_file",
        "expected_arguments": {"file_path": "/home/gem/user-data/uploads/document.pdf"},
        "category": "single_tool",
    },
    {
        "task_id": "no-tool-001",
        "language": "vi",
        "input_text": "Giải thích ngắn gọn RAG là gì.",
        "expected_decision": "no_tool_needed",
        "expected_tool": None,
        "expected_arguments": {},
        "category": "no_tool_needed",
    },
    {
        "task_id": "clarification-001",
        "language": "vi",
        "input_text": "Tìm tài liệu giúp tôi.",
        "expected_decision": "clarification",
        "expected_tool": None,
        "expected_arguments": {},
        "category": "clarification",
    },
    {
        "task_id": "invalid-path-001",
        "language": "vi",
        "input_text": "OCR file /tmp/private.pdf.",
        "expected_decision": "tool_call",
        "expected_tool": "ocr_parse_file",
        "expected_arguments": {"file_path": "/tmp/private.pdf"},
        "category": "tool_error_recovery",
    },
)


def tool_schema(tool_obj) -> dict:
    schema = {}
    args_schema = getattr(tool_obj, "args_schema", None)
    if args_schema is not None:
        if hasattr(args_schema, "model_json_schema"):
            schema = args_schema.model_json_schema()
        elif hasattr(args_schema, "schema"):
            schema = args_schema.schema()
        elif isinstance(args_schema, dict):
            schema = args_schema
    return {
        "name": tool_obj.name,
        "description": tool_obj.description,
        "parameters": schema,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import yuxi.agents.toolkits  # noqa: F401
    from yuxi.agents.toolkits.registry import get_all_tool_instances

    tools = {tool.name: tool for tool in get_all_tool_instances()}
    missing = sorted(set(SELECTED_TOOLS) - set(tools))
    if missing:
        raise SystemExit(
            f"Selected Yuxi tools are not registered: {', '.join(missing)}"
        )

    result = {
        "schema_version": "1.0",
        "suite": "yuxi-agentkit-tool-suite",
        "source": "Yuxi registered toolkits",
        "tools": [tool_schema(tools[name]) for name in SELECTED_TOOLS],
        "tasks": list(TASKS),
        "execution": {
            "model_decision": "pending",
            "tool_handlers": "bound at runtime",
            "trace_schema": "AgentKitTrace v1",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(SELECTED_TOOLS)} tools and {len(TASKS)} tasks to {args.output}")


if __name__ == "__main__":
    main()
