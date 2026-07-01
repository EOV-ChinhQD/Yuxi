# API Key Tích hợp bên ngoài

Yuxi Nền tảng cung cấp API Key Cơ chế xác thực，Cho phép các hệ thống bên ngoài gọi giao diện đối thoại tổng đài viên mà không yêu cầu người dùng đăng nhập。Tài liệu này giới thiệu chi tiết API Key Cách sử dụng、Phương thức gọi giao diện và biện pháp phòng ngừa bảo mật。

## API Key Tổng quan

API Key là một chuỗi khóa được sử dụng để xác thực，Hệ thống bên ngoài có thể được truy cập bằng cách mang thông tin xác thực trong tiêu đề yêu cầu Yuxi giao diện đàm thoại。So với phương thức đăng nhập tên người dùng và mật khẩu truyền thống，API Key Phù hợp hơn với các tình huống gọi tự động giữa các hệ thống。Yuxi của API Key để `yxkey_` làm tiền tố，chiều dài là 54 nhân vật，nhận nuôi SHA-256 Lưu trữ băm，Đảm bảo rằng khóa đó không được lưu trong cơ sở dữ liệu ở dạng văn bản rõ ràng。Hệ thống sẽ ghi lại từng API Key lần sử dụng cuối cùng，Tạo điều kiện cho quản trị viên theo dõi việc sử dụng。

## tạo ra API Key

Sau khi đăng nhập vào hệ thống，nhập API Key Giao diện quản lý，Có thể tạo khóa mới。Khi tạo nó cần phải có API Key đặt tên，được sử dụng để xác định mục đích của nó，Ví dụ"Hệ thống chăm sóc khách hàng bên ngoài"hoặc"Dịch vụ đồng bộ dữ liệu"。Đã tạo API Key Sẽ tự động được liên kết với người dùng hiện đang đăng nhập，Sau khi ràng buộc API Key Khi gọi giao diện, thao tác sẽ được thực hiện với tư cách người dùng。API Key Nó cũng hỗ trợ thiết lập thời gian hết hạn，Key sẽ tự động hết hạn sau khi hết hạn。

Điều cần đặc biệt quan tâm đó là，tạo ra API Key Khóa hoàn chỉnh được trả về khi（secret）Sẽ chỉ hiển thị một lần，Hãy nhớ lưu nó an toàn khi bạn tạo nó。nếu bị mất，cần phải vượt qua"tái sinh"Chức năng tạo khóa mới，Khóa gốc sẽ trở nên không hợp lệ ngay lập tức。

Giao diện quản lý cũng áp dụng xác thực phổ quát.：

- `GET /api/user/apikey/`：Liệt kê những thứ hiển thị cho người dùng hiện tại API Key
- `POST /api/user/apikey/`：tạo ra API Key
- `PUT /api/user/apikey/{api_key_id}`：Cập nhật tên、trạng thái hoặc thời gian hết hạn
- `POST /api/user/apikey/{api_key_id}/regenerate`：Tạo lại khóa
- `DELETE /api/user/apikey/{api_key_id}`：phím xóa

## được rồi API Địa chỉ truy cập

Yuxi Dịch vụ phụ trợ bị ràng buộc với `0.0.0.0:5050`，Sẽ không tự động phát hiện hoặc thông báo máy này với thế giới bên ngoài IP。Địa chỉ truy cập thực tế phụ thuộc vào môi trường triển khai：

- **phát triển địa phương**：`http://localhost:5050`
- **Triển khai sản xuất（Nginx proxy ngược）**：**Khuyến khích sử dụng HTTPS**，Đó là `https://<Tên miền máy chủ>`（443 hải cảng）。do API Key Sẽ được truyền bằng văn bản rõ ràng trong tiêu đề yêu cầu，sử dụng HTTP（80 hải cảng）Sẽ khiến key bị nghe lén hoặc giả mạo trong quá trình truyền mạng，phải tránh

hoàn thành API Quá trình tương tác có thể đề cập đến các dữ liệu được tạo tự động Swagger Tài liệu：`{base_url}/docs`。

## Phương thức gọi giao diện

> **Giới thiệu `agent_id` mô tả**：trong tất cả các ví dụ dưới đây `agent_id` Tương ứng với cơ thể thông minh **slug** trường（Chẳng hạn như `default-chatbot`），Thay vì tự động tăng cơ sở dữ liệu ID hoặc `agent_config_id`。Xin vui lòng vượt qua `GET /api/agent` Giao diện danh sách xác nhận tác nhân mục tiêu slug giá trị。

Hệ thống bên ngoài đi qua HTTP yêu cầu cuộc gọi Yuxi giao diện，Cần phải được đưa vào tiêu đề yêu cầu API Key：

