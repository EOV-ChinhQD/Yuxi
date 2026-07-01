# Contributing to Yuxi

cảm ơn bạn đã quan tâm Yuxi。Các bài nộp đều được chào đón Issue、Cải thiện tài liệu、sửa chữa Bug hoặc đóng góp những tính năng mới。

Để có tài liệu phát triển đầy đủ hơn, vui lòng tham khảo [docs/develop-guides/contributing.md](docs/develop-guides/contributing.md)。

## trước khi bắt đầu

- Vui lòng tìm kiếm những cái hiện có trước khi gửi [Issues](https://github.com/xerrors/Yuxi/issues)
- Đối với những thay đổi chức năng lớn hơn，Nên mở trước Issue Kế hoạch thảo luận
- Giữ các thay đổi tập trung，tránh một lần PR Kết hợp tái cấu trúc không liên quan

## Phương pháp phát triển

Dự án này đã thông qua Docker Compose phát triển，Nên gỡ lỗi trực tiếp trong môi trường container。

```bash
docker compose up -d
docker ps
docker logs api-dev --tail 100
```

trong dự án `api-dev` và `web-dev` Tải lại nóng được hỗ trợ theo mặc định，Thường không cần phải khởi động lại vùng chứa sau khi sửa đổi mã cục bộ。

## Quá trình nộp hồ sơ

1. Fork Kho lưu trữ và tạo chi nhánh
2. Hoàn thành phát triển và thử nghiệm trong thư mục tương ứng
3. Gửi rõ ràng Commit Message
4. khởi xướng Pull Request，và giải thích nội dung sửa đổi、Lý do và phương pháp xác minh
5. PR mẫu [PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md) Các mục kiểm tra cần phải được hoàn thành trước khi gửi

Ví dụ：

```bash
git checkout -b feature/your-change
git commit -m "feat: add knowledge graph import flow"
git push origin feature/your-change
```

## Yêu cầu về mã

### phổ quát

- Giữ việc triển khai đơn giản và dễ hiểu，Tránh thiết kế quá mức
- Chỉ sửa đổi những gì cần thiết cho nhiệm vụ hiện tại，Thực hiện tái cấu trúc thêm không hề dễ dàng
- Cập nhật tài liệu liên quan
- nếu cần thiết，Cập nhật đồng bộ [docs/develop-guides/changelog.md](docs/develop-guides/changelog.md)
- Vui lòng tham khảo phần thiết kế [docs/develop-guides/design.md](docs/develop-guides/design.md)

### phụ trợ

- sử dụng Python 3.12+ phong cách
- Chạy trước khi gửi：

```bash
make format
make lint
docker compose exec api uv run pytest
```

- Khuyến nghị nên đặt tập lệnh thử nghiệm vào `backend/test`

### giao diện người dùng

- sử dụng `pnpm`
- API Các giao diện được thống nhất trong `web/src/apis`
- ưu tiên sử dụng `lucide-vue-next` biểu tượng
- Cách sử dụng kiểu `less`
- Ưu tiên tái sử dụng trừ trường hợp đặc biệt [web/src/assets/css/base.css](web/src/assets/css/base.css) biến màu trong

## Pull Request Đề xuất

- Xóa tiêu đề，Có thể giải thích mục tiêu của sự thay đổi
- Mô tả có chứa những thay đổi、Phạm vi tác động và kết quả xác minh
- nếu nó liên quan đến UI，Vui lòng đính kèm ảnh chụp màn hình hoặc bản ghi màn hình
- Nếu nó liên quan đến thay đổi giao diện hoặc hành vi，Vui lòng thêm tài liệu

## Gửi thông tin gợi ý

Nên sử dụng các tiền tố sau：

- `feat`
- `fix`
- `docs`
- `refactor`
- `test`
- `chore`

## Phản hồi vấn đề

- Bug phản hồi/Thảo luận chức năng：<https://github.com/xerrors/Yuxi/issues>

cảm ơn vì sự đóng góp của bạn ❤️。
