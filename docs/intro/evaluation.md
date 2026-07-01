# Hướng dẫn đánh giá cơ sở kiến thức

Đánh giá cơ sở tri thức là RAG Liên kết quan trọng trong phát triển hệ thống。thông qua đánh giá định lượng，Chúng ta có thể hiểu chất lượng của việc truy xuất và tạo，Tìm vấn đề và tiếp tục tối ưu hóa。

## Tại sao cần đánh giá

Khi xây dựng hệ thống cơ sở tri thức，Bạn có thể gặp phải những vấn đề này：

- Kết quả tìm kiếm không chính xác，Người dùng không thể tìm thấy những gì họ muốn
- Câu trả lời được tạo không khớp với tài liệu，ảo giác hiện sinh
- Chiến lược hoặc mô hình chunking được tinh chỉnh，Hiệu quả ngày càng tốt hơn hay tệ hơn?？

Chức năng đánh giá được thiết kế để trả lời những câu hỏi này。Nó đi qua các câu hỏi kiểm tra cài sẵn và câu trả lời tiêu chuẩn，Định lượng hiệu suất hệ thống，Giúp bạn đưa ra quyết định tối ưu hóa dựa trên dữ liệu。

## Giải thích các chỉ số đánh giá

Hệ thống cung cấp các chỉ số cốt lõi sau：

| chỉ báo | ý nghĩa | Giá trị tham khảo |
|------|------|--------|
| Recall@1 | Tỷ lệ kết quả tìm kiếm đầu tiên chứa tài liệu chính xác | > 0.6 tốt hơn |
| Recall@5 | trước đây5Tỷ lệ kết quả tìm kiếm có chứa tài liệu chính xác | > 0.8 tốt hơn |
| F1@K | Trung bình hài hòa của độ chính xác và thu hồi | để so sánh theo chiều ngang |
| Trả lời chính xác | Tính nhất quán giữa câu trả lời được tạo và câu trả lời tiêu chuẩn | Càng cao càng tốt |

## Tạo cơ sở đánh giá

### Chuẩn bị dữ liệu theo cách thủ công

chuẩn bị JSONL Hình thức hồ sơ đánh giá，Một mẫu trên mỗi dòng：

```json
{"query": "trí tuệ nhân tạo là gì？", "gold_chunk_ids": ["chunk_001"], "gold_answer": "trí tuệ nhân tạo là..."}
{"query": "Các loại học máy là gì?？", "gold_chunk_ids": ["chunk_005"], "gold_answer": "Chủ yếu bao gồm học tập có giám sát..."}
```

Mô tả trường：
- `query`：câu hỏi kiểm tra，bắt buộc
- `gold_chunk_ids`：Khối tài liệu dự kiến sẽ được lấy ID，Tùy chọn
- `gold_answer`：Câu trả lời chuẩn，Dùng để đánh giá chất lượng xây dựng，Tùy chọn

JSONL Chỉ là một định dạng trao đổi để nhập và xuất。Sau khi nhập，Hệ thống sẽ đánh giá tập dữ liệu、tiêu đề、Quá trình đánh giá và kết quả từng câu hỏi được lưu vào cơ sở dữ liệu，Không phụ thuộc vào địa phương JSONL Tệp dưới dạng bộ nhớ trong。

::: tip Công cụ được đề xuất
Có thể được sử dụng [EasyDataset](https://github.com/ConardLi/easy-dataset) Tạo hàng loạt cặp câu hỏi và câu trả lời từ tài liệu。Lưu ý khi xuất hãy đổi tên trường thành `query` và `gold_answer`。
:::

### Được tạo tự động

Hệ thống còn hỗ trợ tạo dữ liệu đánh giá tự động：Lấy mẫu ngẫu nhiên các khối tài liệu từ cơ sở kiến thức，Tìm nội dung tương tự bằng cách sử dụng mô hình nhúng，Cuối cùng, một mô hình lớn được sử dụng để tạo ra các cặp câu hỏi và câu trả lời。

Thông số được đề xuất：
- Số lượng câu hỏi：10-50 một
- Số lượng tài liệu tương tự：2-5 một
- Số lượng bản dựng đồng thời：Mặc định 10，tối đa 20；Nếu giới hạn hiện tại của dịch vụ mô hình chặt chẽ hơn, nó có thể được hạ xuống.

## Chạy đánh giá

Ở thanh bên trái của trang chi tiết cơ sở kiến thức，「Đường cơ sở đánh giá」Tab Được sử dụng để quản lý bộ dữ liệu đánh giá，「RAG Đánh giá」Tab Dùng để chạy đánh giá và xem kết quả。trong「RAG Đánh giá」Điền tên đánh giá、Cấu hình sau khi chọn tập dữ liệu đánh giá：

1. **mô hình tạo câu trả lời**（Tùy chọn）：Tạo câu trả lời dựa trên các đoạn tài liệu được truy xuất
2. **Mô hình phán đoán**（Tùy chọn）：Đánh giá tính nhất quán của câu trả lời được tạo ra với câu trả lời chuẩn

nhấp chuột「Bắt đầu đánh giá」，Hệ thống thực thi ở chế độ nền，Sau khi hoàn thành, kết quả của từng chỉ số sẽ được hiển thị.。

## Phân tích kết quả đánh giá

Sau khi nhận được kết quả đánh giá，Có thể phân tích theo các khía cạnh sau：

- **Recall@1 thấp**：Cho biết nội dung phù hợp nhất không được truy xuất trước tiên，Các mô hình nhúng hoặc chiến lược phân đoạn có thể cần được điều chỉnh
- **Recall@5 thấp**：Các tài liệu liên quan đến mô tả không được truy xuất，Có thể cần phải tăng số lượng tìm kiếm hoặc tối ưu hóa truy vấn
- **Độ chính xác của câu trả lời thấp**：Chỉ ra rằng có vấn đề với chất lượng thế hệ，Có thể cần phải điều chỉnh lời nhắc hoặc thay đổi mô hình

## kịch bản sử dụng

- **Xác minh trước khi lên mạng**：Sau khi việc xây dựng cơ sở tri thức được hoàn thành，Đánh giá xem hiệu quả có đáp ứng yêu cầu hay không
- **So sánh cấu hình**：Điều chỉnh chiến lược chunking、Sau khi nhúng mô hình，So sánh kết quả đánh giá
- **Giám sát thường xuyên**：Đánh giá thường xuyên，Phát hiện kịp thời sự suy giảm chất lượng
- **Điều chỉnh tham số**：Tìm tổ hợp tham số tối ưu thông qua nhiều đánh giá

---

Đánh giá là một quá trình liên tục。Khuyến nghị nên thiết lập đường cơ sở đánh giá trong quá trình xây dựng ban đầu，Mỗi thay đổi lớn tiếp theo sẽ được đánh giá，Hình thành một vòng khép kín tối ưu hóa dựa trên dữ liệu。
