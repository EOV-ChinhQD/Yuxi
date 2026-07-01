# chất phụ

Yuxi Đại lý phụ là Agent-backed hình thức：nó vẫn còn `agents` cấp một trong bảng Agent，Chỉ với thêm `is_subagent=true` đánh dấu，và sử dụng một chương trình phụ trợ chuyên dụng `SubAgentBackend`。Đại lý phụ không còn có lối vào tạo độc lập、Bảng độc lập hoặc giao diện quản lý độc lập。

## Quan điểm của người dùng

### Đại lý phụ có thể giải quyết những vấn đề gì?

Khi nhiệm vụ phức tạp、Khi cần phân công lao động，Chúa ơi Agent có thể vượt qua `task` Công cụ gán một nhiệm vụ con cho một tác nhân phụ。Ví dụ：

- Nhiệm vụ chung chung：Để nó ở chế độ tích hợp sẵn `general-purpose` chất phụ，Phân tích quy trình bằng cấu hình chạy mặc định、tổ chức、Viết hoặc xử lý tài liệu。
- nhiệm vụ nghiên cứu：Tập trung vào việc truy xuất và tổ chức dữ liệu。
- xem xét nhiệm vụ phụ：Xem xét dự thảo về cấu trúc và chất lượng。
- Nhiệm vụ phụ của miền：Sử dụng mô hình được chỉ định、Công cụ、cơ sở tri thức hoặc Skills Giải quyết các vấn đề về tên miền cụ thể。

### Nơi tạo và chỉnh sửa

Đại lý phụ và thông thường Agent Sử dụng cùng một cổng quản lý：Nhập cấu hình mô hình“đại lý”Trang quản lý，Bấm để thêm đại lý mới，và chọn loại phụ trợ `SubAgentBackend`。

Tạo và chỉnh sửa các quy trình với thông thường Agent Hãy nhất quán：

- hiển thị thông tin、Quyền chia sẻ、Các từ nhắc hệ thống và cấu hình đang chạy được lưu trong cùng một bản sao Agent Cấu hình。
- người mẫu、Công cụ、cơ sở tri thức、MCP và Skills Vẫn vượt qua Agent runtime config Cấu hình biểu mẫu。
- Đại lý phụ sẽ không xuất hiện trên trang trò chuyện Agent Danh sách chuyển đổi nhanh。
- Các đại lý phụ không còn có thể định cấu hình hoặc gọi các đại lý phụ khác。

### Làm sao để Chúa Agent Gọi đại lý phụ

Chúa ơi Agent sẽ vượt qua runtime config của“chất phụ”Trường được xác định `task` Phạm vi của các tác nhân phụ mà công cụ có thể gọi。

`subagents` Trường đại diện cho mục chính hiện tại Agent danh sách cho phép：

- Khi không có lựa chọn hoặc danh sách trống nào được lưu，Theo mặc định, cho phép tất cả các đại lý phụ hiển thị với người dùng hiện tại，Bao gồm tích hợp `general-purpose`。
- Sau khi lựa chọn rõ ràng，Chỉ cho phép cuộc gọi đến các đại lý phụ được chọn。
- Chỉ những cuộc gọi mà người dùng hiện tại có thể truy cập được và `is_subagent=true` của Agent。
- Mỗi tác nhân phụ sử dụng chính nó `config_json.context`，bao gồm các mô hình、Công cụ、cơ sở tri thức、MCP、Skills và các từ nhắc nhở của hệ thống。

Tích hợp sẵn `general-purpose` của `config_json.context` trống rỗng，Khi chạy nhấn `SubAgentContext` và `BaseContext` Mô hình phân tích giá trị mặc định、Công cụ、cơ sở tri thức、MCP với Skills。

## Quan điểm của nhà phát triển

### mô hình dữ liệu

Tái sử dụng chất phụ `agents` bàn，Các lĩnh vực cốt lõi bao gồm：

| trường | Mô tả |
|------|------|
| `backend_id` | Đại lý phụ sử dụng cố định `SubAgentBackend` |
| `is_subagent` | Thẻ đại lý phụ，`SubAgentBackend` Phải tương ứng `true` |
| `config_json.context` | Cấu hình chạy riêng của tác nhân phụ |
| `share_config` | Quyền hiển thị và quản lý，Kế thừa Agent Mô hình chia sẻ |

Phần phụ trợ sẽ xác minh `backend_id` với `is_subagent` nhất quán：Bình thường Agent Không thể giả vờ là một đại lý phụ，`SubAgentBackend` Cũng không thể coi nó là bình thường Agent Bảo quản hình dạng。Đại lý phụ không thể được đặt làm mặc định Agent。

### API với ngữ nghĩa danh sách

Đại lý phụ kế thừa `/api/agent` CRUD：

- `GET /api/agent` Theo mặc định, chỉ có thể trò chuyện bình thường Agent。
- `GET /api/agent?include_subagents=true` Điền đầy đủ thông tin cần thiết để quay lại trang quản lý Agent danh sách。
- Tạo hoặc cập nhật `SubAgentBackend` thời gian，payload có thể mang hoặc lấy được `is_subagent=true`。
- Chi tiết、Cập nhật và xóa vẫn trải qua quá trình tương tự Agent Giao diện quản lý，và sử dụng lại các bộ lọc quyền hiện có。

