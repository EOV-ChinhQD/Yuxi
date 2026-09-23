#!/usr/bin/env python3
"""Score the prepared printed-document OCR manifest with a selected engine."""

from __future__ import annotations

import argparse
import json
import time
import unicodedata
from pathlib import Path

from yuxi.knowledge.parser.factory import DocumentProcessorFactory


def normalize_text(value: str) -> str:
    """Normalize Unicode and whitespace without removing Vietnamese diacritics."""
    normalized = unicodedata.normalize("NFC", value or "")
    return " ".join(normalized.split())


def edit_distance(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_item in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_item in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_item != right_item),
                )
            )
        previous = current
    return previous[-1]


def error_rate(reference: str, prediction: str, unit: str) -> tuple[int, int]:
    reference_units = list(reference) if unit == "char" else reference.split()
    prediction_units = list(prediction) if unit == "char" else prediction.split()
    return edit_distance(reference_units, prediction_units), len(reference_units)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine", default="rapid_ocr")
    args = parser.parse_args()

    records = [
        json.loads(line)
        for line in args.manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    samples = []
    char_errors = char_total = word_errors = word_total = 0
    for record in records:
        image_path = args.root / record["image"]
        reference = normalize_text(record["reference_text"])
        started = time.perf_counter()
        prediction = DocumentProcessorFactory.process_file(args.engine, str(image_path), params={})
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        normalized_prediction = normalize_text(prediction)
        current_char_errors, current_char_total = error_rate(reference, normalized_prediction, "char")
        current_word_errors, current_word_total = error_rate(reference, normalized_prediction, "word")
        char_errors += current_char_errors
        char_total += current_char_total
        word_errors += current_word_errors
        word_total += current_word_total
        samples.append(
            {
                "sample_id": record["sample_id"],
                "source_dataset": record["source_dataset"],
                "image_sha256": record["image_sha256"],
                "ground_truth_sha256": record["ground_truth_sha256"],
                "reference_chars": current_char_total,
                "prediction_chars": len(normalized_prediction),
                "cer": current_char_errors / current_char_total if current_char_total else 0.0,
                "wer": current_word_errors / current_word_total if current_word_total else 0.0,
                "exact_match": normalized_prediction == reference,
                "latency_ms": latency_ms,
            }
        )

    latencies = [sample["latency_ms"] for sample in samples]
    latencies_sorted = sorted(latencies)
    result = {
        "benchmark": "yuxi-printed-document-ocr",
        "engine": args.engine,
        "manifest": str(args.manifest),
        "sample_size": len(samples),
        "normalization": "Unicode NFC and whitespace collapse; Vietnamese diacritics preserved",
        "summary": {
            "cer": char_errors / char_total if char_total else 0.0,
            "wer": word_errors / word_total if word_total else 0.0,
            "exact_match": sum(sample["exact_match"] for sample in samples) / len(samples),
            "latency_ms": {
                "mean": sum(latencies) / len(latencies),
                "p50": latencies_sorted[len(latencies_sorted) // 2],
                "p95": latencies_sorted[max(0, int(len(latencies_sorted) * 0.95) - 1)],
            },
        },
        "samples": samples,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sample_size": len(samples), "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
