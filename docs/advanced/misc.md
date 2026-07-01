# Các cấu hình khác

Giới thiệu về tài liệu này Yuxi Các tùy chọn cấu hình khác cho，Bao gồm bảo mật nội dung、Cổng dịch vụ và tìm kiếm trên web, v.v.。

## Bảo mật nội dung

Cơ chế xét duyệt nội dung tích hợp trong hệ thống，Giúp đảm bảo tính tuân thủ của nội dung dịch vụ。

### Phương pháp kích hoạt

trong「Cài đặt hệ thống」→「Cài đặt cơ bản」Cấu hình trong trang，Tùy chọn bật tính năng lọc từ khóa và LLM Kiểm duyệt nội dung。

### Quá trình thử nghiệm

Hệ thống sẽ phát hiện vào những thời điểm sau：

1. **Phát hiện đầu vào của người dùng**：Phát hiện ngay sau khi nhận được tin nhắn của người dùng
2. **Phát hiện đầu ra truyền phát**：Phát hiện thời gian thực của từ khóa đầu ra（chế độ chỉ từ khóa）
3. **Kiểm tra hoàn thành đầu ra**：Kiểm tra toàn diện sau khi phát trực tuyến

### chế độ phát hiện

**Phát hiện từ khóa**

Từ vựng nhạy cảm nằm ở `backend/package/yuxi/config/static/bad_keywords.txt`，Một từ khóa trên mỗi dòng。Các sửa đổi sẽ có hiệu lực ngay lập tức，Không cần khởi động lại dịch vụ。

**LLM Phát hiện**

Sử dụng mô hình lớn để xem xét nội dung，Có thể xác định tốt hơn các vấn đề phức tạp như chèn từ nhắc nhở，Nhưng nó sẽ làm tăng độ trễ phản hồi。

::: warning Cân nhắc về hiệu suất
LLM Phát hiện làm tăng độ trễ tương tác của người dùng，Vui lòng chọn kích hoạt tùy theo nhu cầu thực tế。
:::

## tìm kiếm trên mạng

Hệ thống được tích hợp Tavily Khả năng tìm kiếm trên Internet，Cho phép các mô hình lớn thu được thông tin trang web theo thời gian thực。

### Các bước cấu hình

1. chuyến thăm [Tavily Trang web chính thức](https://app.tavily.com/) Đăng ký và tạo API Key
2. trong `.env` Thêm vào tập tin：
   ```env
   TAVILY_API_KEY=sk-xxxxxxxxxxxxxxxx
   ```
3. Khởi động lại dịch vụ：
   ```bash
   docker compose up -d api-dev web-dev
   ```

### Cách sử dụng

Sau khi cấu hình xong，Bạn sẽ thấy trong khu vực cấu hình công cụ của đại lý Tavily Công cụ tìm kiếm。Mô hình tự động xác định khi nào cần gọi tìm kiếm để có được thông tin mới nhất。

Để đóng，Xóa hoặc xóa `TAVILY_API_KEY` Sau đó khởi động lại dịch vụ。

## cảng dịch vụ

Mỗi dịch vụ hệ thống cung cấp quyền truy cập thông qua các cổng sau：

| hải cảng | dịch vụ | Mô tả |
|------|------|------|
| 5173 | Web giao diện người dùng | giao diện người dùng |
| 5050 | API phụ trợ | Giao diện dịch vụ cốt lõi |
| 7474 | Neo4j HTTP | Giao diện quản lý cơ sở dữ liệu đồ thị |
| 7687 | Neo4j Bolt | Kết nối cơ sở dữ liệu đồ thị |
| 9000/9001 | MinIO | lưu trữ đối tượng |
| 19530/9091 | Milvus | cơ sở dữ liệu vector |
| 5432 | PostgreSQL | cơ sở dữ liệu kinh doanh |

### Cổng dịch vụ tùy chọn

| hải cảng | dịch vụ | Mô tả |
|------|------|------|
| 30000 | MinerU | PDF dịch vụ phân tích cú pháp |
| 8080 | PP-Structure-V3 | OCR dịch vụ |
| 8081 | vLLM | Dịch vụ suy luận cục bộ |

### truy cập nhanh

- Web giao diện：http://localhost:5173
- API Tài liệu：http://localhost:5050/docs
- Neo4j quản lý：http://localhost:7474
