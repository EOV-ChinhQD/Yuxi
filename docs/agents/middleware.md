# hệ thống phần mềm trung gian

phần mềm trung gian là Yuxi Cơ chế chính để mở rộng hành vi hoạt động của các tác nhân。nó hoạt động ở LangGraph Agent cuộc gọi người mẫu、Cuộc gọi công cụ、Cập nhật trạng thái và đường dẫn truy cập hệ thống tệp，cơ sở tri thức、Skills、Phụ kiện、chất phụ、Nén bối cảnh và truy cập quan sát chạy cùng một liên kết thực thi。

Tích hợp sẵn `ChatbotAgent` với `SubAgentBackend` sẽ ở đó `get_graph()` Xây dựng danh sách phần mềm trung gian trong。Lọc tài nguyên chạy trước không còn dựa vào phần mềm trung gian cấu hình thời gian chạy cũ nữa，nhưng việc tạo ra Graph trước đây `prepare_agent_runtime_context` Hoàn thành。

## Chuẩn bị thời gian chạy

Chuẩn bị thời gian chạy không phải là phần mềm trung gian，Nhưng nó xác định những tài nguyên mà phần mềm trung gian tiếp theo có thể nhìn thấy。Tích hợp sẵn Agent tạo ra Graph Các bước sau đây sẽ được thực hiện trước：

- `prepare_agent_runtime_context`：Lọc công cụ theo quyền của người dùng hiện tại、cơ sở tri thức、MCP、Skills và đại lý phụ，và bắt nguồn `_visible_knowledge_bases`、`_prompt_skills`、`_readable_skills`
- `build_prompt_with_context`：Dựa trên Context Tạo các từ nhắc hệ thống
- `load_chat_model(context.model)`：Tải mô hình chính
- `resolve_configured_runtime_tools(context)`：Tải các công cụ tích hợp đã được cấu hình và MCP Công cụ

Điều này có nghĩa là phần mềm trung gian không chịu trách nhiệm đánh giá lại“Liệu người dùng có thể truy cập tài nguyên hay không”。Những gì họ tiêu thụ được bình thường hóa runtime context。

## Liên kết phần mềm trung gian tích hợp

Hiện đang được xây dựng ở `ChatbotAgent` Trình tự phần mềm trung gian như sau：

| phần mềm trung gian | chức năng |
| --- | --- |
| `create_agent_filesystem_middleware` | Truy cập hệ thống tệp hộp cát、Không gian làm việc của người dùng、chủ đề uploads/outputs với chế độ chỉ đọc Skills định tuyến，Và viết nội dung khi kết quả tool quá lớn `outputs/large_tool_results` |
| `save_attachments_to_fs` / `AttachmentMiddleware` | từ LangGraph state của `uploads` Đọc đường dẫn đính kèm，Đưa các đường dẫn có thể đọc được vào lời nhắc hệ thống，Mô hình nhắc nhở để sử dụng khi cần thiết `read_file` |
| `SkillsMiddleware` | Có thể nhìn thấy tiêm Skill phần nhắc nhở，Nghe các bài đọc `SKILL.md` sau này Skill kích hoạt，và nối thêm các công cụ và phần phụ thuộc MCP Công cụ；Các công cụ cơ sở tri thức được tích hợp sẵn `knowledge-base` Skill Tải theo yêu cầu |
| `YuxiSubAgentMiddleware` | chỉ chính Agent Được gắn khi có các tác nhân phụ hiển thị，cung cấp `task` công cụ gọi sub thật Agent graph |
| `YuxiSummarizationMiddleware` | Dựa trên DeepAgents `SummarizationMiddleware` Thực hiện nén ngữ cảnh dài，Và làm sạch kết quả công cụ trong lịch sử tóm tắt |
| `TodoListMiddleware` | Cung cấp trạng thái việc cần làm，Làm cho bảng trạng thái giao diện người dùng có thể hiển thị được Agent Tiến độ chạy |
| `PatchToolCallsMiddleware` | Đã sửa một số mẫu tin nhắn cuộc gọi công cụ，Cải thiện khả năng tương thích gọi công cụ |
| `ModelRetryMiddleware` | Thử lại như đã định cấu hình khi cuộc gọi mô hình không thành công |
| `TokenUsageMiddleware` | trong LangGraph state Viết vòng này token Sử dụng ảnh chụp nhanh，Để xem bằng bảng trạng thái giao diện người dùng |

