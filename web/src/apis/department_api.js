/**
 * Quản lý bộ phận API
 */

import {
  apiAdminGet,
  apiSuperAdminGet,
  apiSuperAdminPost,
  apiSuperAdminPut,
  apiSuperAdminDelete
} from './base'

const BASE_URL = '/api/departments'

/**
 * Nhận danh sách bộ phận（Có thể truy cập được đối với quản trị viên thông thường）
 * @returns {Promise<Array>} Danh sách khoa
 */
export const getDepartments = () => {
  return apiAdminGet(BASE_URL)
}

/**
 * Nhận thông tin chi tiết bộ phận
 * @param {number} departmentId - SởID
 * @returns {Promise<Object>} Chi tiết bộ phận
 */
export const getDepartment = (departmentId) => {
  return apiSuperAdminGet(`${BASE_URL}/${departmentId}`)
}

/**
 * Tạo bộ phận
 * @param {Object} data - dữ liệu bộ phận
 * @param {string} data.name - Tên khoa
 * @param {string} [data.description] - Mô tả bộ phận
 * @returns {Promise<Object>} Bộ phận đã tạo
 */
export const createDepartment = (data) => {
  return apiSuperAdminPost(BASE_URL, data)
}

/**
 * Bộ phận cập nhật
 * @param {number} departmentId - SởID
 * @param {Object} data - dữ liệu bộ phận
 * @param {string} [data.name] - Tên khoa
 * @param {string} [data.description] - Mô tả bộ phận
 * @returns {Promise<Object>} bộ phận cập nhật
 */
export const updateDepartment = (departmentId, data) => {
  return apiSuperAdminPut(`${BASE_URL}/${departmentId}`, data)
}

/**
 * Xóa bộ phận
 * @param {number} departmentId - SởID
 * @returns {Promise<Object>} Xóa kết quả
 */
export const deleteDepartment = (departmentId) => {
  return apiSuperAdminDelete(`${BASE_URL}/${departmentId}`)
}

export const departmentApi = {
  getDepartments,
  getDepartment,
  createDepartment,
  updateDepartment,
  deleteDepartment
}
