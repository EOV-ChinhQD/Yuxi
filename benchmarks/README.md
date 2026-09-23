# Yuxi benchmark registry

The registry separates benchmark selection from downloaded data. Dataset files are not committed here unless their license and provenance allow redistribution.

Run the prerequisite check before downloading or executing a benchmark:

```bash
python scripts/eval/check_benchmark_prerequisites.py
```

Raw data, normalized artifacts, and metric outputs are local-only under the ignored `benchmarks/` workspace. The fixed selection and completion gate are defined in `selection.json`.

`preparation-lock.json` records the locally prepared artifact counts and hashes. It does not mean the benchmark has been scored.

`registry.json` is the source of truth for benchmark role, task, source, revision, license, split, metrics, and limitations. Each downloaded snapshot must record its exact revision and SHA-256 before it is used in a report.

Retrieval and QA artifacts use this normalized record:

```json
{
  "dataset": "vire",
  "split": "test",
  "query_id": "q-001",
  "query": "...",
  "documents": [],
  "relevant_document_ids": [],
  "gold_answer": null,
  "answerable": null,
  "metadata": {}
}
```

OCR artifacts use `dataset`, `split`, `sample_id`, `image_path`, `reference_text`, `source`, and `metadata`. Normalize a snapshot with:

```bash
python scripts/eval/prepare_benchmark_artifact.py \
  --input /path/to/source.jsonl \
  --output benchmarks/artifacts/vire/test.jsonl \
  --dataset vire --split test --task retrieval
```

The adapter accepts `.jsonl`, JSON arrays/objects, and CSV sources. ViWikiFC CSV can be normalized with `--task nli`; the Vietnamese Function Calling JSON file uses `--task tool_calling`.

VieQuADRetrieval is distributed as three Parquet files and uses a separate preparation command:

```bash
python scripts/eval/prepare_viequad_retrieval.py \
  --queries benchmarks/raw/viequad-retrieval/queries.parquet \
  --corpus benchmarks/raw/viequad-retrieval/corpus.parquet \
  --qrels benchmarks/raw/viequad-retrieval/qrels.parquet \
  --output benchmarks/artifacts/retrieval/viequad
```

The printed-document set is intentionally a separate artifact. Add 20–50 public Vietnamese printed-document pages only after the source URL, license, image hash, and ground-truth hash have been recorded in `ocr/printed-document-sources.jsonl`. Scene text (VinText) and optional handwriting stress tracks must not be reported as printed-document OCR results.

The current local subset is reproducible with:

```bash
uv run python scripts/eval/prepare_printed_ocr_subset.py \
  --meddies-annotations benchmarks/raw/meddiesocr_annotations.jsonl \
  --meddies-pdf benchmarks/raw/ocr_sources/doi-trong-nguc-1.pdf \
  --vietage-parquet benchmarks/raw/vietage-ocr-test.parquet \
  --output benchmarks/artifacts/printed_real
```

This produces 30 MeddiesOCR pages and 10 VietAge-OCR pages with image and
ground-truth SHA-256 values in separate manifests. The source audit is in
`benchmarks/license-audit.json`. The Meddies source PDF is Public Domain, but
the MeddiesOCR dataset does not declare an annotation license, so its
ground-truth text is cleared for the local benchmark only until that license
is clarified. The selected VietAge records declare CC-BY-SA-4.0.

The local OCR pilot is scored with RapidOCR without a fallback parser:

```bash
docker exec api-dev python /app/project-scripts/eval/run_printed_ocr.py \
  --manifest /app/benchmarks/artifacts/printed_real/meddiesocr_30_pages/manifest.jsonl \
  --root /app/benchmarks/artifacts/printed_real/meddiesocr_30_pages \
  --output /app/benchmarks/results/printed_ocr_meddiesocr_30_rapid_ocr.json \
  --engine rapid_ocr
```

The same command applies to the VietAge manifest. The pilot preserves
Vietnamese diacritics using Unicode NFC, reports CER/WER/exact match and
latency, and must not be interpreted as a representative enterprise-document
OCR benchmark. Meddies results remain internal/conditional because the
annotation license is undeclared.

