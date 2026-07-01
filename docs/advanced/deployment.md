# Hướng dẫn triển khai sản xuất

Tài liệu này mô tả cách triển khai trong môi trường sản xuất Yuxi。

## Điều kiện tiên quyết

- Docker Engine (v24.0+)
- Docker Compose (v2.20+)
- NVIDIA Container Toolkit（Nếu bạn cần sử dụng GPU dịch vụ）

::: warning Những điều cần lưu ý
1. Nên sử dụng các loại máy khác nhau cho môi trường sản xuất và môi trường phát triển，Tránh xung đột cổng và tài nguyên
2. Mặc dù có tên「môi trường sản xuất」，Nhưng đây chỉ là cấu hình cơ bản，Việc ra mắt thực tế cần phải được điều chỉnh theo tình hình thực tế.
3. Có một bảng gỡ lỗi ở mặt trước（Được kích hoạt bằng cách nhấn và giữ thanh bên），Đề nghị đóng cửa môi trường sản xuất
:::

## Các bước triển khai

### 1. Chuẩn bị tập tin cấu hình

Để tránh xung đột với môi trường phát triển，Đề xuất cho môi trường sản xuất `.env.prod` tập tin：

```bash
cp .env.template .env.prod
```

Chỉnh sửa `.env.prod`，Đặt mật khẩu mạnh và cần thiết API chìa khóa：

- `NEO4J_PASSWORD`：Thay đổi mật khẩu mặc định
- `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`：Sửa đổi khóa mặc định
- `SILICONFLOW_API_KEY` khóa mô hình bằng nhau

### 2. Bắt đầu dịch vụ

Bắt đầu sử dụng tệp cấu hình môi trường sản xuất：

```bash
# Chỉ bắt đầu các dịch vụ cốt lõi（CPU chế độ）
docker compose -f docker-compose.prod.yml up -d --build

# Bắt đầu tất cả các dịch vụ（chứa GPU OCR）
docker compose -f docker-compose.prod.yml --profile all up -d --build
```

### 3. Xác minh triển khai

- Web chuyến thăm：http://localhost（vượt qua trực tiếp 80 hải cảng）
- API kiểm tra sức khỏe：`curl http://localhost/api/system/health`

## Bảo trì và cập nhật

### Cập nhật mã

```bash
# Kéo mã mới nhất
git pull

# Xây dựng lại và bắt đầu
docker compose -f docker-compose.prod.yml up -d --build
```

### Xem nhật ký

```bash
# API Nhật ký
docker logs -f api-prod

# Nginx nhật ký truy cập
docker logs -f web-prod
```
