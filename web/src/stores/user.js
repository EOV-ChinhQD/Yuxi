import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAgentStore } from './agent'

export const useUserStore = defineStore('user', () => {
  // Trạng thái
  const token = ref(localStorage.getItem('user_token') || '')
  const userId = ref(null)
  const username = ref('')
  const uid = ref('')
  const phoneNumber = ref('')
  const avatar = ref('')
  const userRole = ref('')
  const departmentId = ref(null)
  const departmentName = ref('')

  // Thuộc tính tính toán
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => userRole.value === 'admin' || userRole.value === 'superadmin')
  const isSuperAdmin = computed(() => userRole.value === 'superadmin')

  // hành động
  async function login(credentials) {
    try {
      const formData = new FormData()
      // hỗ trợuidhoặcphone_numberĐăng nhập
      formData.append('username', credentials.loginId) // sử dụngloginIddưới dạng ID đăng nhập chung
      formData.append('password', credentials.password)

      const response = await fetch('/api/auth/token', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()

        // nếu có423mã trạng thái khóa，Đưa ra lỗi chứa mã trạng thái
        if (response.status === 423) {
          const lockError = new Error(error.detail || 'Tài khoản bị khóa')
          lockError.status = 423
          lockError.headers = response.headers
          throw lockError
        }

        throw new Error(error.detail || 'Đăng nhập không thành công')
      }

      const data = await response.json()

      // cập nhật trạng thái
      token.value = data.access_token
      userId.value = data.user_id
      username.value = data.username
      uid.value = data.uid
      phoneNumber.value = data.phone_number || ''
      avatar.value = data.avatar || ''
      userRole.value = data.role
      departmentId.value = data.department_id || null
      departmentName.value = data.department_name || ''

      // chỉ lưu token vào bộ nhớ cục bộ
      localStorage.setItem('user_token', data.access_token)

      return true
    } catch (error) {
      console.error('Lỗi đăng nhập:', error)
      throw error
    }
  }

  function logout() {
    // trạng thái rõ ràng
    token.value = ''
    userId.value = null
    username.value = ''
    uid.value = ''
    phoneNumber.value = ''
    avatar.value = ''
    userRole.value = ''
    departmentId.value = null
    departmentName.value = ''

    // Xóa agentStore Trạng thái，Đảm bảo dữ liệu được tải chính xác khi bạn đăng nhập lại
    const agentStore = useAgentStore()
    agentStore.reset()

    // chỉ rõ ràng token
    localStorage.removeItem('user_token')
  }

  async function initialize(admin) {
    try {
      const response = await fetch('/api/auth/initialize', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(admin)
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Không khởi tạo được quản trị viên')
      }

      const data = await response.json()

      // cập nhật trạng thái
      token.value = data.access_token
      userId.value = data.user_id
      username.value = data.username
      uid.value = data.uid
      phoneNumber.value = data.phone_number || ''
      avatar.value = data.avatar || ''
      userRole.value = data.role
      departmentId.value = data.department_id || null
      departmentName.value = data.department_name || ''

      // chỉ lưu token vào bộ nhớ cục bộ
      localStorage.setItem('user_token', data.access_token)

      return true
    } catch (error) {
      console.error('Lỗi quản trị viên khởi tạo:', error)
      throw error
    }
  }

  async function checkFirstRun() {
    try {
      const response = await fetch('/api/auth/check-first-run')
      const data = await response.json()
      return data.first_run
    } catch (error) {
      console.error('Kiểm tra lỗi trạng thái lần chạy đầu tiên:', error)
      return false
    }
  }

  // dùng choAPITiêu đề ủy quyền yêu cầu
  function getAuthHeaders() {
    return {
      Authorization: `Bearer ${token.value}`
    }
  }

  // Chức năng quản lý người dùng
  async function getUsers({ pageSize = 100 } = {}) {
    try {
      const users = []
      let skip = 0

      while (true) {
        const params = new URLSearchParams({
          skip: String(skip),
          limit: String(pageSize)
        })
        const response = await fetch(`/api/auth/users?${params.toString()}`, {
          headers: {
            ...getAuthHeaders()
          }
        })

        if (!response.ok) {
          throw new Error('Không lấy được danh sách người dùng')
        }

        const batch = await response.json()
        users.push(...batch)

        if (batch.length < pageSize) {
          break
        }

        skip += pageSize
      }

      return users
    } catch (error) {
      console.error('Gặp lỗi danh sách người dùng:', error)
      throw error
    }
  }

  async function createUser(userData) {
    try {
      const response = await fetch('/api/auth/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify(userData)
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Không tạo được người dùng')
      }

      return await response.json()
    } catch (error) {
      console.error('Tạo lỗi người dùng:', error)
      throw error
    }
  }

  async function updateUser(userId, userData) {
    try {
      const response = await fetch(`/api/auth/users/${userId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify(userData)
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Cập nhật người dùng không thành công')
      }

      return await response.json()
    } catch (error) {
      console.error('Cập nhật lỗi người dùng:', error)
      throw error
    }
  }

  async function deleteUser(userId) {
    try {
      const response = await fetch(`/api/auth/users/${userId}`, {
        method: 'DELETE',
        headers: {
          ...getAuthHeaders()
        }
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Không thể xóa người dùng')
      }

      return await response.json()
    } catch (error) {
      console.error('Xóa lỗi người dùng:', error)
      throw error
    }
  }

  // Xác minh tên người dùng và tạouid
  async function validateUsernameAndGenerateUid(username) {
    try {
      const response = await fetch('/api/auth/validate-username', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify({ username })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Xác minh tên người dùng không thành công')
      }

      return await response.json()
    } catch (error) {
      console.error('Lỗi xác minh tên người dùng:', error)
      throw error
    }
  }

  // Tải hình đại diện lên
  async function uploadAvatar(file) {
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/auth/upload-avatar', {
        method: 'POST',
        headers: {
          ...getAuthHeaders()
        },
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Tải lên hình đại diện không thành công')
      }

      const data = await response.json()

      // Cập nhật trạng thái hình đại diện cục bộ
      avatar.value = data.avatar_url

      return data
    } catch (error) {
      console.error('Lỗi tải lên hình đại diện:', error)
      throw error
    }
  }

  // Nhận thông tin người dùng hiện tại
  async function getCurrentUser() {
    try {
      const response = await fetch('/api/auth/me', {
        headers: {
          ...getAuthHeaders()
        }
      })

      if (!response.ok) {
        throw new Error('Không thể lấy được thông tin người dùng')
      }

      const userData = await response.json()

      // Cập nhật trạng thái cục bộ
      userId.value = userData.id
      username.value = userData.username
      uid.value = userData.uid
      phoneNumber.value = userData.phone_number || ''
      avatar.value = userData.avatar || ''
      userRole.value = userData.role
      departmentId.value = userData.department_id || null
      departmentName.value = userData.department_name || ''

      return userData
    } catch (error) {
      console.error('Gặp lỗi thông tin người dùng:', error)
      throw error
    }
  }

  // Cập nhật hồ sơ
  async function updateProfile(profileData) {
    try {
      const response = await fetch('/api/auth/profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify(profileData)
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Không thể cập nhật hồ sơ')
      }

      const userData = await response.json()

      // Cập nhật trạng thái cục bộ
      if (typeof userData.username === 'string') {
        username.value = userData.username
      }
      if (typeof userData.phone_number !== 'undefined') {
        phoneNumber.value = userData.phone_number || ''
      }

      return userData
    } catch (error) {
      console.error('Lỗi cập nhật hồ sơ:', error)
      throw error
    }
  }

  return {
    // Trạng thái
    token,
    userId,
    username,
    uid,
    phoneNumber,
    avatar,
    userRole,
    departmentId,
    departmentName,

    // Thuộc tính tính toán
    isLoggedIn,
    isAdmin,
    isSuperAdmin,

    // phương pháp
    login,
    logout,
    initialize,
    checkFirstRun,
    getAuthHeaders,
    getUsers,
    createUser,
    updateUser,
    deleteUser,
    validateUsernameAndGenerateUid,
    uploadAvatar,
    getCurrentUser,
    updateProfile
  }
})

// Kiểm tra xem người dùng hiện tại có quyền quản trị viên hay không
export const checkAdminPermission = () => {
  const userStore = useUserStore()
  if (!userStore.isAdmin) {
    throw new Error('Yêu cầu quyền quản trị viên')
  }
  return true
}

// Kiểm tra xem người dùng hiện tại có quyền quản trị viên cấp cao hay không
export const checkSuperAdminPermission = () => {
  const userStore = useUserStore()
  return userStore.isSuperAdmin
}