```http
Authorization: Bearer yxkey_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Việc sử dụng đối thoại của tổng đài viên hiện tại run + SSE quá trình：

1. Tạo chủ đề trò chuyện：`POST /api/chat/thread`
2. Tạo một tác vụ chạy：`POST /api/agent/runs`
3. Đăng ký luồng sự kiện：`GET /api/agent/runs/{run_id}/events`

`POST /api/agent/runs` Yêu cầu nội dung yêu cầu `query`、`agent_id` và `thread_id`，Các trường tùy chọn bao gồm `meta`、`image_content`、`resume`、`parent_run_id`、`resume_request_id`。giao diện trả về `run_id`、`thread_id`、`status`、`request_id` và `stream_url`。

Sau đây là điển hình Python Ví dụ cuộc gọi：

```python
import json
import requests

base_url = "https://your-yuxi-server"  # Phải được sử dụng trong môi trường sản xuất HTTPS；Sự phát triển địa phương có thể được thay đổi thành http://localhost:5050
headers = {
    "Authorization": "Bearer yxkey_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "Content-Type": "application/json",
}

thread_resp = requests.post(
    f"{base_url}/api/chat/thread",
    headers=headers,
    json={
        "agent_id": "default-chatbot",
        "title": "phiên hệ thống bên ngoài",
        "metadata": {},
    },
)
thread_resp.raise_for_status()
thread_id = thread_resp.json()["id"]

run_resp = requests.post(
    f"{base_url}/api/agent/runs",
    headers=headers,
    json={
        "query": "xin chào，xin vui lòng giới thiệu bản thân",
        "agent_id": "default-chatbot",
        "thread_id": thread_id,
        "meta": {"request_id": "external-request-001"},
    },
)
run_resp.raise_for_status()
run = run_resp.json()

with requests.get(f"{base_url}{run['stream_url']}", headers=headers, stream=True) as response:
    response.raise_for_status()
    event_type = None
    data_lines = []

    for line in response.iter_lines(decode_unicode=True):
        if line is None:
            continue
        if line.startswith(":"):
            continue

        if line == "":
            if event_type and data_lines:
                payload = json.loads("\n".join(data_lines))
                print(event_type, payload)
                if event_type == "end":
                    break
            event_type = None
            data_lines = []
            continue

        if line.startswith("event:"):
            event_type = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())
