# ARCHITECTURE.md

Tài liệu này là bản đồ mã nguồn của Yuxi, được duy trì dựa trên đề xuất `ARCHITECTURE.md` của matklad: chỉ mô tả các ranh giới hệ thống tương đối ổn định, trách nhiệm của các thư mục và ràng buộc chéo, tránh đồng bộ hóa các chi tiết triển khai dễ thay đổi. Người mới tham gia nếu không chắc chắn "chức năng nào cần sửa ở đâu", trước tiên hãy đọc ở đây, sau đó sử dụng tìm kiếm biểu tượng để định vị loại, hàm hoặc định tuyến cụ thể.

## Tổng quan

Yuxi là một nền tảng cơ sở kiến thức hướng tới RAG, đồ thị kiến thức và quy trình làm việc đa tác tử (multi-agent). Người dùng cấu hình agent, cơ sở kiến thức, công cụ, kỹ năng (Skills), MCP và SubAgents trong giao diện Vue; frontend gọi FastAPI thông qua `/api`; backend service điều phối cơ sở dữ liệu, lưu trữ đối tượng, kho vector, cơ sở dữ liệu đồ thị, môi trường chạy LangGraph và hộp cát (sandbox); các agent chạy mất nhiều thời gian sẽ được giao cho worker xử lý bất đồng bộ và trả kết quả về frontend qua luồng sự kiện (event stream).

Cấu trúc phát triển và vận hành dựa trên `docker-compose.yml`. Các dịch vụ phát triển cốt lõi bao gồm:

- `web-dev`：Vue/Vite frontend, gắn kết `web/src` và tải lại nóng (hot reload).
- `api-dev`：FastAPI API service, gắn kết `backend/server` và `backend/package` và tải lại nóng.
- `worker-dev`：ARQ background task worker, xử lý các tác vụ bất đồng bộ như chạy agent.
- `sandbox-provisioner`：Cung cấp môi trường hộp cát để thực thi công cụ của agent.
- `postgres`、`redis`、`minio`、`milvus`、`graph`：Lần lượt lưu trữ siêu dữ liệu nghiệp vụ/cơ sở kiến thức, trạng thái hàng đợi và sự kiện chạy, lưu trữ đối tượng, tìm kiếm vector, đồ thị Neo4j.
- `mineru-*`、`paddlex`：Khả năng phân tích tài liệu/OCR được khởi động theo profile `all`.

## Bản đồ mã nguồn Backend

Backend được chia thành hai ranh giới cấp cao nhất: `backend/server` là lối vào ứng dụng Web và lớp điều phối HTTP, `backend/package/yuxi` là gói nghiệp vụ có thể tái sử dụng. Logic nghiệp vụ mới thường được ưu tiên đặt trong gói `yuxi`, lớp định tuyến (router) chỉ thực hiện phân tích yêu cầu, ngữ cảnh xác thực và đóng gói phản hồi.

- `server/main.py` tạo ứng dụng FastAPI, đăng ký middleware và hợp nhất tất cả các cổng nghiệp vụ vào `/api`.
- `server/routers` là ranh giới định tuyến HTTP. Các tuyến được chia theo lĩnh vực, tập trung đăng ký trong `server/routers/__init__.py`; các cổng cơ sở kiến thức, đồ thị, đánh giá và sơ đồ tư duy sẽ không được đăng ký trong `LITE_MODE`.
- `server/utils` đặt các khả năng chung của lớp Web, chẳng hạn như vòng đời, xác thực, nhật ký và hỗ trợ di chuyển dữ liệu.
- `server/worker_main.py` là lối vào worker, thiết lập worker thực tế đến từ `yuxi.services.run_worker`.

`backend/package/yuxi` là phần thân chính của backend:

