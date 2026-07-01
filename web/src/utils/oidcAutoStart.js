const AUTO_START_KEY = 'oidc_auto_start_attempted'

// Có redirect Các thông số để xác minh bảo mật，Ngăn chặn lỗ hổng chuyển hướng mở
// - Phải thuộc loại chuỗi
// - Phải là / Bắt đầu（đường dẫn tương đối cục bộ）
// - không thể được // hoặc \ Bắt đầu（giao thức tương đối URL / đường dẫn không chuẩn）
// Trả lại khi không hợp lệ hoặc thiếu "/"
export function sanitizeRedirect(value) {
  if (
    typeof value === 'string' &&
    value.length > 0 &&
    value[0] === '/' &&
    value[1] !== '/' &&
    value[1] !== '\\'
  ) {
    return value
  }
  return '/'
}

// Kiểm tra xem kích hoạt tự động đã được thử chưa OIDC（trong cùng một phiên，Tránh các vòng lặp vô hạn）
export function hasAutoStartAttempted() {
  return sessionStorage.getItem(AUTO_START_KEY) === '1'
}

// Cờ đã cố gắng tự động kích hoạt
export function markAutoStartAttempted() {
  sessionStorage.setItem(AUTO_START_KEY, '1')
}

// Xóa cờ thử kích hoạt tự động（OIDC Được gọi sau khi đăng nhập thành công）
export function clearAutoStartAttempt() {
  sessionStorage.removeItem(AUTO_START_KEY)
}

// Cố gắng kích hoạt tự động OIDC Đăng nhập
// config: OIDC Đối tượng cấu hình（Được người gọi thu được từ bên ngoài）
// getOIDCLoginUrl: Đăng nhập URL hàm không đồng bộ
// Trở lại true Cho biết rằng một bước nhảy đã được bắt đầu，caller Các quá trình tiếp theo không nên tiếp tục
export async function tryAutoStartOIDC(getOIDCLoginUrl, config) {
  // 1. OIDC Cấu hình chưa sẵn sàng hoặc chưa được kích hoạt
  if (!config || !config.enabled) {
    return false
  }

  // 2. Có oidc_error không còn tự động kích hoạt khi，tránh vòng lặp
  const params = new URLSearchParams(window.location.search)
  if (params.has('oidc_error')) {
    return false
  }

  // 3. Phải có autostartOidc thông số
  if (!params.has('autostartOidc')) {
    return false
  }

  // 4. Đã thử trong cùng một phiên，không lặp lại
  if (hasAutoStartAttempted()) {
    return false
  }

  // 5. Nhận OIDC Đăng nhập URL và nhảy
  let loginUrlResp
  try {
    loginUrlResp = await getOIDCLoginUrl()
  } catch {
    return false
  }

  if (!loginUrlResp || !loginUrlResp.login_url) {
    return false
  }

  // Lưu đường dẫn hiện tại，Trở về sau khi đăng nhập（Kiểm tra an ninh）
  const redirectPath = sanitizeRedirect(params.get('redirect'))
  sessionStorage.setItem('oidc_redirect', redirectPath)

  // Mark đã cố gắng，Ngăn chặn kích hoạt tự động vào lần tiếp theo
  markAutoStartAttempted()

  window.location.href = loginUrlResp.login_url
  return true
}
