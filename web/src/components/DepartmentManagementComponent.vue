<template>
  <div class="department-management">
    <!-- vùng đầu -->
    <div class="header-section">
      <div class="header-content">
        <div class="section-title">Quản lý bộ phận</div>
        <p class="section-description">
          Phòng hệ thống quản lý，Người dùng thuộc bộ phận sẽ được cách ly và quản lý。
        </p>
      </div>
      <div class="header-actions">
        <a-button
          @click="handleRefresh"
          :loading="departmentManagement.refreshing"
          title="Làm mới"
          class="refresh-btn lucide-icon-btn"
        >
          <template #icon
            ><RefreshCw :size="16" :class="{ spin: departmentManagement.refreshing }"
          /></template>
        </a-button>
        <a-button type="primary" @click="showAddDepartmentModal" class="add-btn lucide-icon-btn">
          <template #icon><Plus :size="16" /></template>
          Thêm bộ phận
        </a-button>
      </div>
    </div>

    <!-- khu vực nội dung chính -->
    <div class="content-section">
      <a-spin :spinning="departmentManagement.loading">
        <div v-if="departmentManagement.error" class="error-message">
          <a-alert type="error" :message="departmentManagement.error" show-icon />
        </div>

        <template v-if="departmentManagement.departments.length > 0">
          <a-table
            :dataSource="departmentManagement.departments"
            :columns="columns"
            :rowKey="(record) => record.id"
            :pagination="false"
            class="department-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'name'">
                <div class="department-name">
                  <span class="name-text">{{ record.name }}</span>
                </div>
              </template>
              <template v-if="column.key === 'description'">
                <span class="description-text">{{ record.description || '-' }}</span>
              </template>
              <template v-if="column.key === 'userCount'">
                <span>{{ record.user_count ?? 0 }} mọi người</span>
              </template>
              <template v-if="column.key === 'action'">
                <a-space>
                  <a-tooltip title="Ban biên tập">
                    <a-button
                      type="text"
                      size="small"
                      @click="showEditDepartmentModal(record)"
                      class="action-btn lucide-icon-btn"
                    >
                      <SquarePen :size="14" />
                    </a-button>
                  </a-tooltip>
                  <a-tooltip title="Xóa bộ phận">
                    <a-button
                      type="text"
                      size="small"
                      danger
                      @click="confirmDeleteDepartment(record)"
                      :disabled="record.id === 1"
                      class="action-btn lucide-icon-btn"
                    >
                      <Trash2 :size="14" />
                    </a-button>
                  </a-tooltip>
                </a-space>
              </template>
            </template>
          </a-table>
        </template>

        <div v-else class="empty-state">
          <a-empty description="Chưa có dữ liệu bộ phận" />
        </div>
      </a-spin>
    </div>

    <!-- Hộp phương thức biểu mẫu bộ phận -->
    <a-modal
      v-model:open="departmentManagement.modalVisible"
      :title="departmentManagement.modalTitle"
      @ok="handleDepartmentFormSubmit"
      :confirmLoading="departmentManagement.loading"
      @cancel="departmentManagement.modalVisible = false"
      :maskClosable="false"
      width="520px"
      class="department-modal"
    >
      <a-form layout="vertical" class="department-form">
        <a-form-item label="Tên khoa" required class="form-item">
          <a-input
            v-model:value="departmentManagement.form.name"
            placeholder="Vui lòng nhập tên bộ phận"
            size="large"
            :maxlength="50"
          />
        </a-form-item>

        <a-form-item label="Mô tả bộ phận" class="form-item">
          <a-textarea
            v-model:value="departmentManagement.form.description"
            placeholder="Vui lòng nhập mô tả bộ phận（Tùy chọn）"
            :rows="3"
            :maxlength="255"
            show-count
          />
        </a-form-item>

        <a-divider v-if="!departmentManagement.editMode" />

        <template v-if="!departmentManagement.editMode">
          <p class="admin-section-hint">
            Khi tạo phòng ban cũng phải tạo quản trị viên，Quản trị viên này sẽ chịu trách nhiệm
            quản lý người dùng trong bộ phận này
          </p>

          <a-form-item label="Quản trị viênUID" required class="form-item">
            <a-input
              v-model:value="departmentManagement.form.adminUid"
              placeholder="Vui lòng nhập quản trị viênUID（3-20chữ cái/con số/gạch chân）"
              size="large"
              :maxlength="20"
              @blur="checkAdminUid"
            />
            <div v-if="departmentManagement.form.uidError" class="error-text">
              {{ departmentManagement.form.uidError }}
            </div>
            <div v-else class="help-text">cái này UID sẽ được sử dụng để đăng nhập</div>
          </a-form-item>

          <a-form-item label="Mật khẩu" required class="form-item">
            <a-input-password
              v-model:value="departmentManagement.form.adminPassword"
              placeholder="Vui lòng nhập mật khẩu quản trị viên"
              size="large"
              :maxlength="50"
            />
          </a-form-item>

          <a-form-item label="Xác nhận mật khẩu" required class="form-item">
            <a-input-password
              v-model:value="departmentManagement.form.adminConfirmPassword"
              placeholder="Vui lòng nhập lại mật khẩu"
              size="large"
              :maxlength="50"
            />
          </a-form-item>

          <a-form-item label="Số điện thoại di động（Tùy chọn）" class="form-item">
            <a-input
              v-model:value="departmentManagement.form.adminPhone"
              placeholder="Vui lòng nhập số điện thoại di động（Có sẵn để đăng nhập）"
              size="large"
              :maxlength="11"
            />
            <div v-if="departmentManagement.form.phoneError" class="error-text">
              {{ departmentManagement.form.phoneError }}
            </div>
          </a-form-item>
        </template>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { reactive, onMounted, watch } from 'vue'
