# Tổng quan Dự án (Project Overview)

Yuxi là một nền tảng phát triển cơ sở kiến thức thông minh và tác tử (agent) đồ thị kiến thức dựa trên mô hình ngôn ngữ lớn, tích hợp công nghệ RAG và đồ thị kiến thức, được xây dựng trên kiến trúc LangGraph v1 + Vue.js + FastAPI + LightRAG. Dự án được quản lý hoàn toàn thông qua Docker Compose, hỗ trợ phát triển với tính năng tải lại nóng (hot reload).

Bản đồ mã nguồn kiến trúc xem tại [ARCHITECTURE.md](ARCHITECTURE.md). Trước khi sửa đổi các mô-đun chưa quen thuộc, vui lòng đọc phần mô tả về backend, frontend, luồng vận hành và các bất biến kiến trúc trong đó, sau đó sử dụng tìm kiếm biểu tượng để định vị triển khai cụ thể; tài liệu này chỉ duy trì các ranh giới hệ thống tương đối ổn định và không thay thế tài liệu chi tiết hoặc chú thích mã nguồn.

## Phát triển mẫu chuẩn (Development Guidelines)

Behavior guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- Restate the request as the smallest acceptance criteria you are about to satisfy. If you cannot state it simply, you do not understand the request yet.
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.
- Treat phrases like "可以", "也可以", "类似这样", or "for example" as acceptable simple directions, not permission to design a larger mechanism.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- Do not fill in imagined requirements. If you start adding aggregation, priority rules, fallback layers, protocol interpreters, or generic frameworks that were not explicitly asked for, stop and reduce the solution to the acceptance criteria.
- For small status/progress/summary changes, prefer a direct projection: read the source data, select the needed items, return the smallest useful shape. Do not rebuild an event stream or debug view unless that is the request.
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
- "Add validation" -> "Write tests for invalid inputs, then make them pass"
- "Fix the bug" -> "Write a test that reproduces it, then make it pass"
- "Refactor X" -> "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
3. [Step] -> verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Tiêu chuẩn Review mã nguồn

Khi tiến hành Review mã nguồn, hãy xem xét theo thứ tự sau:

1. Đầu tiên, xác nhận xem mã nguồn có hoàn thành chức năng cơ bản và bao phủ các tình huống sử dụng chính hay không; nếu luồng chính hoặc các kịch bản quan trọng chưa được xác thực rõ ràng, nên được chỉ ra trước tiên.
2. Đánh giá xem giải pháp hiện tại có phải là tối ưu nhất trong ngữ cảnh hay không, và liệu nó có làm tăng gánh nặng hiểu biết cho người dùng hoặc người bảo trì hay không; nếu có một giải pháp ngắn gọn và dễ hiểu hơn nhưng phạm vi thay đổi lớn hơn, đừng viết lại trực tiếp mà hãy giải thích các đánh đổi và xác nhận với người dùng trước.
3. Kiểm tra xem có thiết kế quá mức (over-engineering), phòng thủ quá mức hoặc lồng nhau quá mức hay không: thiết kế quá mức thường biểu hiện bằng việc thêm các tính năng không liên quan; phòng thủ quá mức thường biểu hiện bằng việc che giấu các vấn đề thiết kế bằng các cơ chế fallback hoặc bảo toàn không mong muốn; lồng nhau quá mức thường biểu hiện bằng việc có quá nhiều helper, chuỗi gọi vòng quanh và không tuân theo thứ tự đọc từ trên xuống dưới.
4. Đánh giá nghiêm túc giá trị của các tập lệnh kiểm thử và các ca kiểm thử. Đối với các kiểm thử giá trị thấp và tẻ nhạt nhưng chỉ là "đánh giá mục tiêu sau khi đưa ra mục tiêu", nên đề xuất dọn dẹp hoặc gộp lại; giữ lại các kiểm thử có thể xác thực hành vi thực tế, luồng chính và rủi ro hồi quy.

## Quy trình phát triển và gỡ lỗi (Development & Debugging Workflow)

Dự án này được quản lý hoàn toàn thông qua Docker Compose. Mọi hoạt động phát triển và gỡ lỗi nên được thực hiện trong môi trường container đang chạy. Sử dụng lệnh `docker compose up -d` để xây dựng và khởi động.

**Nguyên tắc cốt lõi**:

1. Do cả dịch vụ api (tên container `api-dev`) và web (tên container `web-dev`) đều được cấu hình tải lại nóng (hot-reloading), việc sửa đổi mã nguồn cục bộ không yêu cầu khởi động lại container, dịch vụ sẽ tự động cập nhật. Nên kiểm tra xem dự án đã được khởi động ở chế độ chạy nền chưa (`docker ps`), kiểm tra nhật ký (`docker logs api-dev --tail 100`), chi tiết có thể xem tại [docker-compose.yml](docker-compose.yml).
2. Sau khi hoàn thành phát triển, bắt buộc phải tiến hành Kiểm tra -> Kiểm thử -> Lint theo phạm vi thay đổi: các bài kiểm thử đơn vị liên quan bắt buộc phải chạy; chạy kiểm thử tích hợp khi có thay đổi API; chạy lại kiểm thử end-to-end cho các đường dẫn chính. Khi các kịch bản kiểm thử chưa hoàn thiện, cần bổ sung và hoàn thiện chúng.
3. Quy chuẩn kiểm thử bắt buộc phải tuân theo quy chuẩn trong [testing-guidelines.md](docs/develop-guides/testing-guidelines.md), các kịch bản kiểm thử phải được đặt trong các thư mục tương ứng `backend/test/unit`, `backend/test/integration` hoặc `backend/test/e2e` và đảm bảo kiểm thử vượt qua trước khi gửi.
4. Cực kỳ quan trọng! Tuyệt đối không sử dụng cơ chế phòng thủ/fallback quá mức để che đậy các khuyết điểm trong thiết kế. Phần mềm tốt nên chạy dưới các điều kiện định sẵn, các tình huống khác đều phải kịp thời phát hiện vấn đề/lỗi và sửa chữa, thay vì che đậy vấn đề bằng cách thêm mã nguồn dư thừa.
5. Phát triển hoàn thành bắt buộc phải kiểm thử trong docker, có thể đọc .env để lấy tài khoản và mật khẩu quản trị viên; các giá trị nhạy cảm chỉ được sử dụng cho các lệnh kiểm thử cục bộ, không xuất ra phản hồi, trích xuất nhật ký, tệp kiểm thử hoặc tài liệu.
6. Tuân theo quy tắc hạ tầng (The Stepdown Rule): các phương thức công khai và cấp cao được đặt ở đầu tệp, các chi tiết kỹ thuật chìm dần theo từng lớp. Người đọc khi đọc từ trên xuống dưới, mỗi lớp chỉ gọi triển khai của lớp ngay tiếp theo, mở rộng chi tiết theo từng cấp giống như đọc tiêu đề báo, không cần nhảy cóc.

