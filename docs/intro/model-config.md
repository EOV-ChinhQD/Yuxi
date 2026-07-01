# Cấu hình mô hình

## Tổng quan

Hệ thống nhất trí thông qua **Cài đặt hệ thống → Cấu hình mô hình** Quản lý trang của tất cả các mô hình（mô hình đối thoại、mô hình nhúng、sắp xếp lại mô hình），Không cần sửa đổi tập tin cấu hình。

## Đường dẫn cấu hình

```
Cài đặt hệ thống → Cấu hình mô hình
```

## API Cấu hình thông tin xác thực

Hỗ trợ hai phương thức cấu hình thông tin xác thực：

| đường | Các tình huống áp dụng |
|------|----------|
| biến môi trường | Môi trường sản xuất có thể không được hiển thị trên giao diện Key bối cảnh |
| Điền trực tiếp | Phát triển và gỡ lỗi，Theo đuổi sự thuận tiện về cấu hình |

**phương pháp biến môi trường**：Điền tên biến trong cấu hình nhà cung cấp（Chẳng hạn như `SILICONFLOW_API_KEY`），Đảm bảo môi trường thời gian chạy đã cấu hình các biến tương ứng。

**Phương pháp điền trực tiếp**：Điền trực tiếp vào cấu hình nhà cung cấp API Key。

## Quản lý nhà cung cấp

### Mẫu nhà cung cấp tích hợp

Một bộ tích hợp sẵn provider mẫu。Mẫu chỉ cung cấp Provider ID、Base URL、Biến môi trường thông tin xác thực và địa chỉ khám phá mô hình từ xa；Tính khả dụng thực tế vẫn phụ thuộc vào việc bạn có định cấu hình thông tin xác thực hay không、Cho phép nhà cung cấp và thêm mô hình。

| nhà cung cấp | Provider ID | Loại hỗ trợ | Biến môi trường thông tin xác thực |
|--------|-------------|----------|--------------|
| OpenAI | `openai` | chat | `OPENAI_API_KEY` |
| DeepSeek | `deepseek` | chat | `DEEPSEEK_API_KEY` |
| DashScope | `alibaba` | chat, embedding, rerank | `DASHSCOPE_API_KEY` |
| Aliyun Coding Plan | `alibaba-coding-plan-cn` | chat | `DASHSCOPE_API_KEY` |
| Aliyun Coding Plan International | `alibaba-coding-plan` | chat | `DASHSCOPE_API_KEY` |
| Zhipu BigModel | `zhipuai` | chat | `ZHIPUAI_API_KEY` |
| Zhipu BigModel Coding Plan | `zhipuai-coding-plan` | chat | `ZHIPUAI_API_KEY` |
| Z.AI | `zai` | chat | `ZAI_API_KEY` |
| Z.AI Coding Plan | `zai-coding-plan` | chat | `ZAI_API_KEY` |
| XiaomiMiMo Token Plan | `xiaomi-token-plan-cn` | chat | `XIAOMI_MIMO_TOKEN_PLAN_API_KEY` |
| XiaomiMiMo | `xiaomi` | chat | `XIAOMI_MIMO_API_KEY` |
| Kimi Code | `kimi-for-coding` | chat | `KIMI_CODE_API_KEY` |
| Moonshot | `moonshotai-cn` | chat | `MOONSHOT_API_KEY` |
| Moonshot International | `moonshotai` | chat | `MOONSHOT_API_KEY` |
| MiniMax | `minimax-cn` | chat | `MINIMAX_API_KEY` |
| MiniMax International | `minimax` | chat | `MINIMAX_API_KEY` |
| OpenRouter | `openrouter` | chat, embedding | `OPENROUTER_API_KEY` |
| ModelScope | `modelscope` | chat | `MODELSCOPE_ACCESS_TOKEN` |
| OpenCode | `opencode` | chat | Không có biến môi trường mặc định |
| SiliconFlow | `siliconflow-cn` | chat, embedding, rerank | `SILICONFLOW_API_KEY` |
| SiliconFlow International | `siliconflow` | chat, embedding, rerank | `SILICONFLOW_GLOBAL_API_KEY` |

Trong số đó `alibaba`、`siliconflow-cn` Bộ phận cài sẵn embedding / rerank người mẫu；Các nhà cung cấp khác thường cần nhập trang chi tiết và vượt qua「Nhận mô hình từ xa」hoặc「Thêm thủ công」Mô hình bổ sung。

### Quá trình vận hành

1. **Thêm nhà cung cấp mới**：nhấp chuột「Thêm nhà cung cấp mới」，Điền thông tin cơ bản（Provider ID、Base URL Đợi đã）
2. **Định cấu hình thông tin xác thực**：điền vào API Key hoặc tên biến môi trường
3. **cho phép nhà cung cấp**：Bật công tắc trạng thái nhà cung cấp
4. **Nhận mô hình**：Nhập chi tiết nhà cung cấp，nhấp chuột「Nhận mô hình từ xa」từ API Kéo danh sách các mô hình có sẵn

## Quản lý người mẫu

### Thêm mô hình

**Phương pháp một：Kéo từ xa**

Nhập chi tiết nhà cung cấp → nhấp chuột「Nhận mô hình từ xa」→ Chọn Thêm từ Danh sách Ứng viên

**Phương pháp 2：Thêm thủ công**

Nhập chi tiết nhà cung cấp → nhấp chuột「Thêm thủ công」→ Điền vào mô hình ID và gõ

### Thông số cấu hình

mô hình nhúng（embedding）Cần cấu hình kích thước vector，Vui lòng tham khảo thông số kỹ thuật của nhà cung cấp mô hình。

### Xóa mô hình

Xóa các mô hình không mong muốn khỏi danh sách các mô hình được kích hoạt trong chi tiết nhà cung cấp。

## Định dạng nhận dạng mô hình

Sử dụng thống nhất các mô hình thời gian chạy `provider_id:model_id` định dạng，Ví dụ `siliconflow-cn:Pro/BAAI/bge-m3`。`model_id` có thể chứa `/`，Hệ thống chỉ nhấn nút đầu tiên `:` Phân biệt nhà cung cấp và mẫu mã ID。

Phiên bản cũ `provider/model`、Cơ sở kiến thức kế thừa JSON lĩnh vực mô hình、trong tập tin cấu hình `model_names` / `embed_model_names` / `reranker_names` Không còn có sẵn dưới dạng nguồn mô hình thời gian chạy。cơ sở kiến thức lịch sử hoặc Agent Cấu hình nếu định dạng cũ vẫn được lưu，Bạn cần chọn lại phiên bản mới của mô hình trong giao diện và lưu lại.。

## Ollama hỗ trợ

Nó không còn được tích hợp vào phiên bản hiện tại Ollama provider type，không còn có sẵn Ollama embedding Thích ứng thời gian chạy。Đã rồi Ollama embedding Cơ sở kiến thức yêu cầu quản trị viên chọn mới embedding Chỉ số mô hình và xây dựng lại，Tránh trộn lẫn các không gian vectơ khác nhau。

## Câu hỏi thường gặp

**Cảnh báo thiếu thông tin đăng nhập**：Kiểm tra API Key Nó có được cấu hình đúng không?，Hoặc xác nhận xem biến môi trường đã được đặt chưa。

**Cấu hình mô hình không có hiệu lực**：Xác nhận rằng mô hình đã được thêm vào danh sách kích hoạt của nhà cung cấp。
