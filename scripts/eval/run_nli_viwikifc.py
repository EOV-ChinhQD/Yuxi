#!/usr/bin/env python3
"""Score ViWikiFC claim-evidence pairs with two NLI configurations.

Config A (production): replicates NLIVerifier._run_batch_nli exactly --
zero-shot pipeline with the evidence as sequence, the claim as the single
candidate label, and the 0.6/0.3 entailment/neutral thresholds.

Config B (standard): the same model weights used as a proper 3-way NLI
classifier -- candidate labels are entailment/neutral/contradiction and the
prediction is the argmax. This measures the model capability ceiling and shows
whether production's inverted formulation loses accuracy.

Both configs run on CPU with zero API quota.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

LABELS = ("ENTAILMENT", "NEUTRAL", "CONTRADICTION")

PRODUCTION_THRESHOLDS = (0.6, 0.3)


def _load_pipeline():
    from yuxi.knowledge.grounding.nli_verifier import get_nli_pipeline

    return get_nli_pipeline()


def _predict_production(pipeline, claim: str, context: str) -> tuple[str, float]:
    output = pipeline(
        sequences=context,
        candidate_labels=[claim],
        hypothesis_template="This text implies that: {}",
        multi_label=True,
    )
    scores = dict(zip(output.get("labels", []), output.get("scores", [])))
    score = float(scores.get(claim, 0.0))
    entailment_cut, neutral_cut = PRODUCTION_THRESHOLDS
    if score > entailment_cut:
        return "ENTAILMENT", score
    if score > neutral_cut:
        return "NEUTRAL", score
    return "CONTRADICTION", score


def _predict_standard(pipeline, claim: str, context: str) -> tuple[str, dict[str, float]]:
    output = pipeline(
        sequences=f"{context} {claim}",
        candidate_labels=["entailment", "neutral", "contradiction"],
        hypothesis_template="The relation between the premise and the hypothesis is {}.",
        multi_label=False,
    )
    scores = {label.upper(): float(score) for label, score in zip(output.get("labels", []), output.get("scores", []))}
    predicted = max(LABELS, key=lambda label: scores.get(label, 0.0))
    return predicted, scores


def _prf(confusion: dict[str, Counter], label: str) -> dict[str, float]:
    true_positive = confusion[label][label]
    predicted_positive = sum(confusion[predicted][label] for predicted in LABELS)
    actual_positive = sum(confusion[label][predicted] for predicted in LABELS)
    precision = true_positive / predicted_positive if predicted_positive else 0.0
    recall = true_positive / actual_positive if actual_positive else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0,
        "support": actual_positive,
    }


def run(args: argparse.Namespace) -> dict:
    rows = [
        json.loads(line)
        for line in args.input.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.limit:
        rows = rows[: args.limit]
    pipeline = _load_pipeline()
    configs = args.configs.split(",")
    results: dict[str, dict] = {}
    for config in configs:
        confusion: dict[str, Counter] = {label: Counter() for label in LABELS}
        samples = []
        latencies: list[float] = []
        for row in rows:
            context = "\n".join(row.get("evidence") or [])
            if not context.strip():
                predicted, detail = "NEUTRAL", {"reason": "empty_evidence"}
            else:
                started = time.perf_counter()
                if config == "production":
                    predicted, score = _predict_production(pipeline, row["claim"], context)
                    detail = {"score": score}
                else:
                    predicted, detail = _predict_standard(pipeline, row["claim"], context)
                latencies.append((time.perf_counter() - started) * 1000)
            expected = row["label"]
            confusion[expected][predicted] += 1
            samples.append(
                {
                    "sample_id": row["sample_id"],
                    "expected": expected,
                    "predicted": predicted,
                    "detail": detail,
                }
            )
        per_class = {label: _prf(confusion, label) for label in LABELS}
        correct = sum(confusion[label][label] for label in LABELS)
        results[config] = {
            "sample_size": len(samples),
            "accuracy": correct / len(samples) if samples else 0.0,
            "macro_f1": sum(metrics["f1"] for metrics in per_class.values()) / len(per_class),
            "per_class": per_class,
            "confusion": {label: dict(confusion[label]) for label in LABELS},
            "latency_ms": {
                "mean": sum(latencies) / len(latencies) if latencies else 0.0,
                "p50": sorted(latencies)[len(latencies) // 2] if latencies else 0.0,
            },
            "samples": samples,
        }
    return {
        "benchmark": "viwikifc",
        "split": "test",
        "model": "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7",
        "device": "cpu",
        "production_thresholds": list(PRODUCTION_THRESHOLDS),
        "configs": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--configs", default="production,standard")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    result = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                config: {
                    key: value
                    for key, value in payload.items()
                    if key in ("sample_size", "accuracy", "macro_f1", "per_class")
                }
                for config, payload in result["configs"].items()
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
