#!/usr/bin/env python3
"""Real E2E QA run on the UIT-ViQuAD 2.0 artifact (no gold-derived answers).

Pipeline per sample: standalone BM25 retrieval over the artifact corpus, then
one generation arm. Arms implemented here:

- extractive: top-1 passage, answer is the sentence with the highest question
  token overlap. Never abstains. Honest weak baseline.
- standard_rag: top-k passages in the prompt, single LLM call. May abstain
  with the exact ABSTAIN_PHRASE when the context is insufficient.

Agentic arms (LangGraph + NLI gate) are NOT implemented here: they require a
populated knowledge base and are tracked as Missing in the thesis.

Metrics: EM and whitespace-token F1 on normalized Vietnamese text, Hit@K,
abstention precision/recall against is_impossible, CJK-free language check,
and per-sample latency. Impossible questions score EM/F1 1.0 iff abstained.
"""

from __future__ import annotations

import argparse
import asyncio
import heapq
import json
import math
import re
import time
from collections import Counter
from pathlib import Path

from yuxi.models.chat import select_model

from usage_tracker import UsageTracker

ABSTAIN_PHRASE = "KHÔNG ĐỦ THÔNG TIN"
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
TOKEN_RE = re.compile(r"\w+", re.UNICODE)
PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.casefold())


def normalize_vi(text: str) -> str:
    cleaned = PUNCT_RE.sub(" ", text.casefold())
    return re.sub(r"\s+", " ", cleaned).strip()


class BM25Index:
    def __init__(self, corpus: list[dict], k1: float = 1.5, b: float = 0.75) -> None:
        self.ids = [row["document_id"] for row in corpus]
        self.texts = [row["text"] for row in corpus]
        self.doc_tokens = [tokens(text) for text in self.texts]
        self.doc_freq = Counter(token for doc in self.doc_tokens for token in set(doc))
        self.avg_len = sum(map(len, self.doc_tokens)) / len(self.doc_tokens)
        self.count = len(corpus)
        self.k1 = k1
        self.b = b

    def retrieve(self, query: str, top_k: int) -> list[tuple[str, float]]:
        query_terms = Counter(tokens(query))
        scored = []
        for index, document in enumerate(self.doc_tokens):
            term_counts = Counter(document)
            score = 0.0
            for term, query_frequency in query_terms.items():
                frequency = term_counts.get(term, 0)
                if not frequency:
                    continue
                idf = math.log(
                    1 + (self.count - self.doc_freq[term] + 0.5) / (self.doc_freq[term] + 0.5)
                )
                denominator = frequency + self.k1 * (1 - self.b + self.b * len(document) / self.avg_len)
                score += idf * frequency * (self.k1 + 1) / denominator * query_frequency
            if score > 0:
                scored.append((self.ids[index], score))
        return heapq.nlargest(top_k, scored, key=lambda item: item[1])


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]


def extractive_answer(question: str, passage: str) -> str:
    question_tokens = set(tokens(question))
    best, best_overlap = "", -1
    for sentence in split_sentences(passage):
        overlap = len(question_tokens & set(tokens(sentence)))
        if overlap > best_overlap:
            best, best_overlap = sentence, overlap
    return best


def em_score(predicted: str, golds: list[str], abstained: bool, answerable: bool) -> float:
    if not answerable:
        return 1.0 if abstained else 0.0
    if abstained:
        return 0.0
    normalized = normalize_vi(predicted)
    return 1.0 if any(normalized == normalize_vi(gold) for gold in golds) else 0.0


def f1_score(predicted: str, golds: list[str], abstained: bool, answerable: bool) -> float:
    if not answerable:
        return 1.0 if abstained else 0.0
    if abstained:
        return 0.0
    pred_tokens = tokens(normalize_vi(predicted))
    if not pred_tokens:
        return 0.0
    best = 0.0
    for gold in golds:
        gold_tokens = tokens(normalize_vi(gold))
        if not gold_tokens:
            continue
        common = Counter(pred_tokens) & Counter(gold_tokens)
        overlap = sum(common.values())
        if not overlap:
            continue
        precision = overlap / len(pred_tokens)
        recall = overlap / len(gold_tokens)
        best = max(best, 2 * precision * recall / (precision + recall))
    return best


def is_abstained(answer: str) -> bool:
    return ABSTAIN_PHRASE in answer


def hit_at_k(hits: dict, k: int) -> bool:
    """Read JSON-safe string keys while accepting integer keys in tests."""
    return bool(hits.get(str(k), hits.get(k, False)))


def select_evidence(ranked_ids: list[str], by_id: dict[str, str], question: str, limit: int) -> list[str]:
    """Keep the highest-ranked passages with direct query-token overlap."""
    if limit <= 0:
        return []
    query_terms = set(tokens(question))
    selected = [
        document_id
        for document_id in ranked_ids
        if query_terms & set(tokens(by_id.get(document_id, "")))
    ]
    return (selected or ranked_ids)[:limit]


