#!/usr/bin/env python3
"""Prepare a fixed, auditable BFCL subset from the pinned upstream files."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--category", default="simple_python")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data_path = args.data / f"BFCL_v4_{args.category}.json"
    answers_path = args.answers / f"BFCL_v4_{args.category}.json"
    rows = {row["id"]: row for row in read_jsonl(data_path)}
    answers = {row["id"]: row["ground_truth"] for row in read_jsonl(answers_path)}
    ids = sorted(set(rows) & set(answers))
    if len(ids) < args.count:
        raise ValueError(f"Only {len(ids)} matched records, need {args.count}")
    random.Random(args.seed).shuffle(ids)
    selected = []
    for sample_id in ids[: args.count]:
        row = dict(rows[sample_id])
        row["ground_truth"] = answers[sample_id]
        selected.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected),
        encoding="utf-8",
    )
    manifest = {
        "benchmark": "bfcl",
        "category": args.category,
        "sample_size": len(selected),
        "seed": args.seed,
        "source_revision": args.source_revision,
        "license": "Apache-2.0",
        "data_sha256": sha256(data_path),
        "answers_sha256": sha256(answers_path),
        "artifact_sha256": sha256(args.output),
    }
    args.output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
