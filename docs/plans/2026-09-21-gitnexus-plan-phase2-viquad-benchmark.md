# GitNexus Engineering Plan

> Task: Phase 2 — ViQuAD benchmark (T2 data prep, T3 retrieval ablation, T4 E2E 300-sample, T5 OCR metrics, T6 consensus grid-search)
> Evidence verified at commit a4794c855f8042735533b5dee0ca93afba69e273; GitNexus index not used (Yuxi not indexed; fallback mode — all findings source-derived).
> Evidence provenance schema 2; global dirty digest 62115171e561b673367ff90d9a7fa47604e41e3e0a77116470e18b33851af969; cited-path manifest 11 sorted entries; exact generated plan path excluded.

## 1. Objective

Produce honest, reproducible benchmark numbers proving the current RAG/agent stack beats baselines: retrieval ablation on full ViQuAD dev (T3), E2E answer quality on a stratified 300-sample across 3 arms (T4), real OCR CER/WER on rendered ground-truth PDFs (T5), and data-driven consensus weights replacing the dummy tuner (T6) — all fed by a normalized ViQuAD corpus+qrels ingested into a dedicated bench KB (T2).

## 2. Current Behaviour

- [verified] Eval harness exists and runs through the API: `POST /databases/{kb_id}/datasets/upload` accepts `.jsonl` only (`knowledge_eval_router.py:51`), parsed by `EvaluationService._parse_jsonl_questions` requiring `query` per line with optional `gold_chunk_ids` / `gold_answer` (`service.py:149-172`).
- [verified] `POST /databases/{kb_id}/runs` takes `{dataset_id, name, model_config}` where `RunEvaluationRequest.retrieval_config` is aliased from `model_config` (`knowledge_eval_router.py:35-38`), and the service merges it over KB defaults via `retrieval_config.update(model_config)` (`service.py:481`) — so ablations need no code change, only different `model_config` per run.
- [verified] Per-question eval goes through `SemanticRouter.route` with `llm_model_spec` defaulting to `gpt-4o-mini` (`evaluator.py:60-80`); KB defaults come from `get_query_params_config` options (`base.py:1144-1151`).
- [verified] Consensus fusion reads `KB.metadata_["consensus_weights"]` when present, else constructor defaults (`consensus_retriever.py:306-320`); relational queries get hardcoded routing weights (`:90-95`).
- [verified] `backend/scripts/tune_consensus_weights.py` is a dummy (`sleep(2)` + hardcoded weights, full file read); `scripts/benchmark_ocr.py:calculate_cer_wer` returns `0.0`.
- [verified] Ingest path for T2: `POST /databases/{kb_id}/documents` (`knowledge_router.py:661`), `POST .../documents/add` (`:844`), `POST .../documents/parse` (`:1140`); the e2e test demonstrates the full upload→parse→poll-indexed→chunks→chat flow against `localhost:5050` (`test_rag_pipeline_e2e.py:1-60`).
- [verified] Seeded data facts (session measurement): HF `NghiemAbe/viquad` train 33084 rows, cols `[answer, prompt]`; parsed q/ctx 33084/33084, unique contexts 9959, answer-in-context 18992; cache at `/mnt/new-volume/yuxi-eval/hf_cache`.

## 3. Relevant Architecture

- Modules: `yuxi.knowledge.eval` (service/evaluator/metrics/OCR metrics stub) → `yuxi.knowledge.retrieval` (consensus, rewriter, multi-hop, router) → Milvus vectors + Neo4j graph + Postgres metadata; API layer `backend/server/routers/knowledge_{router,eval_router}.py`; bench scripts in `backend/scripts/` + `scripts/`.
- Boundaries: all bench execution goes through the running `api-dev` container (hot-reload) — no direct DB writes except the already-applied embedding_cache fix; large artifacts (corpus, runs output) live on `/mnt/new-volume/yuxi-eval/` (fuseblk, blobs only), never on `/` (7GB free).
- Established pattern: requests-based driver scripts (e2e test style) over `POST /runs` with per-arm `model_config`; weights persisted in KB `metadata_`, never in code.

## 4. GitNexus Findings

