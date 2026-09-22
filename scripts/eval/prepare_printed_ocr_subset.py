#!/usr/bin/env python3
"""Prepare the reproducible printed-document OCR evaluation subset."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz
import pyarrow.parquet as pq


MEDDIES_SOURCE = (
    "https://upload.wikimedia.org/wikipedia/commons/4/4a/Doi_trong_nguc_1.pdf"
)
MEDDIES_LICENSE = "Public Domain (Wikimedia Commons; PD-Vietnam and PD-US tags)"
VIETAGE_LICENSE = "CC-BY-SA-4.0"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_sample(
    output_dir: Path,
    sample_id: str,
    image_bytes: bytes,
    reference_text: str,
    metadata: dict[str, object],
    image_suffix: str = ".png",
) -> dict[str, object]:
    image_path = output_dir / "images" / f"{sample_id}{image_suffix}"
    text_path = output_dir / "text" / f"{sample_id}.txt"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(image_bytes)
    text_path.write_text(reference_text, encoding="utf-8")
    return {
        "sample_id": sample_id,
        "image": str(image_path.relative_to(output_dir)),
        "ground_truth": str(text_path.relative_to(output_dir)),
        "reference_text": reference_text,
        "image_sha256": sha256_bytes(image_bytes),
        "ground_truth_sha256": sha256_bytes(reference_text.encode("utf-8")),
        **metadata,
    }


def prepare_meddies(
    annotations_path: Path,
    pdf_path: Path,
    output_dir: Path,
    source_url: str,
    limit: int,
) -> list[dict[str, object]]:
    rows = [
        json.loads(line)
        for line in annotations_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = [row for row in rows if row["source_url"] == source_url]
    selected.sort(key=lambda row: row["page_number"])
    selected = selected[:limit]
    if len(selected) != limit:
        raise ValueError(f"Expected {limit} Meddies rows, found {len(selected)}")

    document = fitz.open(pdf_path)
    records = []
    for row in selected:
        page_number = int(row["page_number"])
        if page_number >= len(document):
            raise ValueError(f"Page {page_number} is outside {pdf_path}")
        pixmap = document.load_page(page_number).get_pixmap(
            matrix=fitz.Matrix(2, 2), alpha=False
        )
        sample_id = f"meddiesocr_{page_number:03d}"
        records.append(
            write_sample(
                output_dir,
                sample_id,
                pixmap.tobytes("png"),
                row["text"],
                {
                    "source_dataset": "MeddiesOCR",
                    "source_url": source_url,
                    "source_license": MEDDIES_LICENSE,
                    "license": MEDDIES_LICENSE,
                    "document_type": "printed_document",
                    "image_origin": "rendered_from_public_domain_source_pdf",
                    "doc_id": row["doc_id"],
                    "page_number": page_number,
                    "difficulty": "historical_print_scan",
                },
            )
        )
    document.close()
    return records


def prepare_vietage(
    parquet_path: Path, output_dir: Path, limit: int
) -> list[dict[str, object]]:
    rows = pq.read_table(
        parquet_path, columns=["id", "image", "label", "metadata"]
    ).to_pylist()
    selected = [row for row in rows if row["metadata"]["stratum"] == "wikisource_qn"]
    selected.sort(key=lambda row: row["id"])
    selected = selected[:limit]
    if len(selected) != limit:
        raise ValueError(f"Expected {limit} VietAge rows, found {len(selected)}")

    records = []
    for index, row in enumerate(selected, start=1):
        metadata = row["metadata"]
        if metadata["license"] != VIETAGE_LICENSE:
            raise ValueError(f"Unexpected VietAge license: {metadata['license']}")
        records.append(
            write_sample(
                output_dir,
                f"vietage_{index:03d}",
                row["image"]["bytes"],
                row["label"],
                {
                    "source_dataset": "VietAge-OCR",
                    "source_url": metadata["source"],
                    "source_license": metadata["license"],
                    "license": metadata["license"],
                    "document_type": "printed_document",
                    "image_origin": "dataset_embedded_image",
                    "doc_id": row["id"],
                    "page_number": metadata["page"],
                    "difficulty": "historical_print_scan",
                },
                image_suffix=".jpg",
            )
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--meddies-annotations", type=Path, required=True)
    parser.add_argument("--meddies-pdf", type=Path, required=True)
    parser.add_argument("--vietage-parquet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--meddies-limit", type=int, default=30)
    parser.add_argument("--vietage-limit", type=int, default=10)
    args = parser.parse_args()

    meddies_dir = args.output / "meddiesocr_30_pages"
    vietage_dir = args.output / "vietage_10_pages"
    meddies = prepare_meddies(
        args.meddies_annotations,
        args.meddies_pdf,
        meddies_dir,
        MEDDIES_SOURCE,
        args.meddies_limit,
    )
    vietage = prepare_vietage(args.vietage_parquet, vietage_dir, args.vietage_limit)
    for directory, records in ((meddies_dir, meddies), (vietage_dir, vietage)):
        manifest = directory / "manifest.jsonl"
        manifest.write_text(
            "".join(
                json.dumps(record, ensure_ascii=False) + "\n" for record in records
            ),
            encoding="utf-8",
        )
        print(f"{directory}: {len(records)} samples, manifest={manifest}")


if __name__ == "__main__":
    main()
