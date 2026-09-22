"""Data contracts and adapters for the reproducible benchmark registry."""

from __future__ import annotations

import hashlib
import json
import csv
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BenchmarkDocument:
    document_id: str
    text: str


@dataclass(frozen=True)
class RetrievalRecord:
    dataset: str
    split: str
    query_id: str
    query: str
    documents: tuple[BenchmarkDocument, ...] = ()
    relevant_document_ids: tuple[str, ...] = ()
    gold_answer: str | None = None
    answerable: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {
            "documents": [asdict(document) for document in self.documents],
            "relevant_document_ids": list(self.relevant_document_ids),
        }


@dataclass(frozen=True)
class OCRRecord:
    dataset: str
    split: str
    sample_id: str
    image_path: str
    reference_text: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NLIRecord:
    dataset: str
    split: str
    sample_id: str
    claim: str
    evidence: tuple[str, ...]
    label: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"evidence": list(self.evidence)}


@dataclass(frozen=True)
class ToolCallingRecord:
    dataset: str
    split: str
    sample_id: str
    input_text: str
    tools: tuple[Any, ...]
    expected_tool_call: Any = None
    decision: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"tools": list(self.tools)}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def adapt_retrieval_rows(rows: Iterable[dict[str, Any]], dataset: str, split: str) -> list[RetrievalRecord]:
    records = []
    for index, row in enumerate(rows):
        query = row.get("query", row.get("question"))
        if not query:
            raise ValueError(f"Row {index} is missing query/question")

        documents = tuple(
            BenchmarkDocument(str(document["id"]), str(document["text"])) for document in row.get("documents", [])
        )
        relevant_ids = row.get("relevant_document_ids", row.get("gold_chunk_ids"))
        if relevant_ids is None and row.get("gold_passage_id") is not None:
            relevant_ids = [row["gold_passage_id"]]
        records.append(
            RetrievalRecord(
                dataset=dataset,
                split=split,
                query_id=str(row.get("query_id", row.get("id", index))),
                query=str(query),
                documents=documents,
                relevant_document_ids=tuple(str(item) for item in (relevant_ids or [])),
                gold_answer=row.get("gold_answer", row.get("answer")),
                answerable=row.get("answerable"),
                metadata=dict(row.get("metadata", {})),
            )
        )
    return records


def adapt_ocr_rows(rows: Iterable[dict[str, Any]], dataset: str, split: str) -> list[OCRRecord]:
    records = []
    for index, row in enumerate(rows):
        image_path = row.get("image_path", row.get("image"))
        reference_text = row.get("reference_text", row.get("text"))
        if not image_path or reference_text is None:
            raise ValueError(f"Row {index} must contain image_path/image and reference_text")
        records.append(
            OCRRecord(
                dataset=dataset,
                split=split,
                sample_id=str(row.get("sample_id", row.get("id", index))),
                image_path=str(image_path),
                reference_text=str(reference_text),
                source=str(row.get("source", row.get("source_url", ""))),
                metadata=dict(row.get("metadata", {})),
            )
        )
    return records


def adapt_nli_rows(rows: Iterable[dict[str, Any]], dataset: str, split: str) -> list[NLIRecord]:
    label_map = {
        "supports": "ENTAILMENT",
        "support": "ENTAILMENT",
        "refutes": "CONTRADICTION",
        "refute": "CONTRADICTION",
        "not enough information": "NEUTRAL",
        "not_enough_information": "NEUTRAL",
        "neutral": "NEUTRAL",
    }
    records = []
    for index, row in enumerate(rows):
        claim = row.get("claim")
        raw_label = str(row.get("label", row.get("gold_label", ""))).strip().lower()
        if not claim or raw_label not in label_map:
            raise ValueError(f"Row {index} must contain claim and a supported evidence label")
        evidence = row.get("evidence", row.get("context", ""))
        evidence_items = [evidence] if isinstance(evidence, str) else list(evidence)
        records.append(
            NLIRecord(
                dataset=dataset,
                split=split,
                sample_id=str(row.get("sample_id", row.get("pairID", row.get("id", index)))),
                claim=str(claim),
                evidence=tuple(str(item) for item in evidence_items),
                label=label_map[raw_label],
                metadata={"source_label": raw_label, **dict(row.get("metadata", {}))},
            )
        )
    return records


def adapt_tool_calling_rows(rows: Iterable[dict[str, Any]], dataset: str, split: str) -> list[ToolCallingRecord]:
    records = []
    for index, row in enumerate(rows):
        input_text = row.get("input_text", row.get("question"))
        if not input_text:
            raise ValueError(f"Row {index} is missing input_text/question")
        expected = row.get("expected_tool_call", row.get("output", row.get("correct_answer")))
        decision = row.get("decision", row.get("correct_answer"))
        records.append(
            ToolCallingRecord(
                dataset=dataset,
                split=split,
                sample_id=str(row.get("sample_id", row.get("uuid", row.get("id", index)))),
                input_text=str(input_text),
                tools=tuple(row.get("tools", [])),
                expected_tool_call=expected,
                decision=str(decision) if decision is not None else None,
                metadata=dict(row.get("metadata", {})),
            )
        )
    return records


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Line {line_number} of {path} must be a JSON object")
            rows.append(value)
    return rows


def load_source_rows(path: str | Path) -> list[dict[str, Any]]:
    source_path = Path(path)
    if source_path.suffix == ".jsonl":
        return load_jsonl(source_path)
    if source_path.suffix == ".csv":
        with source_path.open(encoding="utf-8", newline="") as source:
            return [dict(row) for row in csv.DictReader(source)]
    if source_path.suffix == ".json":
        value = json.loads(source_path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list) and all(isinstance(row, dict) for row in value):
            return value
    raise ValueError(f"Unsupported source format for {path}; use .jsonl, .json, or .csv")


def write_jsonl(
    path: str | Path,
    records: Iterable[RetrievalRecord | OCRRecord | NLIRecord | ToolCallingRecord],
) -> None:
    with Path(path).open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
