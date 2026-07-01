/**
 * AgentIDLớp công cụ xác minh
 * Xử lý thống nhấtAgentIDLogic xác minh liên quan
 */
export class AgentValidator {
  /**
   * Xác minhAgentIDtồn tại
   * @param {string} agentId - Để được xác minhAgentID
   * @param {string} operation - Tên hoạt động，Được sử dụng để nhắc nhở lỗi
   * @returns {boolean} Xác minh đã được thông qua
   */
  static validateAgentId(agentId, operation = 'hoạt động') {
    if (!agentId) {
      console.warn(`không xác địnhAgentID，Không thể${operation}`)
      return false
    }
    return true
  }

  /**
   * Xác minhAgentIDvà hiển thị thông báo lỗi
   * @param {string} agentId - Để được xác minhAgentID
   * @param {string} operation - Tên hoạt động
   * @param {Function} errorHandler - chức năng xử lý lỗi
   * @returns {boolean} Xác minh đã được thông qua
   */
  static validateAgentIdWithError(agentId, operation, errorHandler) {
    if (!agentId) {
      const message = `không xác địnhAgentID，Không thể${operation}`
      if (errorHandler) {
        errorHandler(message)
      }
      return false
    }
    return true
  }

  /**
   * Xác minh các điều kiện tiên quyết cho các hoạt động liên quan đến cuộc hội thoại
   * @param {string} agentId - AgentID
   * @param {string} chatId - đối thoạiID（Tùy chọn）
   * @param {string} operation - Tên hoạt động
   * @param {Function} errorHandler - chức năng xử lý lỗi
   * @returns {boolean} Xác minh đã được thông qua
   */
  static validateChatOperation(agentId, chatId, operation, errorHandler) {
    // Xác minhAgentID
    if (!this.validateAgentIdWithError(agentId, operation, errorHandler)) {
      return false
    }

    // Nếu cần xác minhchatId
    if (chatId !== undefined && !chatId) {
      const message = `Vui lòng chọn cuộc trò chuyện trước`
      if (errorHandler) {
        errorHandler(message)
      }
      return false
    }

    return true
  }

  /**
   * Xác thực các tham số cho thao tác đổi tên
   * @param {string} chatId - đối thoạiID
   * @param {string} title - tiêu đề mới
   * @param {string} agentId - AgentID
   * @param {Function} errorHandler - chức năng xử lý lỗi
   * @returns {boolean} Xác minh đã được thông qua
   */
  static validateRenameOperation(chatId, title, agentId, errorHandler) {
    // Xác minh các thông số cơ bản
    if (!chatId || !title) {
      const message = 'Cuộc trò chuyện không được chỉ địnhIDhoặc tiêu đề，Không thể đổi tên cuộc trò chuyện'
      if (errorHandler) {
        errorHandler(message)
      }
      return false
    }

    // Xác minh tiêu đề không trống
    if (!title.trim()) {
      const message = 'Tiêu đề không thể trống'
      if (errorHandler) {
        errorHandler(message)
      }
      return false
    }

    // Xác minhAgentID
    return this.validateAgentIdWithError(agentId, 'Đổi tên cuộc trò chuyện', errorHandler)
  }

  /**
   * Xác minh các điều kiện tiên quyết cho hoạt động chia sẻ
   * @param {string} chatId - đối thoạiID
   * @param {Object} agent - đối tượng đại lý hiện tại
   * @param {Function} errorHandler - chức năng xử lý lỗi
   * @returns {boolean} Xác minh đã được thông qua
   */
  static validateShareOperation(chatId, agent, errorHandler) {
    if (!chatId || !agent) {
      const message = 'Vui lòng chọn cuộc trò chuyện trước'
      if (errorHandler) {
        errorHandler(message)
      }
      return false
    }
    return true
  }

  /**
   * Xác minh các điều kiện tiên quyết cho hoạt động tải
   * @param {string} agentId - AgentID
   * @param {string} operation - Tên hoạt động
   * @returns {boolean} Xác minh đã được thông qua
   */
  static validateLoadOperation(agentId, operation = 'Trạng thái tải') {
    if (!agentId) {
      console.warn(`không xác địnhAgentID，Không thể${operation}`)
      return false
    }
    return true
  }
}
