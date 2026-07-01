<template>
  <div class="user-management">
    <!-- vùng đầu -->
    <div class="header-section">
      <div class="header-content">
        <div class="section-title">Quản lý người dùng</div>
        <p class="section-description">
          Quản lý người dùng hệ thống，Hãy hoạt động một cách thận trọng。Sau khi xóa người dùng, người dùng sẽ không thể đăng nhập vào hệ thống.。
        </p>
      </div>
      <div class="header-actions">
        <a-button
          @click="handleRefresh"
          :loading="userManagement.refreshing"
          title="Làm mới"
          class="refresh-btn lucide-icon-btn"
        >
          <template #icon>
            <RefreshCw :size="16" :class="{ spin: userManagement.refreshing }" />
          </template>
        </a-button>
        <a-button type="primary" @click="showAddUserModal" class="add-btn lucide-icon-btn">
          <template #icon><Plus :size="16" /></template>
          Thêm người dùng
        </a-button>
      </div>
    </div>

    <div class="filter-section">
      <a-input
        v-model:value="userManagement.searchKeyword"
        class="search-input"
        placeholder="Tìm kiếm tên người dùng / ID / Số điện thoại di động"
        allow-clear
      >
        <template #prefix><Search :size="16" /></template>
      </a-input>
      <div class="filter-actions">
        <a-select v-model:value="userManagement.departmentFilter" class="filter-select">
          <a-select-option value="">Tất cả các phòng ban</a-select-option>
          <a-select-option
            v-for="dept in departmentFilterOptions"
            :key="dept.value"
            :value="dept.value"
          >
            {{ dept.label }}
          </a-select-option>
        </a-select>
        <a-select v-model:value="userManagement.roleFilter" class="filter-select">
          <a-select-option value="">Tất cả các quyền</a-select-option>
          <a-select-option value="superadmin">siêu quản trị viên</a-select-option>
          <a-select-option value="admin">Quản trị viên</a-select-option>
          <a-select-option value="user">Người dùng thông thường</a-select-option>
        </a-select>
      </div>
    </div>

    <!-- khu vực nội dung chính -->
    <div class="content-section">
      <a-spin :spinning="userManagement.loading">
        <div v-if="userManagement.error" class="error-message">
          <a-alert type="error" :message="userManagement.error" show-icon />
        </div>

        <div class="cards-container">
          <div v-if="filteredUsers.length === 0" class="empty-state">
            <a-empty
              :description="userManagement.users.length === 0 ? 'Chưa có dữ liệu người dùng' : 'Không có người dùng phù hợp'"
            />
          </div>
          <div v-else class="user-cards-grid">
            <div v-for="user in paginatedUsers" :key="user.id" class="user-card">
              <div class="card-header">
                <div class="user-info-main">
                  <div class="user-avatar">
                    <FallbackAvatar
                      :src="user.avatar"
                      :default-src="getUserDefaultAvatarSrc(user)"
                      :name="user.username"
                      :seed="user.uid || user.username"
                      kind="user"
                      :size="40"
                      shape="circle"
                      :alt="user.username"
                      class="avatar-img"
                    />
                  </div>
                  <div class="user-info-content">
                    <div class="name-tag-row">
                      <h4 class="username">{{ user.username }}</h4>
                      <div
                        v-if="
                          user.role === 'admin' ||
                          user.role === 'superadmin' ||
                          user.department_name
                        "
                        class="role-dept-badge"
                      >
                        <span class="role-icon-wrapper" :class="getRoleClass(user.role)">
                          <UserLock v-if="user.role === 'superadmin'" :size="14" />
                          <UserStar v-else-if="user.role === 'admin'" :size="14" />
                          <User v-else :size="14" />
                        </span>
                        <span v-if="user.department_name" class="dept-text">
                          {{ user.department_name }}
                        </span>
                      </div>
                    </div>
                    <div class="user-id-row">ID: {{ user.uid || '-' }}</div>
                  </div>
                </div>

                <a-dropdown :trigger="['click']" placement="bottomRight">
                  <template #overlay>
                    <a-menu>
                      <a-menu-item key="edit" @click.stop="showEditUserModal(user)">
                        <span class="user-card-menu-item">
                          <SquarePen :size="14" />
                          Chỉnh sửa người dùng
                        </span>
                      </a-menu-item>
                      <a-menu-item
                        key="delete"
                        :disabled="isUserDeleteDisabled(user)"
                        @click.stop="confirmDeleteUser(user)"
                      >
                        <span
                          class="user-card-menu-item"
                          :class="{ danger: !isUserDeleteDisabled(user) }"
                        >
                          <Trash2 :size="14" />
                          Xóa người dùng
                        </span>
                      </a-menu-item>
                    </a-menu>
                  </template>
                  <a-button
                    type="text"
                    size="small"
                    class="card-menu-trigger lucide-icon-btn"
                    aria-label="Hành động của người dùng"
                    @click.stop
                  >
                    <MoreVertical :size="16" />
                  </a-button>
                </a-dropdown>
              </div>

              <div class="card-content">
                <div class="info-item">
                  <span class="info-label">Số điện thoại di động:</span>
                  <span class="info-value phone-text">{{ user.phone_number || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">thời gian sáng tạo:</span>
                  <span class="info-value time-text">{{ formatTime(user.created_at) }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">lần đăng nhập cuối cùng:</span>
                  <span class="info-value time-text">{{ formatTime(user.last_login) }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-if="filteredUsers.length > userManagement.pageSize" class="pagination-section">
            <a-pagination
              v-model:current="userManagement.currentPage"
              v-model:page-size="userManagement.pageSize"
              :total="filteredUsers.length"
              :page-size-options="['20', '50', '100']"
              show-size-changer
              size="small"
            />
          </div>
        </div>
      </a-spin>
    </div>

    <!-- Hộp phương thức biểu mẫu người dùng -->
    <a-modal
      v-model:open="userManagement.modalVisible"
      :title="userManagement.modalTitle"
      @ok="handleUserFormSubmit"
      :confirmLoading="userManagement.loading"
      @cancel="userManagement.modalVisible = false"
      :maskClosable="false"
      width="480px"
      class="user-modal"
    >
      <a-form layout="vertical" class="user-form">
        <a-form-item label="Tên người dùng" required class="form-item">
          <a-input
            v-model:value="userManagement.form.username"
            placeholder="Vui lòng nhập tên người dùng（2-20nhân vật）"
            @blur="validateAndGenerateUid"
            :maxlength="20"
          />
          <div v-if="userManagement.form.usernameError" class="error-text">
            {{ userManagement.form.usernameError }}
          </div>
          <div
            v-if="userManagement.form.generatedUid && !userManagement.editMode"
            class="help-text"
          >
            Đăng nhậpID：{{ userManagement.form.generatedUid }}，cái nàyIDsẽ được sử dụng để đăng nhập，Tự động tạo dựa trên tên người dùng
          </div>
        </a-form-item>

        <!-- Trường số điện thoại di động -->
        <a-form-item label="Số điện thoại di động" class="form-item">
          <a-input
            v-model:value="userManagement.form.phoneNumber"
            placeholder="Vui lòng nhập số điện thoại di động（Tùy chọn，Có sẵn để đăng nhập）"
            :maxlength="11"
          />
          <div v-if="userManagement.form.phoneError" class="error-text">
            {{ userManagement.form.phoneError }}
          </div>
        </a-form-item>

        <template v-if="userManagement.editMode">
          <div class="password-toggle">
            <a-checkbox v-model:checked="userManagement.displayPasswordFields">
              Thay đổi mật khẩu
            </a-checkbox>
          </div>
        </template>

        <template v-if="!userManagement.editMode || userManagement.displayPasswordFields">
          <a-form-item label="Mật khẩu" required class="form-item">
            <a-input-password
              v-model:value="userManagement.form.password"
              placeholder="Vui lòng nhập mật khẩu"
            />
          </a-form-item>

          <a-form-item label="Xác nhận mật khẩu" required class="form-item">
            <a-input-password
              v-model:value="userManagement.form.confirmPassword"
              placeholder="Vui lòng nhập lại mật khẩu"
            />
          </a-form-item>
        </template>

        <a-form-item
          v-if="userManagement.editMode && userManagement.form.role === 'superadmin'"
          label="vai trò"
          class="form-item"
        >
          <a-input value="siêu quản trị viên" disabled />
          <div class="help-text">Tài khoản quản trị viên cấp cao không thể sửa đổi vai trò</div>
        </a-form-item>
        <a-form-item v-else label="vai trò" class="form-item">
          <a-select v-model:value="userManagement.form.role">
            <a-select-option value="user">Người dùng thông thường</a-select-option>
            <a-select-option value="admin" v-if="userStore.isSuperAdmin">Quản trị viên</a-select-option>
          </a-select>
        </a-form-item>

        <!-- Bộ chọn bộ phận（Chỉ hiển thị với quản trị viên cấp cao） -->
        <a-form-item v-if="userStore.isSuperAdmin" label="Sở" class="form-item">
          <a-select v-model:value="userManagement.form.departmentId" placeholder="Vui lòng chọn một bộ phận">
            <a-select-option
              v-for="dept in departmentManagement.departments"
              :key="dept.id"
              :value="dept.id"
            >
              {{ dept.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { reactive, onMounted, watch, computed } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useUserStore } from '@/stores/user'
import { departmentApi } from '@/apis'
import {
  Plus,
  SquarePen,
  Trash2,
  User,
  UserLock,
  UserStar,
  RefreshCw,
  Search,
  MoreVertical
} from 'lucide-vue-next'
import { formatDateTime } from '@/utils/time'
import { generatePixelAvatar } from '@/utils/pixelAvatar'
import FallbackAvatar from '@/components/common/FallbackAvatar.vue'

const userStore = useUserStore()

// Trạng thái liên quan đến quản lý người dùng
const userManagement = reactive({
  loading: false,
  refreshing: false,
  users: [],
  searchKeyword: '',
  departmentFilter: '',
  roleFilter: '',
  currentPage: 1,
  pageSize: 50,
  error: null,
  modalVisible: false,
  modalTitle: 'Thêm người dùng',
  editMode: false,
  editUserId: null,
  form: {
    username: '',
    generatedUid: '', // được tạo tự độnguid
    phoneNumber: '', // Số điện thoại di động
    password: '',
    confirmPassword: '',
    role: 'user', // Vai trò mặc định
    departmentId: null, // SởID
    usernameError: '', // Thông báo lỗi tên người dùng
    phoneError: '' // Thông báo lỗi số điện thoại di động
  },
  displayPasswordFields: true // Có hiển thị trường mật khẩu khi chỉnh sửa hay không
})

// Danh sách khoa（Chỉ dành cho quản trị viên cấp cao）
const departmentManagement = reactive({
  departments: []
})

const departmentFilterOptions = computed(() => {
  const options = new Map()

  departmentManagement.departments.forEach((dept) => {
    options.set(String(dept.id), {
      value: String(dept.id),
      label: dept.name
    })
  })

  userManagement.users.forEach((user) => {
    const departmentId = user.department_id
    const departmentName = user.department_name

    if (departmentId == null && !departmentName) return

    const value = String(departmentId ?? departmentName)

    if (!options.has(value)) {
      options.set(value, {
        value,
        label: departmentName || `Sở ${departmentId}`
      })
    }
  })

  return [...options.values()]
})

const filteredUsers = computed(() => {
  const keyword = userManagement.searchKeyword.trim().toLowerCase()

  return userManagement.users.filter((user) => {
    const matchesKeyword =
      !keyword ||
      [user.username, user.uid, user.phone_number].some((value) =>
        String(value || '')
          .toLowerCase()
          .includes(keyword)
      )
    const matchesDepartment =
      !userManagement.departmentFilter ||
      String(user.department_id ?? user.department_name ?? '') === userManagement.departmentFilter
    const matchesRole = !userManagement.roleFilter || user.role === userManagement.roleFilter

    return matchesKeyword && matchesDepartment && matchesRole
  })
})

const paginatedUsers = computed(() => {
  const pageSize = Number(userManagement.pageSize)
  const start = (userManagement.currentPage - 1) * pageSize
  return filteredUsers.value.slice(start, start + pageSize)
})

// Nhận danh sách bộ phận
const fetchDepartments = async () => {
  if (!userStore.isSuperAdmin) return // Quản trị viên thông thường không cần phải có danh sách tất cả các phòng ban
  try {
    const departments = await departmentApi.getDepartments()
    departmentManagement.departments = departments
  } catch (error) {
    console.error('Không lấy được danh sách phòng ban:', error)
  }
}

// Thêm tên người dùng xác minh và tạouidchức năng
const validateAndGenerateUid = async () => {
  const username = userManagement.form.username.trim()

  // Xóa các lỗi trước đó và tạo raID
  userManagement.form.usernameError = ''
  userManagement.form.generatedUid = ''

  if (!username) {
    return
  }

  // ở chế độ chỉnh sửa，Không cần phải tái sinhuid
  if (userManagement.editMode) {
    return
  }

  try {
    const result = await userStore.validateUsernameAndGenerateUid(username)
    userManagement.form.generatedUid = result.uid
  } catch (error) {
    userManagement.form.usernameError = error.message || 'Xác minh tên người dùng không thành công'
  }
}

// Xác minh định dạng số điện thoại di động
const validatePhoneNumber = (phone) => {
  if (!phone) {
    return true // Số điện thoại di động tùy chọn
  }

  // Xác minh định dạng số điện thoại di động Trung Quốc đại lục
  const phoneRegex = /^1[3-9]\d{9}$/
  return phoneRegex.test(phone)
}

// Theo dõi các thay đổi trạng thái hiển thị trường mật khẩu
watch(
  () => userManagement.displayPasswordFields,
  (newVal) => {
    // Khi trường mật khẩu bị chặn，Xóa mật khẩu đã nhập
    if (!newVal) {
      userManagement.form.password = ''
      userManagement.form.confirmPassword = ''
    }
  }
)

// Theo dõi những thay đổi khi nhập số điện thoại di động
watch(
  () => userManagement.form.phoneNumber,
  (newPhone) => {
    userManagement.form.phoneError = ''

    if (newPhone && !validatePhoneNumber(newPhone)) {
      userManagement.form.phoneError = 'Vui lòng nhập đúng định dạng số điện thoại di động'
    }
  }
)

watch(
  () => [userManagement.searchKeyword, userManagement.departmentFilter, userManagement.roleFilter],
  () => {
    userManagement.currentPage = 1
  }
)

watch(
  () => filteredUsers.value.length,
  (total) => {
    const maxPage = Math.max(1, Math.ceil(total / Number(userManagement.pageSize)))
    if (userManagement.currentPage > maxPage) {
      userManagement.currentPage = maxPage
    }
  }
)

// Định dạng hiển thị thời gian
const formatTime = (timeStr) => formatDateTime(timeStr)

const getUserDefaultAvatarSrc = (user) => (user.uid ? generatePixelAvatar(user.uid) : '')

const isUserDeleteDisabled = (user) =>
  user.id === userStore.userId ||
  (user.role === 'superadmin' && userStore.userRole !== 'superadmin')

// Lấy danh sách người dùng
const fetchUsers = async () => {
  try {
    userManagement.loading = true
    const users = await userStore.getUsers()
    userManagement.users = users
    userManagement.error = null
  } catch (error) {
    console.error('Không lấy được danh sách người dùng:', error)
    userManagement.error = 'Không lấy được danh sách người dùng'
  } finally {
    userManagement.loading = false
  }
}

// Làm mới thông tin người dùng và bộ phận
const handleRefresh = async () => {
  if (userManagement.refreshing) return
  userManagement.refreshing = true
  try {
    await Promise.all([fetchUsers(), fetchDepartments()])
    message.success('Làm mới thành công')
  } catch (error) {
    console.error('Làm mới không thành công:', error)
    message.error('Làm mới không thành công')
  } finally {
    userManagement.refreshing = false
  }
}

// Mở hộp phương thức thêm người dùng
const showAddUserModal = () => {
  userManagement.modalTitle = 'Thêm người dùng'
  userManagement.editMode = false
  userManagement.editUserId = null
  userManagement.form = {
    username: '',
    generatedUid: '',
    phoneNumber: '',
    password: '',
    confirmPassword: '',
    role: 'user', // Vai trò mặc định là người dùng thông thường
    departmentId: null,
    usernameError: '',
    phoneError: ''
  }
  userManagement.displayPasswordFields = true
  userManagement.modalVisible = true
}

// Mở hộp phương thức chỉnh sửa người dùng
const showEditUserModal = (user) => {
  userManagement.modalTitle = 'Chỉnh sửa người dùng'
  userManagement.editMode = true
  userManagement.editUserId = user.id
  userManagement.form = {
    username: user.username,
    generatedUid: user.uid || '', // Chế độ chỉnh sửa hiển thị hiện cóuid
    phoneNumber: user.phone_number || '',
    password: '',
    confirmPassword: '',
    role: user.role,
    departmentId: user.department_id || null,
    usernameError: '',
    phoneError: ''
  }
  userManagement.displayPasswordFields = false // Trường mật khẩu không được hiển thị theo mặc định
  userManagement.modalVisible = true
}

// Xử lý việc gửi biểu mẫu của người dùng
const handleUserFormSubmit = async () => {
  try {
    // Xác minh đơn giản
    if (!userManagement.form.username.trim()) {
      message.error('Tên người dùng không thể trống')
      return
    }

    // Xác minh độ dài tên người dùng
    if (
      userManagement.form.username.trim().length < 2 ||
      userManagement.form.username.trim().length > 20
    ) {
      message.error('Độ dài tên người dùng phải nằm trong 2-20 giữa các ký tự')
      return
    }

    // Xác minh số điện thoại di động
    if (userManagement.form.phoneNumber && !validatePhoneNumber(userManagement.form.phoneNumber)) {
      message.error('Vui lòng nhập đúng định dạng số điện thoại di động')
      return
    }

    if (userManagement.displayPasswordFields) {
      if (!userManagement.form.password) {
        message.error('Mật khẩu không thể trống')
        return
      }

      if (userManagement.form.password !== userManagement.form.confirmPassword) {
        message.error('Mật khẩu nhập hai lần không nhất quán')
        return
      }
    }

    userManagement.loading = true

    // Quyết định tạo hoặc cập nhật người dùng dựa trên chế độ
    if (userManagement.editMode) {
      // Tạo đối tượng dữ liệu cập nhật
      const updateData = {
        username: userManagement.form.username.trim(),
        role: userManagement.form.role
      }

      // Thêm trường số điện thoại di động
      if (userManagement.form.phoneNumber) {
        updateData.phone_number = userManagement.form.phoneNumber
      }

      // Quản trị viên cấp cao có thể sửa đổi các phòng ban
      if (userStore.isSuperAdmin && userManagement.form.departmentId) {
        updateData.department_id = userManagement.form.departmentId
      }

      // Nếu trường mật khẩu được hiển thị và mật khẩu được điền vào，Chỉ cần cập nhật mật khẩu
      if (userManagement.displayPasswordFields && userManagement.form.password) {
        updateData.password = userManagement.form.password
      }

      await userStore.updateUser(userManagement.editUserId, updateData)
      message.success('Cập nhật người dùng thành công')
    } else {
      // Tạo người dùng mới
      const createData = {
        username: userManagement.form.username.trim(),
        password: userManagement.form.password,
        role: userManagement.form.role
      }

      // Quản trị viên cấp cao có thể chỉ định các phòng ban
      if (userStore.isSuperAdmin && userManagement.form.departmentId) {
        createData.department_id = userManagement.form.departmentId
      }

      // Thêm trường số điện thoại di động（Nếu điền vào）
      if (userManagement.form.phoneNumber) {
        createData.phone_number = userManagement.form.phoneNumber
      }

      await userStore.createUser(createData)
      message.success('Người dùng được tạo thành công')
    }

    // Truy xuất danh sách người dùng
    await fetchUsers()
    userManagement.modalVisible = false
  } catch (error) {
    console.error('Thao tác của người dùng không thành công:', error)
    message.error(error.message || 'Thao tác không thành công，Vui lòng thử lại sau')
  } finally {
    userManagement.loading = false
  }
}

// Xóa người dùng
const confirmDeleteUser = (user) => {
  // Bạn không thể xóa chính mình
  if (user.id === userStore.userId) {
    message.error('Không thể xóa tài khoản của chính mình')
    return
  }

  // Hộp thoại xác nhận
  Modal.confirm({
    title: 'Xác nhận xóa người dùng',
    content: `Bạn có chắc chắn muốn xóa người dùng này không? "${user.username}" ?？Hành động này không thể thay đổi được。`,
    okText: 'Xóa',
    okType: 'danger',
    cancelText: 'Hủy bỏ',
    async onOk() {
      try {
        userManagement.loading = true
        await userStore.deleteUser(user.id)
        message.success('Người dùng đã xóa thành công')
        // Truy xuất danh sách người dùng
        await fetchUsers()
      } catch (error) {
        console.error('Không thể xóa người dùng:', error)
        message.error(error.message || 'Xóa không thành công，Vui lòng thử lại sau')
      } finally {
        userManagement.loading = false
      }
    }
  })
}

const getRoleClass = (role) => {
  switch (role) {
    case 'superadmin':
      return 'role-superadmin'
    case 'admin':
      return 'role-admin'
    case 'user':
      return 'role-user'
    default:
      return 'role-default'
  }
}

// Lấy danh sách người dùng khi thành phần được gắn kết
onMounted(async () => {
  await fetchUsers()
  await fetchDepartments()
})
</script>

<style lang="less" scoped>
.user-management {
  .header-section {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 16px;
    margin-bottom: 16px;

    .header-content {
      flex: 1;
      min-width: 0;

      .section-title {
        font-size: 16px;
        font-weight: 500;
        color: var(--gray-900);
        line-height: 1.4;
        margin: 12px 0 12px;
      }

      .section-description {
        font-size: 14px;
        color: var(--gray-600);
        line-height: 1.4;
        margin: 0;
      }
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 8px;

      .refresh-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: 6px;
        transition: all 0.2s ease;

        &:hover {
          background: var(--gray-25);
        }

        .spin {
          animation: spin 1s linear infinite;
        }

        :deep(.ant-btn-loading-icon) {
          color: var(--gray-600);
        }
      }
    }
  }

  .filter-section {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;

    .search-input {
      width: 300px;
      max-width: 100%;

      :deep(.ant-input-prefix) {
        color: var(--gray-500);
        margin-right: 6px;
      }
    }

    .filter-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      margin-left: auto;
    }

    .filter-select {
      width: 150px;
    }
  }

  @media (max-width: 640px) {
    .filter-section {
      align-items: stretch;

      .search-input,
      .filter-actions {
        width: 100%;
      }

      .filter-actions {
        margin-left: 0;
      }

      .filter-select {
        flex: 1;
        min-width: 0;
      }
    }
  }

  .content-section {
    overflow: hidden;

    .error-message {
      padding: 16px 24px;
    }

    .cards-container {
      .empty-state {
        padding: 60px 20px;
        text-align: center;
      }

      .user-cards-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
        gap: 16px;
        // padding: 16px;

        .user-card {
          background: var(--gray-0);
          border: 1px solid var(--gray-150);
          border-radius: 8px;
          padding: 12px;

          transition: all 0.2s ease;
          box-shadow: 0 1px 3px var(--shadow-1);

          &:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            border-color: var(--gray-200);
          }

          .card-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 8px;
            margin-bottom: 10px;

            .user-info-main {
              display: flex;
              flex: 1;
              min-width: 0;
              gap: 12px;
              align-items: center;

              .user-avatar {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: var(--gray-50);
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
                flex-shrink: 0;

                .avatar-img {
                  width: 100%;
                  height: 100%;
                  object-fit: cover;
                }
              }

              .user-info-content {
                flex: 1;
                min-width: 0;

                .name-tag-row {
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  gap: 8px;
                  margin-bottom: 2px;
                  flex-wrap: wrap;

                  .username {
                    margin: 0;
                    font-size: 15px;
                    font-weight: 600;
                    color: var(--gray-900);
                    line-height: 1.2;
                    flex-shrink: 0;
                  }

                  .role-dept-badge {
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                    padding: 2px 8px 2px 4px;
                    background: var(--gray-50);
                    border-radius: 4px;

                    .role-icon-wrapper {
                      display: flex;
                      align-items: center;
                      justify-content: center;
                      width: 16px;
                      height: 16px;

                      &.role-superadmin {
                        color: var(--color-error-700);
                      }
                      &.role-admin {
                        color: var(--color-info-700);
                      }
                      &.role-user {
                        color: var(--color-success-700);
                      }
                    }

                    .dept-text {
                      font-size: 12px;
                      color: var(--gray-700);
                      font-weight: 500;
                    }
                  }
                }

                .user-id-row {
                  font-size: 12px;
                  color: var(--gray-500);
                  font-family: 'Monaco', 'Consolas', monospace;
                  line-height: 1.2;
                }
              }
            }

            .card-menu-trigger {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              width: 28px;
              height: 28px;
              flex-shrink: 0;
              color: var(--gray-600);

              &:hover,
              &:focus {
                color: var(--gray-700);
                background: var(--gray-50);
              }
            }
          }

          .card-content {
            .info-item {
              display: flex;
              justify-content: space-between;
              align-items: center;
              padding: 2px 0;
              border-bottom: 1px solid var(--gray-25);

              &:last-child {
                border-bottom: none;
              }

              .info-label {
                font-size: 12px;
                color: var(--gray-600);
                font-weight: 500;
                min-width: 70px;
              }

              .info-value {
                font-size: 12px;
                color: var(--gray-900);
                text-align: right;
                flex: 1;

                &.time-text {
                  color: var(--gray-700);
                }

                &.phone-text {
                  font-family: 'Monaco', 'Consolas', monospace;
                }
              }
            }
          }
        }
      }

      .pagination-section {
        display: flex;
        justify-content: flex-end;
        margin-top: 16px;
      }
    }
  }

  .time-text {
    font-size: 13px;
    color: var(--gray-700);
  }

  .phone-text,
  .user-id-text {
    font-size: 13px;
    color: var(--gray-900);
    font-family: 'Monaco', 'Consolas', monospace;
  }
}

