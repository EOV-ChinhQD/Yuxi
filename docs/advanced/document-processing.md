# Xử lý tài liệu và OCR

Yuxi Hỗ trợ phân tích cú pháp thông minh của nhiều định dạng tài liệu，Từ các tập tin văn bản đơn giản đến phức tạp PDF Tài liệu，có thể tự động trích xuất nội dung và chuyển đổi nó sang định dạng có thể tìm kiếm được。

## Các loại tệp được hỗ trợ

### Tài liệu chung

| Loại | định dạng | Mô tả |
|------|------|------|
| văn bản | .txt, .md, .html, .htm | Trích xuất nội dung trực tiếp |
| Word | .docx | Giữ nguyên định dạng và cấu trúc |
| PowerPoint | .pptx | Giữ nguyên cấu trúc văn bản chính |
| PDF | .pdf | Hỗ trợ văn bản và hình ảnh PDF |
| bàn | .csv, .xls, .xlsx | Xác định cấu trúc bảng |
| JSON | .json | dữ liệu có cấu trúc |

### Tệp hình ảnh

Đối với tập tin hình ảnh，Cần kích hoạt OCR để trích xuất văn bản：
- .jpg, .jpeg, .png, .bmp, .tiff, .tif

### Gói nén

Hỗ trợ tải lên ZIP Gói nén，Hệ thống sẽ：
- Tự động trích xuất và xử lý Markdown tập tin
- Xử lý hình ảnh và tải lên bộ nhớ đối tượng
- Nhận dạng thông minh `full.md` hoặc đầu tiên `.md` tập tin

### Nội dung trang web

Hỗ trợ thông qua URL Chụp nội dung web trực tiếp：

1. Cấu hình `YUXI_URL_WHITELIST` Biến môi trường cho phép cơ chế danh sách trắng
2. Hệ thống tự động HTML Chuyển đổi thành Markdown
3. Cơ chế chống trùng lặp tích hợp，Tránh thu thập thông tin lặp đi lặp lại

::: tip URL Cấu hình danh sách trắng
Ví dụ：`YUXI_URL_WHITELIST=github.com,*.wikipedia.org,docs.python.org`
:::

## OCR Lựa chọn giải pháp

Hệ thống cung cấp nhiều loại OCR Kế hoạch，Thích hợp cho các kịch bản khác nhau：

### So sánh kế hoạch

| Kế hoạch | Các tình huống áp dụng | Yêu cầu phần cứng | Tính năng |
|------|----------|----------|------|
| RapidOCR | Nhận dạng văn bản cơ bản | CPU | Nguồn mở và miễn phí，nhanh |
| MinerU | phức tạp PDF、bàn | GPU | Độ chính xác cao，Phân tích bố cục tốt |
| MinerU Official | Tài liệu phức tạp | không có | Dịch vụ đám mây chính thức，Sẵn sàng ra khỏi hộp |
| PP-Structure-V3 | bàn、hóa đơn | GPU | Phân tích bố cục chuyên nghiệp |
| DeepSeek OCR | Sự hiểu biết thông minh | không có | Dịch vụ đám mây，Markdown đầu ra |

### Chọn đề xuất

- **sử dụng cá nhân hoặc CPU môi trường**：chọn RapidOCR，Sử dụng tài nguyên miễn phí và thấp
- **Yêu cầu độ chính xác cao**：chọn MinerU（cần GPU）hoặc MinerU Official
- **Tài liệu chuyên sâu về bảng**：chọn PP-Structure-V3
- **Dịch vụ đám mây đơn giản**：chọn DeepSeek OCR

## Cấu hình nhanh

### RapidOCR

Nó sẽ được tải xuống theo mặc định sau khi khởi động，Không cần cấu hình

### MinerU（Độ chính xác cao）

Dự án được xây dựng trong mineru-api dịch vụ（nằm ở docker-compose.yml，Thuộc về all profile），Không cần tải xuống chính thức bổ sung compose tập tin。Lần đầu tiên hình ảnh được xây dựng nó sẽ dựa trên docker/mineru.Dockerfile Tải xuống mô hình，Quá trình này mất nhiều thời gian。

Bắt đầu dịch vụ（cần GPU）：

```bash
docker compose --profile all up -d --build mineru-api
```

Dịch vụ này đang ở `30001` Cổng được cung cấp `/file_parse` giao diện，phụ trợ `api` / `worker` Vượt qua theo mặc định `MINERU_API_URI=http://mineru-api:30001` kết nối，Thông thường không cần cấu hình bổ sung。

::: tip Bộ nhớ video không đủ
Nếu bộ nhớ video bị hạn chế thì quá trình khởi động sẽ không thành công.，Có sẵn tại `docker-compose.yml` của `mineru-api` Phát hành dưới dịch vụ `--gpu-memory-utilization` thông số（Chẳng hạn như `0.5`，Giảm thêm nếu cần thiết）。
:::

### MinerU Official（dịch vụ đám mây）

từ [MinerU Trang web chính thức](https://mineru.net) Nhận API chìa khóa，trong .env Cấu hình các biến môi trường

```env
MINERU_API_KEY=your-api-key-here
```

### PP-Structure-V3（có cấu trúc）

Bắt đầu dịch vụ（cần GPU）

```bash
docker compose up paddlex -d
```

### DeepSeek OCR（Dịch vụ đám mây đơn giản）

trong .env Cấu hình（Sử dụng hiện có SiliconFlow chìa khóa）

```env
SILICONFLOW_API_KEY=your-api-key-here
```

## Cấu hình hiển thị hình ảnh

Hình ảnh trong tài liệu đã tải lên cần phải được định cấu hình chính xác trước khi có thể hiển thị ra bên ngoài：

trong `.env` Thiết lập máy chủ trong IP：

```
HOST_IP=your_server_ip
```

## Những điều cần lưu ý

1. **Tệp hình ảnh phải được bật OCR**：Nếu không thì không thể trích xuất nội dung
2. **GPU yêu cầu**：MinerU và PP-Structure-V3 cần GPU hỗ trợ
3. **API chìa khóa**：Một số dịch vụ yêu cầu bổ sung API Cấu hình khóa
4. **Xử lý thời gian chờ**：Việc phân tích các tài liệu phức tạp có thể mất nhiều thời gian，Có thể vượt qua `MINERU_TIMEOUT` Hết thời gian điều chỉnh biến môi trường
5. **Giới hạn kích thước tập tin**：Kích thước của một tệp được tải lên không vượt quá 100 MB
