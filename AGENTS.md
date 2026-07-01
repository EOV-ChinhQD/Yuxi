
# Cấu trúc thư mục dự án (Project Overview)

Yuxi Nó là một nền tảng phát triển tác nhân đồ thị tri thức và cơ sở tri thức thông minh dựa trên các mô hình lớn.，hợp nhất RAG Công nghệ và công nghệ đồ thị tri thức，Dựa trên LangGraph v1 + Vue.js + FastAPI + LightRAG Kiến trúc xây dựng。Dự án hoàn toàn được thông qua Docker Compose Quản lý，Hỗ trợ phát triển tải lại nóng。

Bản đồ mã kiến trúc xem [ARCHITECTURE.md](ARCHITECTURE.md)。Trước khi sửa đổi các mô-đun không quen thuộc，Đọc phần phụ trợ trước、giao diện người dùng、Liên kết hoạt động và mô tả bất biến kiến trúc，Sau đó sử dụng các ký hiệu để tìm kiếm và xác định vị trí triển khai cụ thể；Tài liệu này chỉ duy trì ranh giới hệ thống tương đối ổn định，Không thay thế tài liệu chi tiết hoặc nhận xét về mã nguồn。

## hướng dẫn phát triển

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Quy trình phát triển và gỡ lỗi (Development & Debugging Workflow)

Dự án này đã được phê duyệt đầy đủ Docker Compose Quản lý。Tất cả quá trình phát triển và gỡ lỗi phải được thực hiện trong môi trường container đang chạy。sử dụng `docker compose up -d` Lệnh xây dựng và bắt đầu。

**nguyên tắc cốt lõi**:

1. do api-dev và web-dev Dịch vụ được cấu hình với tải lại nóng (hot-reloading)，Không cần phải khởi động lại vùng chứa sau khi sửa đổi mã cục bộ，Dịch vụ sẽ tự động cập nhật。Trước tiên bạn nên kiểm tra xem dự án đã được bắt đầu ở chế độ nền chưa（`docker ps`），Xem nhật ký（`docker logs api-dev --tail 100`）Bạn có thể đọc chi tiết [docker-compose.yml](docker-compose.yml).
2. Phải được thực hiện sau khi quá trình phát triển hoàn tất Kiểm tra -> kiểm tra -> Lint，và thử nghiệm từ đầu đến cuối，Khi kịch bản kiểm thử chưa hoàn chỉnh, kịch bản cần được cải thiện。
3. Thông số kỹ thuật kiểm tra phải được tuân theo [testing-guidelines.md](docs/develop-guides/testing-guidelines.md) thông số kỹ thuật trong，Kịch bản kiểm tra phải được đặt trong backend/test dưới thư mục，Và đảm bảo bài kiểm tra đạt trước khi gửi。
4. rất quan trọng！Không bao giờ sử dụng phòng thủ quá mức/Cơ chế dự phòng để che các lỗi thiết kế，Phần mềm tốt nên chạy trong điều kiện định sẵn，Trong các trường hợp khác, vấn đề cần được phát hiện kịp thời/lỗi và sửa lỗi，thay vì che giấu vấn đề bằng cách thêm mã dự phòng。

### Thông số kỹ thuật truyền thông yêu cầu

Khi giao tiếp nhu cầu，Khi yêu cầu không rõ ràng，Cần tích cực tìm hiểu chi tiết nhu cầu，Tiêu chí chấp nhận cho các yêu cầu căn chỉnh，Làm rõ mức độ ưu tiên và phạm vi của các yêu cầu，Tránh thiết kế quá mức và những công việc không cần thiết do yêu cầu mơ hồ。

- nhu cầu/sửa đổi Sau khi làm rõ，Nếu sự thay đổi lớn，thì cần phải ở trong docs/vibe Tạo một tài liệu chứa ngày trong thư mục，Chi tiết yêu cầu tài liệu và tiêu chí chấp nhận
- Trong tài liệu yêu cầu này，Nó cũng nên bao gồm các mục tiêu của sứ mệnh và checklist（Tóm tắt）

### Thông số kỹ thuật phát triển front-end
- sử dụng pnpm quản lý
- API Đặc điểm giao diện：tất cả API Giao diện nên được xác định trong web/src/apis bên dưới
- Icon nên ưu tiên cho lucide-vue-next （Được đề xuất，Nhưng bạn cần chú ý đến kích thước）
- Cách sử dụng kiểu less，Phải sử dụng trừ trường hợp đặc biệt [base.css](web/src/assets/css/base.css) biến màu trong
- UI Để biết thông số kỹ thuật thiết kế chi tiết, xem [design](docs/develop-guides/design.md)


### Thông số kỹ thuật phát triển back-end

```bash
# Kiểm tra và định dạng mã
make format        # Mã định dạng

```
Lưu ý：
- Python Mã phải tuân thủ pythonic phong cách
- Hãy thử sử dụng cú pháp mới hơn，Tránh sử dụng các phiên bản cú pháp cũ hơn（phiên bản tương thích với 3.12+）
- cập nhật [changelog.md](docs/develop-guides/changelog.md) Tài liệu ghi lại sự sửa đổi này，Một số cập nhật tính năng tương tự đã được thêm vào cùng nhau
- Sau khi quá trình phát triển hoàn tất, hãy đảm bảo docker Kiểm tra trong，Có thể đọc .env Nhận tài khoản và mật khẩu quản trị viên
- Không được phép viết mã thưa thớt：Đừng xé nát từng mảnh nhỏ để có logic tuyến tính đơn giản helper；Ưu tiên viết bài với trách nhiệm rõ ràng、Cấu trúc hoàn chỉnh、Triển khai có thể được đọc trong nháy mắt。
- Các hàm phân rã phải phục vụ việc tái sử dụng rõ ràng、Cô lập các tác dụng phụ hoặc giảm tải nhận thức；Nếu chuỗi cuộc gọi trở nên phức tạp hơn sau khi chia tách、Bối cảnh lan tỏa hơn，nên được hợp nhất lại thành một triển khai trực tiếp hơn。

**Khác**：

- Nếu bạn cần tạo một tài liệu mới（Chỉ hiển thị với nhà phát triển，Không tạo trừ khi cần thiết），được lưu trong `docs/vibe` Bên dưới thư mục
- Sau khi mã được cập nhật, hãy kiểm tra xem có nội dung nào trong tài liệu cần được cập nhật hay không.，Thư mục tài liệu được xác định trong `docs/.vitepress/config.mts` trong
- Nếu bạn thêm tài liệu chính thức hướng tới người dùng，Ngoài việc sửa nội dung tài liệu，Cần được cập nhật đồng thời `docs/.vitepress/config.mts` Điều hướng；Langfuse Hướng dẫn tích hợp được lưu trữ tại `docs/agents` Duy trì theo nhóm，và đồng bộ hóa các bản cập nhật `docs/develop-guides/changelog.md`

## Thông số kỹ thuật gửi

1. Tài liệu tham khảo [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) Chuẩn hóa thông tin gửi。
2. Gửi thông tin bằng tiếng Trung，Tiêu đề ngắn gọn và rõ ràng，Nêu rõ những thay đổi cụ thể và nguyên nhân。
3. tạo ra PR Phải tham khảo [contributing.md](docs/develop-guides/contributing.md) và PR mẫu[PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md)，và hoàn tất việc kiểm tra trước khi gửi.。