Fallback mode — Yuxi is not in the GitNexus index (`list_repos` returned only EOV-WaterDemand/HanoiWaterDemand), so no graph/impact queries were run. All findings below are source-derived (grep + targeted reads), each with its provenance:

- `grep "class RunEvaluationRequest" -A 25 knowledge_eval_router.py` → `{dataset_id, name, model_config→retrieval_config}`; quote: `retrieval_config: dict[str, Any] = Field(default_factory=dict, alias="model_config")`.
- `grep "retrieval_config" eval/service.py` → lines 465-509 (KB-default fallback), 526-583 (run loop, judge model pick), 659/714 (result persistence).
- `sed base.py:1144-1190` → defaults extracted from `get_query_params_config(kb_id)` options list.
- `sed consensus_retriever.py:295-320` → dynamic-weights branch; `:72-95` → KB-metadata load + relational routing.
- `cat backend/scripts/tune_consensus_weights.py` (whole, 50 lines) → dummy confirmed.
- `grep "^def/^class" scripts/benchmark_ocr.py` → `calculate_cer_wer`, `evaluate_layout`, `evaluate_structure`, `run_engine`, `main`.
- `sed test_rag_pipeline_e2e.py:1-60` → 8-stage requests flow, `BASE_URL localhost:5050`, admin/admin.
- `grep "@knowledge.post" knowledge_router.py` → ingest endpoints at :661/:844/:1140/:1172.
- `grep "_parse_jsonl_questions" -A 45 service.py` → `query` required; `gold_chunk_ids`/`gold_answer` optional flags.

## 5. Statement-Level PDG Findings

No PDG layer indexed (repo not in GitNexus; no `--pdg` run — deliberately skipped: indexing cost vs little value for new-script work). Statement-level constraints below are source-derived:

- `service.py:481 retrieval_config.update(model_config)` — run-level config strictly overrides KB defaults; ablation arms are isolated per run row (`:526-583`), no cross-run leakage. Implementation consequence: T3 needs zero production-code edits.
- `evaluator.py:60-80` — every eval question passes `SemanticRouter`; a question misrouted as CHIT_CHAT skips retrieval and would score 0. Consequence: T3/T4 driver must assert route distribution in run results and quarantine chit-chat verdicts.
- `consensus_retriever.py:306-320` — `dynamic_weights.get(key, self.w_*)` falls back per-key; partial metadata writes are safe. Consequence: T6 can write winners incrementally.
- `service.py:149-172` — a JSONL line missing `query` raises and aborts the whole upload. Consequence: T2 writer must validate every line before upload.

## 6. Proposed Changes

- `backend/scripts/prepare_viquad_bench.py` (new): parse HF cache → `corpus/` (9959 passage files, stable `passage_id`), `qrels.jsonl` (`query`, `gold_passage_id`, `gold_answer`), `eval_sample300.jsonl` (stratified: answerable/unanswerable ratio preserved, de-dup passages). Validate-then-write; all outputs under `/mnt/new-volume/yuxi-eval/`.
- Bench KB `BENCH_VIQUAD` (runtime object, no file): created via API, corpus ingested via `:661`→`:1140`, polled to `indexed`; chunk→passage back-map built from the chunks endpoint (same pattern as e2e STAGE 6).
- `backend/scripts/run_retrieval_ablation.py` (new): 6 `POST /runs` arms (BM25 pyvi off/on → vector → hybrid → +RRF → +rewrite → +consensus) with discovered `model_config` keys; passage-level hit (retrieved chunk ∈ gold passage) as primary, chunk-id hit only if mapping proves 1:1.
- `backend/scripts/run_e2e_sample.py` (new): 300-sample × 3 arms (retrieval-only baseline vs full RAG vs +agent chat); EM/F1 via `AnswerMetrics`, judge model pinned to a configured spec.
- `scripts/benchmark_ocr.py` (modify `calculate_cer_wer` only): real CER/WER via `jiwer` (add to test-group deps if missing); ground-truth PDFs rendered from ViQuAD passages with known text.
- `backend/scripts/tune_consensus_weights.py` (replace dummy body, keep CLI): grid search over the 4 weights on a retrieval metric (nDCG@5), reusing `EvaluationService` or `/runs`; write winner to `KB.metadata_["consensus_weights"]`; keep `--reset`.
- `docs/vibe/2026-09-21-nghiem-thu-rag-benchmark.md` (append): results tables per workstream.

