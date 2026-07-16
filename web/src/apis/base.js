import { useUserStore, checkAdminPermission, checkSuperAdminPermission } from '@/stores/user'
import { message } from 'ant-design-vue'

/**
 * Khái niệm cơ bảnAPIYêu cầu đóng gói
 * Cung cấp một phương thức yêu cầu thống nhất，Tự động xử lý các tiêu đề và lỗi xác thực
 */

/**
 * gửiAPIYêu cầu chức năng cơ bản
 * @param {string} url - APIđiểm cuối
 * @param {Object} options - Tùy chọn yêu cầu
 * @param {boolean} requiresAuth - Tiêu đề xác thực có cần thiết không?
 * @param {string} responseType - kiểu phản hồi: 'json' | 'text' | 'blob'
 * @returns {Promise} - Yêu cầu kết quả
 */
export async function apiRequest(url, options = {}, requiresAuth = true, responseType = 'json') {
  try {
    const isFormData = options?.body instanceof FormData
    // Cấu hình yêu cầu mặc định
    const requestOptions = {
      ...options,
      headers: {
        ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers
      }
    }

    // Nếu cần xác thực，Thêm tiêu đề xác thực
    if (requiresAuth) {
      const userStore = useUserStore()
      if (!userStore.isLoggedIn) {
        throw new Error('Người dùng chưa đăng nhập')
      }

      Object.assign(requestOptions.headers, userStore.getAuthHeaders())
    }

    // Gửi yêu cầu
    const response = await fetch(url, requestOptions)

    // Quy trìnhAPIlỗi được trả về
    if (!response.ok) {
      // Cố gắng phân tích thông báo lỗi
      let errorMessage = `Yêu cầu không thành công: ${response.status}, ${response.statusText}`
      let errorData = null

      console.log('APIYêu cầu không thành công:', {
        url,
        status: response.status,
        statusText: response.statusText,
        headers: Object.fromEntries(response.headers.entries())
      })

      try {
        errorData = await response.json()
        // detail có thể là một chuỗi，Nó cũng có thể là một đối tượng có cấu trúc（Chẳng hạn như { error, message }），Cái sau yêu cầu lấy ra bản sao có thể đọc được，
        // Nếu không, việc nối trực tiếp sẽ dẫn đến "[object Object]"。
        const detail = errorData.detail
        if (detail && typeof detail === 'object') {
          errorMessage = detail.message || detail.error || errorMessage
        } else {
          errorMessage = detail || errorData.message || errorMessage
        }
        console.log('APIChi tiết lỗi:', errorData)

        // nếu có422Lỗi，In thông tin chi tiết hơn
        if (response.status === 422) {
          console.error('422Chi tiết lỗi xác minh:', {
            url,
            requestMethod: requestOptions.method,
            requestHeaders: requestOptions.headers,
            requestBody: requestOptions.body,
            responseData: errorData
          })
        }
      } catch (e) {
        // Nếu không thể phân tích đượcJSON，Sử dụng thông báo lỗi mặc định
        console.log('Không thể phân tích phản hồi lỗiJSON:', e)
      }

      // xử lý đặc biệt401và403Lỗi
      const error = new Error(errorMessage)
      error.response = {
        status: response.status,
        statusText: response.statusText,
        data: errorData
      }

      if (response.status === 401) {
        // Nếu xác thực thất bại，Bạn có thể cần phải đăng nhập lại
        const userStore = useUserStore()

        // Kiểm tra xem có phải khôngtokenĐã hết hạn（errorMessage Hợp nhất thành chuỗi，tránh đồ vật detail gọi includes lỗi ném）
        const isTokenExpired =
          errorMessage?.includes('Mã thông báo đã hết hạn') ||
          errorMessage?.includes('token expired')

        message.error(
          isTokenExpired
            ? 'Đăng nhập đã hết hạn，Vui lòng đăng nhập lại'
            : 'Xác thực không thành công，Vui lòng đăng nhập lại'
        )

        // Nếu người dùng hiện cho rằng họ đã đăng nhập，sau đó đăng xuất
        if (userStore.isLoggedIn) {
          userStore.logout()
        }

        // sử dụngsetTimeoutĐảm bảo thông báo được hiển thị trước khi nhảy
        setTimeout(() => {
          window.location.href = '/login'
        }, 1500)

        throw error
      } else if (response.status === 403) {
        error.message = 'Không có quyền thực hiện thao tác này'
        throw error
      } else if (response.status === 500) {
        error.message =
          'Lỗi nội bộ máy chủ，Vui lòng sử dụng docker logs api-dev Xem nhật ký chi tiết'
        throw error
      }

      throw error
    }

    // TheoresponseTypeXử lý phản hồi
    if (responseType === 'blob') {
      return response
    } else if (responseType === 'json') {
      // Kiểm traContent-Typeđể xác định cách xử lý phản hồi
      const contentType = response.headers.get('Content-Type')
      if (contentType && contentType.includes('application/json')) {
        return await response.json()
      }
      return await response.text()
    } else if (responseType === 'text') {
      return await response.text()
    } else {
      return response
    }
  } catch (error) {
    if (error.name !== 'AbortError') {
      console.error('APILỗi yêu cầu:', error)
    }
    throw error
  }
}

