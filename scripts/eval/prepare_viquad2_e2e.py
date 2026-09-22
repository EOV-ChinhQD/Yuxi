#!/usr/bin/env python3
"""Prepare UIT-ViQuAD 2.0 validation split as a scored E2E QA artifact.

Outputs corpus.jsonl (deduplicated contexts), queries.jsonl (stratified sample
with gold answers and answerability flags), qrels.jsonl, and manifest.json with
counts, seed, and sampling rule. Sampling is deterministic for a fixed seed.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
from pathlib import Path


def read_rows(path: Path) -> list[dict]:
    import pyarrow.parquet as parquet

    return parquet.read_table(path).to_pylist()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_answers(raw: object) -> list[str]:
    if raw is None or raw == "None":
        return []
    if isinstance(raw, dict):
        return [str(text) for text in raw.get("text", [])]
    try:
        parsed = ast.literal_eval(str(raw))
    except (ValueError, SyntaxError):
        return []
    if isinstance(parsed, dict):
        return [str(text) for text in parsed.get("text", [])]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n-answerable", type=int, default=100)
    parser.add_argument("--n-impossible", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows = read_rows(args.parquet)
    rng = random.Random(args.seed)

    answerable = [row for row in rows if str(row["is_impossible"]).lower() != "true"]
    impossible = [row for row in rows if str(row["is_impossible"]).lower() == "true"]
    rng.shuffle(answerable)
    rng.shuffle(impossible)
    sampled = answerable[: args.n_answerable] + impossible[: args.n_impossible]
    if len(sampled) < args.n_answerable + args.n_impossible:
        raise ValueError("Not enough rows for the requested sample sizes")

    corpus_by_text: dict[str, dict] = {}
    for row in rows:
        text = row["context"]
        if text not in corpus_by_text:
            corpus_by_text[text] = {
                "document_id": f"p{len(corpus_by_text):05d}",
                "title": row["title"],
                "text": text,
            }
    doc_id_by_text = {text: entry["document_id"] for text, entry in corpus_by_text.items()}

    queries = [
        {
            "dataset": "uit-viquad-2",
            "split": "validation",
            "query_id": str(row["id"]),
            "query": row["question"],
            "documents": [],
            "relevant_document_ids": [doc_id_by_text[row["context"]]],
            "gold_answers": _parse_answers(row["answers"]),
            "answerable": str(row["is_impossible"]).lower() != "true",
            "metadata": {"title": row["title"], "uit_id": row["uit_id"]},
        }
        for row in sampled
    ]
    qrels = [
        {
            "query_id": query["query_id"],
            "document_id": query["relevant_document_ids"][0],
            "score": 1,
        }
        for query in queries
    ]

    write_jsonl(args.output / "corpus.jsonl", list(corpus_by_text.values()))
    write_jsonl(args.output / "queries.jsonl", queries)
    write_jsonl(args.output / "qrels.jsonl", qrels)
    manifest = {
        "dataset": "uit-viquad-2",
        "split": "validation",
        "source_rows": len(rows),
        "corpus_documents": len(corpus_by_text),
        "sampled_queries": len(queries),
        "n_answerable": args.n_answerable,
        "n_impossible": args.n_impossible,
        "seed": args.seed,
        "sampling_rule": "seeded shuffle, first N per answerability class",
        "files": {
            name: sha256_file(args.output / name)
            for name in ("corpus.jsonl", "queries.jsonl", "qrels.jsonl")
        },
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: manifest[key] for key in ("source_rows", "corpus_documents", "sampled_queries", "seed")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