- `agents` định nghĩa hệ thống agent LangGraph. `BaseAgent` là lớp cơ sở agent, `BaseContext` là ngữ cảnh cấu hình chạy; `buildin` chứa các agent tích hợp sẵn; `middlewares` chịu trách nhiệm gắn kết cơ sở kiến thức, kỹ năng, MCP, tệp đính kèm, cấu hình chạy và các khả năng khác vào runtime; `toolkits` chứa đăng ký công cụ và công cụ tích hợp sẵn; `backends` kết nối với các đầu thực thi/tài nguyên bên ngoài như hộp cát và kỹ năng.
- `services` là lớp use case, chịu trách nhiệm kết nối repositories, agents, knowledge, storage và các hệ thống bên ngoài. Các quy trình liên quan đến chat, hàng đợi chạy, chế độ xem tệp, kỹ năng, MCP, SubAgents, đánh giá đều nằm ở đây.
- `repositories` là ranh giới truy cập cơ sở dữ liệu, đóng gói các truy vấn SQLAlchemy cho đối tượng nghiệp vụ và siêu dữ liệu cơ sở kiến thức. Không cho phép router vượt qua repository để thao tác trực tiếp với model, trừ khi có mẫu cục bộ yêu cầu.
- `storage` đặt cơ sở hạ tầng lưu trữ. `storage/postgres` quản lý nhóm kết nối cho bảng nghiệp vụ, bảng cơ sở kiến thức và LangGraph checkpoint; `storage/minio` quản lý lưu trữ đối tượng.
- `knowledge` là lĩnh vực cơ sở kiến thức và đồ thị. `KnowledgeBaseManager` phân phối đến các triển khai cụ thể dựa trên loại cơ sở kiến thức; `implementations` đặt các triển khai cơ sở kiến thức như Milvus, Dify; `graphs` đặt dịch vụ xây dựng và tương thích đồ thị cơ sở kiến thức Milvus; `chunking` đặt chiến lược phân đoạn tài liệu.
- `knowledge/parser` là ranh giới phân tích tài liệu, đóng gói các triển khai phân tích như MinerU, PaddleX, RapidOCR, DeepSeek OCR.
- `models` đóng gói thích ứng cho chat, embedding, rerank; `config` duy trì cấu hình ứng dụng và thông tin mô hình tích hợp sẵn; `utils` đặt các công cụ chung xuyên lĩnh vực.

Mã nguồn kiểm thử nằm trong `backend/test`, được tổ chức theo các lớp `unit`, `integration`, `e2e`. Khi thêm mới hoặc sửa đổi hành vi backend, các bài kiểm thử nên nằm ở lớp có thể bao phủ rủi ro tốt nhất.

## Bản đồ mã nguồn Frontend

Frontend là ứng dụng Vue 3 + Vite, lối vào nghiệp vụ tập trung trong `web/src`.

- `main.js` gắn kết ứng dụng, `App.vue` là component gốc.
- `router` định nghĩa định tuyến trang và quyền chuyển hướng. Người dùng thông thường mặc định vào trang chat agent, các trang đồ thị, cơ sở kiến thức, dashboard, quản lý mở rộng có ràng buộc quyền quản trị viên.
- `apis` là vị trí duy nhất được khuyến nghị để đóng gói giao diện backend. Khi thêm cổng backend mới, hãy bổ sung đồng thời phương thức API tương ứng tại đây, tái sử dụng yêu cầu, xác thực và xử lý lỗi của `base.js`.
- `stores` đặt trạng thái Pinia, chẳng hạn như cấu hình người dùng, agent, theme, đồ thị và trạng thái nhiệm vụ.
- `views` là lối vào cấp trang, `components` là các khối giao diện có thể tái sử dụng; các trang phức tạp như chat agent, cơ sở kiến thức, đồ thị, quản lý mở rộng được kết hợp từ view và nhiều component.
- `composables` đặt logic chạy frontend có thể kết hợp, chẳng hạn như xử lý tin nhắn luồng, đăng ký sự kiện chạy, phê duyệt, nhập liệu thủ công và trạng thái thread agent.
- `utils` đặt các công cụ chung và logic chuyển đổi nhẹ của frontend; style tập trung trong `assets/css`, các quy tắc cơ bản và màu sắc ưu tiên sử dụng lại `base.css` và các file less hiện có.

## Luồng vận hành

Một cuộc hội thoại agent điển hình thường đi qua các ranh giới sau:

