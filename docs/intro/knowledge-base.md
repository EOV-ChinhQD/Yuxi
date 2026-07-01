# Cơ sở tri thức và biểu đồ tri thức

Yuxi Cung cấp nền tảng kiến thức tài liệu、tìm kiếm véc tơ、Khả năng xây dựng bản đồ tri thức và đồ thị tri thức。Hiện được hỗ trợ Milvus cơ sở tri thức、Milvus Xây dựng đồ thị trong cơ sở tri thức/hiển thị/Tìm kiếm，và Dify Dataset、Notion Data Source Tìm kiếm chỉ đọc。

## Tại sao bạn cần một nền tảng kiến thức

Trong các kịch bản ứng dụng mô hình lớn，Chỉ dựa vào kiến ​​thức nội bộ của mô hình thường không đủ chính xác và toàn diện。Bằng cách xây dựng nền tảng kiến thức，chúng ta có thể：

- **Truyền đạt kiến thức riêng tư**：Cho phép mô hình trả lời câu hỏi dựa trên tài liệu riêng tư
- **Giảm ảo giác**：Nội dung câu trả lời có thể được truy nguyên từ tài liệu gốc
- **Tái sử dụng kiến thức**：tải lên một lần，Được sử dụng nhiều lần trong nhiều vòng đối thoại

## Loại cơ sở tri thức

| Loại | Tính năng | Các tình huống áp dụng |
|------|------|----------|
| **Milvus** | Truy xuất vectơ hiệu suất cao，Hỗ trợ lưu trữ tài liệu、Kiểm tra truy xuất、Bản đồ kiến thức、Đánh giá và xây dựng đồ thị kiến thức | Cơ sở kiến thức tài liệu tự xây dựng và phục hồi sản xuất |
| **Dify** | kết nối Dify Dataset Tìm kiếm API，trình kết nối chỉ đọc | Tái sử dụng hiện có Dify Tập dữ liệu |
| **Notion** | kết nối Notion Data Source Tìm kiếm API，trình kết nối chỉ đọc | Tái sử dụng hiện có Notion Nội dung trang |

trình kết nối chỉ đọc（Dify、Notion）Chỉ để truy xuất，Tải lên và lưu trữ không được hỗ trợ；lịch sử LightRAG Loại không còn được hiển thị hoặc tạo dưới dạng loại được hỗ trợ。

## Tạo nền tảng kiến thức

chuyến thăm Web Giao diện「cơ sở tri thức」Trang，nhấp chuột「Tạo nền tảng kiến thức mới」：

1. Điền tên cơ sở kiến thức và mô tả
2. Chọn loại cơ sở tri thức（Milvus、Dify hoặc Notion）
3. Milvus Định cấu hình mô hình nhúng và chiến lược chunking；trình kết nối chỉ đọc（Dify、Notion）Tự động hiển thị các tham số kết nối theo loại（Chẳng hạn như API URL、Token、Dataset ID Đợi đã）
4. Định cấu hình quyền truy cập
5. lưu lại

::: tip Mẹo
Tên và mô tả của cơ sở tri thức được tác nhân sử dụng để xác định khi nào nên sử dụng cơ sở tri thức này để truy xuất.，Vì vậy hãy mô tả nó càng chi tiết càng tốt。
:::

## Luồng xử lý tập tin

Milvus Các tập tin có thể truy xuất được từ việc tải lên，Trải qua ba giai đoạn：

### 1. Giai đoạn tải lên

Tải tập tin cục bộ lên máy chủ。Các tập tin được lưu trữ ở định dạng ban đầu。

### 2. giai đoạn phân tích cú pháp

Hệ thống chuyển đổi tập tin thành Markdown định dạng：

- Trích xuất nội dung văn bản
- Hình ảnh được tải lên MinIO，Và trong Markdown Trung Quốc sử dụng URL Trích dẫn
- bàn、Cố gắng giữ các công thức, v.v. càng có cấu trúc càng tốt

### 3. Giai đoạn nhập kho

cặp hệ thống Markdown nội dung đoạn，sẽ chunk Nội dung và siêu dữ liệu được ghi vào PostgreSQL của `knowledge_chunks` bàn，và viết vectơ Milvus。

Trong giao diện phía trước，Hai giai đoạn đầu tiên sẽ được hoàn thành tự động theo mặc định.。Nếu bạn cần tự động lưu trữ，Kiểm tra「Tự động đưa vào bộ nhớ sau khi tải lên」Tùy chọn；Nếu không, bạn cần nhấp vào nút nhập kho theo cách thủ công。

## Bản đồ kiến thức và câu hỏi mẫu

