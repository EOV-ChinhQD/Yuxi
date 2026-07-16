import { apiGet, apiPost, apiDelete, apiPut, apiRequest } from './base'
import { useUserStore } from '@/stores/user'

/**
 * đại lýAPImô-đun
 * Bao gồm quản lý đại lý、trò chuyện、Cấu hình và các chức năng khác
 * Yêu cầu về quyền: bất kỳ người dùng nào đã đăng nhập（Người dùng thông thường、Quản trị viên、siêu quản trị viên）
 */

// =============================================================================
// === Nhóm trò chuyện đại lý ===
// =============================================================================

export const agentApi = {
  /**
   * Cuộc gọi trò chuyện đơn giản（không phát trực tuyến）
   * @param {string} query - Nội dung truy vấn
   * @returns {Promise} - Phản hồi trò chuyện
   */
  simpleCall: (query) => apiPost('/api/chat/call', { query }),

  /**
   * Tạo tiêu đề cuộc trò chuyện
   * @param {string} query - Nội dung truy vấn
   * @param {Object} modelSpec - Cấu hình mô hình
   * @returns {Promise<string>} - tiêu đề được tạo
   */
  generateTitle: async (query, modelSpec) => {
    const response = await apiPost('/api/chat/call', {
      query: `Tạo tiêu đề ngắn gọn (tối đa 30 ký tự) dựa trên cuộc trò chuyện sau, chỉ sử dụng tiếng Việt, không bao gồm các định dạng markdown:\n\n${query.slice(0, 2000)}`,
      meta: { model_spec: modelSpec }
    })
    return response.response
  },

  /**
   * Lấy danh sách đại lý
   * @returns {Promise} - Danh sách đại lý
   */
  getAgents: ({ includeSubagents = false } = {}) => {
    const params = new URLSearchParams()
    if (includeSubagents) params.set('include_subagents', 'true')
    const query = params.toString()
    return apiGet(query ? `/api/agent?${query}` : '/api/agent')
  },

  getAgentBackends: () => apiGet('/api/agent/backends'),

  /**
   * Nhận chi tiết đại lý cá nhân
   * @param {string} agentId - đại lýID
   * @returns {Promise} - Chi tiết đại lý
   */
  getAgentDetail: (agentId) => apiGet(`/api/agent/${agentId}`),

  /**
   * Nhận tin nhắn lịch sử của đại lý
   * @param {string} agentId - đại lýID
   * @param {string} threadId - phiênID
   * @returns {Promise} - tin tức lịch sử
   */
  getAgentHistory: (threadId) => apiGet(`/api/chat/thread/${threadId}/history`),

  /**
   * Nhận phiên được chỉ định AgentState
   * @param {string} agentId - đại lýID
   * @param {string} threadId - phiênID
   * @returns {Promise} - AgentState
   */
  getAgentState: (threadId, { includeMessages = false } = {}) =>
    apiGet(`/api/chat/thread/${threadId}/state${includeMessages ? '?include_messages=true' : ''}`),

  /**
   * Submit feedback for a message
   * @param {number} messageId - Message ID
   * @param {string} rating - 'like' or 'dislike'
   * @param {string|null} reason - Optional reason for dislike
   * @returns {Promise} - Feedback response
   */
  submitMessageFeedback: (messageId, rating, reason = null) =>
    apiPost(`/api/chat/message/${messageId}/feedback`, { rating, reason }),

  /**
   * Get feedback status for a message
   * @param {number} messageId - Message ID
   * @returns {Promise} - Feedback status
   */
  getMessageFeedback: (messageId) => apiGet(`/api/chat/message/${messageId}/feedback`),

  createAgent: (payload) => apiPost('/api/agent', payload),

  updateAgent: (agentId, payload) => apiPut(`/api/agent/${agentId}`, payload),

  deleteAgent: (agentId) => apiDelete(`/api/agent/${agentId}`),

  /**
   * Tạo một tác vụ không đồng bộ（Run）
   * @param {Object} data - run Nội dung yêu cầu
   * @returns {Promise<Object>}
   */
  createAgentRun: (data) =>
    apiPost('/api/agent/runs', {
      query: data.query,
      agent_slug: data.agent_slug,
      thread_id: data.thread_id,
      meta: data.meta || {},
      image_content: data.image_content || null,
      model_spec: data.model_spec || null,
      resume: data.resume ?? null,
      created_by_run_id: data.created_by_run_id || null
    }),

  /**
   * Nhận Run Trạng thái
   * @param {string} runId - run ID
   * @returns {Promise<Object>}
   */
  getAgentRun: (runId) => apiGet(`/api/agent/runs/${runId}`),

  /**
   * Hủy bỏ Run
   * @param {string} runId - run ID
   * @returns {Promise<Object>}
   */
  cancelAgentRun: (runId) => apiPost(`/api/agent/runs/${runId}/cancel`, {}),

  /**
   * Nhận chủ đề hoạt động Run
   * @param {string} threadId - chủ đềID
   * @returns {Promise<Object>}
   */
  getThreadActiveRun: (threadId) => apiGet(`/api/agent/thread/${threadId}/active_run`),

  /**
   * mở Run sự kiện SSE kết nối（Người gọi có trách nhiệm đóng）
   * @param {string} runId - run ID
   * @param {string} afterSeq - bắt đầu seq/cursor
   * @param {Object} options - { signal, verbose }
   * @returns {Promise<Response>}
   */
  streamAgentRunEvents: (runId, afterSeq = '0-0', options = {}) => {
    const { signal, verbose = false } = options
    const headers = {
      ...useUserStore().getAuthHeaders()
    }
    const cursor = String(afterSeq || '0-0')
    if (cursor && cursor !== '0-0') {
      headers['Last-Event-ID'] = cursor
    }
    const params = new URLSearchParams({ verbose: String(verbose) })
    return fetch(`/api/agent/runs/${runId}/events?${params.toString()}`, {
      method: 'GET',
      headers,
      signal
    })
  }
}