## 7. Implementation Sequence

1. T2a — Write `prepare_viquad_bench.py`; emit corpus + qrels + sample300 to `/mnt/new-volume/yuxi-eval/`; assert counts (9959 passages, 33084 qrels, 300 sample) and zero unparseable lines. (Stop-safe: pure local files.)
2. T2b — Create `BENCH_VIQUAD` via API, ingest corpus, poll to indexed, build chunk→passage map; assert indexed chunk count > 0 and map coverage = 100% of passages.
3. T3a (discovery) — Enumerate exact `model_config` keys from `get_query_params_config` (via API database-info or one debug run); record the 6 arm configs in the vibe doc. (Blocks T3b/T4/T6.)
4. T3b — Run 6 retrieval arms on full dev qrels; collect recall@5/nDCG@5/MRR; quarantine chit-chat-routed questions; write table.
5. T4 — Run 300-sample × 3 arms with pinned judge/answer model; EM/F1 + judge verdicts; write table + failure buckets (≥20 inspected).
6. T5 — Render ground-truth PDFs, run `run_engine` per engine, real CER/WER via `jiwer`; table per engine.
7. T6 — Implement grid search, run on retrieval metric, write winning weights to KB metadata, re-run best T3 arm as confirmation; table (before/after).
8. Final — Regenerate/refresh result artifacts once (tables + figures data), append vibe doc, update changelog; single verification pass (T8 scope stays separate).

## 8. Test Strategy

- New scripts are drivers, not unit code: verify by contract asserts inside each script (counts, coverage, route distribution) + API run rows persisted (`GET /runs/{run_id}` re-readable).
- Existing tests touched: none (no production-code edits except `calculate_cer_wer` + tuner body). Regression: `backend/test/e2e/test_rag_pipeline_e2e.py` smoke after T2b (KB creation path shared); full T8 suite stays out of this plan.
- Edge cases: unanswerable ViQuAD questions (score 0 for retrieval-only, must not crash judge); `prompt`-wrapped rows failing parse (quarantine file, count asserted); Milvus re-index time on 9959 passages (poll with timeout + resume); LLM rate limits on 900 generations (batch + retry, cost logged).
- Verification commands (all exist and runnable):
  - `docker compose exec -T api uv run python scripts/seed_initial_users.py` (idempotent admin check)
  - `docker compose exec -T api uv run python backend/scripts/prepare_viquad_bench.py` (T2a; run from repo root mount — confirm cwd inside container before use)
  - `curl -s http://localhost:5050/api/system/health` (gate before any bench run)
  - `curl -s http://localhost:5173/ -o /dev/null -w "%{http_code}"` (web sanity, optional)

## 9. Risk and Impact Analysis

- No production-code blast radius: only two existing files change (`benchmark_ocr.py` one function, tuner body); both are scripts with no importers (verified by grep — no `import benchmark_ocr` / tuner imports outside CLI). No d=1 dependents to account for.
- Cost/time: 300×3 LLM generations + full-dev retrieval runs; mitigate with pinned cheap spec for retrieval arms (no generation) and generation only in T4.
- Gold-mapping brittleness: chunk ids are index-time artifacts — passage-level gold chosen deliberately; chunk-id gold explicitly rejected.
- Judge availability: `gpt-4o-mini` default likely unconfigured (env: Gemini/OpenRouter) — executor must discover the configured spec first (T3a) or all E2E arms fail at generation.
- Disk: `/` at 92% — all bench outputs to `/mnt/new-volume/yuxi-eval/`; monitor with `df -h /` before T3b/T4.
- Observability: every run persists a run row; driver scripts log arm config + run_id to the vibe doc for audit.

## 10. Files Expected to Change

| File | Symbols | Reason |
| ---- | ------- | ------ |
| `backend/scripts/prepare_viquad_bench.py` | (new) | T2 corpus/qrels/sample300 writer |
| `backend/scripts/run_retrieval_ablation.py` | (new) | T3 6-arm driver |
| `backend/scripts/run_e2e_sample.py` | (new) | T4 3-arm driver |
| `scripts/benchmark_ocr.py` | `calculate_cer_wer` | T5 real CER/WER via jiwer |
| `backend/scripts/tune_consensus_weights.py` | `tune_weights` | T6 real grid search |
| `docs/vibe/2026-09-21-nghiem-thu-rag-benchmark.md` | — | append result tables |
| `docs/develop-guides/changelog.md` | — | record bench + tuner changes |