Milvus Được cung cấp trên trang chi tiết cơ sở kiến thức「Bản đồ kiến thức」Tab，Được sử dụng để sắp xếp danh sách tệp cơ sở kiến ​​thức thành cấu trúc phân cấp。khi được tạo ra，Phần phụ trợ sẽ đọc siêu dữ liệu tệp của cơ sở kiến thức hiện tại，Đặt tên tệp và loại cho thế hệ mô hình mặc định JSON cây，và lưu vào cơ sở kiến thức `mindmap` trường。Khi số lượng tập tin lớn，Việc thực hiện hiện nay là tiến tới cao nhất 20 các tập tin tham gia vào thế hệ，Tránh nhắc từ quá dài。Agent Bạn cũng có thể vượt qua `get_mindmap` Công cụ đọc cấu trúc này，Được sử dụng để nhanh chóng xác định thông tin cơ bản chứa đựng trong cơ sở kiến ​​thức。

Cơ sở kiến thức cũng hỗ trợ việc tạo ra các câu hỏi mẫu。Khả năng này tạo ra các câu hỏi phù hợp cho việc kiểm tra truy xuất dựa trên danh sách các tệp，và lưu vào `sample_questions` trường；Khu vực kiểm tra truy xuất front-end sẽ ưu tiên sử dụng những câu hỏi này làm ví dụ truy vấn.。Vấn đề mẫu chỉ dựa vào siêu dữ liệu của tệp，Nó không tương đương với việc tóm tắt toàn văn từng tài liệu.；Nếu bạn muốn trả lời cụ thể xung quanh cuộc trò chuyện，vẫn nên vượt qua `query_kb`、`find_kb_document` và `open_kb_document` Truy xuất bản gốc chunk hoặc đoạn tài liệu。

## Kiểm soát quyền cơ sở kiến thức

Mỗi cơ sở kiến thức có thể được cấu hình với quyền truy cập độc lập：

- **chia sẻ toàn cầu**：Có thể truy cập được cho tất cả người dùng
- **Chia sẻ khoa**：Có thể truy cập vào các bộ phận được chỉ định，Và phải bao gồm bộ phận nơi người dùng hiện tại đang ở
- **người được chỉ định**：Chỉ người sáng tạo、Có thể truy cập bởi quản trị viên và nhân viên được ủy quyền rõ ràng

Quy tắc cấp phép：

- Siêu quản trị viên có quyền truy cập vào tất cả các cơ sở kiến thức
- Quản trị viên có thể truy cập cơ sở tri thức được chia sẻ và cơ sở tri thức của bộ phận
- Người dùng thông thường chỉ có thể truy cập cơ sở kiến thức được ủy quyền

## Sơ đồ tri thức

Milvus Được cung cấp trên trang chi tiết cơ sở kiến thức「Sơ đồ tri thức」Tab。Quá trình xây dựng đồ thị sẽ bắt đầu từ chunks Trích xuất các thực thể và mối quan hệ từ，sẽ entity/triple Bản thể học và chunk Viết tài liệu tham khảo Neo4j và PostgreSQL，và là thực thể duy nhất/Sáng tạo ba lần Milvus Lập chỉ mục ngữ nghĩa；Các thực thể và bộ ba đồ thị có thể được gọi lại trong quá trình truy xuất，và với chunk Lượt kết quả hợp nhất（RRF）。

Khả năng chính：

- Cấu hình LLM máy vắt，Nhiều phương pháp chiết xuất đang được phát triển
- Xây dựng để được lập chỉ mục chunks Các thực thể và mối quan hệ của đồ thị
- Xem trạng thái xây dựng、Nhãn và số liệu thống kê
- Tìm kiếm và hiển thị hình ảnh phụ trên trang chi tiết cơ sở kiến thức
- Đặt lại cấu hình biểu đồ và dữ liệu được xây dựng

Neo4j vẫn như Milvus Lưu giữ dịch vụ lưu trữ bản đồ，nhưng không còn mang lại sự độc lập `/graph` Trang đầu，Tải lên không còn được hỗ trợ JSONL bộ ba vào bản đồ toàn cầu mặc định。

### Neo4j Cấu hình

Neo4j Thông tin kết nối có thể được tìm thấy tại `.env` Cấu hình trung bình：

- Tài khoản mặc định：`neo4j`
- mật khẩu mặc định：`0123456789`
- Giao diện quản lý：http://localhost:7474
- địa chỉ kết nối：bolt://localhost:7687

## API sử dụng

Nếu bạn cần xử lý hàng loạt tệp thông qua một chương trình，Các giao diện sau có thể được sử dụng：

```bash
# 1. Tải tập tin lên
POST /api/knowledge/files/upload?kb_id=<cơ sở tri thứcID>
# Trở lại file_path và content_hash

# 2. Phân tích và hợp nhất vào cơ sở dữ liệu
POST /api/knowledge/databases/{kb_id}/documents
# Trở lại status=queued và task_id
```

Hệ thống sẽ tự động loại bỏ trùng lặp：Xác định xem tệp tương tự đã tồn tại hay chưa dựa trên hàm băm nội dung。