nền độc lập cũ SubAgent Liên kết quản lý đã bị xóa，Không còn duy trì trạng thái bắt đầu và dừng riêng biệt、khởi tạo tích hợp hoặc spec bộ nhớ đệm。

### Chuỗi cuộc gọi thời gian chạy

Chúa ơi Agent Khi soạn một bức tranh，Sẽ đặt nó lên hàng đầu `context.subagents` Được chuẩn hóa thành danh sách được phép hiển thị cho người dùng hiện tại；Cho phép gắn kết khi danh sách không trống Yuxi của task middleware。middleware Một danh sách các tác nhân phụ được phép sẽ được đưa vào gợi ý mô hình，và phơi bày một `task` Công cụ。

Các thông số của công cụ là：

```python
class TaskToolSchema(BaseModel):
    description: str
    subagent_type: str
    thread_id: str | None = None
```

`thread_id` là một chủ đề tác nhân phụ tùy chọn ID。Nhiệm vụ mới không cần phải điền；Nếu bạn muốn tiếp tục nhiệm vụ đại lý phụ tương tự，nên sử dụng cuối cùng `task` trong kết quả công cụ `Chủ đề đại lý phụ ID`。

Các quy trình chính trong quá trình thực hiện：

1. từ cha Agent của `context.subagents` Đọc các tác nhân phụ được phép slug；Không được định cấu hình rõ ràng hoặc danh sách trống sẽ được mở rộng cho tất cả các đại lý phụ hiển thị cho người dùng hiện tại.。
2. sử dụng `AgentRepository` Đang tải được hiển thị cho người dùng hiện tại và `is_subagent=true` của Agent。
3. Một nhiệm vụ mới sẽ được tạo cho cuộc gọi này child checkpoint thread id，Ví dụ `<parent_thread_id>_sub_<slug>_<uuid8>`；Nhiệm vụ tiếp tục sẽ xác minh và sử dụng lại dữ liệu đến `thread_id`。
4. Sử dụng của đại lý phụ `SubAgentContext` và `config_json.context` xây dựng thực tế Agent graph。
5. Sau khi cuộc gọi kết thúc，chủ đề đại lý phụ ID và cuối cùng assistant văn bản như `task` Kết quả công cụ được trả về chính Agent。

`SubAgentBackend` Tái sử dụng bình thường Agent Quá trình chuẩn hóa tài nguyên thời gian chạy，nhưng sẽ không gắn kết task middleware；nó `subagents` Các trường bị ẩn và trống theo mặc định，Do đó, các cuộc gọi tác nhân phụ lồng nhau không được hình thành。

### Hệ thống tập tin và phạm vi hộp cát

Đại lý phụ và chủ Agent Sử dụng phạm vi phân chia khi chia sẻ hệ thống tệp：

| con đường/Phạm vi | Bình thường Agent | chất phụ |
|------|------|------|
| LangGraph checkpoint | hiện tại `thread_id` | child `thread_id` |
| `/home/gem/user-data/workspace` | hiện tại `uid` không gian làm việc chung | giống nhau `uid` không gian làm việc chung |
| `/home/gem/user-data/uploads` | Phạm vi tệp phiên hiện tại | phiên họp phụ huynh `file_thread_id` |
| `/home/gem/user-data/outputs` | Phạm vi tệp phiên hiện tại | phiên họp phụ huynh `file_thread_id` |
| `/home/gem/skills` | hiện tại Agent của Skills Phạm vi | của đại lý phụ `skills_thread_id` |

Điều này đảm bảo rằng tác nhân con có thể đọc phiên tải lên của cha mẹ、Các tạo phẩm cũng được trả về phiên cha mẹ artifacts trong，Đồng thời, đại lý phụ Skills Sẽ không làm ô uế Chúa Agent。

## Câu hỏi thường gặp

### Tại sao các đại lý phụ được tạo ra?，Chúa ơi Agent Vẫn không gọi？

Chúa ơi Agent Chỉ các tác nhân phụ mà người dùng hiện tại có thể truy cập mới được gọi。Nếu chính Agent Danh sách cho phép đại lý phụ được lưu rõ ràng，Các đại lý phụ mới cần được thêm vào danh sách này；Không được định cấu hình rõ ràng hoặc danh sách trống sẽ sử dụng tất cả các tác nhân phụ hiển thị cho người dùng hiện tại。

### tại sao lại trò chuyện Agent Đại lý phụ không thể được nhìn thấy trong danh sách？

Đây là hành vi được mong đợi。Đại lý con là chủ Agent Cấu hình phụ trợ được gọi là，Không trực tiếp vào cuộc trò chuyện Agent；Trang quản trị sử dụng danh sách các đại lý con。

### Tác nhân con có thể kế thừa cái chính không? Agent mô hình hoặc công cụ？

Tác nhân phụ sử dụng chính nó Agent Cấu hình。Khi thực sự cần sự nhất quán，Mô hình tương tự phải được chọn rõ ràng trong cấu hình đại lý phụ、công cụ hoặc Skills；Thời gian chạy chỉ kế thừa phạm vi phiên cha mẹ cần thiết，Ví dụ uploads/outputs。
