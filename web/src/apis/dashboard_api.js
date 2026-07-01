import { apiAdminGet } from './base'

/**
 * Dashboard APImô-đun
 * Được quản trị viên sử dụng để xem bản ghi cuộc trò chuyện của tất cả người dùng
 */

export const dashboardApi = {
  /**
   * Nhận tất cả các bản ghi cuộc trò chuyện
   * @param {Object} params - tham số truy vấn
   * @param {string} params.uid - người dùng UID bộ lọc
   * @param {string} params.agent_id - đại lýIDbộ lọc
   * @param {string} params.status - Lọc trạng thái (active/deleted/all)
   * @param {number} params.limit - Số lượng mỗi trang
   * @param {number} params.offset - bù đắp
   * @returns {Promise<Array>} - Danh sách cuộc trò chuyện
   */
  getConversations: (params = {}) => {
    const queryParams = new URLSearchParams()
    if (params.uid) queryParams.append('uid', params.uid)
    if (params.agent_id) queryParams.append('agent_id', params.agent_id)
    if (params.status) queryParams.append('status', params.status)
    if (params.limit) queryParams.append('limit', params.limit)
    if (params.offset) queryParams.append('offset', params.offset)

    return apiAdminGet(`/api/dashboard/conversations?${queryParams.toString()}`)
  },

  /**
   * Nhận chi tiết cuộc trò chuyện
   * @param {string} threadId - chủ đề hội thoạiID
   * @returns {Promise<Object>} - Chi tiết cuộc trò chuyện
   */
  getConversationDetail: (threadId) => {
    return apiAdminGet(`/api/dashboard/conversations/${threadId}`)
  },

  /**
   * NhậnDashboardThống kê
   * @returns {Promise<Object>} - Thống kê
   */
  getStats: () => {
    return apiAdminGet('/api/dashboard/stats')
  },

  /**
   * Nhận danh sách phản hồi của người dùng
   * @param {Object} params - tham số truy vấn
   * @param {string} params.rating - Lọc loại phản hồi (like/dislike/all)
   * @param {string} params.agent_id - đại lýIDbộ lọc
   * @returns {Promise<Array>} - Danh sách phản hồi
   */
  getFeedbacks: (params = {}) => {
    const queryParams = new URLSearchParams()
    if (params.rating && params.rating !== 'all') queryParams.append('rating', params.rating)
    if (params.agent_id) queryParams.append('agent_id', params.agent_id)

    return apiAdminGet(`/api/dashboard/feedbacks?${queryParams.toString()}`)
  },

  // ========== Thêm song songAPIgiao diện ==========

  /**
   * Nhận số liệu thống kê hoạt động của người dùng
   * @returns {Promise<Object>} - Thống kê hoạt động của người dùng
   */
  getUserStats: () => {
    return apiAdminGet('/api/dashboard/stats/users')
  },

  /**
   * Nhận số liệu thống kê cuộc gọi công cụ
   * @returns {Promise<Object>} - Thống kê cuộc gọi công cụ
   */
  getToolStats: () => {
    return apiAdminGet('/api/dashboard/stats/tools')
  },

  /**
   * Nhận số liệu thống kê cơ sở kiến thức
   * @returns {Promise<Object>} - Thống kê cơ sở kiến thức
   */
  getKnowledgeStats: () => {
    return apiAdminGet('/api/dashboard/stats/knowledge')
  },

  /**
   * NhậnAIĐại lý phân tích dữ liệu
   * @returns {Promise<Object>} - AIThông tin phân tích đại lý
   */
  getAgentStats: () => {
    return apiAdminGet('/api/dashboard/stats/agents')
  },

  /**
   * Nhận tất cả số liệu thống kê theo đợt（Yêu cầu song song）
   * @returns {Promise<Object>} - Tất cả số liệu thống kê
   */
  getAllStats: async () => {
    try {
      const [basicStats, userStats, toolStats, knowledgeStats, agentStats] = await Promise.all([
        apiAdminGet('/api/dashboard/stats'),
        apiAdminGet('/api/dashboard/stats/users'),
        apiAdminGet('/api/dashboard/stats/tools'),
        apiAdminGet('/api/dashboard/stats/knowledge'),
        apiAdminGet('/api/dashboard/stats/agents')
      ])

      return {
        basic: basicStats,
        users: userStats,
        tools: toolStats,
        knowledge: knowledgeStats,
        agents: agentStats
      }
    } catch (error) {
      console.error('Không thể lấy số liệu thống kê theo đợt:', error)
      throw error
    }
  },

  /**
   * Nhận dữ liệu chuỗi thời gian thống kê cuộc gọi
   * @param {string} type - kiểu dữ liệu (models/agents/tokens/tools)
   * @param {string} timeRange - phạm vi thời gian (14hours/14days/14weeks)
   * @returns {Promise<Object>} - thống kê chuỗi thời gian
   */
  getCallTimeseries: (type = 'models', timeRange = '14days') => {
    return apiAdminGet(`/api/dashboard/stats/calls/timeseries?type=${type}&time_range=${timeRange}`)
  }
}
