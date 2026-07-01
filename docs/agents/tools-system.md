# Hệ thống công cụ

Yuxi Hệ thống công cụ hoạt động dựa trên cơ chế đăng ký，Hỗ trợ lắp ráp động nhiều loại công cụ。

## Cơ chế đăng ký công cụ

Yuxi Hệ thống công cụ thông qua `@tool` Cơ chế đăng ký trang trí，Cốt lõi nằm ở `backend/package/yuxi/agents/toolkits/registry.py`。

### @tool Người trang trí

```python
from yuxi.agents.toolkits.registry import tool

@tool(category="buildin", tags=["Ví dụ"], display_name="Công cụ mẫu")
def example_tool(text: str) -> str:
    """Công cụ mẫu：Trả về văn bản đã xử lý"""
    ...
```

Thông số trang trí：
- **category**: Phân loại công cụ，để phân nhóm（`buildin`、`mysql`、`debug`）
- **tags**: danh sách thẻ，Dành cho màn hình phía trước
- **display_name**: tên hiển thị（tên cho mọi người xem）
- **icon**: Tên biểu tượng（Tùy chọn）

### tự động phát hiện

nhập khẩu `toolkits` Đăng ký sẽ được kích hoạt tự động khi gói được：

```python
from yuxi.agents.toolkits import buildin, mysql  # cò súng @tool Thi công trang trí
```

`toolkits/__init__.py` Bao gồm trong `buildin`、`mysql`、`debug` Nhập khẩu mô-đun，Khi các mô-đun này được tải, chúng sẽ tự động đăng ký tất cả các băng tần `@tool` Chức năng trang trí。

## Phân loại công cụ

### Công cụ tích hợp (buildin)

| Công cụ | Mô tả |
|------|------|
| `ask_user_question` | Đặt câu hỏi tương tác cho người dùng |
| `present_artifacts` | hiển thị Agent hộp cát outputs Tệp sản phẩm trong thư mục |
| `install_skill` | từ đường dẫn hộp cát hoặc Git Nguồn cài đặt người dùng hiện tại riêng tư Skill，và kích hoạt phiên đại lý chính hiện tại；Đại lý phụ bị vô hiệu hóa |
| `tavily_search` | Tavily tìm kiếm trên mạng（Cần cấu hình `TAVILY_API_KEY`） |

Qwen-Image Khả năng tạo đã được chuyển sang tích hợp sẵn Skill `image-gen`。Gọi mẫu và tải hình ảnh đều có tại Agent Thực hiện trong hộp cát，Hình ảnh được tạo sẽ được lưu vào `/home/gem/user-data/outputs/`，vượt qua lần nữa `present_artifacts` hiển thị。

### MySQL Công cụ (mysql)

| Công cụ | Mô tả |
|------|------|
| `mysql_list_tables` | Liệt kê tất cả các bảng trong cơ sở dữ liệu |
| `mysql_describe_table` | Nhận thông tin cấu trúc bảng |
| `mysql_query` | Thực hiện chỉ đọc SQL Truy vấn |

### Công cụ cơ sở tri thức (kbs)

Sử dụng các công cụ cơ sở tri thức `@tool(category="knowledge")` Đăng ký，và thông qua tích hợp sẵn `knowledge-base` Skill của `tool_dependencies` Tải theo yêu cầu。`get_common_kb_tools()` Vẫn có sẵn để truy cập trực tiếp vào danh sách công cụ đầy đủ：

```python
from yuxi.agents.toolkits.kbs import get_common_kb_tools

kb_tools = get_common_kb_tools()
# Trở lại: [list_kbs, get_mindmap, query_kb, find_kb_document, open_kb_document]
```

| Công cụ | Mô tả |
|------|------|
| `list_kbs` | Liệt kê các cơ sở tri thức mà người dùng có thể truy cập |
| `get_mindmap` | Có được cấu trúc bản đồ tư duy của cơ sở tri thức |
| `query_kb` | Tìm kiếm nội dung trong cơ sở kiến thức được chỉ định，Cấu trúc trả về `resource_id`（Đó là `kb_id`）/`file_id`/`chunk` |
| `find_kb_document` | Xác định vị trí nội dung trong các tệp đã biết theo từ khóa hoặc biểu thức thông thường |
| `open_kb_document` | nhấn `file_id` Mở tài liệu cơ sở kiến thức theo từng phần（cửa sổ mặc định 1800 được rồi） |

## Lắp ráp công cụ

Dụng cụ được lắp ráp tại Graph Giai đoạn sáng tạo đã hoàn thành。Tích hợp sẵn Agent sẽ được gọi đầu tiên `prepare_agent_runtime_context` Lọc tài nguyên có sẵn cho người dùng hiện tại，gọi lại `resolve_configured_runtime_tools(context)` Tải các công cụ được cấu hình：

1. **công cụ cơ bản**：từ `context.tools` Lọc theo tên
2. **MCP Công cụ**：Theo `context.mcps` Tải MCP Công cụ máy chủ
3. **Skill Công cụ phụ thuộc**：bởi `SkillsMiddleware` trong Skill Thêm khi cần thiết sau khi kích hoạt，bao gồm `knowledge-base` Các công cụ cơ sở kiến thức đi kèm

```python
from yuxi.agents.context import prepare_agent_runtime_context
from yuxi.agents.toolkits.service import resolve_configured_runtime_tools

context = await prepare_agent_runtime_context(context, user=current_user, db=db)
tools = await resolve_configured_runtime_tools(context)
```

## Skills Tích hợp

Skills và công cụ là hai cơ chế mở rộng khác nhau。Công cụ là việc triển khai chức năng cụ thể，Và Skills chứa các từ gợi ý、Gói kỹ năng hoàn chỉnh cho các phụ thuộc và siêu dữ liệu của công cụ。Vượt qua `context.skills` Cấu hình Skills thời gian，Tệp kỹ năng tương ứng sẽ được gắn vào hộp cát `/home/gem/skills/<slug>/...`，Tác nhân có thể đọc bằng SKILL.md để học cách sử dụng những kỹ năng này。

Giới thiệu Skills Cơ chế chi tiết của，Xem [Skills quản lý](./skills-management.md)。
