# Tùy chỉnh thương hiệu

Yuxi Hỗ trợ tùy chỉnh thương hiệu hoàn chỉnh，bao gồm Logo、Tên tổ chức、Thông tin bản quyền、Thỏa thuận đăng nhập, v.v.，Tạo điều kiện tùy biến thương hiệu cho người dùng doanh nghiệp。

## Cấu hình thông tin thương hiệu

### bước 1：Sao chép tập tin mẫu

```bash
cp backend/package/yuxi/config/static/info.template.yaml backend/package/yuxi/config/static/info.local.yaml
```

### bước 2：Chỉnh sửa thông tin thương hiệu

trong `backend/package/yuxi/config/static/info.local.yaml` Định cấu hình thông tin thương hiệu của bạn trong：

- Tên ứng dụng
- Tên tổ chức
- Logo
- Thông tin bản quyền
- Thỏa thuận người dùng trang đăng nhập/Liên kết chính sách quyền riêng tư

### bước 3：Chỉ định tập tin cấu hình

trong `.env` Chỉ định đường dẫn tệp cấu hình trong：

```env
YUXI_BRAND_FILE_PATH=backend/package/yuxi/config/static/info.local.yaml
```

::: tip Định cấu hình mức độ ưu tiên
`info.local.yaml` > `info.template.yaml`（Mặc định）
:::

## Cấu hình giao thức đăng nhập

Trang đăng nhập hỗ trợ đọc các liên kết thỏa thuận người dùng và thỏa thuận quyền riêng tư từ cấu hình thương hiệu.。

### Các mục cấu hình

trong `backend/package/yuxi/config/static/info.local.yaml` của `footer` Thêm các trường sau bên dưới：

```yaml
footer:
  copyright: "© your org 2026"
  user_agreement_url: "/protocols/user-agreement.template.html"
  privacy_policy_url: "/protocols/privacy-policy.template.html"
```

### Hiển thị quy tắc

- Khi nào `user_agreement_url` và `privacy_policy_url` Khi cả hai đều có giá trị，Trang đăng nhập sẽ hiển thị tùy chọn kiểm tra giao thức。
- Khi bất kỳ trường nào trống，Trang đăng nhập không hiển thị tùy chọn kiểm tra giao thức。
- Khi thỏa thuận không được kiểm tra，Gửi thông tin đăng nhập/Việc khởi tạo sẽ nhắc người dùng đồng ý với thỏa thuận thông qua tin nhắn.。

### File mẫu thỏa thuận

Hệ thống mặc định cung cấp hai HTML tập tin mẫu：

- `web/public/protocols/user-agreement.template.html`
- `web/public/protocols/privacy-policy.template.html`

Bạn có thể chỉnh sửa trực tiếp nội dung giao thức trong hai tệp này，và thay thế phần giữ chỗ（Chẳng hạn như `{{ORG_NAME}}`、`{{PRODUCT_NAME}}`、`{{EFFECTIVE_DATE}}`）。

Nếu bạn có trang thỏa thuận của riêng mình，Bạn cũng có thể `user_agreement_url` và `privacy_policy_url` Trỏ tới một đường dẫn tùy chỉnh hoặc liên kết bên ngoài。

### Icon tùy chỉnh

Hệ thống cài sẵn nhiều loại Icon，Để biết thêm biểu tượng，Có thể lấy được từ `lucide-vue-next` được giới thiệu ở。

## Tùy chỉnh phong cách

Hệ thống hỗ trợ tùy chỉnh màu sắc chủ đề hoàn chỉnh。Tệp cấu hình được đặt tại `web/src/assets/css/base.css`，và `web/src/assets/css/base.dark.css`：

```css
:root {
  --main-color: #1890ff;        /* màu chủ đạo */
  --main-1000: #f0f2f5;          /* mẫu màu */
  --main-900: #e6f7ff;           /* mẫu màu */
  /* ... Bảng màu khác */
}
```

Sau khi sửa đổi các biến khớp màu，Giao diện sẽ được cập nhật theo thời gian thực，Không cần khởi động lại dịch vụ。

Ngoài ra，`web/src/stores/theme.js` trong `colorPrimary` Cũng cần phải sửa đổi đồng bộ。
