import { message } from 'ant-design-vue'

/**
 * Lớp công cụ xử lý lỗi thống nhất
 */
export class ErrorHandler {
  /**
   * Xử lý các lỗi thường gặp
   * @param {Error} error - đối tượng lỗi
   * @param {string} context - bối cảnh lỗi
   * @param {Object} options - Tùy chọn cấu hình
   */
  static handleError(error, context = 'hoạt động', options = {}) {
    const {
      showMessage = true,
      logToConsole = true,
      customMessage = null,
      severity = 'error'
    } = options

    // nhật ký bảng điều khiển
    if (logToConsole) {
      console.error(`${context}thất bại:`, error)
    }

    // Mẹo sử dụng
    if (showMessage) {
      const displayMessage = customMessage || this.getErrorMessage(error, context)

      switch (severity) {
        case 'warning':
          message.warning(displayMessage)
          break
        case 'info':
          message.info(displayMessage)
          break
        case 'error':
        default:
          message.error(displayMessage)
          break
      }
    }

    return error
  }

  /**
   * Nhận thông báo lỗi
   * @param {Error} error - đối tượng lỗi
   * @param {string} context - bối cảnh lỗi
   * @returns {string} thông báo lỗi
   */
  static getErrorMessage(error, context) {
    if (error?.message) {
      return `${context}thất bại: ${error.message}`
    }
    return `${context}thất bại`
  }

  /**
   * Xử lý lỗi yêu cầu mạng
   * @param {Error} error - đối tượng lỗi
   * @param {string} context - bối cảnh lỗi
   */
  static handleNetworkError(error, context = 'yêu cầu mạng') {
    let customMessage = null

    if (error?.code === 'NETWORK_ERROR') {
      customMessage = 'Kết nối mạng không thành công，Vui lòng kiểm tra cài đặt mạng'
    } else if (error?.status === 401) {
      customMessage = 'Xác thực không thành công，Vui lòng đăng nhập lại'
    } else if (error?.status === 403) {
      customMessage = 'Không đủ quyền，Không thể thực hiện thao tác này'
    } else if (error?.status === 404) {
      customMessage = 'Tài nguyên được yêu cầu không tồn tại'
    } else if (error?.status >= 500) {
      customMessage = 'Lỗi máy chủ，Vui lòng thử lại sau'
    }

    return this.handleError(error, context, { customMessage })
  }

  /**
   * Xử lý các lỗi liên quan đến trò chuyện
   * @param {Error} error - đối tượng lỗi
   * @param {string} operation - Loại hoạt động
   */
  static handleChatError(error, operation) {
    const contextMap = {
      send: 'Gửi tin nhắn',
      create: 'Tạo cuộc trò chuyện',
      delete: 'Xóa cuộc trò chuyện',
      rename: 'Đổi tên cuộc trò chuyện',
      load: 'Tải cuộc trò chuyện',
      export: 'Xuất cuộc trò chuyện',
      stream: 'phát trực tuyến'
    }

    const context = contextMap[operation] || operation
    return this.handleError(error, context)
  }

  /**
   * Xử lý lỗi xác thực
   * @param {string} message - Thông báo lỗi xác thực
   */
  static handleValidationError(message) {
    return this.handleError(new Error(message), 'Xác thực đầu vào', {
      severity: 'warning',
      customMessage: message
    })
  }

  /**
   * Xử lý lỗi hoạt động không đồng bộ
   * @param {Function} asyncFn - hàm không đồng bộ
   * @param {string} context - bối cảnh lỗi
   * @param {Object} options - Tùy chọn cấu hình
   */
  static async handleAsync(asyncFn, context, options = {}) {
    try {
      return await asyncFn()
    } catch (error) {
      this.handleError(error, context, options)
      throw error
    }
  }

  /**
   * Tạo một trang trí xử lý lỗi
   * @param {string} context - bối cảnh lỗi
   * @param {Object} options - Tùy chọn cấu hình
   */
  static createHandler(context, options = {}) {
    return (error) => this.handleError(error, context, options)
  }
}

/**
 * phương pháp phím tắt
 */
export const handleChatError = ErrorHandler.handleChatError.bind(ErrorHandler)
export const handleNetworkError = ErrorHandler.handleNetworkError.bind(ErrorHandler)
export const handleValidationError = ErrorHandler.handleValidationError.bind(ErrorHandler)
export const handleAsync = ErrorHandler.handleAsync.bind(ErrorHandler)

export default ErrorHandler
