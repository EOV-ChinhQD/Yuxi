#!/usr/bin/env python3
"""Normalize a source JSONL snapshot into a Yuxi benchmark artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BACKEND_PACKAGE = Path(__file__).resolve().parents[2] / "backend" / "package"
sys.path.insert(0, str(BACKEND_PACKAGE))

from yuxi.evaluation.benchmark_registry import (  # noqa: E402
    adapt_ocr_rows,
    adapt_nli_rows,
    adapt_retrieval_rows,
    adapt_tool_calling_rows,
    load_source_rows,
    sha256_file,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--task", choices=("retrieval", "ocr", "nli", "tool_calling"), required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = load_source_rows(args.input)
    adapters = {
        "retrieval": adapt_retrieval_rows,
        "ocr": adapt_ocr_rows,
        "nli": adapt_nli_rows,
        "tool_calling": adapt_tool_calling_rows,
    }
    records = adapters[args.task](rows, args.dataset, args.split)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output, records)
    print(
        json.dumps(
            {
                "dataset": args.dataset,
                "split": args.split,
                "task": args.task,
                "records": len(records),
                "artifact_sha256": sha256_file(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