## 11. Reusable Implementation Context

```yaml
implementation_context:
  task_summary: 'Phase 2 ViQuAD benchmark: T2 corpus/qrels ingest, T3 6-arm retrieval ablation via POST /runs model_config, T4 300-sample x 3-arm E2E, T5 real OCR CER/WER, T6 consensus grid-search replacing dummy tuner'
  acceptance_criteria:
    - 'T2: 9959 passages ingested to BENCH_VIQUAD, chunk->passage map 100%, qrels 33084 + sample300 validated'
    - 'T3: 6 arms recall@5/nDCG@5/MRR table on full dev, chit-chat quarantined'
    - 'T4: 300-sample EM/F1 table baseline vs full vs +agent, >=20 failures inspected'
    - 'T5: per-engine CER/WER table on rendered ground-truth PDFs, no 0.0 placeholders'
    - 'T6: grid-searched weights in KB metadata_, T3-best-arm confirmation delta recorded'
  evidence_provenance:
{
  "schema_version": 2,
  "head_commit": "a4794c855f8042735533b5dee0ca93afba69e273",
  "generated_plan_path": "docs/plans/2026-09-21-gitnexus-plan-phase2-viquad-benchmark.md",
  "global_dirty_digest": {
    "algorithm": "sha256",
    "canonicalization": "gitnexus-evidence-provenance-v2 NUL-framed UTF-8 records",
    "value": "62115171e561b673367ff90d9a7fa47604e41e3e0a77116470e18b33851af969"
  },
  "cited_path_manifest": [
    {
      "path": "backend/package/yuxi/knowledge/base.py",
      "object_kind": {
        "head": "regular",
        "index": "regular",
        "worktree": "regular",
        "untracked": "absent"
      },
      "state": "clean",
      "rename_from": null,
      "rename_to": null,
      "head_digest": "sha256:025b204d3e7d4af2509651b73e6257e68efcbb218530c11a27ac6cac947019b6",
      "index_digest": "sha256:025b204d3e7d4af2509651b73e6257e68efcbb218530c11a27ac6cac947019b6",
      "worktree_digest": "sha256:025b204d3e7d4af2509651b73e6257e68efcbb218530c11a27ac6cac947019b6",
      "untracked_digest": "absent"
    },
    {
      "path": "backend/package/yuxi/knowledge/eval/evaluator.py",
      "object_kind": {
        "head": "regular",
        "index": "regular",
        "worktree": "regular",
        "untracked": "absent"
      },
      "state": "clean",
      "rename_from": null,
      "rename_to": null,
      "head_digest": "sha256:315358645d80691468f931b0ec86dcc1f9b9ffd7f2d9b50eb4397611a35765d5",
      "index_digest": "sha256:315358645d80691468f931b0ec86dcc1f9b9ffd7f2d9b50eb4397611a35765d5",
      "worktree_digest": "sha256:315358645d80691468f931b0ec86dcc1f9b9ffd7f2d9b50eb4397611a35765d5",
      "untracked_digest": "absent"
    },
    {
      "path": "backend/package/yuxi/knowledge/eval/metrics.py",
      "object_kind": {
        "head": "regular",
        "index": "regular",
        "worktree": "regular",
        "untracked": "absent"
      },
      "state": "clean",
      "rename_from": null,
      "rename_to": null,
      "head_digest": "sha256:9a4936ecdc6b2babbf32325da2021aa63fce983330b2e7fe53af97e26eafaabe",
      "index_digest": "sha256:9a4936ecdc6b2babbf32325da2021aa63fce983330b2e7fe53af97e26eafaabe",
      "worktree_digest": "sha256:9a4936ecdc6b2babbf32325da2021aa63fce983330b2e7fe53af97e26eafaabe",
      "untracked_digest": "absent"
    },
    {
      "path": "backend/package/yuxi/knowledge/eval/service.py",
      "object_kind": {
        "head": "regular",
        "index": "regular",
        "worktree": "regular",
        "untracked": "absent"
      },
      "state": "clean",
      "rename_from": null,
      "rename_to": null,
      "head_digest": "sha256:cb485f33c609e6478f4a7867db33b7f06ca05207cda1ae2f947a49464978071b",
      "index_digest": "sha256:cb485f33c609e6478f4a7867db33b7f06ca05207cda1ae2f947a49464978071b",
      "worktree_digest": "sha256:cb485f33c609e6478f4a7867db33b7f06ca05207cda1ae2f947a49464978071b",
      "untracked_digest": "absent"
    },
    {
      "path": "backend/package/yuxi/knowledge/retrieval/consensus_retriever.py",
      "object_kind": {
        "head": "regular",
        "index": "regular",
        "worktree": "regular",
        "untracked": "absent"
      },
      "state": "clean",
      "rename_from": null,
      "rename_to": null,
      "head_digest": "sha256:c44d5e288f667669efef2978bdcedd202446cb9ebe24d5171591cdd967814b3c",
      "index_digest": "sha256:c44d5e288f667669efef2978bdcedd202446cb9ebe24d5171591cdd967814b3c",
      "worktree_digest": "sha256:c44d5e288f667669efef2978bdcedd202446cb9ebe24d5171591cdd967814b3c",
      "untracked_digest": "absent"
    },
    {
      "path": "backend/scripts/tune_consensus_weights.py",
      "object_kind": {
        "head": "regular",
        "index": "regular",
        "worktree": "regular",
        "untracked": "absent"
      },
      "state": "clean",
      "rename_from": null,
      "rename_to": null,
      "head_digest": "sha256:c1cf99172350ec1e2988439118659c2238482d5def7752314f0507ffb31f29db",
      "index_digest": "sha256:c1cf99172350ec1e2988439118659c2238482d5def7752314f0507ffb31f29db",
      "worktree_digest": "sha256:c1cf99172350ec1e2988439118659c2238482d5def7752314f0507ffb31f29db",
      "untracked_digest": "absent"
    },
    {
      "path": "backend/server/routers/knowledge_eval_router.py",
      "object_kind": {
        "head": "regular",
        "index": "regular",
        "worktree": "regular",
        "untracked": "absent"
      },
      "state": "clean",
      "rename_from": null,
      "rename_to": null,
      "head_digest": "sha256:886ad29abb8360a4e7e70535ad3bcc0476b7b7453592ef018f68cff74d1598f9",
      "index_digest": "sha256:886ad29abb8360a4e7e70535ad3bcc0476b7b7453592ef018f68cff74d1598f9",
      "worktree_digest": "sha256:886ad29abb8360a4e7e70535ad3bcc0476b7b7453592ef018f68cff74d1598f9",
      "untracked_digest": "absent"
    },
    {
      "path": "backend/server/routers/knowledge_router.py",
      "object_kind": {
        "head": "regular",
        "index": "regular",
        "worktree": "regular",
        "untracked": "absent"
      },
      "state": "unstaged",
      "rename_from": null,
      "rename_to": null,
      "head_digest": "sha256:8bf0e2e3d4d4ed23275bf37bea61811dd4ae38f5c691b0da045dbe4be71163b5",
      "index_digest": "sha256:8bf0e2e3d4d4ed23275bf37bea61811dd4ae38f5c691b0da045dbe4be71163b5",
      "worktree_digest": "sha256:766b84641bf16f157c7ebb2b9c1cf8c4f588a2e20bcf2d01fefcc6881466e5c8",
      "untracked_digest": "absent"
    },
    {
      "path": "backend/test/e2e/test_rag_pipeline_e2e.py",
      "object_kind": {
        "head": "regular",
        "index": "regular",
        "worktree": "regular",
        "untracked": "absent"
      },
      "state": "clean",
      "rename_from": null,
      "rename_to": null,
      "head_digest": "sha256:d574912974c42a8486ff7cb24a3fe5ca85a973d44296b30543fa1f4eaaae6ba2",
      "index_digest": "sha256:d574912974c42a8486ff7cb24a3fe5ca85a973d44296b30543fa1f4eaaae6ba2",
      "worktree_digest": "sha256:d574912974c42a8486ff7cb24a3fe5ca85a973d44296b30543fa1f4eaaae6ba2",
      "untracked_digest": "absent"
    },
    {
      "path": "docs/vibe/2026-09-21-nghiem-thu-rag-benchmark.md",
      "object_kind": {
        "head": "absent",
        "index": "absent",
        "worktree": "absent",
        "untracked": "regular"
      },
      "state": "untracked",
      "rename_from": null,
      "rename_to": null,
      "head_digest": "absent",
      "index_digest": "absent",
      "worktree_digest": "absent",
      "untracked_digest": "sha256:f868a50fac525bd221817ca2cd5950751e5e8fa8fcca5b8c9a0a7810525307da"
    },
    {
      "path": "scripts/benchmark_ocr.py",
      "object_kind": {
        "head": "regular",
        "index": "regular",
        "worktree": "regular",
        "untracked": "absent"
      },
      "state": "clean",
      "rename_from": null,
      "rename_to": null,
      "head_digest": "sha256:8c82b52ab0f09aa388e6e004833b92a9605207d4ee1c8ad0c6461acad939f010",
      "index_digest": "sha256:8c82b52ab0f09aa388e6e004833b92a9605207d4ee1c8ad0c6461acad939f010",
      "worktree_digest": "sha256:8c82b52ab0f09aa388e6e004833b92a9605207d4ee1c8ad0c6461acad939f010",
      "untracked_digest": "absent"
    }
  ]
}

  primary_symbols:
    - symbol: 'EvaluationService'
      file: 'backend/package/yuxi/knowledge/eval/service.py'
      lines: '149-200,460-590'
      role: 'dataset upload parsing + run loop + result persistence'
    - symbol: 'evaluate_question'
      file: 'backend/package/yuxi/knowledge/eval/evaluator.py'
      lines: '60-180'
      role: 'per-question retrieval+generation+j judge path, SemanticRouter entry'
    - symbol: 'RunEvaluationRequest'
      file: 'backend/server/routers/knowledge_eval_router.py'
      lines: '35-60'
      role: 'API contract: dataset_id + model_config alias retrieval_config, .jsonl-only upload'
    - symbol: 'ConsensusRetriever weights'
      file: 'backend/package/yuxi/knowledge/retrieval/consensus_retriever.py'
      lines: '72-95,306-320'
      role: 'dynamic weights from KB metadata_, per-key fallback, relational routing'
    - symbol: 'tune_weights'
      file: 'backend/scripts/tune_consensus_weights.py'
      lines: '1-50'
      role: 'dummy to replace with real grid search, keep CLI incl. --reset'
    - symbol: 'calculate_cer_wer/run_engine'
      file: 'scripts/benchmark_ocr.py'
      lines: '12-90'
      role: 'OCR bench skeleton; only CER/WER body changes'
  related_symbols:
    - symbol: 'test_rag_pipeline_e2e flow'
      relationship: 'test-of ingest+chat pattern'
      relevance: 'template for T2b ingest polling and T4 agent arm'
    - symbol: '_get_default_query_params'
      relationship: 'CALLS get_query_params_config'
      relevance: 'T3a must enumerate option keys before writing arm configs'
    - symbol: 'add_documents/parse_documents'
      relationship: 'API route'
      relevance: 'T2b ingest endpoints knowledge_router.py:661,844,1140,1172'
  execution_path:
    - 'Driver scripts call api-dev (localhost:5050) — never direct DB writes'
    - 'Dataset JSONL (query + gold_passage_id + gold_answer) -> upload -> runs with model_config overrides -> run rows -> tables'
    - 'Weights flow: grid search -> KB metadata_ consensus_weights -> confirmation run'
  pdg_constraints: []
  architectural_patterns:
    - pattern: 'requests-based API driver scripts'
      example_location: 'backend/test/e2e/test_rag_pipeline_e2e.py'
      usage_guidance: 'Copy its stage/log/poll structure for new bench drivers'
    - pattern: 'run-level model_config override'
      example_location: 'backend/package/yuxi/knowledge/eval/service.py:481'
      usage_guidance: 'Ablate via API config, never branch production code'
  files_to_modify:
    - file: 'backend/scripts/prepare_viquad_bench.py'
      symbols: []
      intended_change: 'new: HF cache -> corpus + qrels + sample300 on /mnt/new-volume/yuxi-eval/'
    - file: 'backend/scripts/run_retrieval_ablation.py'
      symbols: []
      intended_change: 'new: 6 POST /runs arms, passage-level hits, metrics table'
    - file: 'backend/scripts/run_e2e_sample.py'
      symbols: []
      intended_change: 'new: 300-sample x 3 arms EM/F1 + judge'
    - file: 'scripts/benchmark_ocr.py'
      symbols: ['calculate_cer_wer']
      intended_change: 'real CER/WER via jiwer only'
    - file: 'backend/scripts/tune_consensus_weights.py'
      symbols: ['tune_weights']
      intended_change: 'real grid search writing KB metadata_, keep CLI'
  tests:
    - file: 'backend/test/e2e/test_rag_pipeline_e2e.py'
      scenarios: ['post-T2b smoke: existing 8-stage flow still green against live api-dev']
  verification_commands:
    - 'curl -s http://localhost:5050/api/system/health'
    - 'docker compose exec -T api uv run python <bench-script>'
    - 'df -h / (before T3b/T4; keep outputs on /mnt/new-volume/yuxi-eval/)'
  risks:
    - 'judge/answer LLM spec unconfigured (default gpt-4o-mini) — discover in T3a'
    - 'SemanticRouter chit-chat misroute zeroing scores — assert route distribution'
    - 'chunk-id gold brittleness — use passage-level gold'
    - 'LLM cost/time on 900 generations + full-dev runs — batch, retry, log cost'
    - '/ at 92% — outputs only on /mnt/new-volume'
  assumptions:
    - 'HF cache at /mnt/new-volume/yuxi-eval/hf_cache intact — CHECK: ls + row count before T2a'
    - '.env LLM provider (Gemini/OpenRouter) configured in api-dev — CHECK: T3a discovery run'
    - 'No importers of benchmark_ocr/tuner outside CLI — CHECK: grep before editing'
  open_questions:
    - 'Exact model_config option keys (top_k? rrf? rewrite flags?) — answered in T3a via get_query_params_config'
    - 'OCR engines enumerated in run_engine main() — read before T5'
    - 'Configured judge/answer model spec name — read .env + provider router in T3a'
  avoid:
    - 'Do not repeat full repository discovery'
    - 'Do not replace established patterns without evidence'
    - 'Do not write bench outputs to / (disk 92%) — use /mnt/new-volume/yuxi-eval/'
    - 'Do not quote CER/WER or weights without executed runs behind them'
    - 'Do not touch waterdemand containers'
    - 'Do not commit until user reviews bench tables'
```