import { notification, message, Modal } from 'ant-design-vue'
import { departmentApi, apiSuperAdminGet } from '@/apis'
import { Plus, RefreshCw, SquarePen, Trash2 } from 'lucide-vue-next'

// định nghĩa cột trong bảng
const columns = [
  {
    title: 'Tên khoa',
    dataIndex: 'name',
    key: 'name',
    width: 200
  },
  {
    title: 'Mô tả',
    dataIndex: 'description',
    key: 'description',
    ellipsis: true
  },
  {
    title: 'số lượng người dùng',
    dataIndex: 'user_count',
    key: 'userCount',
    width: 100,
    align: 'center'
  },
  {
    title: 'hoạt động',
    key: 'action',
    width: 120,
    align: 'center'
  }
]

// Tình trạng quản lý bộ phận
const departmentManagement = reactive({
  loading: false,
  refreshing: false,
  departments: [],
  error: null,
  modalVisible: false,
  modalTitle: 'Thêm bộ phận',
  editMode: false,
  editDepartmentId: null,
  form: {
    name: '',
    description: '',
    adminUid: '',
    adminPassword: '',
    adminConfirmPassword: '',
    adminPhone: '',
    uidError: '',
    phoneError: ''
  }
})

// Nhận danh sách bộ phận
const fetchDepartments = async () => {
  try {
    departmentManagement.loading = true
    departmentManagement.error = null
    const departments = await departmentApi.getDepartments()
    departmentManagement.departments = departments
  } catch (error) {
    console.error('Không lấy được danh sách phòng ban:', error)
    departmentManagement.error = 'Không lấy được danh sách phòng ban'
  } finally {
    departmentManagement.loading = false
  }
}

// Làm mới danh sách bộ phận
const handleRefresh = async () => {
  if (departmentManagement.refreshing) return
  departmentManagement.refreshing = true
  try {
    await fetchDepartments()
    message.success('Làm mới thành công')
  } catch (error) {
    console.error('Làm mới không thành công:', error)
    message.error('Làm mới không thành công')
  } finally {
    departmentManagement.refreshing = false
  }
}

// Mở hộp phương thức thêm bộ phận
const showAddDepartmentModal = () => {
  departmentManagement.modalTitle = 'Thêm bộ phận'
  departmentManagement.editMode = false
  departmentManagement.editDepartmentId = null
  departmentManagement.form = {
    name: '',
    description: '',
    adminUid: '',
    adminPassword: '',
    adminConfirmPassword: '',
    adminPhone: '',
    uidError: '',
    phoneError: ''
  }
  departmentManagement.modalVisible = true
}