`SubAgentBackend` Sử dụng cùng một bộ năng lực cốt lõi，nhưng sẽ không gắn kết `YuxiSubAgentMiddleware`，và lọc bổ sung `present_artifacts`、`ask_user_question`、`install_skill` và các công cụ khác không phù hợp để đại lý phụ sử dụng trực tiếp。

## Công cụ cơ sở tri thức

Khả năng truy cập cơ sở kiến thức được tích hợp sẵn `knowledge-base` Skill。Agent đọc `/home/gem/skills/knowledge-base/SKILL.md` kích hoạt cái này Skill sau，`SkillsMiddleware` Sẽ được nối thêm theo phụ thuộc `list_kbs`、`query_kb`、`find_kb_document`、`open_kb_document`、`get_mindmap` công cụ cơ sở tri thức。

Cơ sở kiến thức hữu hình thực tế vẫn bao gồm `prepare_agent_runtime_context` Dựa trên người dùng hiện tại và Agent Ghi cấu hình `_visible_knowledge_bases`，Khi công cụ này được thực thi, nó sẽ chỉ tìm kiếm trong loạt cơ sở kiến thức này.。`context.knowledges` là phạm vi tài nguyên，Không Skill chính nó。

Hệ thống sẽ không đưa cây file cơ sở tri thức vào sandbox。Agent Để truy cập nội dung cơ sở kiến thức bạn nên sử dụng `query_kb`、`find_kb_document` và `open_kb_document`，thay vì đi ngang qua `/home/gem/kbs` Những con đường cũ như vậy。

## Skills Tiêm và kích hoạt

`SkillsMiddleware` Làm việc theo hai bước：

1. Đọc trước khi gọi mô hình `_prompt_skills`，làm cho có thể nhìn thấy Skill tên、mô tả và `SKILL.md` Đường dẫn được thêm vào dấu nhắc hệ thống。
2. Sau khi công cụ được gọi, hãy kiểm tra xem mô hình đã được đọc chưa `/home/gem/skills/<slug>/SKILL.md`。Nếu Skill trong `_readable_skills` trong phạm vi，Chỉ cần viết nó `activated_skills`，và nối thêm các công cụ đã khai báo của nó và MCP phụ thuộc vào。

Thiết kế này cho phép Skill Nó có thể được hiển thị đầu tiên dưới dạng mô tả，Chỉ mở rộng bộ công cụ sau khi mô hình đã thực sự được đọc và kích hoạt，Tránh nhồi nhét tất cả các công cụ phụ thuộc vào ngữ cảnh ngay từ đầu。

## Tệp đính kèm và hệ thống tệp

Sau khi tệp đính kèm được tải lên, trước tiên nó sẽ được đặt trong hệ thống tệp luồng.，Và trong LangGraph state kỷ lục trung bình `uploads`。`AttachmentMiddleware` Chỉ đưa tên tệp và đường dẫn có thể đọc được vào từ nhắc，Toàn bộ nội dung file sẽ không được chèn vào ngữ cảnh mô hình.。Khi mô hình cần xem tệp đính kèm，nên vượt qua `read_file` Đọc đường dẫn tương ứng。

Phần mềm trung gian của hệ thống tập tin chịu trách nhiệm sandbox backend、chủ đề uploads/outputs、Không gian làm việc của người dùng và chỉ đọc Skills kết hợp thành Agent Hệ thống tập tin ảo có thể truy cập。Bình thường Agent Theo mặc định, hiện tại `thread_id` như phạm vi tập tin；Sử dụng chất phụ child `thread_id` làm checkpoint，Đồng thời, luồng cha uploads/outputs，và sử dụng phụ Agent sở hữu Skills Phạm vi。

## Nhiệm vụ của đại lý phụ

Chúa ơi Agent Nếu các tác nhân phụ hiển thị được định cấu hình，Sẽ gắn kết `YuxiSubAgentMiddleware` và nhận được `task` Công cụ。Công cụ này sẽ không gọi độc lập cũ SubAgents bàn，Thay vào đó hãy tìm `agents.is_subagent=true` Và phần phụ trợ là `SubAgentBackend` của thực tế Agent Cấu hình，Sau đó bắt đầu con tương ứng Agent graph。

Tác nhân phụ sẽ giành được sự độc lập khi thực hiện child thread、độc lập checkpoint và `agent_runs(run_type=subagent)` ghi lại；Kết quả công cụ sẽ trả về child thread ID，Việc này có thể được thực hiện sau ID trở về `task` Tiếp tục nhiệm vụ phụ tương tự。Bản thân tác nhân phụ sẽ không gắn kết lớp tiếp theo `task` phần mềm trung gian，Tránh hình thành các liên kết tác nhân phụ lồng nhau。

