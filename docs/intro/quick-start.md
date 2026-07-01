# Hướng dẫn bắt đầu nhanh

Chào mừng Yuxi（Phân tích ngôn ngữ），Đây là cơ sở tri thức thông minh và biểu đồ tri thức Agent Nền tảng phát triển。
Hướng dẫn này sẽ giúp bạn thiết lập và chạy hệ thống của mình trong vài phút，cho phép bạn tận dụng LangGraph、RAG Xây dựng đồ thị công nghệ và tri thức AI Ứng dụng kiến thức định hướng。

![Sơ đồ kiến trúc hệ thống](https://xerrors.oss-cn-shanghai.aliyuncs.com/github/arch.png)


::: tip Mẹo
Ngoài trang tài liệu này，Bạn cũng có thể ghé thăm [Zread](https://zread.ai/xerrors/Yuxi) hoặc [DeepWiki](https://deepwiki.com/xerrors/Yuxi) Xem tài liệu dự án chi tiết được tạo tự động。
:::

## Yêu cầu về môi trường

Dự án áp dụng thiết kế kiến trúc microservice，Dịch vụ mặc định không cần thiết GPU hỗ trợ。Nếu cần sử dụng OCR chức năng，Các dịch vụ bên ngoài có thể được cấu hình thông qua các biến môi trường。

## Cài đặt nhanh

### bước một：Nhận mã dự án

```bash
# Sao chép phiên bản mới nhất
git clone --branch v0.7.0 --depth 1 https://github.com/xerrors/Yuxi.git
cd Yuxi
```

`--depth 1` cờ sẽ tạo một bản sao nông，Chỉ bao gồm các cam kết mới nhất，do đó giảm đáng kể thời gian tải xuống và sử dụng đĩa。Bảng sau đây cung cấp hướng dẫn về lựa chọn phiên bản。

| Phiên bản | Các tình huống áp dụng |
|------|----------|
| v0.7.0 | Phiên bản ổn định hiện tại，Khuyến nghị sử dụng cho sản xuất |
| main | phiên bản phát triển，Chứa các tính năng mới nhất（Có thể không ổn định） |

### Bước 2：Cấu hình các biến môi trường

**Phương pháp một：Sử dụng tập lệnh khởi tạo（Được đề xuất）**

Chúng tôi cung cấp các kịch bản tự động hóa，Giúp bạn hoàn thành cấu hình môi trường và Docker Kéo hình ảnh：

```bash
# Linux/macOS
./scripts/init.sh

# Windows PowerShell
.\scripts\init.ps1
```

Tập lệnh sẽ hướng dẫn bạn cấu hình sau：
- tạo ra `.env` Tệp cấu hình
- cài đặt `SILICONFLOW_API_KEY`（bắt buộc，Dùng để gọi các mô hình lớn）
- cài đặt `TAVILY_API_KEY`（Tùy chọn，cho các dịch vụ tìm kiếm）
- Tự động kéo yêu cầu Docker gương

::: tip API Key Nhận
- **dòng chảy dựa trên silicon**：chuyến thăm [cloud.siliconflow.cn](https://cloud.siliconflow.cn/i/Eo5yTHGJ)，Đăng ký và được chứng nhận 16 Hạn ngạch nhân dân tệ
- **Tavily**：chuyến thăm [app.tavily.com](https://app.tavily.com/) Nhận tìm kiếm API Key（Tùy chọn）
:::

**Phương pháp 2：Cấu hình thủ công**

Nếu cấu hình thủ công được ưu tiên：

```bash
# Sao chép mẫu biến môi trường
cp .env.template .env

# Chỉnh sửa .env tập tin，điền vào của bạn API Key
```

### Bước 3：Bắt đầu dịch vụ

```bash
# Xây dựng và bắt đầu tất cả các dịch vụ
docker compose up --build -d
```

Khi dịch vụ được khởi động lần đầu tiên, nó cần đợi hình ảnh được kéo và biên dịch.，xin hãy kiên nhẫn 2-3 phút。

::: tip Chế độ nhẹ（Lite Mode）
Nếu bạn không cần cơ sở kiến thức và các hàm biểu đồ tri thức，Có thể bắt đầu sử dụng chế độ nhẹ，bỏ qua Milvus、Neo4j、etcd Đang chờ dịch vụ，Tiết kiệm tài nguyên hệ thống：

```bash
make up-lite  # macOS or Linux
```

Chế độ nhẹ chỉ khởi động các dịch vụ cốt lõi（giao diện người dùng、phụ trợ、PostgreSQL、Redis、MinIO），Thanh bên ở giao diện người dùng sẽ tự động ẩn cơ sở kiến ​​thức và lối vào biểu đồ。Để chuyển về chế độ đầy đủ, chỉ cần chạy `make up`。
:::

### Bước 4：hệ thống truy cập

Sau khi dịch vụ bắt đầu，Hãy đến địa chỉ sau：

| dịch vụ | địa chỉ |
|------|------|
| Web giao diện | http://localhost:5173 |
| API Tài liệu | http://localhost:5050/docs |

trong chuyến thăm đầu tiên，Hệ thống sẽ yêu cầu bạn thiết lập tài khoản và mật khẩu quản trị viên cấp cao，Hãy giữ nó đúng cách。

## Khắc phục sự cố

### Kiểm tra trạng thái dịch vụ

```bash
# Xem tất cả trạng thái vùng chứa
docker ps

# Xem nhật ký phụ trợ trong thời gian thực
docker logs api-dev -f

# Xem nhật ký giao diện người dùng trong thời gian thực
docker logs web-dev -f
```

### Câu hỏi thường gặp

<details>
<summary><strong>Docker Kéo hình ảnh không thành công</strong></summary>

Nếu việc kéo hình ảnh không thành công vì lý do mạng，có thể thử：

```bash
# Kéo hình ảnh cơ sở theo cách thủ công
bash scripts/pull_image.sh python:3.12-slim
```

**Giải pháp triển khai môi trường ngoại tuyến**：

```bash
# Xuất hình ảnh trong môi trường mạng，Chú ý kiểm tra danh sách gương，Không nhất thiết phải là mới nhất。
bash docker/save_docker_images.sh

# Chuyển đến máy mục tiêu
scp docker_images_xxx.tar user@host:/path/

# Nhập hình ảnh
docker load -i docker_images_xxx.tar
```
</details>

<details>
<summary><strong>Xây dựng không thành công</strong></summary>

Hầu hết các lỗi xây dựng là do sự cố mạng。Hãy thử định cấu hình proxy：

```bash
# Linux/macOS
export HTTP_PROXY=http://IP:PORT
export HTTPS_PROXY=http://IP:PORT

# Windows PowerShell
$env:HTTP_PROXY="http://IP:PORT"
$env:HTTPS_PROXY="http://IP:PORT"
```

Nếu không thành công sau khi định cấu hình proxy，Hãy thử xóa proxy và thử lại。
</details>

<details>
<summary><strong>Milvus Khởi động dịch vụ không thành công</strong></summary>

```bash
# Khởi động lại Milvus dịch vụ
docker compose up milvus -d
docker restart api-dev
```
</details>

::: tip Bảng gỡ lỗi
Giao diện người dùng cung cấp bảng gỡ lỗi（Tìm thấy trong menu hình đại diện），Thông tin chi tiết về yêu cầu và phản hồi có thể được xem。Nên tắt tính năng này trong môi trường sản xuất。
:::

## Bước tiếp theo

- Tìm hiểu cách định cấu hình mô hình của bạn：đọc [Cấu hình mô hình](./model-config.md)
- Khám phá các tính năng cơ sở kiến thức：đọc [Cơ sở tri thức và biểu đồ tri thức](./knowledge-base.md)
- Phát triển đại lý học tập：đọc [Phát triển đại lý](../agents/agents-config.md)
- Tìm hiểu thêm về hệ thống cấu hình：đọc [Giải thích chi tiết về hệ thống cấu hình](../advanced/configuration.md)