// =============================================================================
// === Hỗ trợ nhóm hình ảnh đa phương thức ===
// =============================================================================

export const multimodalApi = {
  /**
   * Tải ảnh lên và nhậnbase64mã hóa
   * @param {File} file - Tệp hình ảnh
   * @returns {Promise} - Tải kết quả lên
   */
  uploadImage: (file) => {
    const formData = new FormData()
    formData.append('file', file)

    return apiRequest(
      '/api/chat/image/upload',
      {
        method: 'POST',
        body: formData
      },
      true
    )
  }
}

// =============================================================================
// === Nhóm chủ đề hội thoại ===
// =============================================================================

export const threadApi = {
  /**
   * Lấy danh sách các chủ đề hội thoại
   * @param {string | null | undefined} agentId - đại lýID，Tùy chọn；Trả về tất cả các cuộc hội thoại của tổng đài viên nếu không được thông qua
   * @param {number} limit - Giới hạn số lượng trả lại，Mặc định100
   * @param {number} offset - bù đắp，Mặc định0
   * @returns {Promise} - Danh sách chủ đề hội thoại
   */
  getThreads: (agentId = null, limit = 100, offset = 0) => {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset)
    })
    if (agentId) {
      params.set('agent_id', agentId)
    }
    const url = `/api/chat/threads?${params.toString()}`
    return apiGet(url)
  },

  /**
   * Tìm kiếm các cuộc trò chuyện lịch sử
   * @param {string} query - Tìm kiếm từ khóa
   * @param {Object} options - Tùy chọn tìm kiếm
   * @param {string | null | undefined} options.agentId - đại lýID，Tùy chọn
   * @param {number} options.limit - Giới hạn số lượng trả lại
   * @param {number} options.offset - bù đắp
   * @returns {Promise} - Kết quả tìm kiếm
   */
  searchThreads: (query, { agentId = null, limit = 20, offset = 0 } = {}) => {
    const params = new URLSearchParams({
      q: query,
      limit: String(limit),
      offset: String(offset)
    })
    if (agentId) {
      params.set('agent_id', agentId)
    }
    return apiGet(`/api/chat/threads/search?${params.toString()}`)
  },

  /**
   * Tạo chủ đề trò chuyện mới
   * @param {string} agentId - đại lýID
   * @param {string} title - Tiêu đề cuộc trò chuyện
   * @param {Object} metadata - Siêu dữ liệu
   * @returns {Promise} - Tạo kết quả
   */
  createThread: (agentId, title, metadata) =>
    apiPost('/api/chat/thread', {
      agent_id: agentId,
      title: title || 'cuộc trò chuyện mới',
      metadata: metadata || {}
    }),

  /**
   * Cập nhật chuỗi cuộc trò chuyện
   * @param {string} threadId - chủ đề hội thoạiID
   * @param {string} title - Tiêu đề cuộc trò chuyện
   * @param {boolean} is_pinned - Có nên ghim nó lên đầu không
   * @returns {Promise} - Cập nhật kết quả
   */
  updateThread: (threadId, title, is_pinned) =>
    apiPut(`/api/chat/thread/${threadId}`, {
      title,
      is_pinned
    }),

  /**
   * Xóa chuỗi cuộc trò chuyện
   * @param {string} threadId - chủ đề hội thoạiID
   * @returns {Promise} - Xóa kết quả
   */
  deleteThread: (threadId) => apiDelete(`/api/chat/thread/${threadId}`),

  /**
   * Nhận danh sách các tệp đính kèm chủ đề
   * @param {string} threadId - chủ đề hội thoạiID
   * @returns {Promise}
   */
  getThreadAttachments: (threadId) => apiGet(`/api/chat/thread/${threadId}/attachments`),

  /**
   * Liệt kê các tập tin chủ đề（Thư mục）
   * @param {string} threadId
   * @param {string} path
   * @param {boolean} recursive
   * @returns {Promise}
   */
  listThreadFiles: (threadId, path = '/home/gem/user-data', recursive = false) =>
    apiGet(
      `/api/chat/thread/${threadId}/files?path=${encodeURIComponent(path)}&recursive=${recursive}`
    ),

  /**
   * Đọc nội dung tập tin văn bản chủ đề（Phân trang）
   * @param {string} threadId
   * @param {string} path
   * @param {number} offset
   * @param {number} limit
   * @returns {Promise}
   */
  readThreadFile: (threadId, path, offset = 0, limit = 2000) =>
    apiGet(
      `/api/chat/thread/${threadId}/files/content?path=${encodeURIComponent(path)}&offset=${offset}&limit=${limit}`
    ),

  /**
   * Tải xuống tập tin chủ đề/Xem trước URL
   * @param {string} threadId
   * @param {string} path
   * @param {boolean} download
   * @returns {string}
   */
  getThreadArtifactUrl: (threadId, path, download = false) => {
    const encodedPath = path
      .split('/')
      .filter(Boolean)
      .map((segment) => encodeURIComponent(segment))
      .join('/')
    const query = download ? '?download=true' : ''
    return `/api/chat/thread/${threadId}/artifacts/${encodedPath}${query}`
  },

  /**
   * Tải xuống tập tin chủ đề（Với xác thực）
   * @param {string} threadId
   * @param {string} path
   * @returns {Promise<Response>}
   */
  downloadThreadArtifact: (threadId, path) =>
    apiGet(threadApi.getThreadArtifactUrl(threadId, path, true), {}, true, 'blob'),

  /**
   * Lưu sản phẩm bàn giao vào workspace/saved_artifacts
   * @param {string} threadId
   * @param {string} path
   * @returns {Promise}
   */
  saveThreadArtifactToWorkspace: (threadId, path) =>
    apiPost(`/api/chat/thread/${threadId}/artifacts/save`, { path }),

  /**
   * Tải lên tệp đính kèm tạm thời
   * @param {File} file
   * @returns {Promise}
   */
  uploadTmpAttachment: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiRequest('/api/chat/attachments/tmp', {
      method: 'POST',
      body: formData
    })
  },

  /**
   * Phân tích các tệp đính kèm tạm thời
   * @param {Object} payload
   * @returns {Promise}
   */
  parseTmpAttachment: (payload) => apiPost('/api/chat/attachments/tmp/parse', payload),

  /**
   * Xác nhận thêm tệp đính kèm tạm thời vào chuỗi
   * @param {string} threadId
   * @param {Array} attachments
   * @returns {Promise}
   */
  confirmTmpThreadAttachments: (threadId, attachments) =>
    apiPost(`/api/chat/thread/${threadId}/attachments/confirm`, { attachments }),

  /**
   * Tải lên tệp đính kèm
   * @param {string} threadId
   * @param {File} file
   * @returns {Promise}
   */
  uploadThreadAttachment: (threadId, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiRequest(`/api/chat/thread/${threadId}/attachments`, {
      method: 'POST',
      body: formData
    })
  },

  /**
   * Xóa tệp đính kèm
   * @param {string} threadId
   * @param {string} fileId
   * @returns {Promise}
   */
  deleteThreadAttachment: (threadId, fileId) =>
    apiDelete(`/api/chat/thread/${threadId}/attachments/${fileId}`)
}
