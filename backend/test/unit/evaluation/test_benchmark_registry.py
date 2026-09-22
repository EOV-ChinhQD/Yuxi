import json

import pytest

from yuxi.evaluation.benchmark_registry import (
    adapt_nli_rows,
    adapt_ocr_rows,
    adapt_retrieval_rows,
    adapt_tool_calling_rows,
    load_jsonl,
    load_source_rows,
    sha256_file,
    write_jsonl,
)


def test_adapt_retrieval_rows_supports_viquad_style_fields():
    records = adapt_retrieval_rows(
        [{"id": "q1", "question": "Ai?", "gold_passage_id": "p1", "answer": "Nguyễn."}],
        "uit-viquad-2",
        "test",
    )

    assert records[0].to_dict() == {
        "dataset": "uit-viquad-2",
        "split": "test",
        "query_id": "q1",
        "query": "Ai?",
        "documents": [],
        "relevant_document_ids": ["p1"],
        "gold_answer": "Nguyễn.",
        "answerable": None,
        "metadata": {},
    }


def test_adapt_ocr_rows_requires_reference_text():
    with pytest.raises(ValueError, match="reference_text"):
        adapt_ocr_rows([{"sample_id": "OCR-1", "image_path": "a.png"}], "vintext", "test")


def test_adapt_nli_rows_maps_vikwifc_labels():
    record = adapt_nli_rows(
        [{"pairID": "p1", "claim": "A", "evidence": "B", "gold_label": "Supports"}],
        "viwikifc",
        "test",
    )[0]

    assert record.label == "ENTAILMENT"
    assert record.evidence == ("B",)

    neutral = adapt_nli_rows(
        [{"claim": "C", "evidence": "D", "gold_label": "Not_Enough_Information"}],
        "viwikifc",
        "test",
    )[0]
    assert neutral.label == "NEUTRAL"


def test_adapt_tool_calling_rows_supports_when2call_fields():
    record = adapt_tool_calling_rows(
        [{"uuid": "t1", "question": "Can you call it?", "correct_answer": "cannot_answer", "tools": []}],
        "when2call",
        "test",
    )[0]

    assert record.sample_id == "t1"
    assert record.decision == "cannot_answer"


def test_jsonl_round_trip_preserves_vietnamese(tmp_path):
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({"query": "Đồ thị tri thức?"}, ensure_ascii=False) + "\n", encoding="utf-8")
    records = adapt_retrieval_rows(load_jsonl(source), "vire", "test")
    output = tmp_path / "artifact.jsonl"
    write_jsonl(output, records)

    assert "Đồ thị tri thức" in output.read_text(encoding="utf-8")
    assert len(sha256_file(output)) == 64


def test_source_loader_supports_csv_and_json_array(tmp_path):
    csv_source = tmp_path / "claims.csv"
    csv_source.write_text("claim,evidence,gold_label\nA,B,Supports\n", encoding="utf-8")
    json_source = tmp_path / "tools.json"
    json_source.write_text('[{"input_text":"Gọi tool","tools":[]}]', encoding="utf-8")

    assert load_source_rows(csv_source)[0]["gold_label"] == "Supports"
    assert load_source_rows(json_source)[0]["input_text"] == "Gọi tool"