### Quy chuẩn trao đổi yêu cầu

Khi trao đổi về yêu cầu, nếu yêu cầu chưa rõ ràng, cần chủ động khai thác các chi tiết yêu cầu, thống nhất tiêu chuẩn nghiệm thu, làm rõ độ ưu tiên và phạm vi của yêu cầu, tránh thiết kế quá mức hoặc các công việc không cần thiết do yêu cầu mơ hồ.

- Sau khi yêu cầu/sửa đổi đã rõ ràng, nếu có thay đổi lớn, cần tạo một tài liệu chứa ngày tháng trong thư mục `docs/vibe` để ghi lại chi tiết yêu cầu và tiêu chuẩn nghiệm thu.
- Trong tài liệu yêu cầu đó, cũng nên bao gồm mục tiêu của nhiệm vụ lần này và checklist (tóm tắt).

### Quy chuẩn phát triển Frontend
- Sử dụng pnpm để quản lý.
- Quy chuẩn giao diện API: Tất cả các giao diện API nên được định nghĩa dưới thư mục `web/src/apis`.
- Icon nên được ưu tiên chọn từ `lucide-vue-next` (khuyến nghị, nhưng cần chú ý đến kích thước).
- Style sử dụng less, ngoại trừ trường hợp đặc biệt, bắt buộc phải sử dụng các biến màu sắc trong [base.css](web/src/assets/css/base.css).
- Quy chuẩn thiết kế UI xem chi tiết tại [design](docs/develop-guides/design.md).


### Quy chuẩn phát triển Backend

```bash
# Kiểm tra và định dạng mã nguồn
make format        # Định dạng mã nguồn
```

Chú ý:
- Mã nguồn Python phải tuân theo phong cách pythonic.
- Cố gắng sử dụng cú pháp mới hơn, tránh sử dụng cú pháp phiên bản cũ (tương thích phiên bản từ 3.12 trở lên).
- Cập nhật tài liệu [changelog.md](docs/develop-guides/changelog.md) để ghi lại sửa đổi lần này, các cập nhật tính năng tương tự đã được bổ sung cùng nhau.
- Sau khi hoàn thành phát triển, bắt buộc phải tiến hành kiểm thử trong docker, có thể đọc .env để lấy tài khoản và mật khẩu quản trị viên.
- Không cho phép viết mã nguồn rời rạc: Đừng chia nhỏ thành một đống helper vụn vặt cho các logic tuyến tính đơn giản; ưu tiên viết các triển khai có trách nhiệm rõ ràng, cấu trúc hoàn chỉnh và có thể đọc hiểu ngay lập tức.
- Việc tách hàm phải phục vụ cho mục đích tái sử dụng rõ ràng, cô lập tác dụng phụ hoặc giảm bớt gánh nặng nhận thức; nếu việc tách hàm làm cho chuỗi gọi hàm trở nên phức tạp hơn, ngữ cảnh phân tán hơn, thì nên gộp lại thành một triển khai trực tiếp hơn.

**Khác**:

- Nếu cần tạo tài liệu hướng dẫn mới (chỉ nhà phát triển mới nhìn thấy, không tạo nếu không cần thiết), hãy lưu trong thư mục `docs/vibe`.
- Sau khi cập nhật mã nguồn, cần kiểm tra xem phần tài liệu có cần cập nhật hay không, danh mục tài liệu được định nghĩa trong `docs/.vitepress/config.mts`.
- Nếu thêm tài liệu chính thức mới hướng tới người dùng, ngoài việc bổ sung nội dung tài liệu, còn cần đồng bộ cập nhật điều hướng của `docs/.vitepress/config.mts`; tài liệu hướng dẫn tích hợp Langfuse được lưu trữ dưới nhóm `docs/agents` và đồng bộ cập nhật tài liệu `docs/develop-guides/changelog.md`.

## Quy chuẩn Commit

1. Tham khảo quy chuẩn [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) để viết thông điệp commit.
2. Sử dụng thông điệp commit bằng tiếng Việt hoặc tiếng Anh, tiêu đề ngắn gọn rõ ràng, mô tả chi tiết nội dung và lý do thay đổi.
3. Tạo PR bắt buộc phải tham khảo [contributing.md](docs/develop-guides/contributing.md) cũng như template PR [PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md), và hoàn thành các mục kiểm tra trong đó trước khi gửi.
