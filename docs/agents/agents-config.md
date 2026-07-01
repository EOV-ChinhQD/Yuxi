# Cấu hình đại lý

Yuxi Hệ thống tác nhân thông minh dựa trên LangGraph xây dựng。dành cho nhà phát triển，Điều quan trọng nhất là không hiểu riêng một trang hay một lĩnh vực nào，Nhưng hãy hiểu ba điều：

- Agent Làm thế nào để được xác định và khám phá
- Context Cách điều khiển giao diện cấu hình
- Context Làm thế nào để thâm nhập một lần Agent Chạy chu kỳ

Bài viết này tập trung vào ba phần này。

## 1. cấu trúc tổng thể

Phát triển đại lý xoay quanh bốn đối tượng cốt lõi：

- **`BaseAgent`**：thống nhất Agent trừu tượng，độ nét `get_graph()`、`context_schema`、`capabilities`
- **`BaseContext`**：Cấu hình Schema，Nó cũng là nguồn của các mục cấu hình front-end
- **Graph / Middleware**：LangGraph Đồ thị và chuỗi phần mềm trung gian，Xác định hành vi thời gian chạy
- **Agent**：Phiên bản tác nhân cấp 1 trong cơ sở dữ liệu，Lưu thông tin hiển thị、phụ trợ `backend_id`、quyền chia sẻ và `config_json.context`

Đã có các tác nhân được tích hợp sẵn trong kho để bạn có thể tham khảo trực tiếp.：

- `chatbot`：Tác nhân đàm thoại phổ quát，sử dụng `ChatBotContext` Cấu hình tác nhân phụ có thể gọi mở rộng
- `subagent`：Phần phụ trợ của đại lý phụ chuyên dụng，sử dụng `SubAgentContext`，được sử dụng để làm chủ Agent Vượt qua task Cuộc gọi công cụ

## 2. Agent tổ chức mã

Đó là khuyến khích để `backend/package/yuxi/agents` Tổ chức đại lý theo gói：

```text
backend/package/yuxi/agents/
└── my_agent/
    ├── __init__.py
    ├── context.py
    └── graph.py
```

Việc triển khai tối thiểu thường chứa：

- một sự thừa kế `BaseAgent` lớp học chính
- một `context_schema`
- một `get_graph()` nhận ra

Ví dụ：

```python
from yuxi.agents import BaseAgent, BaseContext, load_chat_model
from langchain.agents import create_agent


class MyAgent(BaseAgent):
    name = "đại lý của tôi"
    description = "Đại lý mẫu"
    context_schema = BaseContext

    async def get_graph(self, context=None, **kwargs):
        context = context or self.context_schema()
        graph = create_agent(
            model=load_chat_model(context.model),
            system_prompt=context.system_prompt,
            checkpointer=await self._get_checkpointer(),
        )
        return graph
```

## 3. Context là mô hình cấu hình，Không chỉ các tham số thời gian chạy

### 3.1 `BaseContext` vai trò

`BaseContext` được định nghĩa trong `backend/package/yuxi/agents/context.py`，Nó không phải là một lớp dữ liệu thông thường，Nó là cốt lõi của toàn bộ liên kết cấu hình tác nhân thông minh.：

- nó định nghĩa Agent Những trường nào có thể được cấu hình
- Nó xác định cách các trường này được hiển thị ở mặt trước
- Nó cũng được truyền vào trong thời gian chạy Graph và các đối tượng bối cảnh phần mềm trung gian

Các trường cơ bản hiện tại bao gồm：