async def run(args: argparse.Namespace) -> dict:
    queries = [json.loads(line) for line in args.queries.read_text(encoding="utf-8").splitlines() if line.strip()]
    corpus = [json.loads(line) for line in args.corpus.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id = {row["document_id"]: row["text"] for row in corpus}
    answerable = [row for row in queries if row["answerable"]][: args.n_answerable or None]
    impossible = [row for row in queries if not row["answerable"]][: args.n_impossible or None]
    selected = answerable + impossible

    index = BM25Index(corpus)
    model = None
    tracker = UsageTracker(max_calls=args.max_calls, log_path=args.usage_log)
    arms = args.arms.split(",")
    if "standard_rag" in arms:
        model = select_model(args.model, temperature=0, max_tokens=args.max_tokens)

    samples = []
    for row in selected:
        if "standard_rag" in arms and not tracker.allow():
            break
        ranked = [doc_id for doc_id, _ in index.retrieve(row["query"], args.top_k)]
        gold_ids = set(row["relevant_document_ids"])
        hits = {str(k): bool(set(ranked[:k]) & gold_ids) for k in (1, min(5, args.top_k), min(10, args.top_k))}
        evidence_ids = select_evidence(ranked, by_id, row["query"], args.evidence_k)
        arm_outputs = {}
        if "extractive" in arms:
            started = time.perf_counter()
            passage = by_id.get(ranked[0], "") if ranked else ""
            answer = extractive_answer(row["query"], passage)
            latency = round((time.perf_counter() - started) * 1000, 1)
            arm_outputs["extractive"] = {
                "answer": answer,
                "abstained": False,
                "em": em_score(answer, row["gold_answers"], False, row["answerable"]),
                "f1": f1_score(answer, row["gold_answers"], False, row["answerable"]),
                "language_valid": not CJK_RE.search(answer),
                "latency_ms": latency,
            }
        if "standard_rag" in arms:
            context = "\n\n".join(
                f"<evidence id=\"{doc_id}\">{by_id.get(doc_id, '')}</evidence>"
                for doc_id in evidence_ids
            )
            prompt = (
                "You are a Vietnamese extractive QA system. Return only the direct answer to the question, "
                "not reasoning, a summary of the evidence, source labels, or XML tags. "
                "Use an answer only when one evidence passage directly supports it; do not infer from general knowledge "
                f"or combine weak clues. If no passage directly supports the answer, return exactly: {ABSTAIN_PHRASE}. "
                "Keep the answer concise and in Vietnamese; preserve names, numbers, and dates from the evidence.\n\n"
                f"Câu hỏi: {row['query']}\n\nNgữ cảnh:\n{context}"
            )
            started = time.perf_counter()
            try:
                response = await asyncio.wait_for(
                    model.call(prompt, stream=False), timeout=args.timeout
                )
                tracker.record(True, len(prompt), len(response.content or ""))
                answer = (response.content or "").strip()
            except Exception as error:
                tracker.record(False, len(prompt))
                answer = f"LỖI: {error!r}"
            abstained = is_abstained(answer)
            arm_outputs["standard_rag"] = {
                "answer": answer,
                "abstained": abstained,
                "em": em_score(answer, row["gold_answers"], abstained, row["answerable"]),
                "f1": f1_score(answer, row["gold_answers"], abstained, row["answerable"]),
                "language_valid": not CJK_RE.search(answer),
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        samples.append(
            {
                "query_id": row["query_id"],
                "answerable": row["answerable"],
                "gold_answers": row["gold_answers"],
                "retrieved_ids": ranked,
                "hits": hits,
                "evidence_ids": evidence_ids,
                "arms": arm_outputs,
            }
        )

    summary = {}
    for arm in arms:
        arm_samples = [sample for sample in samples if arm in sample["arms"]]
        if not arm_samples:
            continue
        abstained = [sample["arms"][arm]["abstained"] for sample in arm_samples]
        impossible_flags = [not sample["answerable"] for sample in arm_samples]
        predicted_positives = sum(abstained)
        actual_positives = sum(impossible_flags)
        true_positives = sum(a and b for a, b in zip(abstained, impossible_flags))
        latencies = [sample["arms"][arm]["latency_ms"] for sample in arm_samples]
        summary[arm] = {
            "sample_size": len(arm_samples),
            "hit@1": sum(hit_at_k(sample["hits"], 1) for sample in arm_samples) / len(arm_samples),
            "em": sum(sample["arms"][arm]["em"] for sample in arm_samples) / len(arm_samples),
            "f1": sum(sample["arms"][arm]["f1"] for sample in arm_samples) / len(arm_samples),
            "abstention_precision": true_positives / predicted_positives if predicted_positives else 0.0,
            "abstention_recall": true_positives / actual_positives if actual_positives else 0.0,
            "language_valid_rate": sum(sample["arms"][arm]["language_valid"] for sample in arm_samples)
            / len(arm_samples),
            "latency_ms": {
                "mean": sum(latencies) / len(latencies),
                "p50": sorted(latencies)[len(latencies) // 2],
            },
        }
    tracker.write_log(
        "run_e2e_viquad2.py", args.model, {"output": str(args.output), "sample_size": len(samples)}
    )
    return {
        "benchmark": "uit-viquad-2-e2e",
        "split": "validation-sample",
        "model": args.model,
        "model_params": {"temperature": 0, "max_tokens": args.max_tokens, "top_k": args.top_k},
        "tokenizer": "whitespace-unicode-word-regex",
        "abstain_phrase": ABSTAIN_PHRASE,
        "sample_size": len(samples),
        "usage": tracker.summary(),
        "summary": summary,
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="nvidia:deepseek-ai/deepseek-v4.1-flash")
    parser.add_argument("--arms", default="extractive,standard_rag")
    parser.add_argument("--n-answerable", type=int, default=0)
    parser.add_argument("--n-impossible", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--evidence-k", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--usage-log", type=Path, default=None)
    args = parser.parse_args()
    result = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("sample_size", "usage", "summary")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