## Summary Nén ngữ cảnh

Những cuộc hội thoại dài được nén bởi Yuxi đóng gói `YuxiSummarizationMiddleware` chịu trách nhiệm。nó dựa trên DeepAgents của `SummarizationMiddleware`，Nhưng đối với Yuxi Việc xử lý bổ sung đã được thực hiện trên các kết quả tìm kiếm cơ sở kiến ​​thức và gọi công cụ.。

Điều kiện kích hoạt xuất phát từ Agent Context：

| trường | Mô tả |
| --- | --- |
| `summary_threshold` | bối cảnh ngoài đó K token Tóm tắt kích hoạt sau ngưỡng |
| `summary_keep_messages` | Giữ số lượng tin nhắn gần đây sau khi tiêu hóa |
| `summary_prompt` | Các từ nhắc nhở được sử dụng bởi các mô hình tóm tắt |
| `summary_tool_result_token_limit` | Xem trước kết quả công cụ trong lịch sử tóm tắt token giới hạn trên |

Sử dụng phán đoán kích hoạt Yuxi xấp xỉ riêng token Kết quả tính toán，Trả lại mà không sử dụng mô hình `usage_metadata.total_tokens` như một tác nhân kích hoạt，tránh provider Tầm cỡ thanh toán、Tầm cỡ tích lũy hoặc báo cáo bất thường dẫn đến việc nén sớm các cuộc trò chuyện ngắn。

Sau khi kích hoạt，Phần mềm trung gian sẽ nén tin nhắn trước đó thành một summary message，và giữ lại tin nhắn gốc trong cửa sổ gần đây。Tóm tắt kết quả công cụ lịch sử，nó sẽ không hoàn thành `ToolMessage.content` Gửi trực tiếp summary prompt，Thay vào đó hãy viết dòng điện Agent có thể nhìn thấy `outputs/large_tool_results`，Tái sử dụng tên công cụ、Khoảng token con số、Đường dẫn kết quả đầy đủ và nội dung kết quả công cụ thay thế xem trước có giới hạn。

Điều này đặc biệt quan trọng đối với việc truy xuất cơ sở tri thức：`query_kb`、`open_kb_document`、`find_kb_document` Các công cụ khác có thể trả về các đoạn dài hơn、Nội dung trích dẫn và tài liệu。Summary Giai đoạn dành riêng“Bạn đã kiểm tra những gì?、kết quả ở đâu、Xem trước khóa là gì”，Đồng thời, tránh đưa nhiều lần một số lượng lớn văn bản gốc được truy xuất vào phần tóm tắt.，Giảm ô nhiễm bối cảnh và token áp lực。

Không được kích hoạt summary Các cuộc gọi mô hình thông thường không làm sạch thêm kết quả công cụ trong cửa sổ gần đây；Việc lập ngân sách kết quả công cụ thông thường chủ yếu được xử lý bởi phần mềm trung gian của hệ thống tệp trong giai đoạn trả lại công cụ。

## Phần mềm trung gian tùy chỉnh

Khi thêm phần mềm trung gian，Đưa việc thực hiện vào `backend/package/yuxi/agents/middlewares`，Cụ thể hơn Agent của `get_graph()` Tham gia `middleware` danh sách。Trước khi thêm một cái mới, hãy xác nhận trách nhiệm của nó.：

- Lọc tài nguyên、Sự hội tụ quyền và lựa chọn tài nguyên mặc định nên được đặt trong `prepare_agent_runtime_context` một loại Graph Logic trước khi sáng tạo。
- Tiêm gợi ý mô hình、Công cụ bổ sung động、xử lý kết quả công cụ và state Cập nhật phù hợp để được thực hiện LangChain Agent middleware。
- Đọc và ghi tập tin、Kết quả công cụ gỡ cài đặt và artifacts Màn hình nên được ưu tiên sử dụng lại `create_agent_filesystem_middleware` với hộp cát backend。

vẫn còn trong kho `DynamicToolMiddleware`，Nhưng hiện tại được xây dựng trong Agent công cụ và MCP Việc tải đã được thực hiện bởi `resolve_configured_runtime_tools(context)` với `SkillsMiddleware` giả sử。Theo mặc định, khi thêm các tính năng mới, không sử dụng lại phần mềm trung gian công cụ động cũ，Trừ khi thực sự cần thiết“Lọc theo yêu cầu sau khi đăng ký trước”chế độ。
