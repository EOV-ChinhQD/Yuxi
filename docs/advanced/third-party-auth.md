# Xác thực đăng nhập của bên thứ ba
Yuxi Hỗ trợOIDCTruy cập xác thực đăng nhập của bên thứ ba，Thuận tiện cho người dùng doanh nghiệp tích hợp các hệ thống xác thực danh tính hiện có。
> Tính năng này bị tắt theo mặc định，Cần phải được kích hoạt trong tệp cấu hình và cung cấp các thông số liên quan。

## Các bước cấu hình
### 1. Điều kiện tiên quyết
trong của bạnSSOĐăng ký một ứng dụng khách mới trong hệ thống，Nhận thông tin sau：
- khách hàngID（Client ID）
- khóa khách hàng（Client Secret）
- ISSUER URL

Điền địa chỉ gọi lại（Redirect URI）：https://<your_yuxi_host>/api/auth/oidc/callback

### 2. Cấu hìnhYuxi
trongYuxicủa.envThêm các mục cấu hình sau vào tập tin：

```sh
# Có bật hay không OIDC Chứng nhận (true/false)
# OIDC_ENABLED=false

# Tên nguồn xác thực（Văn bản hiển thị trên nút đăng nhập，Đề xuất phải ngắn gọn và dễ nhận biết, Mặc định: OIDCĐăng nhập）
# OIDC_PROVIDER_NAME="OIDCĐăng nhập"

# OIDC Provider của Issuer URL (Ví dụ: https://auth.example.com)
# OIDC_ISSUER_URL=

# OIDC Client ID
# OIDC_CLIENT_ID=

# OIDC Client Secret
# OIDC_CLIENT_SECRET=

# OIDC gọi lại URL (Tùy chọn，Mặc định được xây dựng tự động như /api/auth/oidc/callback, Không nên tùy chỉnh)
# Điền đầy đủ địa chỉ：https://<your_yuxi_host>/api/auth/oidc/callback
# Cần đảm bảo điều này URL trong OIDC Provider Đã đăng ký tại
# OIDC_REDIRECT_URI=

# Điểm cuối ủy quyền (Tùy chọn，tự động từ discovery Nhận)
# OIDC_AUTHORIZATION_ENDPOINT=

# Token điểm cuối (Tùy chọn，tự động từ discovery Nhận)
# OIDC_TOKEN_ENDPOINT=

# UserInfo điểm cuối (Tùy chọn，tự động từ discovery Nhận)
# OIDC_USERINFO_ENDPOINT=

# Điểm cuối đăng xuất (Tùy chọn，tự động từ discovery Nhận)
# OIDC_END_SESSION_ENDPOINT=

# Đã yêu cầu scope (Mặc định: openid profile email)
# OIDC_SCOPES=openid profile email

# Có tự động tạo người dùng hay không (true/false，Mặc định: true)
# OIDC_AUTO_CREATE_USER=true

# OIDC Vai trò mặc định của người dùng (user/admin，Mặc định: user)
# OIDC_DEFAULT_ROLE=user

# OIDC Tên bộ phận mặc định của người dùng (Mặc định: OIDCngười dùng)
# OIDC_DEFAULT_DEPARTMENT=OIDCngười dùng

# Trường ánh xạ tên người dùng (Mặc định: preferred_username)
# OIDC_USERNAME_CLAIM=preferred_username

# Các trường ánh xạ hộp thư (Mặc định: email)
# OIDC_EMAIL_CLAIM=email

# Trường ánh xạ tên (Mặc định: name)
# OIDC_NAME_CLAIM=name

# Có nên sử dụng tên người dùng ban đầu hay không（không có oidc: tiền tố），Cho phép ánh xạ tới Yuxi Tài khoản cục bộ hiện có (true/false，Mặc định: false)
# Sau khi mở，OIDC trả lại username Nó sẽ được sử dụng trực tiếp làm ID đăng nhập doanh nghiệp. uid Đăng nhập，Quản trị viên cần tạo trước tài khoản người dùng
# OIDC_USE_RAW_USERNAME=false

# Cho dù từOIDC userinfo Lấy thông tin phòng ban và tự động tạo các phòng ban liên quan (true/false，Mặc định: false)
# OIDC_FETCH_DEPARTMENT_INFO=false

# Ánh xạ trường tên bộ phận (Mặc định: department)
# OIDC_DEPARTMENT_CLAIM=department

# OIDC Có buộc người dùng đăng nhập lại khi đăng nhập hay không (thêm prompt=login thông số，true/false，Mặc định: true)
# OIDC_FORCE_PROMPT_LOGIN=true

```
### 3. Khởi động lạiYuxiDịch vụ giúp cấu hình hiệu quả
```bash
docker restart api-dev web-dev
```

## Mô tả chức năng

### Sử dụng tên người dùng ban đầu（OIDC_USE_RAW_USERNAME=true）
khi bạn cần Yuxi Tài khoản cục bộ đã có trong hệ thống và OIDC SSO ràng buộc，Tùy chọn này có thể được bật。

**Nguyên tắc ràng buộc**（Không cần sửa đổi cơ sở dữ liệu）：  
Người dùng giữ chỗ được tạo và được đánh dấu để xóa `oidc:{sub}:{target_user_id}` ghi lại OIDC sub với Yuxi Mối quan hệ ràng buộc người dùng，Hãy chắc chắn rằng chỉ có những cái bị ràng buộc OIDC Chỉ với danh tính chính xác, bạn mới có thể đăng nhập vào tài khoản tương ứng.，**Ngăn chặn gian lận tài khoản**。Trong số đó `target_user_id` là một giá trị trong cơ sở dữ liệu `users.id`；ID đăng nhập của người dùng vẫn sử dụng chuỗi `uid`。

### Tự động lấy thông tin bộ phận（OIDC_FETCH_DEPARTMENT_INFO=true）
Sau khi mở，Hệ thống sẽ bắt đầu từ OIDC userinfo Đọc tên bộ phận và mô tả trong，tự động vào Yuxi Tạo một bộ phận trong và liên kết người dùng với bộ phận đó。

- Thư từ OIDC Tên bộ phận thu được sẽ được tự động `strip()` xóa dấu cách，và cắt ngắn thành 50 nhân vật
- Mô tả bộ phận sẽ được tự động cắt ngắn thành 255 nhân vật
- Nếu tên bộ phận trống sau khi xử lý，sẽ quay lại sử dụng `OIDC_DEFAULT_DEPARTMENT` Bộ phận mặc định
