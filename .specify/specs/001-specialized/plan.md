# Plan 001 — Specialized

## Architecture
- `Project` là single owner của `Workdir` (`models_business.py:292` `workdir_path`, `directory_mode=linked`, `selection_status=selectable/implicit`). `Conversation` FK `fk_conversations_project_uid` `models_business.py:364`.
- Thin router (`project_router.py:74`) → service (`project_service.py:170`) → repo (`project_repository.py:68`) → `Workdir.open_existing`.

## Steps
1. **P2 Backend**: Thêm `UniqueConstraint(uid, workdir_path)`, repo `get_by_workdir_path/update/delete`, router `PATCH/DELETE/GET /{id}`, service `list_history_candidates` DB-side.
2. **P3 Queue**: `recover_pending_dispatches` bọc `pg_advisory_xact_lock('queue-recover')`, `stream_request_events` cache `queue_position` qua Redis 1s TTL.
3. **P4 Frontend**: Tách `ProjectCreateModal.vue`, dùng `viewer_filesystem` API cho picker, `project.js` thêm `updateProject/deleteProject/getProject`.
4. **P5 i18n**: Sweep `zh-CN` → `vi`, `config.mts` `lang:vi`, thêm `Project` sidebar entry.

## Risk
- `uid+workdir_path` unique conflict với existing duplicate linked projects → cần migration `SELECT ... GROUP BY HAVING COUNT>1` báo lỗi trước.
- Queue advisory lock phải `hashtextextended` đồng nhất `project_service.py:21`.

## Verify
`docker compose up -d && docker logs api-dev --tail 100`, `make format`, `pytest -k project or queue`, `pnpm build`.
