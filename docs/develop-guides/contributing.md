# Tham gia và đóng góp

cảm ơn bạn vì Yuxi lãi suất。chúng tôi hoan nghênh Issue、Cải tiến tài liệu、Bug sửa chữa、Thử nghiệm bổ sung và đóng góp tính năng mới。

Nếu bạn chỉ muốn biết nhanh thông tin ra vào kho，Bạn có thể nhìn vào thư mục gốc trước [CONTRIBUTING.md](../../CONTRIBUTING.md)。

<a href="https://github.com/xerrors/Yuxi/contributors">
    <img src="https://contributors.nn.ci/api?repo=xerrors/Yuxi" alt="Danh sách cộng tác viên">
</a>

## trước khi bắt đầu

Nên hoàn thành các bước kiểm tra sau trước khi gửi：

- Tìm kiếm rồi [Issues](https://github.com/xerrors/Yuxi/issues)
- Những thay đổi chức năng chính，Bắt đầu Issue Thảo luận về thiết kế và ranh giới
- giữ một lần PR Chỉ giải quyết một vấn đề rõ ràng，Tránh trộn lẫn các phép tái cấu trúc không liên quan với nhau

## Nguyên tắc phát triển

Dự án này tuân theo các nguyên tắc phát triển sau theo mặc định：

- Tránh thiết kế quá mức，Chỉ thực hiện những thay đổi cần thiết trực tiếp cho nhu cầu hiện tại
- Không có bổ sung bổ sung“Tối ưu hóa dễ dàng”、Lớp tương thích hoặc trừu tượng hóa các yêu cầu trong tương lai
- Sử dụng lại các triển khai hiện có càng nhiều càng tốt，Giữ mã của bạn đơn giản、tiêu điểm、Có thể bảo trì
- Chỉ thực hiện xác minh cần thiết ở ranh giới hệ thống，Đừng thêm sự phức tạp vào các tình huống nội bộ không thể thực hiện được

## môi trường phát triển

Yuxi Dựa trên Docker Compose Quản lý môi trường phát triển。phát triển、Gỡ lỗi、Việc kiểm tra nên được thực hiện trong vùng chứa đang chạy bất cứ khi nào có thể。

### Bắt đầu một dự án

```bash
docker compose up -d
```

### Các lệnh kiểm tra thường dùng

```bash
docker ps
docker logs api-dev --tail 100
```

`api-dev` và `web-dev` Tải lại nóng được hỗ trợ theo mặc định。Thông thường，Không cần phải khởi động lại vùng chứa sau khi sửa đổi mã cục bộ。

Để tìm hiểu thêm về định nghĩa dịch vụ，Có sẵn để xem [docker-compose.yml](../../docker-compose.yml)。

## Quy trình đóng góp

### 1. Fork nhà kho

trong GitHub trên Fork Kho này đi vào tài khoản cá nhân của bạn。

### 2. Tạo một chi nhánh

Vui lòng sử dụng tên chi nhánh rõ ràng về mặt ngữ nghĩa，Ví dụ：

```bash
git checkout -b feature/amazing-feature
git checkout -b fix/chat-stream-interrupt
git checkout -b docs/update-contributing-guide
```

### 3. Phát triển và xác minh

Hoàn thành mã theo thông số kỹ thuật của dự án、Kiểm tra và cập nhật tài liệu。Sau khi phát triển xong，Ít nhất là hoàn thành：

- Kiểm tra
- kiểm tra
- Lint
- Xác minh đầu cuối cần thiết

Nếu tập lệnh kiểm thử hiện tại không đủ để đáp ứng những thay đổi của bạn，Các xét nghiệm tương ứng cần được bổ sung，Kịch bản thử nghiệm được ưu tiên `backend/test`。

### 4. Gửi mã

```bash
git commit -m "feat: add knowledge graph import flow"
```

### 5. Đẩy và bắt đầu Pull Request

```bash
git push origin feature/amazing-feature
```

tạo ra PR thời gian，Hãy viết rõ ràng：

- Sửa đổi nội dung
- Lý do sửa đổi
- Phạm vi ảnh hưởng
- Phương pháp xác minh

nếu nó liên quan đến UI Thay đổi，Nên đính kèm ảnh chụp màn hình hoặc bản ghi màn hình。

## Thông số kỹ thuật đóng góp cho giao diện người dùng

Thư mục frontend nằm ở `web/`，Vui lòng tuân thủ các ràng buộc sau trước khi gửi：

- Cách sử dụng trình quản lý gói `pnpm`
- tất cả API Định nghĩa giao diện được thống nhất trong `web/src/apis`
- Icon ưu tiên sử dụng `lucide-vue-next`
- Cách sử dụng kiểu `less`
- Việc tái sử dụng phải được ưu tiên trừ khi có trường hợp đặc biệt [web/src/assets/css/base.css](../../web/src/assets/css/base.css) biến màu trong

Các ràng buộc về thiết kế giao diện và phong cách có thể được tham khảo [design.md](./design.md)。

## Thông số đóng góp phụ trợ

Thư mục phụ trợ được đặt tại `backend/`，Xin lưu ý khi gửi：

- Python Giữ phong cách nhiều nhất có thể pythonic
- Thích cú pháp mới hơn，Mục tiêu tương thích là Python 3.12+
- Ưu tiên chạy các lệnh gỡ lỗi và kiểm tra trong vùng chứa

Ví dụ：

```bash
docker compose exec api uv run python test/your_script.py
```

Khuyến nghị nên đặt tập lệnh thử nghiệm vào `backend/test` xuống。

## Kiểm tra chất lượng

Vui lòng hoàn thành ít nhất các bước kiểm tra sau trước khi gửi：

### Định dạng và kiểm tra tĩnh

```bash
make format
make lint
```

Nếu bài kiểm tra dựa vào tài khoản quản trị viên，Có sẵn từ thư mục gốc của dự án `.env` Đọc cấu hình liên quan trong。

## Yêu cầu bảo trì tài liệu

Sau khi thay đổi mã，Vui lòng kiểm tra xem tài liệu có cần được cập nhật đồng thời không。

- Tài liệu phát triển chung được đặt tại `docs/`
- Điều hướng tài liệu được xác định trong `docs/.vitepress/config.mts`
- Quy hoạch dang dở、Cập nhật về các mốc quan trọng trong tương lai hoặc các vấn đề đã biết [roadmap.md](./roadmap.md)；Đã hoàn thành các thay đổi mà người dùng có thể nhìn thấy hoặc cập nhật ghi chú phát hành [changelog.md](./changelog.md)
- Nếu bạn thực sự cần thêm tài liệu mà chỉ nhà phát triển mới hiển thị，mặc vào `docs/vibe/`

## Gửi thông số kỹ thuật

Nên sử dụng rõ ràng、Tiền tố cam kết có thể tìm kiếm：

```text
feat: Thêm tính năng mới
fix: sửa chữa bug
docs: Cập nhật tài liệu
refactor: tái cấu trúc mã
test: Thêm bài kiểm tra
chore: Những thay đổi trong quá trình xây dựng hoặc các công cụ phụ trợ
```

## đại lý

nếu có Agent đã gửi PR（Chẳng hạn như Claude Code、Codex Đợi đã），làm ơn PR Tiêu đề được thêm lần cuối 🤖 biểu tượng。

Và trong PR Thêm vào văn bản

```
<details>
<summary>Tuyên bố đóng góp</summary>

Ben PR bởi [Agent Name] Được tạo tự động，không có sự can thiệp của con người。
</details>
```

## kênh phản hồi

- Bug phản hồi：<https://github.com/xerrors/Yuxi/issues>
- Thảo luận chức năng：<https://github.com/xerrors/Yuxi/discussions>

Cảm ơn mọi người đóng góp cho ý kiến ​​đóng góp của họ。
