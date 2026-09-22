# Yuxi benchmark handoff for 2026-09-23

Date prepared: 2026-09-22
Branch: `phase2-viquad-benchmark`
Latest commit: `2e8cc176e`

## Current verified state

The following results were executed with real data and should be treated as
the current baseline:

| Area | Scope | Result | Artifact |
|---|---|---:|---|
| AgentKit Vietnamese Function Calling | Qwen3 native, 100 samples | tool selection 100%, exact match 93% | `benchmarks/results/vietnamese_function_calling_qwen3_native_schema_final_100.json` |
| When2Call | Qwen3 native, 20 samples per class, 60 total | decision accuracy 55% | `benchmarks/results/when2call_qwen3_native_stratified60.json` |
| VieQuAD BM25 | full validation, 2,048 queries | Recall@10 91.80%, MRR@10 70.10% | `benchmarks/results/viequad_bm25_full_final.json` |
| Native Ollama LangGraph loop | chatbot/sub-agent path | tool call → ToolMessage → final answer verified | Docker integration check |

Benchmark result files are local and ignored by Git. Recreate them from the
commands in the benchmark README and the native Ollama evaluation document.

## Runtime prerequisite

The API container must be able to reach Ollama on the host:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
docker exec api-dev curl -fsS http://host.docker.internal:11434/api/tags
```

If the second command fails, do not run a benchmark or keep its output. The
last failure was caused by Ollama binding only to `127.0.0.1`; the invalid
zero-score artifact was removed.

## Work still pending

### P0 — Real E2E RAG generation

Build a runner that calls the real Yuxi retrieval/generation path with Ollama
and records per sample:

- query and gold answer;
- retrieved document IDs and hit@K;
- generated answer;
- EM and Vietnamese token F1;
- answerable/unanswerable decision;
- abstention precision/recall;
- language validity;
- latency and failures.

Do not use `backend/scripts/run_e2e_sample.py` for metrics: it constructs
predictions from gold answers and is simulation-only.

Recommended order:

1. 20-sample smoke using `ollama:qwen2.5:7b` or `ollama:qwen3:8b`.
2. 100-sample validation.
3. Full available split only after the smoke artifact is valid.

### P1 — Grounding/NLI

- Run the ViWikiFC adapter artifact through a real NLI/grounding evaluator.
- Report evidence recall separately from entailment/contradiction metrics.
- Do not call ViWikiFC a native RAG benchmark.
- Keep the internal gold-claim set marked pending until labels and hashes are
  exported.

### P1 — OCR metrics

- Run CER, WER, normalized CER, exact match, and latency on VinText.
- Run the 30 MeddiesOCR + 10 VietAge pages only as an internal evaluation set.
- Keep MeddiesOCR non-redistributable until annotation licensing is clarified.
- Do not mark the printed-document track public or complete based only on the
  existing manifests.

### P2 — Agent benchmark expansion

- Add and lock a BFCL subset of 50–100 tasks.
- Decide whether to keep When2Call at stratified 60 or expand it after the
  decision prompt is stable.
- Review the 7% remaining Vietnamese Function Calling failures; separate gold
  normalization problems from model slot extraction problems.

### P2 — Production retrieval validation

- Run keyword, vector, hybrid, and RRF against a populated Yuxi KB.
- Compare the production path with the standalone BM25 baseline.
- Keep `vector=0.3`, `bm25=0.7` labeled as the production default, not as the
  globally optimal VieQuAD weight; the full VieQuAD holdout favored pure BM25.

## Definition of done for the next session

- [ ] Real E2E generation runner exists and does not use gold-derived answers.
- [ ] 20-sample RAG smoke has a valid artifact and reproducible command.
- [ ] EM/F1, answerability, abstention, language, and latency are reported.
- [ ] ViWikiFC NLI run is measured or explicitly blocked with a documented
      reason.
- [ ] OCR metric run is measured or explicitly blocked by license/runtime.
- [ ] Every new result has a command, model, split, sample count, and artifact.
- [ ] Changes are tested in Docker and committed/pushed with a clear message.

## Do not claim yet

- “Full E2E RAG is complete.”
- “MeddiesOCR is cleared for redistribution.”
- “When2Call represents Vietnamese product quality.”
- “The BM25 baseline is the production RAG score.”
- “The remaining AgentKit errors are all model errors”; several are annotation
  or schema-normalization mismatches.
