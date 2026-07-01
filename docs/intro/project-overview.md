# Giới thiệu dự án

Yuxi (Phân tích ngôn ngữ) Nó là một cơ sở tri thức thông minh và biểu đồ tri thức Agent Nền tảng phát triển，Có thể giúp bạn xây dựng một thế hệ nâng cao truy xuất kết hợp (RAG) Lập luận ở cấp độ sản xuất với biểu đồ tri thức AI ứng dụng。Nền tảng này dựa trên LangGraph、Vue.js 3、FastAPI、Milvus và Neo4j xây dựng，Tạo cuộc trò chuyện AI Điều phối các tác nhân theo yêu cầu của hệ thống、thu hồi kiến thức、Lập luận đồ thị、Cuộc gọi công cụ và khả năng của hệ thống tập tin。

## khái niệm thiết kế

Mục tiêu thiết kế của dự án là cung cấp cho các nhà phát triển một công cụ dễ sử dụng、mạnh mẽ AI khung phát triển ứng dụng。Chúng tôi tuân thủ các nguyên tắc sau：

- **Ngăn xếp công nghệ đơn giản**：Chọn công nghệ chủ đạo và trưởng thành，Giảm chi phí học tập và bảo trì
- **MIT Thỏa thuận nguồn mở**：Nguồn mở hoàn toàn，Cho phép sử dụng miễn phí và phát triển thứ cấp
- **Triển khai trong container**：Vượt qua Docker Compose quản lý，Đơn giản hóa quá trình triển khai

## Kiến trúc kỹ thuật

| Hệ thống phân cấp | Công nghệ | Mục đích |
|------|------|------|
| giao diện người dùng | Vue.js 3, Vite, Ant Design Vue | Đáp ứng hiện đại UI Thư viện khung và thành phần |
| Quản lý trạng thái | Pinia | Quản lý trạng thái tập trung phía trước |
| phụ trợ API | FastAPI, Uvicorn | Hiệu suất cao không đồng bộ Python Web khung |
| Agent khung | LangGraph | Agent Sắp xếp、quản lý trạng thái và checkpoint |
| cơ sở tri thức | Milvus（Có thể xây dựng và lưu trữ cơ sở dữ liệu）、Dify / Notion（trình kết nối chỉ đọc） | cơ sở kiến thức vector RAG Truy xuất bằng các nguồn dữ liệu chỉ đọc bên ngoài |
| cơ sở dữ liệu đồ thị | Neo4j | Milvus Lưu trữ và truy vấn biểu đồ tri thức trong cơ sở tri thức |
| Xử lý tài liệu | MinerU, PaddleX, RapidOCR | Phân tích tài liệu đa định dạng và OCR |
| hàng đợi nhiệm vụ | Redis, PostgreSQL Workers | Xử lý tác vụ không đồng bộ |
| lưu trữ đối tượng | MinIO | Lưu trữ tập tin và tài liệu |
| cơ sở dữ liệu quan hệ | PostgreSQL | Tính bền vững của siêu dữ liệu và dữ liệu người dùng |
| triển khai | Docker, Docker Compose | Triển khai và điều phối trong container |


## năng lực cốt lõi

Yuxi Năng lực cốt lõi không nằm ở“Mang theo mô hình lớn”，Nhưng đó là về việc đặt **Phát triển đại lý、cơ sở tri thức/RAG、Sơ đồ tri thức** Đặt nó vào cùng một hệ thống，và để chúng thực sự làm việc cùng nhau trong thời gian chạy。

### 1. Phát triển thông minh cho doanh nghiệp thực sự

Yuxi Dựa trên LangGraph Cung cấp khả năng phát triển đại lý thông minh，Không chỉ là lối vào hỏi đáp cố định，Đúng hơn, nó là một tập hợp các cấu hình có thể cấu hình được、có thể mở rộng Agent Chạy khung。Các nhà phát triển có thể xây dựng xung quanh cùng một Agent Cấu hình mô hình、lời nhắc、Công cụ、MCP、Skills、Đại lý phụ và phần mềm trung gian，làm“Kỹ năng đàm thoại”trở thành“Khả năng kinh doanh có thể điều phối”。