/**
 * gửiGETYêu cầu
 * @param {string} url - APIđiểm cuối
 * @param {Object} options - Tùy chọn yêu cầu
 * @param {boolean} requiresAuth - Có cần chứng nhận hay không
 * @param {string} responseType - kiểu phản hồi: 'json' | 'text' | 'blob'
 * @returns {Promise} - Yêu cầu kết quả
 */
export function apiGet(url, options = {}, requiresAuth = true, responseType = 'json') {
  return apiRequest(url, { method: 'GET', ...options }, requiresAuth, responseType)
}

export function apiAdminGet(url, options = {}, responseType = 'json') {
  checkAdminPermission()
  return apiGet(url, options, true, responseType)
}

export function apiSuperAdminGet(url, options = {}, responseType = 'json') {
  checkSuperAdminPermission()
  return apiGet(url, options, true, responseType)
}

/**
 * gửiPOSTYêu cầu
 * @param {string} url - APIđiểm cuối
 * @param {Object} data - Yêu cầu dữ liệu cơ thể
 * @param {Object} options - Tùy chọn yêu cầu khác
 * @param {boolean} requiresAuth - Có cần chứng nhận hay không
 * @param {string} responseType - kiểu phản hồi: 'json' | 'text' | 'blob'
 * @returns {Promise} - Yêu cầu kết quả
 */
export function apiPost(url, data = {}, options = {}, requiresAuth = true, responseType = 'json') {
  return apiRequest(
    url,
    {
      method: 'POST',
      body: data instanceof FormData ? data : JSON.stringify(data),
      ...options
    },
    requiresAuth,
    responseType
  )
}

export function apiAdminPost(url, data = {}, options = {}, responseType = 'json') {
  checkAdminPermission()
  return apiPost(url, data, options, true, responseType)
}

export function apiSuperAdminPost(url, data = {}, options = {}, responseType = 'json') {
  checkSuperAdminPermission()
  return apiPost(url, data, options, true, responseType)
}

/**
 * gửiPUTYêu cầu
 * @param {string} url - APIđiểm cuối
 * @param {Object} data - Yêu cầu dữ liệu cơ thể
 * @param {Object} options - Tùy chọn yêu cầu khác
 * @param {boolean} requiresAuth - Có cần chứng nhận hay không
 * @param {string} responseType - kiểu phản hồi: 'json' | 'text' | 'blob'
 * @returns {Promise} - Yêu cầu kết quả
 */
export function apiPut(url, data = {}, options = {}, requiresAuth = true, responseType = 'json') {
  return apiRequest(
    url,
    {
      method: 'PUT',
      body: data instanceof FormData ? data : JSON.stringify(data),
      ...options
    },
    requiresAuth,
    responseType
  )
}

export function apiAdminPut(url, data = {}, options = {}, responseType = 'json') {
  checkAdminPermission()
  return apiPut(url, data, options, true, responseType)
}

export function apiSuperAdminPut(url, data = {}, options = {}, responseType = 'json') {
  checkSuperAdminPermission()
  return apiPut(url, data, options, true, responseType)
}

/**
 * gửiDELETEYêu cầu
 * @param {string} url - APIđiểm cuối
 * @param {Object} options - Tùy chọn yêu cầu
 * @param {boolean} requiresAuth - Có cần chứng nhận hay không
 * @param {string} responseType - kiểu phản hồi: 'json' | 'text' | 'blob'
 * @returns {Promise} - Yêu cầu kết quả
 */
export function apiDelete(url, options = {}, requiresAuth = true, responseType = 'json') {
  return apiRequest(url, { method: 'DELETE', ...options }, requiresAuth, responseType)
}

export function apiAdminDelete(url, options = {}) {
  checkAdminPermission()
  return apiDelete(url, options, true)
}

export function apiSuperAdminDelete(url, options = {}) {
  checkSuperAdminPermission()
  return apiDelete(url, options, true)
}
