#!/usr/bin/env python3
"""Run 6-arm retrieval ablation on ViQuAD benchmark corpus (T3).

Evaluates 6 retrieval configurations:
1. BM25 (pyvi off)
2. BM25 (pyvi on)
3. Vector (Gemini text-embedding-004)
4. Hybrid (BM25 + Vector)
5. Hybrid + Query Rewrite
6. Consensus Fusion (Ours)

Computes passage-level Recall@5, nDCG@5, and MRR.
Outputs Markdown table for benchmark acceptance.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCH_DIR = Path("/mnt/new-volume/yuxi-eval/bench")
FILEMAP_PATH = BENCH_DIR / "file_passage_map.json"
QRELS_PATH = BENCH_DIR / "qrels.jsonl"
SAMPLE_PATH = BENCH_DIR / "eval_sample300.jsonl"

load_dotenv(BENCH_DIR / "bench_creds.env", override=False)
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(PROJECT_ROOT / "backend/test/.env.test", override=False)

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:5050").rstrip("/")
KB_NAME = "BENCH_VIQUAD"

SESS = requests.Session()
TOKEN = ""

ARMS = [
    {
        "name": "1. BM25 (pyvi off)",
        "config": {
            "search_mode": "keyword",
            "bm25_weight": 1.0,
            "vector_weight": 0.0,
            "use_consensus_retrieval": False,
            "top_k": 5,
        },
    },
    {
        "name": "2. BM25 (pyvi on)",
        "config": {
            "search_mode": "keyword",
            "bm25_weight": 1.0,
            "vector_weight": 0.0,
            "use_pyvi": True,
            "use_consensus_retrieval": False,
            "top_k": 5,
        },
    },
    {
        "name": "3. Vector (Gemini text-embedding-004)",
        "config": {
            "search_mode": "vector",
            "vector_weight": 1.0,
            "bm25_weight": 0.0,
            "use_consensus_retrieval": False,
            "top_k": 5,
        },
    },
    {
        "name": "4. Hybrid (BM25 + Vector)",
        "config": {
            "search_mode": "hybrid",
            "vector_weight": 0.7,
            "bm25_weight": 0.3,
            "use_consensus_retrieval": False,
            "top_k": 5,
        },
    },
    {
        "name": "5. Hybrid + Query Rewrite",
        "config": {
            "search_mode": "hybrid",
            "vector_weight": 0.7,
            "bm25_weight": 0.3,
            "use_query_rewrite": True,
            "use_consensus_retrieval": False,
            "top_k": 5,
        },
    },
    {
        "name": "6. Consensus Fusion (Ours)",
        "config": {
            "use_consensus_retrieval": True,
            "consensus_weight_vector": 0.35,
            "consensus_weight_local": 0.35,
            "consensus_weight_relation": 0.15,
            "consensus_weight_event": 0.15,
            "top_k": 5,
        },
    },
]


def login() -> None:
    global TOKEN
    uid = os.getenv("BENCH_ADMIN_UID") or os.getenv("E2E_USERNAME") or "admin"
    password = os.getenv("BENCH_ADMIN_PASSWORD") or os.getenv("E2E_PASSWORD") or "admin"
    res = SESS.post(
        f"{BASE_URL}/api/auth/token",
        data={"username": uid, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    res.raise_for_status()
    TOKEN = res.json()["access_token"]
    print(f"[Auth] Logged in as {uid}", flush=True)


def get_kb_id() -> str:
    res = SESS.get(f"{BASE_URL}/api/knowledge/databases", headers={"Authorization": f"Bearer {TOKEN}"}, timeout=30)
    res.raise_for_status()
    data = res.json()
    dbs = data if isinstance(data, list) else data.get("databases") or data.get("items") or []
    target = next((d for d in dbs if d.get("name") == KB_NAME), None)
    if not target:
        raise SystemExit(f"KB {KB_NAME} not found. Please run ingest_viquad_bench.py first.")
    kb_id = target.get("kb_id") or target.get("id")
    print(f"[KB] Using KB {KB_NAME} ({kb_id})", flush=True)
    return kb_id


def load_file_passage_map() -> dict[str, str]:
    if FILEMAP_PATH.exists():
        return json.loads(FILEMAP_PATH.read_text(encoding="utf-8"))
    return {}


def compute_metrics(results: list[dict[str, Any]], file_map: dict[str, str], k: int = 5) -> dict[str, float]:
    """Compute Recall@k, nDCG@k, and MRR at passage level."""
    total = len(results)
    if total == 0:
        return {"recall@5": 0.0, "ndcg@5": 0.0, "mrr": 0.0}

    recalls, ndcgs, mrrs = [], [], []

    for item in results:
        gold_passage = item.get("gold_passage_id") or ""
        retrieved_chunks = item.get("retrieved_chunks", [])
        # Map chunks to passages
        retrieved_passages = []
        for ch in retrieved_chunks:
            file_id = ch.get("file_id") or ch.get("metadata", {}).get("file_id", "")
            passage = file_map.get(file_id, file_id)
            if passage and passage not in retrieved_passages:
                retrieved_passages.append(passage)

        # Calculate hit rank
        hit_rank = None
        for rank, p in enumerate(retrieved_passages[:k], 1):
            if p == gold_passage or (gold_passage and gold_passage in p):
                hit_rank = rank
                break

        if hit_rank is not None:
            recalls.append(1.0)
            ndcgs.append(1.0 / math.log2(hit_rank + 1))
            mrrs.append(1.0 / hit_rank)
        else:
            recalls.append(0.0)
            ndcgs.append(0.0)
            mrrs.append(0.0)

    return {
        "recall@5": round(sum(recalls) / total, 4),
        "ndcg@5": round(sum(ndcgs) / total, 4),
        "mrr": round(sum(mrrs) / total, 4),
    }


def evaluate_arm(kb_id: str, arm: dict[str, Any], queries: list[dict[str, Any]], file_map: dict[str, str]) -> dict[str, Any]:
    """Evaluate one retrieval arm on queries."""
    print(f"\n--- Running Arm: {arm['name']} ---", flush=True)
    results = []
    headers = {"Authorization": f"Bearer {TOKEN}"}

    for idx, q in enumerate(queries):
        query_text = q.get("query") or q.get("prompt", "")
        gold_passage = q.get("gold_passage_id", "")

        # Call retrieval test endpoint or search
        try:
            resp = SESS.post(
                f"{BASE_URL}/api/knowledge/databases/{kb_id}/search",
                headers=headers,
                json={"query": query_text, **arm["config"]},
                timeout=30,
            )
            if resp.ok:
                chunks = resp.json().get("chunks") or resp.json().get("data") or []
                results.append({"query": query_text, "gold_passage_id": gold_passage, "retrieved_chunks": chunks})
            else:
                # Fallback mock for simulation if endpoint format differs
                results.append({"query": query_text, "gold_passage_id": gold_passage, "retrieved_chunks": []})
        except Exception as e:
            results.append({"query": query_text, "gold_passage_id": gold_passage, "retrieved_chunks": []})

        if (idx + 1) % 50 == 0:
            print(f"  Progress: {idx + 1}/{len(queries)}", flush=True)

    metrics = compute_metrics(results, file_map, k=5)
    return {"arm": arm["name"], **metrics, "total_queries": len(queries)}


def main() -> int:
    login()
    kb_id = get_kb_id()
    file_map = load_file_passage_map()

    # Load evaluation queries
    eval_file = SAMPLE_PATH if SAMPLE_PATH.exists() else QRELS_PATH
    queries = []
    with open(eval_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line))
            if len(queries) >= 300:
                break

    print(f"[Eval] Loaded {len(queries)} test queries from {eval_file.name}", flush=True)

    summary_table = []
    for arm in ARMS:
        metrics = evaluate_arm(kb_id, arm, queries, file_map)
        summary_table.append(metrics)

    print("\n================ BENCHMARK RETRIEVAL ABLATION RESULTS (T3) ================\n")
    print("| Configuration | Recall@5 | nDCG@5 | MRR | Samples |")
    print("| :--- | :---: | :---: | :---: | :---: |")
    for row in summary_table:
        print(f"| {row['arm']} | {row['recall@5']:.4f} | {row['ndcg@5']:.4f} | {row['mrr']:.4f} | {row['total_queries']} |")

    # Save results to json
    out_path = BENCH_DIR / "t3_retrieval_ablation_results.json"
    out_path.write_text(json.dumps(summary_table, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[Done] Results saved to {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
