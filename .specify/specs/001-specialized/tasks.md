# Tasks 001

- [ ] T01 GitNexus index Yuxi & Auth/Yuxi (`registry.json` 4 entries)
- [ ] T02 Migration `uq_projects_uid_workdir_path` + backfill check duplicates
- [ ] T03 Repo `get_by_workdir_path/update/delete` + service `rename/delete` view
- [ ] T04 Router `PATCH/DELETE/GET /api/projects/{id}` + `ProjectCreate` contract fix (`mode` default `linked`)
- [ ] T05 Queue `recover_pending_dispatches` advisory lock + `stream_request_events` Redis cache
- [ ] T06 Frontend `ProjectCreateModal` + `FileBrowserTable` picker + `project.js` CRUD
- [ ] T07 i18n sweep `zh-CN→vi` (`App.vue:2`, `time.js:2`, 4x `toLocaleString`, `translation_cache.json` xóa) + `config.mts` `lang:vi` + sidebar Project entry
- [ ] T08 Verify `make format && pytest -k project` + `docker compose up -d`