1. `AgentView` và các thành phần liên quan thu thập đầu vào, tệp đính kèm và cấu hình agent.
2. `web/src/apis` gọi các giao diện liên quan đến `/api/chat`.
3. `server/routers/chat_router.py` đi vào backend, ủy thác cho `yuxi.services.chat_service` hoặc `agent_run_service`.
4. Lớp dịch vụ đọc cấu hình hội thoại, cấu hình agent, công cụ, kỹ năng, cơ sở kiến thức, v.v., và tạo run nền khi cần thiết.
5. `worker-dev` thực thi agent LangGraph; middleware gắn kết các khả năng cơ sở kiến thức, kỹ năng, MCP, tệp đính kèm và hộp cát dựa trên ngữ cảnh.
6. Các sự kiện chạy được ghi vào Redis, trạng thái cuối cùng và bản ghi nghiệp vụ được ghi vào Postgres; tệp và sản phẩm đầu ra được lưu vào `saves`, MinIO hoặc thư mục dữ liệu người dùng hộp cát.
7. Frontend tiêu thụ các sự kiện chạy thông qua SSE/polling, hiển thị tin nhắn, cuộc gọi công cụ, nguồn tham chiếu, thẻ sản phẩm và bản xem trước tệp.

## Các bất biến kiến trúc

- Docker Compose là nguồn gốc thực tế cho môi trường phát triển. Khi phát triển, ưu tiên kiểm tra container, nhật ký và tải lại nóng, không mặc định yêu cầu chạy trực tiếp các dịch vụ trên máy chủ local.
- Lớp định tuyến HTTP nên giữ độ mỏng nhẹ; quy trình nghiệp vụ đặt trong `yuxi.services`, truy vấn lưu trữ đặt trong `yuxi.repositories`.
- Cuộc gọi API frontend nên tập trung trong `web/src/apis`, các thành phần không được tự ghép nối URL backend riêng lẻ.
- Khả năng của agent được kết hợp qua context, middleware, toolkits, backends; truy cập cơ sở kiến thức qua công cụ, không mã hóa cứng logic cơ sở kiến thức, MCP, kỹ năng hoặc hộp cát vào trang hoặc tuyến đơn lẻ.
- Chế độ LITE phải cho phép bỏ qua các khả năng phụ thuộc nặng như cơ sở kiến thức, đồ thị, đánh giá; hãy tôn trọng ranh giới này khi thêm giao diện mới hoặc logic khởi tạo.
- Đường dẫn ảo của hộp cát lấy `SANDBOX_VIRTUAL_PATH_PREFIX` làm ranh giới, không dùng lẫn lộn giữa đường dẫn người dùng thấy và đường dẫn thực tế trên máy chủ.
- Đầu vào đối mặt với người dùng hoặc hệ thống bên ngoài được xác thực tại ranh giới; giữa các dịch vụ nội bộ ưu tiên tin tưởng các ràng buộc hiện có của kiểu dữ liệu, lưu trữ và khung ứng dụng, tránh tích lũy mã phòng thủ cho các tình huống giả định.

## Các khía cạnh chéo

- **Cấu hình**: Biến môi trường đến từ Compose và `.env`, cấu hình bền vững của người dùng do `yuxi.config.app.Config` quản lý, cấu hình runtime đi vào LangGraph qua agent context.
- **Quyền hạn**: Bộ bảo vệ định tuyến frontend cung cấp chuyển hướng cấp trang, xác thực và kiểm tra quyền backend vẫn là ranh giới cuối cùng.
- **Trạng thái và lưu trữ**: Postgres lưu trữ siêu dữ liệu nghiệp vụ và cơ sở kiến thức, LangGraph checkpoint sử dụng nhóm kết nối độc lập hoặc SQLite fallback, Redis lưu trữ sự kiện chạy và tín hiệu hủy, MinIO/`saves` local/thư mục hộp cát lưu trữ tệp tin.
- **Xử lý tài liệu**: Tệp tải lên trước tiên đi vào ranh giới phân tích và phân đoạn, sau đó đi vào triển khai cơ sở kiến thức; plugin phân tích và triển khai cơ sở kiến thức phải giữ khả năng thay thế.
- **Giám sát và gỡ lỗi**: Trong giai đoạn phát triển, ưu tiên sử dụng `docker logs api-dev --tail 100`, nhật ký worker và các bài kiểm thử hiện có để định vị sự cố; logic liên quan đến Langfuse tập trung xung quanh lớp dịch vụ và cấu hình chạy agent.
