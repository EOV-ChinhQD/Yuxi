# Engineering Plan: Phase 3 & Phase 4 Delivery (T7 - T10)

> Task: Complete codebase sanitization (T7), full test regression (T8), documentation revamp (T9), and report/media delivery assets (T10).
> Scope: Yuxi Multi-Agent RAG & Knowledge Platform.

## 1. Objectives (Aligned via Grill-Me)

1. **T7 (Sanitization & Code Cleanliness)**: 100% CJK cleanup across the entire codebase (comments, docstrings, logs, UI, and scripts converted to clean English/Vietnamese per Rule 5).
2. **T8 (Test Suite Regression)**: Full 3-tier regression (Unit, Integration, and live E2E against Docker container `api-dev`), achieving 100% pass rate with zero unresolved failures.
3. **T9 (README & Documentation Revamp)**: High-standard English technical `README.md` featuring architecture, LangGraph v1 workflow, Milvus + LightRAG, and a Vietnamese project summary section for academic evaluation.
4. **T10 (Reporting Artifacts & Demo Blueprint)**: Complete benchmark report tables (Recall@5, nDCG@5, EM, F1, CER, WER, tuning delta) and a 3-minute video demo blueprint.

## 2. Work Breakdown & Subagent Assignment (Engineer Kit)

| Task | Phase | Subagent Role | Target Deliverable |
| :--- | :---: | :--- | :--- |
| **T7** | Cook | `ponytail-dev` | CJK-clean codebase; `grep CJK` clean report |
| **T8** | Verify | `test-engineer` | Full pytest run in `api-dev`; test matrix in vibe doc |
| **T9** | Cook | `code-explorer` | Polished `README.md` + VitePress docs update |
| **T10** | Ship | `senior-architect` | Final benchmark report, figure data & demo script |

## 3. Atomic Execution Steps

### Step 1: T7 — CJK Sanitization & Tree Cleanup (~20 mins)
- Run `grep -rnP "[\x{4e00}-\x{9fff}]" backend/ package/ scripts/` to locate all occurrences.
- Translate Chinese comments in `backend/package/yuxi/agents/middlewares/summary.py`, `backend/package/yuxi/knowledge/parser/paddleocr_api.py`, `backend/server/routers/`, and `backend/alembic/versions/` into concise English comments.
- Verify zero residual CJK characters in `backend/` and `scripts/`.

### Step 2: T8 — Test Suite Regression & Quality Gate (~25 mins)
- Run unit test suite: `docker compose exec -T api uv run pytest test/unit`.
- Run integration test suite: `docker compose exec -T api uv run pytest test/integration` (or active endpoints).
- Run E2E smoke test: `docker compose exec -T api uv run pytest test/e2e/test_rag_pipeline_e2e.py`.
- Document pass/fail matrix in `docs/vibe/2026-09-21-nghiem-thu-rag-benchmark.md`.

### Step 3: T9 — README.md & Docs Revamp (~20 mins)
- Restructure `README.md` with modern badges, system architecture, LangGraph v1 workflow, Milvus + LightRAG integration, benchmark results summary, and Docker Compose deployment instructions.
- Update `docs/develop-guides/changelog.md` and VitePress navigation.

### Step 4: T10 — Project Report Mapping & Demo Script (~15 mins)
- Consolidate all Phase 2 benchmark numbers (Recall@5, nDCG@5, MRR, EM, F1, CER, WER, Consensus weights) into final report section.
- Draft a 3-minute video demo outline and course project presentation checklist.

## 4. Definition of Done

- `grep -rnP "[\x{4e00}-\x{9fff}]" backend/` returns 0 matches.
- All unit & E2E smoke tests in `backend/test/` pass without regressions.
- `README.md` is updated and fully verified.
- `docs/vibe/2026-09-21-nghiem-thu-rag-benchmark.md` checklist marked 100% complete (T1 to T10).
