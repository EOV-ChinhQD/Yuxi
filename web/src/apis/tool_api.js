import { apiAdminGet } from './base'

/**
 * Quản lý công cụ API mô-đun
 * Bao gồm chức năng truy vấn của các công cụ tích hợp trong hệ thống
 */

const BASE_URL = '/api/system/tools'

/**
 * Lấy danh sách các công cụ
 * @param {string} category - Tùy chọn，Lọc theo danh mục
 * @returns {Promise} - Danh sách công cụ
 */
export const getTools = async (category = null) => {
  const query = category ? `?${new URLSearchParams({ category }).toString()}` : ''
  return apiAdminGet(`${BASE_URL}${query}`)
}

/**
 * Nhận danh sách các tùy chọn công cụ（để lựa chọn thả xuống）
 * @returns {Promise} - Tùy chọn công cụ
 */
export const getToolOptions = async () => {
  return apiAdminGet(`${BASE_URL}/options`)
}

export const toolApi = {
  getTools,
  getToolOptions
}

export default toolApi