// Mở hộp phương thức bộ phận chỉnh sửa
const showEditDepartmentModal = (department) => {
  departmentManagement.modalTitle = 'Ban biên tập'
  departmentManagement.editMode = true
  departmentManagement.editDepartmentId = department.id
  departmentManagement.form = {
    name: department.name,
    description: department.description || '',
    adminUid: '',
    adminPassword: '',
    adminConfirmPassword: '',
    adminPhone: '',
    uidError: '',
    phoneError: ''
  }
  departmentManagement.modalVisible = true
}

// Xác minh định dạng số điện thoại di động
const validatePhoneNumber = (phone) => {
  if (!phone) {
    return true // Số điện thoại di động tùy chọn
  }
  const phoneRegex = /^1[3-9]\d{9}$/
  return phoneRegex.test(phone)
}

// Theo dõi những thay đổi khi nhập số điện thoại di động
watch(
  () => departmentManagement.form.adminPhone,
  (newPhone) => {
    departmentManagement.form.phoneError = ''
    if (newPhone && !validatePhoneNumber(newPhone)) {
      departmentManagement.form.phoneError = 'Vui lòng nhập đúng định dạng số điện thoại di động'
    }
  }
)

// kiểm tra quản trị viênUIDNó có sẵn không
const checkAdminUid = async () => {
  const uid = departmentManagement.form.adminUid.trim()
  departmentManagement.form.uidError = ''

  if (!uid) {
    return
  }

  // Xác minh định dạng
  if (!/^[a-zA-Z0-9_]+$/.test(uid)) {
    departmentManagement.form.uidError = 'UIDChỉ có thể chứa các chữ cái、Số và dấu gạch dưới'
    return
  }

  if (uid.length < 3 || uid.length > 20) {
    departmentManagement.form.uidError = 'UIDĐộ dài phải nằm trong3-20giữa các ký tự'
    return
  }

  // Kiểm tra xem nó đã tồn tại chưa
  try {
    const result = await apiSuperAdminGet(`/api/auth/check-uid/${uid}`)
    if (!result.is_available) {
      departmentManagement.form.uidError = 'cáiUIDĐã sử dụng'
    }
  } catch (error) {
    console.error('Kiểm traUIDthất bại:', error)
  }
}

// Quy trình gửi biểu mẫu của bộ phận
const handleDepartmentFormSubmit = async () => {
  try {
    // Xác minh tên bộ phận
    if (!departmentManagement.form.name.trim()) {
      notification.error({ message: 'Tên bộ phận không được để trống' })
      return
    }

    if (departmentManagement.form.name.trim().length < 2) {
      notification.error({ message: 'Tên bộ phận ít nhất2nhân vật' })
      return
    }

    // Xác minh quản trị viênUID
    const adminUid = departmentManagement.form.adminUid.trim()
    if (!adminUid) {
      notification.error({ message: 'Vui lòng nhập quản trị viênUID' })
      return
    }

    if (!/^[a-zA-Z0-9_]+$/.test(adminUid)) {
      notification.error({ message: 'UIDChỉ có thể chứa các chữ cái、Số và dấu gạch dưới' })
      return
    }

    if (adminUid.length < 3 || adminUid.length > 20) {
      notification.error({ message: 'UIDĐộ dài phải nằm trong3-20giữa các ký tự' })
      return
    }

    if (departmentManagement.form.uidError) {
      notification.error({ message: 'Quản trị viênUIDĐã tồn tại hoặc có định dạng sai' })
      return
    }

    // Xác minh mật khẩu
    if (!departmentManagement.form.adminPassword) {
      notification.error({ message: 'Vui lòng nhập mật khẩu quản trị viên' })
      return
    }

    if (
      departmentManagement.form.adminPassword !== departmentManagement.form.adminConfirmPassword
    ) {
      notification.error({ message: 'Mật khẩu nhập hai lần không nhất quán' })
      return
    }

    // Xác minh số điện thoại di động
    if (
      departmentManagement.form.adminPhone &&
      !validatePhoneNumber(departmentManagement.form.adminPhone)
    ) {
      notification.error({ message: 'Vui lòng nhập đúng định dạng số điện thoại di động' })
      return
    }

    departmentManagement.loading = true

    if (departmentManagement.editMode) {
      // Bộ phận cập nhật
      await departmentApi.updateDepartment(departmentManagement.editDepartmentId, {
        name: departmentManagement.form.name.trim(),
        description: departmentManagement.form.description.trim() || undefined
      })
      notification.success({ message: 'Khoa được cập nhật thành công' })
    } else {
      // Tạo bộ phận，Đồng thời tạo quản trị viên
      await departmentApi.createDepartment({
        name: departmentManagement.form.name.trim(),
        description: departmentManagement.form.description.trim() || undefined,
        admin_uid: adminUid,
        admin_password: departmentManagement.form.adminPassword,
        admin_phone: departmentManagement.form.adminPhone || undefined
      })

      message.success(`Đã tạo thành công bộ phận，Quản trị viên "${adminUid}" Đã tạo`)
    }

    // Truy xuất danh sách bộ phận
    await fetchDepartments()
    departmentManagement.modalVisible = false
  } catch (error) {
    console.error('Hoạt động của bộ phận không thành công:', error)
    notification.error({
      message: 'Thao tác không thành công',
      description: error.message || 'Vui lòng thử lại sau'
    })
  } finally {
    departmentManagement.loading = false
  }
}

