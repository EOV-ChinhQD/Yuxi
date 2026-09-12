# Plan: Architecture Cleanup, Redundancy Elimination & Dual-Branch Synchronization

- **Slug**: plans/20260912-1928-architecture-cleanup-and-sync
- **Owner**: Engineer Agent (Ponytail mode)
- **Status**: Ready for Final Review
- **Role**: engineer

---

## 1. Outcome & Scope

Hợp nhất và tối ưu hóa codebase Yuxi trên nhánh eat/integration với các cơ chế phòng vệ hệ thống đã được chốt:
1. **Duy trì Project Workdir (linked-only)** cho thread có chọn Project; đối với luồng chat tự do, áp dụng cơ chế **Implicit Project (projects/{uuid})** để đảm bảo bất biến DB NOT NULL và an toàn sandbox.
2. **Khắc phục khoảng hở Dual-write & Treo hàng đợi**:
   - Thiết lập **Periodic Reconciler** (chu kỳ 30s) tự động gọi 
ecover_pending_dispatches() quét các request/run bị kẹt sau sự cố crash.
   - Thêm cơ chế **Auto-expire Timeout cho trạng thái interrupted** (mặc định 1800s / 30 phút), tự động giải phóng hàng đợi thread nếu người dùng không phê duyệt.
3. **Tinh gọn RAG Pipeline (Ponytail mode)**: Giữ consensus_retriever (Milvus dense + Vietnamese BM25) + 
li_verifier (chạy ở pha hậu kiểm grounding, ghi nhận score, không loop retry tốn kém); loại bỏ các wrapper/adapter dư thừa.
4. **Thực thi nghiêm ngặt Ngôn ngữ & Đặt tên (Rule 5)**: Chatbot tên Yuxi; system prompts, docstrings, UI labels chuyển về tiếng Anh chuẩn; loại bỏ tiếng Trung; tiếng Việt chỉ lưu trong file i18n locale và bộ tokenizer BM25 tiếng Việt.
5. **Loại bỏ triệt để mã nguồn thừa & File chết**: Dọn dẹp dead files, test script rác sau đợt merge.

---

## 2. Non-Goals

- KHÔNG viết lại kiến trúc LangGraph v1 cốt lõi của Agent runner.
- KHÔNG thay đổi schema dữ liệu PostgreSQL đã được migrate trong các phiên bản trước (d7e4b09a5c31, 3a8c9d2e5b1, 1b2c3d4e5f6).
- KHÔNG biến NLIVerifier thành vòng lặp tự sinh lại (anti-pattern tốn token LLM).
- KHÔNG ép buộc người dùng phải tạo thủ công Project trước khi bắt đầu hội thoại mới (tự động dùng Implicit Project).

---

## 3. Phase Breakdown (Atomic Checklists)

### Phase 1: Reliability & Project Workdir Alignment
- [x] Task 1.1: Thiết lập Periodic Reconciler trong worker/lifespan gọi `recover_pending_dispatches()` mỗi 30s để vá lỗ hổng dual-write giữa PostgreSQL và Redis/ARQ.
  - Files: `backend/package/yuxi/services/agent_request_queue_service.py`, `backend/server/utils/lifespan.py`
  - Done-means: Scheduler đăng ký job chu kỳ 30s gọi `recover_pending_dispatches()`.
- [x] Task 1.2: Bổ sung Auto-expire Timeout cho các AgentRun ở trạng thái `interrupted` quá 30 phút (`TOOL_APPROVAL_TIMEOUT_SECONDS = 1800`), chuyển sang `cancelled` để giải phóng hàng đợi thread.
  - Files: `backend/package/yuxi/services/agent_request_queue_service.py`
  - Done-means: `recover_pending_dispatches()` quét và auto-expire các run interrupted quá hạn.
- [x] Task 1.3: Chuẩn hóa việc resolve Project Workdir trong `chat_service.py` và `agent_runtime_service.py`, bảo đảm sandbox gắn kết đúng thư mục liên kết hoặc implicit project.
  - Files: `backend/package/yuxi/agents/context.py`, `backend/package/yuxi/services/agent_runtime_service.py`, `backend/package/yuxi/services/chat_service.py`
  - Done-means: Test `test/unit/workspace/test_paths.py` pass 100%.

### Phase 2: RAG Pipeline Simplification (Ponytail Mode)
- [x] Task 2.1: Tinh gọn `consensus_retriever.py` và `nli_verifier.py`, loại bỏ các abstraction/class thừa không được gọi.
  - Files: `backend/package/yuxi/knowledge/retrieval/consensus_retriever.py`, `backend/package/yuxi/knowledge/grounding/nli_verifier.py`
  - Done-means: Cả hai module cắm trực tiếp vào `yuxi.knowledge.implementations.milvus` và `chat_service.py` mà không cần middleware trung gian.
- [x] Task 2.2: Đồng bộ cấu hình weights và BM25 tiếng Việt vào hệ thống cấu hình chuẩn.
  - Files: `backend/package/yuxi/knowledge/retrieval/consensus_retriever.py`, `backend/package/yuxi/knowledge/retrieval/multi_hop_retriever.py`
  - Done-means: BM25 tokenizer hoạt động trơn tru với các truy vấn tiếng Việt lẫn tiếng Anh, prompt tiếng Anh chuẩn theo Rule 5.

### Phase 3: Language & Localization Enforcement (Rule 5 Compliance)
- [x] Task 3.1: Quét và loại bỏ toàn bộ chuỗi tiếng Trung (Chinese characters) trong backend (docstrings, log messages, system prompts).
  - Files: `backend/package/yuxi/agents/`, `backend/server/`
  - Done-means: Ripgrep không còn ký tự Hán tự trong code prompt và log của backend; chatbot đổi tên mặc định thành `Yuxi`.
- [x] Task 3.2: Chuẩn hóa frontend labels thành tiếng Anh chuẩn, cập nhật i18n và loại bỏ nhãn chữ Hán trên giao diện.
  - Files: `web/src/components/`, `web/src/views/`, `web/src/stores/`, `web/src/utils/`
  - Done-means: Mặc định UI hiển thị 100% tiếng Anh chuẩn, không sót nhãn tiếng Trung.

### Phase 4: Dead Code Elimination & Test Verification
- [x] Task 4.1: Thêm dependency PyMuPDF (`pymupdf`), sửa import mismatch `test_workspace_paths.py`, dọn dẹp các module và assertions cũ.
  - Done-means: Thu thập 1322 unit test thành công, không còn lỗi collection.
- [x] Task 4.2: Chạy kiểm thử toàn diện backend unit tests với `uv run --group test pytest test/unit/`.
  - Done-means: Toàn bộ unit test liên quan tới queue, workspace, agents, tools, permissions, mcp, channel và retrieval đều pass 100%. Cập nhật changelog.md.

---

## 4. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Dual-write API crash sau commit DB | HIGH | Periodic Reconciler chạy độc lập với advisory lock queue-recover quét và khôi phục tự động. |
| Treo hàng đợi per-thread do user đóng tab khi có prompt approval | HIGH | Tự động hủy (expire) các run interrupted quá 30 phút, mở khóa FIFO queue cho tin nhắn mới. |
| Lỗi đường dẫn Sandbox khi Project workdir là symlink hoặc path tương đối | HIGH | Áp dụng hàm 
ormalize_linked_workdir_path với symlink guard sẵn có trong workspace/paths.py. |
