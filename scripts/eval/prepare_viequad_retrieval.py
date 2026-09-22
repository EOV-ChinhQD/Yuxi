#!/usr/bin/env python3
"""Prepare MTEB VieQuADRetrieval parquet files as separate corpus and qrels artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, object]]:
    import pyarrow.parquet as parquet

    return parquet.read_table(path).to_pylist()


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--qrels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    queries = read_rows(args.queries)
    corpus = read_rows(args.corpus)
    qrels = read_rows(args.qrels)
    relevant_by_query: dict[str, list[str]] = {}
    for row in qrels:
        relevant_by_query.setdefault(str(row["query-id"]), []).append(str(row["corpus-id"]))

    write_jsonl(
        args.output / "queries.jsonl",
        [
            {
                "dataset": "viequad-retrieval",
                "split": "validation",
                "query_id": str(row["_id"]),
                "query": row["text"],
                "documents": [],
                "relevant_document_ids": relevant_by_query.get(str(row["_id"]), []),
                "gold_answer": None,
                "answerable": True,
                "metadata": {"source_format": "mteb_parquet"},
            }
            for row in queries
        ],
    )
    write_jsonl(
        args.output / "corpus.jsonl",
        [{"document_id": str(row["_id"]), "text": row["text"], "title": row["title"]} for row in corpus],
    )
    write_jsonl(
        args.output / "qrels.jsonl",
        [{"query_id": str(row["query-id"]), "document_id": str(row["corpus-id"]), "score": row["score"]} for row in qrels],
    )
    print(json.dumps({"queries": len(queries), "corpus": len(corpus), "qrels": len(qrels)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