| trường | chức năng |
| --- | --- |
| `system_prompt` | Lời nhắc hệ thống |
| `model` | mô hình bậc thầy |
| `tools` | Đã bật công cụ tích hợp |
| `knowledges` | Cơ sở kiến thức liên quan |
| `mcps` | đã bật MCP máy chủ |
| `skills` | hiệp hội Skills |
| `summary_threshold` | Ngưỡng kích hoạt tóm tắt |
| `summary_prompt` | Từ nhắc nhở sử dụng khi kích hoạt tóm tắt |
| `summary_keep_messages` | Số lượng tin nhắn gần đây được giữ lại sau khi thông báo |
| `summary_tool_result_token_limit` | Giới hạn xem trước kết quả của công cụ giai đoạn tóm tắt |
| `max_execution_steps` | Số bước thực hiện tối đa trong một lần chạy |
| `thread_id` / `uid` | mã định danh thời gian chạy，Không được hiển thị dưới dạng mục cấu hình trang |

`tools`、`knowledges`、`mcps`、`skills` Khi không được định cấu hình rõ ràng, tất cả tài nguyên mà người dùng hiện tại có thể truy cập sẽ được bật theo mặc định.。

`ChatBotContext` trong `BaseContext` tăng ở trên `subagents` trường，Cho biết nội dung chính hiện tại Agent Các đại lý con được phép gọi。`subagents` Khi không được định cấu hình rõ ràng hoặc khi danh sách trống được lưu, tất cả các tác nhân phụ hiển thị cho người dùng hiện tại sẽ được bật theo mặc định.；Sau khi lựa chọn rõ ràng, nó sẽ được lọc dưới dạng danh sách cho phép.。

`SubAgentContext` trong `BaseContext` tăng ở trên `parent_thread_id`、`file_thread_id`、`skills_thread_id` với `is_subagent_runtime` Chờ để ẩn các trường trạng thái đang chạy，Không bao gồm `subagents`，Do đó, tác nhân phụ không thể tiếp tục định cấu hình lớp tác nhân phụ tiếp theo.。

### 3.2 Cách thay đổi các mục cấu hình giao diện người dùng từ Context tạo ra

`BaseContext.get_configurable_items()` Sẽ duyệt qua các định nghĩa trường，đặt loại trường、Giá trị mặc định、Mô tả、Siêu dữ liệu mẫu được tổ chức thành `configurable_items`。

sau đó：

1. `BaseAgent.get_info()` bị lộ `configurable_items`
2. Đọc front-end Agent Chi tiết
3. `AgentRuntimeConfigForm` nhấn `kind` Hiển thị các điều khiển khác nhau

Tức là nói，`AgentRuntimeConfigForm` Thay vì viết tay vào mọi lĩnh vực，nhưng tiêu dùng trực tiếp `context_schema` Mô tả cấu hình đã tạo。

Đây là lý do tại sao：

- Thêm một cái mới Context trường，Thường ảnh hưởng trực tiếp đến sidebar
- lĩnh vực `metadata` Thông tin sẽ ảnh hưởng trực tiếp đến cách nó được hiển thị

### 3.3 Mẫu cấu hình với Agent mối quan hệ liên kết

Phần này là quan trọng nhất。

ở mặt trước：

- `AgentRuntimeConfigForm.vue` Chịu trách nhiệm hiển thị các biểu mẫu cấu hình
- `agentStore` Khi tải cấu hình，đọc `config_json.context`
- Nếu một số trường không được cấu hình，Sẽ sử dụng `configurable_items` Hoàn thành giá trị mặc định trong
- khi lưu，Giao diện người dùng ghi lại biểu mẫu hiện tại `config_json: { context: agentConfig }`

Do đó mối quan hệ thực sự là：

```text
context_schema
  -> get_configurable_items()
  -> Agent detail API Trở lại configurable_items
  -> AgentRuntimeConfigForm Kết xuất biểu mẫu
  -> Sau khi người dùng chỉnh sửa, lưu vào config_json.context
```

Hai điểm cần đặc biệt chú ý ở đây：

- **Cấu trúc hiển thị thanh bên xuất phát từ `context_schema`**
- **Các giá trị phiên bản cấu hình đến từ cơ sở dữ liệu `config_json.context`**

Người trước quyết định“Những gì có thể được ghép nối với nó?、Cách hiển thị”，Người sau quyết định“Điều gì thực sự được chọn cho cấu hình hiện tại?”。

