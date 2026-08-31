# Spec 001 — Specialized Yuxi (Project-centric)

## Goal
Biến fork `EOV-ChinhQD/Yuxi` `feat/integration 9272efd3a` thành bản chuyên biệt tối ưu (không sync toàn bộ `xerrors/Yuxi` memory/audit), hoàn thiện `Project` + `Queue` + `Vietnamization`.

## Scope (In)
- Project `linked-only` CRUD với `uid+workdir_path` unique, history DB-side search, `conversation.project_id` backfill idempotent `f3a8c9d2e5b1`.
- Queue: 3 policies `enqueue/reject/steer` (`agent_request_queue_service.py:42`), advisory lock cho `recover_pending_dispatches`, SSE không COUNT mỗi tick.
- Workdir: `workspace/workdir.py` stub → thêm symlink guard, giữ `linked` semantics.
- Frontend: `ProjectSelectionSection.vue` picker + API `update/delete`, xóa hardcode `C: 21GB`.

## Out of Scope
- `memory_service`, `audit_logs` hash-chain, `graph_reconciliation` heavy, Hallmark typography/dark mode `4270fb1bc`.

## Acceptance
- `POST /api/projects` idempotent `409` khi `request_id` khác intent `project_service.py:104`.
- `GET /api/projects/{id}` `404` nếu khác `uid`, `PATCH` đổi `name` ≤255, `DELETE` chặn nếu còn `conversations` bound.
- `pytest backend/test/unit -k project` ≥ 15 tests, `test_agent_request_queue_concurrency.py` pass với 2 workers.
- `web/src/App.vue` locale `viVN`, `docs/.vitepress/config.mts` `lang:vi` build không lỗi.
