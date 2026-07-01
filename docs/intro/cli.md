# Công cụ dòng lệnh

`yuxi-cli` Có Yuxi máy khách dòng lệnh，Thích hợp để quản lý các phiên bản từ xa từ tập lệnh hoặc thiết bị đầu cuối cục bộ、Đăng nhập tài khoản、Tải lên tập tin cơ sở kiến thức，và chạy một số nhiệm vụ đại lý。

## Cài đặt

Được đề xuất `uv` hoặc `pipx` Cài đặt：

```bash
uv tool install yuxi-cli
```

Nó cũng có thể được chạy tạm thời：

```bash
uvx --from yuxi-cli yuxi --help
```

Sau khi cài đặt, bạn có thể vượt qua `yuxi --version` Xem phiên bản hiện tại。

## Định cấu hình phiên bản từ xa

Thêm một cái đầu tiên Yuxi Địa chỉ cá thể，Đặt làm mặc định hiện tại remote：

```bash
yuxi remote add local http://localhost:5173
yuxi remote use local
yuxi remote ping
```

Cấu hình sẽ được lưu vào `~/.yuxi/config.toml`。Nếu bạn cần quản lý nhiều phiên bản cùng một lúc，Bạn có thể tiếp tục thêm khác remote，và vượt qua `yuxi remote use <name>` chuyển đổi。

## Đăng nhập

Đăng nhập bằng ủy quyền trình duyệt theo mặc định：

```bash
yuxi login --browser
```

nếu đã ở trong Yuxi được tạo ra ở API Key，Bạn cũng có thể nhập nó trực tiếp：

```bash
yuxi login --api-key yxkey_xxx
```

Các lệnh trạng thái tài khoản thường được sử dụng：

```bash
yuxi whoami
yuxi status
yuxi logout
```

## Tải lên tập tin cơ sở kiến thức

Khi tải lên một thư mục，Nếu không được chỉ định `--kb-id`，CLI sẽ kéo dòng điện remote Cơ sở kiến thức có sẵn và chọn trong thiết bị đầu cuối：

```bash
yuxi kb upload ./docs
```

Văn bản thông dụng và Office Loại tài liệu，Loại tệp có thể được điều chỉnh trong giai đoạn xem trước；Bạn cũng có thể chỉ định nó trực tiếp thông qua các tham số：

```bash
yuxi kb upload ./docs --kb-id kb_xxx --concurrency 4
yuxi kb upload ./docs --include-ext md,html,docx
```

CLI Mỗi đơn vị kiêm nhiệm sẽ được phép hoàn thành việc tải lên một tệp duy nhất và thêm hồ sơ tài liệu.，`--concurrency` Mặc định 10，Phạm vi cho phép 1-300，Được sử dụng để kiểm soát số lượng tệp được xử lý đồng thời。Tải lên giữ nguyên đường dẫn tương đối trong thư mục，Thật thuận tiện khi xem theo cấu trúc thư mục gốc trong danh sách tệp cơ sở tri thức.。

## Chạy đánh giá đại lý

Nếu phiên bản được cấu hình Langfuse Tập dữ liệu，có sẵn CLI Đánh giá tác nhân kích hoạt：

```bash
yuxi agent eval \
  --dataset-name demo-dataset \
  --agent-slug default-agent \
  --experiment-name cli-demo
```

Lệnh này sẽ đọc Langfuse Đầu vào tập dữ liệu，gọi Yuxi Đại lý đang chạy，Và truyền kết quả trở lại thí nghiệm tương ứng。
