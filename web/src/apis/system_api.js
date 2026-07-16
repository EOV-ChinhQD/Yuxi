import { apiGet, apiAdminGet, apiAdminPost, apiAdminPut, apiAdminDelete } from './base'

/**
 * Quản lý hệ thốngAPImô-đun
 * Chứa cấu hình hệ thống、kiểm tra sức khỏe、Quản lý thông tin và các chức năng khác
 */

// =============================================================================
// === nhóm khám sức khỏe ===
// =============================================================================

export const healthApi = {
  /**
   * Kiểm tra sức khỏe hệ thống（giao diện công cộng）
   * @returns {Promise} - Kết quả kiểm tra sức khỏe
   */
  checkHealth: () => apiGet('/api/system/health', {}, false)
}

// =============================================================================
// === Cấu hình các nhóm quản lý ===
// =============================================================================

export const configApi = {
  /**
   * Nhận cấu hình hệ thống
   * @returns {Promise} - Cấu hình hệ thống
   */
  getConfig: async () => apiGet('/api/system/config'),

  /**
   * Cập nhật một mục cấu hình
   * @param {string} key - phím cấu hình
   * @param {any} value - giá trị cấu hình
   * @returns {Promise} - Cập nhật kết quả
   */
  updateConfig: async (key, value) => apiAdminPost('/api/system/config', { key, value }),

  /**
   * Cập nhật các mục cấu hình theo đợt
   * @param {Object} items - Đối tượng mục cấu hình
   * @returns {Promise} - Cập nhật kết quả
   */
  updateConfigBatch: async (items) => apiAdminPost('/api/system/config/update', items),

  /**
   * Nhận nhật ký hệ thống
   * @param {string} levels - Lọc cấp độ nhật ký tùy chọn，Nhiều cấp độ cách nhau bằng dấu phẩy
   * @returns {Promise} - Nhật ký hệ thống
   */
  getLogs: async (levels) => {
    const url = levels
      ? `/api/system/logs?levels=${encodeURIComponent(levels)}`
      : '/api/system/logs'
    return apiAdminGet(url)
  }
}

// =============================================================================
// === Nhóm quản lý thông tin ===
// =============================================================================

export const brandApi = {
  /**
   * Nhận cấu hình thông tin hệ thống（giao diện công cộng）
   * @returns {Promise} - Cấu hình thông tin hệ thống
   */
  getInfoConfig: () => apiGet('/api/system/info', {}, false)
}

// =============================================================================
// === OCRNhóm dịch vụ ===
// =============================================================================

export const ocrApi = {
  /**
   * NhậnOCRTình trạng sức khỏe dịch vụ
   * @returns {Promise} - OCRtình trạng sức khỏe
   */
  getHealth: async () => apiAdminGet('/api/system/ocr/health')
}

// =============================================================================
// === Nhóm kiểm tra trạng thái mô hình trò chuyện ===
// =============================================================================

export const chatModelApi = {}

// =============================================================================
// === Nhóm cấu hình nhà cung cấp mô hình độc lập ===
// =============================================================================

export const modelProviderApi = {
  getProviders: async () => {
    return apiAdminGet('/api/system/model-providers')
  },

  getV2Models: async (modelType = 'chat') => {
    return apiGet(`/api/system/model-providers/models/v2?model_type=${modelType}`)
  },

  refreshModelCache: async () => {
    return apiAdminPost('/api/system/model-providers/models/cache/refresh')
  },

  getModelStatusBySpec: async (spec) => {
    return apiAdminGet(`/api/system/model-providers/models/status?spec=${encodeURIComponent(spec)}`)
  },

  createProvider: async (payload) => {
    return apiAdminPost('/api/system/model-providers', payload)
  },

  updateProvider: async (providerId, payload) => {
    return apiAdminPut(`/api/system/model-providers/${encodeURIComponent(providerId)}`, payload)
  },

  deleteProvider: async (providerId) => {
    return apiAdminDelete(`/api/system/model-providers/${encodeURIComponent(providerId)}`)
  },

  fetchRemoteModels: async (providerId) => {
    return apiAdminGet(
      `/api/system/model-providers/${encodeURIComponent(providerId)}/remote-models`
    )
  },

  getBuiltinProviders: async () => {
    return apiAdminGet('/api/system/model-providers/builtin')
  }
}