### 3.4 Tùy chỉnh Context Phương pháp khuyến nghị

Nếu một tác nhân có cấu hình bổ sung，Không thêm một nhóm biểu mẫu riêng biệt vào giao diện người dùng，Thay vào đó, hãy mở rộng trực tiếp Context：

```python
from dataclasses import dataclass, field
from yuxi.agents import BaseContext


@dataclass(kw_only=True)
class MyAgentContext(BaseContext):
    custom_mode: str = field(
        default="default",
        metadata={
            "name": "chế độ hoạt động",
            "description": "Kiểm soát hành vi tùy chỉnh của đại lý",
            "options": ["default", "strict"],
        },
    )
```

sau đó vào Agent Tuyên bố trong：

```python
class MyAgent(BaseAgent):
    context_schema = MyAgentContext
```

Điều này cũng sẽ ảnh hưởng：

- Cấu trúc cấu hình mà chương trình phụ trợ có thể nhận được
- Nội dung hiển thị thanh bên cấu hình giao diện người dùng
- thời gian chạy `context` Các trường có thể truy cập

## 4. Context làm thế nào để thâm nhập Agent chu kỳ hoạt động

Context Giá trị của“Trang cấu hình”。Nó chạy qua toàn bộ liên kết từ tải cấu hình đến thực thi thực tế。

### 4.1 Giai đoạn tải cấu hình

Khi có yêu cầu trò chuyện đến phần phụ trợ，Dịch vụ đầu tiên sẽ phân tích yêu cầu `agent_id` hoặc bị ràng buộc bởi chủ đề Agent，Sau đó tải cấu hình tương ứng。

Quá trình chính hiện tại là ở `chat_service.py` trong：

1. Chủ đề mới đã được thông qua `agent_id` Tìm người dùng có thể truy cập Agent
2. Một chủ đề đã trôi qua `thread_id` đọc `Conversation.agent_id`，và từ chối chuyển đổi nhanh chóng Agent
3. lấy ra Agent của `config_json.context`
4. với `uid`、`thread_id` Được kết hợp vào đầu vào thời gian chạy

Tức là nói，thời gian chạy Context Nguồn cơ bản không phải là trạng thái tạm thời của giao diện người dùng，Nó được lưu trong cơ sở dữ liệu Agent。

Ngoài ra，Không gian làm việc của người dùng được tạo theo mặc định `agents/AGENTS.md`。Khi nào Agent Khi bắt đầu thực hiện，Phần phụ trợ sẽ đọc tệp này trong không gian làm việc của người dùng hiện tại，và nối thêm nội dung của nó vào `system_prompt`，được sử dụng để bổ sung cho người dùng Agent chỉ thị thường trực hoặc cam kết về không gian làm việc。Tệp này thuộc về không gian làm việc chung ở cấp độ người dùng，Nội dung sẽ thay đổi `uid` và phạm vi luồng hiện đang chạy được ánh xạ tới đường dẫn không gian làm việc thời gian chạy；Tập tin không tồn tại、Nó sẽ không ảnh hưởng nếu nó trống hoặc không thể đọc được. Agent bắt đầu，Số lần đọc tối đa cho một nội dung được chèn 64 KiB，Phần thừa sẽ bị cắt bớt và thêm lời nhắc.。

Cấu trúc từ nhắc gộp có thể hiểu là：

```text
Agent.config_json.context.system_prompt
  + Không gian làm việc của người dùng agents/AGENTS.md nội dung
  + Phần lời nhắc hệ thống mà phần mềm trung gian tiếp tục thêm vào trong thời gian chạy
```

Vì thế，`agents/AGENTS.md` Các ràng buộc ổn định phù hợp để đặt kích thước người dùng，Không phù hợp để đặt yêu cầu nhiệm vụ một lần；Yêu cầu một lần vẫn phải được viết trực tiếp trong cuộc trò chuyện hiện tại。