## First benchmark runs

Run the retrieval baseline with:

```bash
uv run python scripts/eval/run_viequad_bm25.py \
  --queries benchmarks/artifacts/retrieval/viequad/queries.jsonl \
  --corpus benchmarks/artifacts/retrieval/viequad/corpus.jsonl \
  --qrels benchmarks/artifacts/retrieval/viequad/qrels.jsonl \
  --output benchmarks/results/viequad_bm25_validation.json
```

The current result is a BM25 reference baseline, not a Yuxi production-pipeline
score. Agent data contracts can be checked with:

```bash
uv run python scripts/eval/run_agent_contract_validation.py \
  --vietnamese benchmarks/artifacts/agent/vietnamese-function-calling/test.jsonl \
  --when2call benchmarks/artifacts/agent/when2call/test_mcq.jsonl \
  --output benchmarks/results/agent_contract_validation.json
```

This validates 2,899 Vietnamese function-calling records and 3,652 When2Call
records. It deliberately does not report model accuracy; a model-backed agent
executor is still required for tool-selection and argument-scoring metrics.

The AgentKit tool contract is versioned at `benchmarks/agentkit/tool-suite.json`
and is generated from the registered Yuxi tools with:

```bash
PYTHONPATH=backend/package uv run python scripts/eval/prepare_agentkit_tool_suite.py \
  --output benchmarks/agentkit/tool-suite.json
```

Run the model-backed When2Call decision smoke inside `api-dev`:

```bash
docker exec api-dev python /app/project-scripts/eval/run_when2call_local.py \
  --input /app/benchmarks/artifacts/agent/when2call/test_mcq.jsonl \
  --output /app/benchmarks/results/when2call_qwen3_native_stratified60.json \
  --model ollama:qwen3:8b --per-label 20 --native-ollama
```

The When2Call runner enables a model-backed relevance gate by default. Use
`--no-relevance-gate` only for an explicit ungated baseline comparison.

For the E2E RAG runner, `--evidence-k 3` selects the highest-ranked passages
with direct query-token overlap while preserving the retrieval hit metrics:

```bash
docker exec api-dev python /app/project-scripts/eval/run_e2e_viquad2.py \
  --queries /app/benchmarks/artifacts/e2e/uit-viquad-2/queries.jsonl \
  --corpus /app/benchmarks/artifacts/e2e/uit-viquad-2/corpus.jsonl \
  --output /app/benchmarks/results/uit-viquad-2_e2e_improved.json \
  --model ollama:qwen2.5:7b --top-k 5 --evidence-k 3
```

This reports decision accuracy for `cannot_answer`, `request_for_info`, and
`tool_call`; it is not an argument exact-match benchmark.

The completed single-evidence RAG ablation uses the local Qwen2.5 1.5B model
with the same fixed 150-question sample:

```bash
docker exec api-dev python /app/project-scripts/eval/run_e2e_viquad2.py \
  --queries /app/benchmarks/artifacts/e2e/uit-viquad-2/queries.jsonl \
  --corpus /app/benchmarks/artifacts/e2e/uit-viquad-2/corpus.jsonl \
  --output /app/benchmarks/results/uit-viquad-2_e2e_qwen25_15b_full150_single_evidence.json \
  --model ollama:qwen2.5:1.5b --top-k 1 --evidence-k 1 \
  --n-answerable 100 --n-impossible 50 --max-calls 160 \
  --max-tokens 128 --timeout 60
```

This is an ablation/robustness result, not a controlled comparison with the
DeepSeek primary RAG result because the model and evidence configuration differ.

NLI claims and agent tool-calling tasks can use the public sources in `source-lock.json`. ViWikiFC is normalized to `ENTAILMENT`, `CONTRADICTION`, and `NEUTRAL`; When2Call and Vietnamese Function Calling are normalized to the tool-calling schema. These remain source-locked until the exported artifact has its own hash and test report.
