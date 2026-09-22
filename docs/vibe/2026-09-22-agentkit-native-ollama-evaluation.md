# AgentKit native Ollama evaluation

Date: 2026-09-22

## Scope

This change validates the AgentKit-style Vietnamese function-calling path with
the local `ollama:qwen3:8b` model. The benchmark runner is executed inside
`api-dev`; `scripts/` and `benchmarks/` are mounted by Docker Compose so the
command and generated reports use the same runtime as the application.

## Implementation

- Chatbot and sub-agent graphs use Ollama's native `/api/chat` tool-calling
  protocol when the configured provider is Ollama.
- Other providers continue to use the existing OpenAI-compatible loader.
- The benchmark runner validates tool names, required/schema fields, exact
  source casing, download-vs-recommendation intent, and unambiguous IDs.
- Lossless repairs are limited to source-backed casing, honorific prefixes,
  IDs, and date/time field boundaries. Ambiguous semantic normalization is not
  repaired automatically.

## Reproducible command

Start Ollama so the Docker network can reach it:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

Then run:

```bash
docker exec api-dev python /app/project-scripts/eval/run_agentkit_local_smoke.py \
  --input /app/benchmarks/artifacts/agent/vietnamese-function-calling/test.jsonl \
  --output /app/benchmarks/results/vietnamese_function_calling_qwen3_native_schema_final_100.json \
  --model ollama:qwen3:8b --limit 100 --timeout 90 --native-ollama
```

## Measured result

The latest valid 100-sample run produced:

| Metric | Result |
|---|---:|
| Tool selection | 100% |
| Argument exact match | 93% |
| Exact match | 93% |

The result is stored locally at
`benchmarks/results/vietnamese_function_calling_qwen3_native_schema_final_100.json`.
Benchmark result files are intentionally ignored by Git; the report must be
regenerated from the command above.

## Remaining limitations

The remaining misses are mostly semantic slot extraction and inconsistent gold
normalization, such as `Toán cấp 2` being scored against `Toán`, or mapping
`giao tiếp` to `goal` versus `level`. These cases should be resolved by
reviewing the benchmark annotation/schema contract before adding more runtime
heuristics.

## Acceptance checklist

- [x] Native Ollama tool calling completes the LangGraph tool loop.
- [x] Smoke and 100-sample runs execute inside `api-dev`.
- [x] Schema-aware validation and bounded repair are lint-clean.
- [x] Latest valid run reaches 100% tool selection and 93% exact match.
- [x] When2Call stratified model-backed smoke has been executed.
- [ ] Full RAG and E2E API regression remain separate follow-up phases.

## When2Call result

The native Qwen3 stratified run used 20 samples for each decision class (60
total) and produced 55% overall decision accuracy:

| Decision | Accuracy |
|---|---:|
| `cannot_answer` | 45% |
| `request_for_info` | 70% |
| `tool_call` | 50% |

This is a secondary decision benchmark. Its adversarial tool descriptions and
mixed-language examples make it unsuitable as a direct Vietnamese product
quality score. The local artifact is
`benchmarks/results/when2call_qwen3_native_stratified60.json`.

## RAG retrieval regression

The full 2,048-query VieQuAD BM25 baseline was rerun inside `api-dev`:

| Metric | Result |
|---|---:|
| Recall@1 | 58.06% |
| Recall@5 | 85.74% |
| Recall@10 | 91.80% |
| MRR@10 | 70.10% |
| nDCG@10 | 49.19% |
| Mean latency | 11.03 ms/query |

The local result is
`benchmarks/results/viequad_bm25_full_final.json`. The existing simulated
`backend/scripts/run_e2e_sample.py` is not used as an E2E score because it
constructs predictions from gold answers. A real generation runner is still
required before reporting full E2E EM/F1.
