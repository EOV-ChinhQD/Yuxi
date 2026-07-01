import { apiGet, apiAdminGet, apiAdminPost, apiAdminPut, apiAdminDelete } from './base'

/**
 * MCP Quản lý máy chủ API mô-đun
 * chứa MCP Chức năng thêm, xóa, sửa đổi máy chủ và quản lý công cụ
 */

const BASE_URL = '/api/system/mcp-servers'

// =============================================================================
// === MCP máy chủ CRUD ===
// =============================================================================

/**
 * Nhận tất cả MCP Cấu hình máy chủ
 * @returns {Promise} - Danh sách máy chủ
 */
export const getMcpServers = async () => {
  return apiGet(BASE_URL)
}

/**
 * Nhận một đĩa đơn MCP Cấu hình máy chủ
 * @param {string} name - Tên máy chủ
 * @returns {Promise} - Cấu hình máy chủ
 */
export const getMcpServer = async (name) => {
  return apiAdminGet(`${BASE_URL}/${encodeURIComponent(name)}`)
}

/**
 * tạo mới MCP máy chủ
 * @param {Object} data - Dữ liệu cấu hình máy chủ
 * @returns {Promise} - Tạo kết quả
 */
export const createMcpServer = async (data) => {
  return apiAdminPost(BASE_URL, data)
}

/**
 * cập nhật MCP Cấu hình máy chủ
 * @param {string} name - Tên máy chủ
 * @param {Object} data - Cập nhật dữ liệu
 * @returns {Promise} - Cập nhật kết quả
 */
export const updateMcpServer = async (name, data) => {
  return apiAdminPut(`${BASE_URL}/${encodeURIComponent(name)}`, data)
}

/**
 * Xóa MCP máy chủ
 * @param {string} name - Tên máy chủ
 * @returns {Promise} - Xóa kết quả
 */
export const deleteMcpServer = async (name) => {
  return apiAdminDelete(`${BASE_URL}/${encodeURIComponent(name)}`)
}

// =============================================================================
// === MCP Vận hành máy chủ ===
// =============================================================================

/**
 * kiểm tra MCP Kết nối máy chủ
 * @param {string} name - Tên máy chủ
 * @returns {Promise} - Kết quả kiểm tra
 */
export const testMcpServer = async (name) => {
  return apiAdminPost(`${BASE_URL}/${encodeURIComponent(name)}/test`, {})
}

/**
 * cập nhật MCP Trạng thái kích hoạt máy chủ
 * @param {string} name - Tên máy chủ
 * @param {boolean} enabled - Có bật hay không
 * @returns {Promise} - Chuyển đổi kết quả
 */
export const updateMcpServerStatus = async (name, enabled) => {
  return apiAdminPut(`${BASE_URL}/${encodeURIComponent(name)}/status`, { enabled })
}

// =============================================================================
// === MCP Quản lý công cụ ===
// =============================================================================

/**
 * Nhận MCP Danh sách công cụ máy chủ
 * @param {string} name - Tên máy chủ
 * @returns {Promise} - Danh sách công cụ
 */
export const getMcpServerTools = async (name) => {
  return apiAdminGet(`${BASE_URL}/${encodeURIComponent(name)}/tools`)
}

/**
 * Làm mới MCP Danh sách công cụ máy chủ（Xóa bộ nhớ cache và truy xuất lại）
 * @param {string} name - Tên máy chủ
 * @returns {Promise} - làm mới kết quả
 */
export const refreshMcpServerTools = async (name) => {
  return apiAdminPost(`${BASE_URL}/${encodeURIComponent(name)}/tools/refresh`, {})
}

/**
 * Chuyển đổi trạng thái kích hoạt của một công cụ riêng lẻ
 * @param {string} serverName - Tên máy chủ
 * @param {string} toolName - Tên công cụ
 * @returns {Promise} - Chuyển đổi kết quả
 */
export const toggleMcpServerTool = async (serverName, toolName) => {
  return apiAdminPut(
    `${BASE_URL}/${encodeURIComponent(serverName)}/tools/${encodeURIComponent(toolName)}/toggle`,
    {}
  )
}

export const mcpApi = {
  getMcpServers,
  getMcpServer,
  createMcpServer,
  updateMcpServer,
  deleteMcpServer,
  testMcpServer,
  updateMcpServerStatus,
  getMcpServerTools,
  refreshMcpServerTools,
  toggleMcpServerTool
}

export default mcpApi
