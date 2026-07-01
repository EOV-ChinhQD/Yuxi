# Đánh giá đại lý

Yuxi Đánh giá tác nhân được sử dụng để trả lời một câu hỏi cụ thể：ai đó Agent Bạn có thể hoàn thành một cách nhất quán một nhóm nhiệm vụ cố định không?。nó không có ở đó Yuxi Bộ dữ liệu đánh giá bảo trì nội bộ、Quy tắc chấm điểm hoặc báo cáo so sánh，Đúng hơn, những khả năng này được trao cho Langfuse；Yuxi Chỉ chịu trách nhiệm về sự thật Agent Chạy link thực hiện từng mẫu，và ghi lại kết quả vào Langfuse experiment。

## ranh giới áp dụng

Chức năng này dành cho Agent Đánh giá hành vi từ đầu đến cuối，Không phải là đánh giá chỉ số truy xuất cơ sở kiến thức。Nếu bạn muốn đánh giá RAG Thu hồi tìm kiếm、Trả lời chính xác và điểm chuẩn cơ sở kiến thức，Vui lòng sử dụng「Đánh giá cơ sở kiến thức」。Nếu bạn muốn đánh giá một Agent Lập trình、Nghiên cứu、Cuộc gọi công cụ、Hiệu suất thực tế khi lập kế hoạch hoặc thực hiện các nhiệm vụ nhiều bước，sau đó sử dụng những cái được giới thiệu trên trang này Langfuse dataset experiment quá trình。

Đánh giá liên kết duy trì ba ranh giới：

- Langfuse chịu trách nhiệm dataset、experiment、score、So sánh và hình dung。
- Yuxi Phần phụ trợ chịu trách nhiệm tạo ra giao diện bình thường conversation và AgentRun，và tái sử dụng worker Liên kết thực thi。
- `yuxi` CLI Chỉ chịu trách nhiệm đọc Langfuse dataset、chạy experiment、gọi Yuxi eval API，không chịu trách nhiệm tạo hoặc tải lên dataset。

## Điều kiện tiên quyết

1. Yuxi Chương trình phụ trợ đã được kích hoạt Langfuse tracing，Và trong `.env` Cấu hình trung bình：

```bash
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

2. máy cục bộ CLI Môi trường cũng có thể đọc cùng một nhóm Langfuse biến môi trường。`yuxi agent eval` Cần gọi trực tiếp Langfuse SDK đọc dataset và tạo ra experiment。

3. Đã đăng nhập Yuxi CLI：

```bash
yuxi remote add local http://localhost:5173
yuxi login --browser
```

Các lệnh đánh giá phải sử dụng hiện tại remote Trạng thái đăng nhập，Không được hỗ trợ trong `yuxi agent eval` Tải lên trực tiếp token。CI Môi trường trước tiên cũng phải thực hiện bước đăng nhập，Ví dụ：

```bash
yuxi login --api-key "$YUXI_API_KEY"
```

4. được đánh giá Agent đã tồn tại，và hiện tại CLI Người dùng đã đăng nhập có quyền truy cập vào đây Agent。Lệnh được sử dụng là Agent slug，Ví dụ `default-chatbot`。

## chuẩn bị Langfuse Dataset

Bộ dữ liệu đánh giá trước tiên phải được Langfuse sẵn sàng vào。CLI Không có khả năng tải lên được cung cấp，Tránh trộn lẫn trách nhiệm quản lý tập dữ liệu vào các lệnh chạy。

Dataset item của `input` Bạn nên sử dụng bất kỳ trường nào sau đây để mang văn bản nhiệm vụ：

```json
{"input": "Vui lòng sử dụng Python Hoàn thành nhiệm vụ và đưa ra câu trả lời cuối cùng：..."}
```

Cũng tương thích `query`、`question`、`prompt`。`expected_output` Có thể viết câu trả lời chuẩn，Theo dõi trong Langfuse UI hoặc evaluator được sử dụng trong。

## Chạy đánh giá

tải lên dataset sau，sử dụng dataset name chạy：

```bash
yuxi agent eval \
  --dataset-name yuxi-python-tasks-20260619-demo \
  --agent-slug default-chatbot \
  --experiment-name default-chatbot-python-tasks-20260619 \
  --max-concurrency 1 \
  --timeout-seconds 900
```

Quá trình thực hiện lệnh：

1. từ Langfuse đọc dataset。
2. cho mỗi dataset item Trích xuất văn bản nhiệm vụ。
3. gọi `POST /api/agent/eval/runs`。
4. Yuxi Việc tạo backend là bình thường conversation và AgentRun。
5. worker nhấn đúng Agent Nhiệm vụ thực hiện liên kết。
6. Giao diện bị chặn run Trở về trạng thái cuối cùng sau trạng thái cuối cùng assistant output。
7. CLI sẽ output viết lại Langfuse experiment item。

`--max-concurrency` kiểm soát Langfuse experiment runner số lượng đồng thời。phức tạp Agent Hoặc môi trường phát triển cục bộ được khuyến khích bắt đầu từ `1` bắt đầu，Tránh đồng thời áp đảo các dịch vụ mô hình、worker hoặc hộp cát。

## Xem kết quả

Sau khi việc đánh giá hoàn tất，trong Langfuse Bảng điều khiển mở tương ứng dataset，Bạn có thể thấy cái mới được tạo experiment run。mỗi item Lần này sẽ được lưu lại Yuxi Agent Đầu ra cuối cùng của。Yuxi Phần phụ trợ cũng sẽ ghi vào quá trình đánh giá `agent_evaluation` đánh dấu，Thuận tiện trong Langfuse traces Bộ lọc trung bình：

- `source=agent_evaluation`
- `evaluation_dataset_name=<dataset name>`
- `evaluation_dataset_item_id=<item id>`
- `evaluation_experiment_name=<experiment name>`

nếu không nhìn thấy experiment，Xác nhận đầu tiên CLI trong môi trường Langfuse key và dataset name Có đúng không?。nếu experiment Có ghi chép nhưng Yuxi trace Thiếu，Kiểm tra `api-dev` Liệu container có đọc cùng một nhóm hay không Langfuse Cấu hình。