```

Nếu đã có một chuỗi phiên，Có thể tái sử dụng hiện có `thread_id` Tạo trực tiếp run：

```json
{
    "query": "Tiếp tục vòng chủ đề trước",
    "agent_id": "default-chatbot",
    "thread_id": "existing-thread-id",
    "meta": {}
}
```

## định dạng phản hồi

Chạy luồng sự kiện bằng cách sử dụng Server-Sent Events định dạng，Tiêu đề phản hồi là `text/event-stream`。Mỗi sự kiện chứa đựng：

- `event`：loại sự kiện，Có thể là đầu ra của mô hình、Cuộc gọi công cụ、Các sự kiện ngữ nghĩa như đầu ra của tác nhân phụ，Nó cũng có thể là `error` hoặc chấm dứt sự kiện `end`
- `data`：JSON sự kiện được mã hóa envelope，chứa `run_id`、`thread_id`、Tải trọng sự kiện và các trường khác
- `id`：Redis Stream số sê-ri，Có thể được sử dụng như một con trỏ ngắt kết nối và kết nối lại

Máy chủ cũng sẽ định kỳ gửi `:` sự khởi đầu heartbeat Bình luận，Khách hàng nên bỏ qua。Khi bị ngắt kết nối và được kết nối lại，Có thể được chuyển vào tiêu đề yêu cầu `Last-Event-ID`，hoặc trong query Truyền tham số `after_seq`，Máy chủ sẽ tiếp tục phát lại các sự kiện sau số thứ tự này.。

Luồng sự kiện trả về tải trọng hoàn chỉnh theo mặc định，Dễ dàng khắc phục sự cố LangGraph/Langfuse Chi tiết hoạt động。Nếu bạn chỉ cần hiển thị tin nhắn、Cuộc gọi công cụ、Kết quả công cụ、Agent state và tình trạng chấm dứt，Bạn có thể thêm nó tại địa chỉ đăng ký `?verbose=false`。Chế độ thu gọn sẽ vẫn còn SSE `event/data/id`、data trong `run_id/thread_id/request_id/payload` Và các trường cần thiết cho việc tiêu dùng của khách hàng；giống nhau data bên trong `request_id` Sidenote dưới dạng một trường duy nhất。Chế độ thu gọn cũng sẽ bỏ qua `metadata` và trống rỗng `yuxi.agent_state`，và loại bỏ từng chunk lặp đi lặp lại trong `meta`、`metadata`、`thread_id`、`response`、trống rỗng `namespace` và hình ảnh base64 Đợi các trường gỡ lỗi。

Được tạo mọi lúc run sẽ trở lại `request_id`，Có thể được sử dụng để theo dõi nhật ký và khắc phục sự cố。Nếu bạn cần sử dụng cùng một cuộc trò chuyện trong nhiều vòng trò chuyện，Vui lòng sử dụng lại `thread_id`，Hệ thống sẽ ghép các tin nhắn từ cùng một chuỗi để tạo thành bối cảnh hội thoại mạch lạc.。

## Phương thức xác thực

Yuxi của API Giao diện hỗ trợ hai phương thức xác thực một cách thống nhất：

1. **API Key Chứng nhận**：sử dụng `Authorization: Bearer <api_key>` định dạng，Trong số đó API Key Phải là `yxkey_` Bắt đầu bằng tiền tố
2. **JWT Token Chứng nhận**：sử dụng `Authorization: Bearer <jwt_token>` định dạng

Hệ thống này dựa trên token Tiền tố tự động xác định phương thức xác thực。để `yxkey_` sự khởi đầu token coi là API Key，Khác token sau đó như JWT Token Quy trình。Thiết kế này cho phép cùng một giao diện hỗ trợ các hệ thống bên ngoài cùng một lúc（sử dụng API Key）và các ứng dụng ngoại vi nội bộ（Sử dụng trạng thái đăng nhập của người dùng）gọi。

## Biện pháp phòng ngừa an toàn

**bảo mật lớp vận chuyển**：API Key Được truyền ở dạng văn bản rõ ràng trong tiêu đề yêu cầu，**Môi trường sản xuất phải vượt qua HTTPS（443 hải cảng）gọi**，Tránh sử dụng Internet công cộng HTTP Truyền văn bản rõ ràng gây rò rỉ chìa khóa。Đó là khuyến khích để Nginx Đã bật lớp proxy ngược TLS và lực lượng HTTP chuyển hướng đến HTTPS。

Giữ nó an toàn API Key Chìa khóa là nguyên tắc bảo mật quan trọng nhất。do API Key Một khi bị rò rỉ, nó có thể bị lạm dụng，Khuyến cáo không nên hardcode key trong mã，Thay vào đó, nó được quản lý thông qua các biến môi trường hoặc trung tâm cấu hình.。Nếu bạn nghi ngờ khóa đã bị xâm phạm，Điều này cần được tắt ngay trong giao diện quản trị API Key và tái sinh。Cho phép hết hạn khóa là một biện pháp bảo mật tốt，Có thể đặt thời hạn hiệu lực ngắn hơn và luân chuyển thường xuyên。

trong môi trường sản xuất，Nên tạo riêng API Key，Điều này cho phép bạn nhanh chóng xác định được vấn đề và hạn chế phạm vi tác động khi khóa bị xâm phạm.。Đồng thời，Nên kiểm tra thường xuyên trong giao diện quản lý API Key hồ sơ sử dụng，Kiểm tra xem có cuộc gọi bất thường không。

Giới thiệu về kiểm soát quyền，API Key Các quyền tương đương với vai trò của người dùng mà nó bị ràng buộc trong hệ thống.。nếu API Key Liên kết với một người dùng cụ thể，Sau đó tất cả các quyền của người dùng sẽ được phản ánh trong API Key đang hoạt động，Vì vậy hãy đảm bảo giữ nó đúng cách。

## Câu hỏi thường gặp

**Q: API Key Lỗi nào được trả về khi xác thực không thành công?？**
A: Trả về khi xác thực không thành công 401 Unauthorized Lỗi，Thông báo lỗi là"Thông tin xác thực không hợp lệ"。Vui lòng kiểm tra tiêu đề yêu cầu `Authorization` Định dạng của trường có đúng không?，Nó có chứa khóa hoàn chỉnh không?，Và chìa khóa phải là `yxkey_` Bắt đầu。

**Q: Có thể sử dụng đồng thời API Key và JWT Token ?？**
A: Không。Hệ thống này dựa trên token Tiền tố tự động xác định phương thức xác thực。để `yxkey_` sự khởi đầu token sử dụng API Key Chứng nhận，Khác token sử dụng JWT Chứng nhận。

**Q: API Key Có giới hạn tần suất cuộc gọi không?？**
A: Hiện tại không có giới hạn tần số riêng，Nhưng API Key hoạt động giống hệt với danh tính người dùng mà nó bị ràng buộc，Vì vậy, sẽ có một số hạn chế liên quan đến vai trò của người dùng.。

**Q: Tôi nên làm gì nếu nội dung trả về từ cuộc trò chuyện bị cắt xén?？**
A: Hãy chắc chắn rằng khách hàng xử lý nó một cách chính xác UTF-8 mã hóa。Phản hồi phát trực tuyến có thể chứa các ký tự tiếng Trung，Cần sử dụng đúng phương pháp mã hóa để phân tích cú pháp。Nếu các ký tự bị cắt xén được hiển thị trong thiết bị đầu cuối，Bạn có thể kiểm tra cài đặt mã hóa của thiết bị đầu cuối。