// Xóa bộ phận
const confirmDeleteDepartment = (department) => {
  Modal.confirm({
    title: 'Xác nhận xóa bộ phận',
    content: `Bạn có chắc chắn muốn xóa khoa này không? "${department.name}" ?？Hành động này không thể thay đổi được。Người dùng thuộc bộ phận này sẽ được chuyển sang bộ phận mặc định，Cấu hình cấp phòng và các phòng ban API Key Sẽ cùng nhau dọn dẹp。`,
    okText: 'Xóa',
    okType: 'danger',
    cancelText: 'Hủy bỏ',
    async onOk() {
      try {
        departmentManagement.loading = true
        await departmentApi.deleteDepartment(department.id)
        notification.success({ message: 'Đã xóa thành công bộ phận' })
        // Truy xuất danh sách bộ phận
        await fetchDepartments()
      } catch (error) {
        console.error('Không thể xóa bộ phận:', error)
        notification.error({
          message: 'Xóa không thành công',
          description: error.message || 'Vui lòng thử lại sau'
        })
      } finally {
        departmentManagement.loading = false
      }
    }
  })
}

// Lấy danh sách bộ phận khi thành phần được gắn kết
onMounted(() => {
  fetchDepartments()
})
</script>

<style lang="less" scoped>
.department-management {
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
      }
    }
  }

  .content-section {
    overflow: hidden;

    .error-message {
      padding: 16px 24px;
    }

    .empty-state {
      padding: 60px 20px;
      text-align: center;
    }

    .department-table {
      :deep(.ant-table-thead > tr > th) {
        background: var(--gray-50);
        font-weight: 500;
        padding: 8px 12px;
      }

      :deep(.ant-table-tbody > tr > td) {
        padding: 8px 12px;
      }

      .department-name {
        .name-text {
          font-weight: 500;
          color: var(--gray-900);
        }
      }

      .description-text {
        color: var(--gray-600);
      }

      .action-btn {
        padding: 4px 8px;
        border-radius: 6px;
        transition: all 0.2s ease;

        &:hover {
          background: var(--gray-25);
        }
      }
    }
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

.department-modal {
  :deep(.ant-modal-header) {
    padding: 20px 24px;
    border-bottom: 1px solid var(--gray-150);

    .ant-modal-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--gray-900);
    }
  }

  :deep(.ant-modal-body) {
    padding: 24px;
  }

  .department-form {
    .form-item {
      margin-bottom: 20px;

      :deep(.ant-form-item-label) {
        padding-bottom: 4px;

        label {
          font-weight: 500;
          color: var(--gray-900);
        }
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
}
</style>
