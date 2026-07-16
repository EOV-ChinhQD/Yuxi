import json
import os
from typing import Any
import pytest
from pydantic import ValidationError

from yuxi.evaluation.stages.base import (
    EvaluationStage,
    ReportSchema,
    calculate_bootstrap_ci,
)
from yuxi.evaluation.config.manifest import EvaluationManifest
from yuxi.evaluation.datasets.loader import DatasetLoader, EvaluationDataset


# 1. Test Protocol check using runtime checkable
def test_evaluation_stage_protocol():
    class DummyStage:
        def prepare(self, dataset_path: str, manifest: dict[str, Any]) -> None:
            self.dataset_path = dataset_path
            self.manifest = manifest

        async def run(self) -> None:
            pass

        async def evaluate(self) -> dict[str, Any]:
            return {"accuracy": 0.9}

        def report(self) -> ReportSchema:
            return ReportSchema(
                metrics={"accuracy": 0.9},
                performance={"latency_ms": 120.0},
                cost={"tokens": 1500},
                reliability={"retries": 0},
                regression={"improvement": 0.05},
            )

    # Verify that DummyStage implements the EvaluationStage Protocol
    assert isinstance(DummyStage(), EvaluationStage)


# 2. Test calculate_bootstrap_ci function
def test_bootstrap_ci():
    # Test normal inputs
    scores = [0.8, 0.85, 0.9, 0.75, 0.95]
    mean, lower, upper = calculate_bootstrap_ci(scores, n_bootstrap=100, ci_level=0.9)
    assert 0.7 <= mean <= 0.95
    assert lower <= mean <= upper

    # Test empty input
    assert calculate_bootstrap_ci([]) == (0.0, 0.0, 0.0)


# 3. Test EvaluationManifest loading and validation
def test_manifest_loading(tmp_path):
    yaml_content = """
experiment_id: EXP_TEST_A
dataset: test_snapshot_v1
embedding: 
  provider: openai
  model: text-embedding-3-small
  revision: "2025-01"
chunker: structural_v2
retriever: hybrid_alpha
reranker: qwen_rerank
llm: gemini-2.5-flash
date: 2026-07-15
"""
    manifest = EvaluationManifest.from_yaml(yaml_content)
    assert manifest.experiment_id == "EXP_TEST_A"
    assert manifest.dataset == "test_snapshot_v1"
    assert manifest.embedding.provider == "openai"
    assert manifest.embedding.revision == "2025-01"
    assert manifest.reranker == "qwen_rerank"

    # Test file loader
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(yaml_content, encoding="utf-8")
    
    loaded_manifest = EvaluationManifest.from_file(str(manifest_file))
    assert loaded_manifest.experiment_id == "EXP_TEST_A"


def test_manifest_validation_error():
    # Missing required field 'llm'
    yaml_invalid = """
experiment_id: EXP_TEST_B
dataset: test_snapshot_v1
embedding: 
  provider: openai
  model: text-embedding-3-small
chunker: structural_v2
retriever: hybrid_alpha
"""
    with pytest.raises(ValueError):
        EvaluationManifest.from_yaml(yaml_invalid)


# 4. Test DatasetLoader
def test_dataset_loader_success(tmp_path):
    jsonl_content = """{"query": "Làm thế nào để cấu hình RAG?", "gold_chunk_ids": ["c1", "c2"], "gold_answer": "Sử dụng Milvus và LangChain."}
{"query": "Tại sao dùng RRF?", "gold_chunk_ids": ["c3"]}
{"query": "Câu hỏi không có gold answer?"}
"""
    dataset_file = tmp_path / "dataset.jsonl"
    dataset_file.write_text(jsonl_content, encoding="utf-8")

    # Write companion metadata.json
    metadata_content = {
        "name": "Custom Test Dataset",
        "description": "Dataset dùng cho unit test",
        "corpus_metadata": {
            "doc_type": "pdf",
            "language": "vi",
            "source": "yuxi_docs"
        }
    }
    metadata_file = tmp_path / "dataset_metadata.json"
    metadata_file.write_text(json.dumps(metadata_content), encoding="utf-8")

    # Load dataset
    dataset = DatasetLoader.load_from_jsonl(str(dataset_file))
    
    assert isinstance(dataset, EvaluationDataset)
    assert dataset.metadata.name == "Custom Test Dataset"
    assert dataset.metadata.description == "Dataset dùng cho unit test"
    assert dataset.metadata.corpus_metadata["doc_type"] == "pdf"
    
    # Verify items
    assert len(dataset.items) == 3
    assert dataset.items[0].query == "Làm thế nào để cấu hình RAG?"
    assert dataset.items[0].gold_chunk_ids == ["c1", "c2"]
    assert dataset.items[0].gold_answer == "Sử dụng Milvus và LangChain."
    assert dataset.items[1].gold_chunk_ids == ["c3"]
    assert dataset.items[2].gold_answer is None


def test_dataset_loader_missing_query(tmp_path):
    # Missing required field 'query' on line 2
    jsonl_invalid = """{"query": "Làm thế nào để cấu hình RAG?", "gold_chunk_ids": ["c1"]}
{"gold_chunk_ids": ["c2"]}
"""
    dataset_file = tmp_path / "invalid.jsonl"
    dataset_file.write_text(jsonl_invalid, encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        DatasetLoader.load_from_jsonl(str(dataset_file))
    
    assert "Thiếu trường 'query' bắt buộc" in str(excinfo.value)