Lớp này là trung tâm điều khiển của dự án，Xác định cách mô hình gọi công cụ、Cách tiếp cận kiến thức、Cách truy cập hệ thống tệp và cộng tác với các tác nhân phụ khác。

### 2. cơ sở tri thức và RAG Khả năng tích hợp

Yuxi Cung cấp liên kết cơ sở dữ liệu kiến thức đầy đủ，Thay vì chỉ đóng gói giao diện truy xuất。Tài liệu bắt đầu bằng việc tải lên，sẽ được phân tích cú pháp、Cắt nhỏ、vector hóa、Các giai đoạn cấu hình và đánh giá truy xuất，cuối cùng đã trở thành Agent Nguồn kiến thức có thể truy cập trực tiếp。

Biến tài liệu của tổ chức bạn thành trợ lý đàm thoại thông minh。tải lên PDF Hướng dẫn sử dụng、Thông số kỹ thuật、Văn bản chính sách và tài liệu đào tạo，để tạo ra một tìm kiếm có thể、Cơ sở tri thức với khả năng suy luận，Nhân viên có thể sử dụng truy vấn ngôn ngữ tự nhiên。
Hệ thống có thể hiểu được các vấn đề phức tạp，và cung cấp câu trả lời phù hợp với ngữ cảnh kèm theo trích dẫn nguồn。


### 3. Đồ thị tri thức tham gia suy luận，thay vì chỉ hiển thị

Yuxi Khả năng biểu đồ tri thức không phải là một mô-đun trực quan hóa riêng biệt，Nhưng với Milvus Liên kết liên kết lưu trữ cơ sở kiến thức。Hệ thống có thể lưu trữ các chunks Trích xuất các thực thể và mối quan hệ từ，viết Neo4j với PostgreSQL và là thực thể duy nhất/Sáng tạo ba lần Milvus Lập chỉ mục ngữ nghĩa；Các thực thể và bộ ba đồ thị có thể được gọi lại trong quá trình truy xuất，và với chunk Lượt kết quả hợp nhất（RRF），Hiển thị và tìm kiếm các sơ đồ con trên trang chi tiết cơ sở kiến thức。

### 4. Hiểu biết tài liệu và khả năng nền tảng để triển khai sản xuất

Để kiến thức thực sự có thể sử dụng được，Yuxi tích hợp MinerU、PP-Structure-V3、RapidOCR、DeepSeek OCR Khả năng phân tích，Bìa PDF、Office、Markdown、Các định dạng phổ biến như hình ảnh，Giải quyết vấn đề xử lý có cấu trúc dữ liệu thô trước khi vào hệ thống。

Trên cơ sở này，Nền tảng này cũng bổ sung các khả năng kỹ thuật thường được sử dụng trong triển khai kinh doanh.，Ví dụ：

- Quản lý bộ phận và thẩm quyền
- Khả năng kiểm duyệt và bảo vệ nội dung
- Quản lý tập tin và quản lý tác vụ
- Docker Compose Triển khai và phát triển tải lại nóng


## Các tình huống áp dụng

Yuxi Áp dụng cho các tình huống sau：

- **Cơ sở tri thức doanh nghiệp**：Xây dựng hệ thống hỏi đáp kiến thức riêng
- **Dịch vụ khách hàng thông minh**：Câu hỏi và trả lời tự động dựa trên tài liệu
- **quản lý tri thức**：Phân tích tài liệu tự động、Phân loại、Xây dựng bản đồ
- **AI phát triển ứng dụng**：Nhanh chóng xây dựng các nguyên mẫu ứng dụng dựa trên các mô hình lớn

## Bước tiếp theo

- bắt đầu nhanh：đọc [Hướng dẫn bắt đầu nhanh](./quick-start.md)
- Cấu hình mô hình：đọc [Cấu hình mô hình](./model-config.md)
- Cách sử dụng cơ sở kiến thức：đọc [Cơ sở tri thức và biểu đồ tri thức](./knowledge-base.md)
- Phát triển đại lý：đọc [Phát triển đại lý](../agents/agents-config.md)
