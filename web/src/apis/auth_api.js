/**
 * Chứng chỉ liên quan API
 */

import { apiAdminGet, apiGet, apiPost } from './base'

async function parseErrorDetail(response, fallbackMessage) {
  const contentType = response.headers.get('content-type') || ''

  if (contentType.includes('application/json')) {
    const error = await response.json()
    return error?.detail || fallbackMessage
  }

  const text = (await response.text()).trim()
  return text || fallbackMessage
}

/**
 * Nhận OIDC Cấu hình
 * @returns {Promise<{enabled: boolean, provider_name?: string}>}
 */
async function getOIDCConfig() {
  const response = await fetch('/api/auth/oidc/config')
  if (!response.ok) {
    throw new Error('Nhận OIDC Cấu hình không thành công')
  }
  return response.json()
}

/**
 * Nhận OIDC Đăng nhập URL
 * @param {string} redirectPath - Đường dẫn chuyển hướng sau khi đăng nhập
 * @returns {Promise<{login_url: string}>}
 */
async function getOIDCLoginUrl(redirectPath = '/') {
  const params = new URLSearchParams({ redirect_path: redirectPath })
  const response = await fetch(`/api/auth/oidc/login-url?${params}`)
  if (!response.ok) {
    const detail = await parseErrorDetail(response, 'Nhận OIDC Địa chỉ đăng nhập không thành công')
    throw new Error(detail)
  }
  return response.json()
}

/**
 * dùng một lần code trao đổi OIDC Kết quả đăng nhập
 * @param {string} code - Đăng nhập một lần code
 * @returns {Promise<{
 *   access_token: string,
 *   token_type: string,
 *   user_id: number,
 *   username: string,
 *   uid: string,
 *   phone_number: string | null,
 *   avatar: string | null,
 *   role: string,
 *   department_id: number | null,
 *   department_name: string | null
 * }>}
 */
async function getUserAccessOptions() {
  return apiAdminGet('/api/auth/users/access-options')
}

async function exchangeOIDCCode(code) {
  const response = await fetch('/api/auth/oidc/exchange-code', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ code })
  })

  if (!response.ok) {
    const detail = await parseErrorDetail(response, 'OIDC Đăng nhập không thành công')
    throw new Error(detail)
  }

  return response.json()
}

async function getCLIAuthSession(userCode) {
  const encoded = encodeURIComponent(userCode)
  return apiGet(`/api/auth/cli/sessions/${encoded}`)
}

async function approveCLIAuthSession(userCode) {
  const encoded = encodeURIComponent(userCode)
  return apiPost(`/api/auth/cli/sessions/${encoded}/approve`, {})
}

export const authApi = {
  getOIDCConfig,
  getOIDCLoginUrl,
  getUserAccessOptions,
  exchangeOIDCCode,
  getCLIAuthSession,
  approveCLIAuthSession
}