### 4.2 Context giai đoạn khởi tạo

`BaseAgent` sẽ được tạo trước khi chạy `context_schema()` Ví dụ，và vượt qua `update_from_dict()` Chèn giá trị cấu hình。

Sau khi bước này hoàn tất，Context Nó thực sự trở thành một đối tượng thời gian chạy。

Nó có thể được hiểu là：

```text
config_json.context + runtime ids -> context_schema instance
```

### 4.3 Graph giai đoạn xây dựng

`get_graph(context=context)` sẽ nhận được điều này Context。

có tích hợp sẵn `chatbot` Ví dụ，Context sẽ tham gia trực tiếp：

- Lựa chọn mô hình chính：`context.model`
- Nối từ nhắc nhở hệ thống：`context.system_prompt`
- Danh sách các đại lý phụ có thể gọi：`context.subagents`
- ngưỡng tóm tắt：`context.summary_threshold`

Vì thế Graph không và Context tách rời。Ngược lại，Graph Bản thân cấu trúc phụ thuộc vào Context。Bình thường Agent sau khi bình thường hóa `context.subagents` Sẽ được gắn kết khi nó không trống Yuxi của task middleware；`SubAgentBackend` Ẩn chính nó và xóa nó `subagents` trường，Do đó đại lý phụ sẽ không tiếp tục gọi đại lý phụ。

### 4.4 Graph Các giai đoạn xây dựng và chạy phần mềm trung gian

`get_graph()` tạo ra LangGraph sẽ được gọi đầu tiên `prepare_agent_runtime_context`，Lọc lại các trường tài nguyên với người dùng hiện tại，và lấy được các trường thời gian chạy：

- `_visible_knowledge_bases`：Các đối tượng cơ sở kiến thức thực sự có thể được truy vấn trong phiên hiện tại
- `_prompt_skills`：Cần tiêm những lời nhắc nhở Skill đóng cửa
- `_readable_skills`：`/home/gem/skills` và hộp cát có thể đọc được Skill đóng cửa

sau đó Graph Bản dựng sẽ sử dụng trực tiếp cái này Context：

- `load_chat_model(context.model)` Chọn mô hình chính
- `build_prompt_with_context(context)` Tạo các từ nhắc hệ thống
- `resolve_configured_runtime_tools(context)` Lắp ráp các công cụ cài sẵn đã được cấu hình và MCP Công cụ
- `KnowledgeBaseMiddleware` Theo `_visible_knowledge_bases` Trình bày các công cụ cơ sở tri thức
- `SkillsMiddleware` Theo `_prompt_skills` tiêm Skill Phần nhắc nhở，Và trong Skill Sau khi được kích hoạt, hãy gắn các công cụ và MCP phụ thuộc vào
- `save_attachments_to_fs` Chuyển đổi phần đính kèm của luồng thành gợi ý tệp có thể đọc được trong thời gian chạy

Quyền truy cập hệ thống tệp và hộp cát cũng đọc các trường thời gian chạy này：

- Bình thường Agent Theo mặc định, hiện tại `thread_id` dưới dạng tập tin với Skills Phạm vi
- Sử dụng chất phụ child `thread_id` làm checkpoint，`file_thread_id` Trỏ tới phiên cha mẹ uploads/outputs，`skills_thread_id` Chỉ vào chính tác nhân phụ Skills Phạm vi
- Vượt qua `_readable_skills` quyết định `/home/gem/skills` Phạm vi có thể đọc được của

Vì vậy Context Cả hai cấu hình đầu vào，Ngoài ra Graph Bối cảnh tài nguyên thời gian chạy được sắp xếp trước khi tạo。

### 4.5 Hệ thống tập tin và Viewer sân khấu

Dịch vụ hệ thống tệp không phát minh lại cấu trúc cấu hình，Nhưng một lần nữa từ `config_json.context` khôi phục lại runtime context，dùng cho：

