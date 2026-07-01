# MCP Tích hợp

MCP（Model Context Protocol）Đó là một cách quan trọng để mở rộng khả năng của các tác nhân thông minh.。Hệ thống hỗ trợ cấu hình động thông qua giao diện quản lý MCP máy chủ，Không cần sửa đổi mã。

Tích hợp sẵn MCP Máy chủ sử dụng mã làm nguồn sự thật：Các mục còn thiếu sẽ được tự động điền khi hệ thống khởi động.，Và ghi đè định nghĩa cơ sở dữ liệu bằng các trường hiển thị và kết nối mới nhất trong mã；liệu“Đã thêm”và danh sách bị vô hiệu hóa ở cấp công cụ vẫn giữ trạng thái cơ sở dữ liệu。

## Các giao thức truyền tải được hỗ trợ

| thỏa thuận | Mô tả | Các tình huống áp dụng |
|------|------|----------|
| Streamable HTTP | phát trực tuyến HTTP kết nối | từ xa MCP dịch vụ |
| SSE | Server-Sent Events | Tiêu chuẩn HTTP kết nối dài |
| Stdio | đầu vào và đầu ra tiêu chuẩn | quy trình cục bộ |

## Ví dụ cấu hình

### từ xa MCP dịch vụ

```json
{
    "name": "custom-remote-mcp",
    "transport": "streamable_http",
    "url": "https://example.com/mcp"
}
```

### địa phương Python quá trình

```json
{
    "name": "mysql-mcp-server",
    "transport": "stdio",
    "command": "uvx",
    "args": ["mysql_mcp_server"],
    "env": {
        "MYSQL_HOST": "localhost",
        "MYSQL_DATABASE": "your_database"
    }
}
```

## Quản lý máy chủ

Sử dụng giao diện quản lý“thêm / Xóa”Quản lý ngữ nghĩa MCP máy chủ：

- Đã thêm：`enabled=true`，sẽ được tải vào bộ đệm thời gian chạy và có sẵn Agent sử dụng
- Có thể được thêm vào：`enabled=false`，Các bản ghi được giữ lại nhưng không được đưa vào thời gian chạy

## Quản lý công cụ

MCP Công cụ hỗ trợ điều khiển chi tiết：Quản trị viên có thể bật hoặc tắt riêng một MCP Các công cụ cụ thể dưới máy chủ，Thực hiện quản lý quyền tinh tế。