.user-card-menu-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;

  &.danger {
    color: var(--color-error-700);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.user-modal {
  :deep(.ant-modal-header) {
    padding: 20px 24px 16px;
    border-bottom: 1px solid var(--gray-150);

    .ant-modal-title {
      font-size: 17px;
      font-weight: 600;
      color: var(--gray-900);
    }
  }

  :deep(.ant-modal-body) {
    padding: 20px 24px 24px;
  }

  .user-form {
    .form-item {
      margin-bottom: 16px;

      :deep(.ant-form-item-label) {
        padding-bottom: 6px;

        label {
          font-weight: 600;
          font-size: 13px;
          color: var(--gray-800);
        }
      }
    }

    .error-text {
      color: var(--color-error-500);
      font-size: 12px;
      margin-top: 4px;
      line-height: 1.3;
    }

    .help-text {
      color: var(--gray-600);
      font-size: 12px;
      margin-top: 4px;
      line-height: 1.3;
    }

    .password-toggle {
      margin-bottom: 16px;
      padding: 12px 16px;
      background: var(--gray-25);
      border-radius: 8px;
      border: 1px solid var(--gray-100);

      :deep(.ant-checkbox-wrapper) {
        font-weight: 500;
        color: var(--gray-700);
        font-size: 13px;
      }
    }
  }
}
</style>
