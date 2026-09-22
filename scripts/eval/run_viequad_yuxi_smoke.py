#!/usr/bin/env python3
"""Run a small real Milvus retrieval smoke evaluation against a Yuxi KB."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from yuxi.evaluation.backends.milvus_direct import MilvusDirectBackend
from yuxi.evaluation.config.query_options import QueryOptions
from yuxi.knowledge import knowledge_base


async def run(args: argparse.Namespace) -> dict:
    rows = [
        json.loads(line)
        for line in args.queries.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][: args.limit]
    relevant = defaultdict(set)
    qrels = [
        json.loads(line)
        for line in args.qrels.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for row in qrels:
        relevant[str(row["query_id"])].add(str(row["document_id"]))

    kb = knowledge_base._get_or_create_kb_instance("milvus")
    await kb._load_metadata()
    backend = MilvusDirectBackend()
    rankings: dict[str, list[str]] = {}
    latencies: list[float] = []
    failures: list[dict] = []
    options = QueryOptions(
        search_mode=args.search_mode,
        final_top_k=args.top_k,
        use_graph_retrieval=False,
        use_consensus_retrieval=False,
    )
    for row in rows:
        started = time.perf_counter()
        try:
            results = await backend.query(row["query"], args.kb_id, options)
            rankings[str(row["query_id"])] = [
                Path(item.get("metadata", {}).get("source", "")).stem
                for item in results
                if item.get("metadata", {}).get("source")
            ]
        except Exception as exc:
            rankings[str(row["query_id"])] = []
            failures.append({"query_id": row["query_id"], "error": str(exc)})
        latencies.append(time.perf_counter() - started)

    recall = {}
    reciprocal_ranks = []
    for row in rows:
        query_id = str(row["query_id"])
        gold = relevant[query_id]
        ranked = rankings[query_id]
        for k in (1, 5, 10):
            recall[f"recall@{k}"] = recall.get(f"recall@{k}", [])
            recall[f"recall@{k}"].append(float(bool(set(ranked[:k]) & gold)))
        first = next((i for i, doc_id in enumerate(ranked[:10], 1) if doc_id in gold), None)
        reciprocal_ranks.append(1 / first if first else 0.0)

    result = {
        "benchmark": "mteb/VieQuADRetrieval",
        "split": "validation",
        "method": f"yuxi_milvus_{args.search_mode}",
        "kb_id": args.kb_id,
        "embedding_model": args.embedding_model,
        "queries": len(rows),
        "failures": failures,
        "metrics": {
            key: sum(values) / len(values) if values else 0.0
            for key, values in recall.items()
        }
        | {"mrr@10": sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0},
        "latency_seconds": {
            "mean": sum(latencies) / len(latencies) if latencies else 0.0,
            "p50": sorted(latencies)[len(latencies) // 2] if latencies else 0.0,
            "p95": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0.0,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--qrels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kb-id", required=True)
    parser.add_argument("--embedding-model", default="unknown")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--search-mode", choices=("vector", "keyword", "hybrid"), default="vector")
    args = parser.parse_args()

    import asyncio

    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
