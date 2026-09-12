# Session Handoff: Architecture Cleanup, Sync & Reliability Hardening

## 1. Goal
Hợp nhất và tối ưu hóa codebase Yuxi trên nhánh `feat/integration` (upstream `xensor/Yuxi` + fork nội bộ), khắc phục các rủi ro kiến trúc cốt lõi (dual-write, queue lock timeout), tinh gọn RAG pipeline, thực thi nghiêm ngặt Rule 5 (100% tiếng Anh chuẩn, không ký tự tiếng Trung, chatbot tên `Yuxi`), và đưa test suite về trạng thái xanh 100%.

## 2. Decisions & Why
1. **Periodic Reconciler thay vì Distributed Lock phức tạp**:
   - *Why*: Dùng `APScheduler` có sẵn trong `lifespan.py` quét chu kỳ 30s gọi `recover_pending_dispatches()` với `pg_try_advisory_xact_lock` O(1), khắc phục triệt để rủi ro dual-write DB/Redis khi worker crash mà không cần thêm hệ thống fallback cồng kềnh.
2. **Auto-expire Timeout cho Interrupted Run (1800s / 30 phút)**:
   - *Why*: Khi người dùng đóng tab hoặc bỏ quên modal tool approval, run bị treo vĩnh viễn gây khóa FIFO queue của thread. Tự động chuyển về `cancelled` sau 30 phút để giải phóng luồng chat.
3. **Implicit Project Workdir (`projects/{uuid}`)**:
   - *Why*: Đảm bảo bất biến NOT NULL của DB và ranh giới an toàn cho Sandbox ngay cả khi người dùng chat tự do mà không chọn project cụ thể. Gắn kết `project_id` và `workdir_path` trực tiếp vào `BaseContext` và nạp vào runtime context.
4. **Chuẩn hóa Rule 5**:
   - *Why*: Đổi tên Chatbot mặc định thành `Yuxi`. Quét sạch toàn bộ ký tự chữ Hán `[\u4e00-\u9fff]` trong backend router/service/prompt và frontend components/stores/views, đưa toàn bộ hệ thống về tiếng Anh chuẩn.
5. **Đổi tên `test_paths.py` thành `test_workspace_paths.py` & Thêm `pymupdf`**:
   - *Why*: Loại bỏ lỗi pytest import mismatch do trùng tên module giữa utils và workspace; bổ sung `pymupdf` (1.28.2) để density analyzer cho PDF hoạt động trơn tru mà không lỗi collection.

## 3. Evidence
- **Test Suite Results**:
  - `test_agent_request_queue_service.py` & `test_workspace_paths.py`: 61/61 PASSED
  - `test_pdf_density.py` & `test_parser_facade.py`: 27 PASSED, 1 SKIPPED
  - `test/unit/agents/`: 76/76 PASSED
  - `test_retrieval_strategies.py` & `test_consensus_multi_hop.py`: 12/12 PASSED
  - `test/unit/utils/`: 14/14 PASSED
  - `test/unit/toolkits/` & `test_sandbox_download.py`: 51/51 PASSED
  - `test_mcp_service.py` & `test_channel_command_service.py`: 15/15 PASSED
  - `test_resource_permission.py` & `test_options.py`: 23/23 PASSED
  - `test/unit/routers/`: 94/94 PASSED
  - **Tổng cộng: 373 passed, 1 skipped, 0 failed.**
- **Linter**: `ruff check` trên tất cả file backend đã sửa: `All checks passed!`.
- **Review Verdict**: PASS trên cả 2 trục Standards & Spec.

## 4. Blockers
- Không có blocker nào tồn đọng.

## 5. Next Steps
- Triển khai trên môi trường Docker container qua `docker compose up -d`.
- Chạy thử nghiệm live end-to-end trên trình duyệt với chatbot `Yuxi`.
