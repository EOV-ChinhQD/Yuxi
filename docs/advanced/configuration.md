# Giải thích chi tiết về hệ thống cấu hình

## Tổng quan

Hệ thống áp dụng kiến trúc cấu hình nhiều lớp，Cấu hình mô hình được quản lý bằng giao diện web，Cấu hình ứng dụng dựa trên Pydantic + TOML。

## Cấp độ cấu hình

```
Mặc định mã → TOML tập tin → biến môi trường
   (thấp)                      (cao)
```

## Cấu hình mô hình

Quản lý thống nhất theo trang web，Xem chi tiết [Cấu hình mô hình](../intro/model-config.md)。

## Cấu hình ứng dụng

Các mục cấu hình được xác định trong `backend/package/yuxi/config/app.py`，Lưu các sửa đổi của người dùng vào `saves/config/base.toml`。

### Sửa đổi cấu hình

```python
from yuxi.config import config

config.default_model = "provider-id:model-id"
config.save()
```

Cấu hình sẽ được lưu vào `base.toml` viết sau Redis Ảnh chụp nhanh（`yuxi:runtime_config`）。Ảnh chụp nhanh chứa các trường cấu hình hiển thị có thể được đồng bộ hóa khi chạy，Không bao gồm `_` tính chất bên trong lúc đầu và `save_dir`；API/worker Mỗi quá trình bắt đầu một luồng đồng bộ hóa nền khi nó bắt đầu.，nhấn 5 khoảng thời gian giây để làm mới giá trị bộ nhớ từ ảnh chụp nhanh này，Người đọc không cần phải cảm nhận。Redis Tiếp tục sử dụng giá trị bộ nhớ hiện tại khi không có sẵn。

`save_dir` Là cấu hình đường dẫn nội bộ trong quá trình khởi động，Không hiển thị trong cấu hình quản trị viên，Cấu hình giao diện thông qua quản trị viên cũng không được hỗ trợ、`base.toml` hoặc thời gian chạy Redis Sửa đổi ảnh chụp nhanh。sandbox Các cấu hình liên quan vẫn là những cấu hình nhạy cảm trong quá trình khởi động，Chạy các thành phần khởi tạo không cam kết cập nhật đầy đủ nóng，Sau khi sửa đổi, bạn cần khởi động lại dịch vụ để đảm bảo nó có hiệu lực.。

## Câu hỏi thường gặp

**Tập tin cấu hình bị hỏng**：Xóa `saves/config/base.toml`，Hệ thống sẽ tạo lại cấu hình mặc định。
