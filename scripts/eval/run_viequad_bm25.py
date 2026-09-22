#!/usr/bin/env python3
"""Run a dependency-free BM25 baseline on the prepared VieQuAD artifacts."""

from __future__ import annotations

import argparse
import heapq
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path


TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.casefold())


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def dcg(relevances: list[int]) -> float:
    return sum(value / math.log2(rank + 2) for rank, value in enumerate(relevances))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--qrels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()

    queries = load_jsonl(args.queries)
    corpus = load_jsonl(args.corpus)
    qrels = load_jsonl(args.qrels)
    relevant = defaultdict(set)
    for row in qrels:
        if row.get("score", 1) > 0:
            relevant[str(row["query_id"])].add(str(row["document_id"]))

    document_tokens = [tokens(row["text"]) for row in corpus]
    document_frequency = Counter(token for doc in document_tokens for token in set(doc))
    average_length = sum(map(len, document_tokens)) / len(document_tokens)
    document_count = len(corpus)
    k1, b = 1.5, 0.75
    rankings: dict[str, list[str]] = {}
    latencies = []
    started = time.perf_counter()
    for query in queries:
        query_started = time.perf_counter()
        query_terms = Counter(tokens(query["query"]))
        scored = []
        for index, document in enumerate(document_tokens):
            term_counts = Counter(document)
            score = 0.0
            for term, query_frequency in query_terms.items():
                frequency = term_counts.get(term, 0)
                if not frequency:
                    continue
                idf = math.log(
                    1
                    + (document_count - document_frequency[term] + 0.5)
                    / (document_frequency[term] + 0.5)
                )
                denominator = frequency + k1 * (
                    1 - b + b * len(document) / average_length
                )
                score += idf * frequency * (k1 + 1) / denominator * query_frequency
            if score > 0:
                scored.append((score, corpus[index]["document_id"]))
        ranked = [document_id for _, document_id in heapq.nlargest(args.k, scored)]
        rankings[str(query["query_id"])] = ranked
        latencies.append(time.perf_counter() - query_started)

    metric_values = {
        name: [] for name in ("recall@1", "recall@5", "recall@10", "mrr@10", "ndcg@10")
    }
    for query in queries:
        query_id = str(query["query_id"])
        gold = relevant[query_id]
        ranked = rankings[query_id]
        for k in (1, 5, 10):
            metric_values[f"recall@{k}"].append(float(bool(set(ranked[:k]) & gold)))
        first_relevant = next(
            (
                rank
                for rank, document_id in enumerate(ranked[:10], 1)
                if document_id in gold
            ),
            None,
        )
        metric_values["mrr@10"].append(1 / first_relevant if first_relevant else 0.0)
        ideal = dcg([1] * min(len(gold), 10))
        actual = dcg([int(document_id in gold) for document_id in ranked[:10]])
        metric_values["ndcg@10"].append(actual / ideal if ideal else 0.0)

    result = {
        "benchmark": "mteb/VieQuADRetrieval",
        "split": "validation",
        "method": "bm25_baseline",
        "queries": len(queries),
        "corpus_documents": len(corpus),
        "qrels": len(qrels),
        "metrics": {
            name: sum(values) / len(values) for name, values in metric_values.items()
        },
        "latency_seconds": {
            "mean": sum(latencies) / len(latencies),
            "p50": sorted(latencies)[len(latencies) // 2],
            "p95": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)],
            "total": time.perf_counter() - started,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