- Xác định chủ đề hiện tại Agent có thể nhìn thấy Skills
- cấu trúc Agent quan điểm của composite backend
- cấu trúc Viewer Xem hiển thị hệ thống tập tin

Đây là lý do tại sao Context Không chỉ là một phần của liên kết trò chuyện，nó cũng ảnh hưởng：

- Agent công cụ tập tin
- Viewer Trình duyệt tập tin
- Skills khả năng hiển thị
- Ngữ nghĩa gắn kết hộp cát

### 4.6 Giai đoạn phục hồi

trong `resume` đang trong quá trình，Hệ thống cũng sẽ bị ràng buộc thông qua các chủ đề Agent Tái cơ cấu Context，tiếp tục thực hiện Graph。

Tức là nói，Cho dù đó là：

- cuộc trò chuyện đầu tiên
- Phục hồi ngắt
- Chế độ xem hệ thống tập tin

Tất cả đều phụ thuộc vào cùng Context Nguồn cấu hình。

## 5. `capabilities` vai trò

`capabilities` Được sử dụng để khai báo giao diện người dùng trực tiếp từ Agent Công tắc khả năng phán đoán siêu dữ liệu tĩnh，Kiểm soát mục tải lên、Bảng điều khiển tập tin, v.v. đã được sửa UI，không tương đương với Context，Nó cũng không thích hợp để biểu diễn các trạng thái chỉ xảy ra trong quá trình hoạt động.。

Ví dụ：

```python
class MyAgent(BaseAgent):
    capabilities = ["file_upload", "files"]
```

Các khả năng phổ biến hiện tại bao gồm：

| capability | Mô tả |
| --- | --- |
| `file_upload` | Kích hoạt cổng tải lên |
| `files` | Kích hoạt bảng tập tin |

thích todo Loại thông tin trạng thái đang chạy này，Không nên đặt lại `capabilities`。Yuxi Hiện nay nó sẽ được gửi trực tiếp từ LangGraph state chiết xuất từ ​​ `agent_state`，Giao diện người dùng hiển thị mục trạng thái bình thường sau khi tạo cuộc trò chuyện.，và hiển thị trong bảng trạng thái `todos`、`files`、`artifacts`、`subagent_runs` Chờ nội dung thời gian chạy。

Những gì nó giải quyết là“Agent Nó hỗ trợ lối vào cố định nào?”，thay vì“Trạng thái nào hiện được tạo trong thời gian chạy”。

## 6. Đề xuất phát triển

### 6.1 Ưu tiên thay đổi khi thêm cấu hình mới Context

Nếu một mục cấu hình ảnh hưởng Agent hành vi，Hãy ưu tiên nó `context_schema` trường，Thay vì giao diện người dùng duy trì trạng thái riêng biệt。

### 6.2 đặt Graph Logic riêng biệt và logic cấu hình

Các phương pháp được đề xuất：

- `context.py` Xác định mô hình cấu hình
- `graph.py` Xây dựng với các cấu hình này Graph

Bằng cách này, mối quan hệ liên kết giữa mặt trước và mặt sau sẽ rõ ràng hơn rất nhiều.。

### 6.3 đặt“Nguồn cấu hình”và“trạng thái thời gian chạy”phân biệt

Nên luôn phân biệt giữa hai cấp độ ngữ nghĩa：

- `config_json.context`：Nguồn cấu hình liên tục
- `runtime.context`：đối tượng đang chạy thực tế，Có thể được bổ sung hoặc sửa đổi thêm bởi phần mềm trung gian

## 7. Chủ đề liên quan

- [Hệ thống công cụ](./tools-system.md)
- [phần mềm trung gian](./middleware.md)
- [Kiến trúc và thiết kế hộp cát](./sandbox-architecture.md)
- [MCP Tích hợp](./mcp-integration.md)
- [Skills quản lý](./skills-management.md)
- [chất phụ](./subagents-management.md)
- [Langfuse Tích hợp](../advanced/langfuse-integration.md)