## 12. Assumptions and Open Questions

- [assumed] HF cache intact with 33084 rows — executor re-checks row count first (cheap).
- [assumed] `api-dev` hot-reloads `backend/scripts/` (scripts mount — verify with a trivial log line if T2a behaves stale).
- [assumed] `jiwer` installable in api image (test-group); if not, executor adds it and rebuilds api (disk check first).
- Open: exact `model_config` keys; OCR engine list in `main()`; configured LLM spec names; Milvus index time for 9959 passages (measure in T2b, adapt polling).
- Deferred (not this plan): T8 regression suite, T9 README/vibe finalization, T10 figures/voiceover, leftover CJK in `scripts/`+`docker/`+`alembic/` comments, changelog entry for the embedding_cache fix (do with T8 commit).

## 13. Definition of Done

- T2: `BENCH_VIQUAD` indexed; map coverage 100%; `qrels.jsonl` 33084 lines all with `query`; `eval_sample300.jsonl` 300 lines stratified.
- T3: run rows for 6 arms persisted + retrievable via `GET /runs/{run_id}`; table with recall@5, nDCG@5, MRR; chit-chat count reported, not silently dropped.
- T4: 3 arm run rows; EM/F1 table; ≥20 failure cases inspected and bucketed in vibe doc.
- T5: per-engine CER/WER from executed runs; `calculate_cer_wer` contains no constant return.
- T6: `tune_weights` contains no `sleep`/hardcoded optimum; winning weights present in KB metadata; confirmation run delta recorded.
- Vibe doc appended with all tables + run_ids; no fabricated numbers anywhere.
