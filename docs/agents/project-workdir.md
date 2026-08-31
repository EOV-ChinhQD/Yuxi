# Project & Workdir (Specialized)

`Project` là owner duy nhất của `Workdir` trong fork chuyên biệt này.

*   **Model**: `backend/package/yuxi/storage/postgres/models_business.py:292` `Project(uid, workdir_path, directory_mode=linked, selection_status=selectable/implicit)` + `UniqueConstraint(uid, workdir_path)` `a1b2c3d4e5f6`.
*   **Flow**: `AgentView` chọn Project → `projectApi.createProject` (`web/src/apis/project.js`) → `project_service.create_project_view` kiểm tra `Workdir.open_existing` + `get_by_workdir_path` chống trùng → `conversation_service.create_thread_view` bind `project_id` (implicit fallback).
*   **History reuse**: `GET /api/projects/history-candidates?q=&limit=&offset=` query DB-side `ILIKE` `project_repository.py:52`.
*   **CRUD**: `GET /api/projects`, `GET /{id}`, `PATCH /{id}` (rename), `DELETE /{id}` (409 nếu còn conversations).
*   **Linked-only**: `directory_mode` ép `linked`, `managed` chỉ cho implicit `projects/{uuid}` tự tạo. Symlink guard ở `workspace/workdir.py:18`.

> Không đồng bộ `workdir_service` fd-based hay `memory/audit` của upstream — giữ tối ưu cho RAG chuyên biệt.
