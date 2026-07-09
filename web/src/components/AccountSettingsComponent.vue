<template>
  <div class="account-settings">
    <div class="header-section">
      <div class="header-content">
        <div class="section-title">Cài đặt tài khoản</div>
        <p class="section-description">Quản lý thông tin tài khoản, thông tin cá nhân và API Key。</p>
      </div>
      <a-button class="lucide-icon-btn" :loading="refreshing" @click="refreshProfile">
        <template #icon><RefreshCw :size="16" :class="{ spin: refreshing }" /></template>
        Làm mới
      </a-button>
    </div>

    <div class="account-card profile-card">
      <div class="profile-left">
        <a-upload
          :show-upload-list="false"
          :before-upload="beforeUpload"
          @change="handleAvatarChange"
          accept="image/*"
        >
          <div class="avatar-upload" :class="{ uploading: avatarUploading }">
            <FallbackAvatar
              :src="userStore.avatar"
              :default-src="avatarDefaultSrc"
              :name="userStore.username"
              :seed="userStore.uid || userStore.username"
              kind="user"
              :size="80"
              shape="circle"
              :alt="userStore.username"
              class="account-avatar"
            />
            <div class="avatar-mask">
              <Upload v-if="!avatarUploading" :size="16" />
              <RefreshCw v-else :size="16" class="spin" />
              <span>{{ userStore.avatar ? 'Thay thế' : 'Tải lên' }}</span>
            </div>
          </div>
        </a-upload>

        <div class="profile-fields">
          <div class="profile-row editable-row">
            <span class="profile-label">Tên người dùng</span>
            <a-input
              v-if="editingField === 'username'"
              ref="usernameInput"
              v-model:value="profileDraft.username"
              class="inline-input"
              size="small"
              :max-length="20"
              :disabled="savingField === 'username'"
              @press-enter="saveField('username')"
              @keydown.esc.stop.prevent="cancelField"
              @blur="cancelField"
            />
            <button v-else type="button" class="editable-value" @click="startFieldEdit('username')">
              {{ userStore.username || 'Chưa thiết lập' }}
            </button>
          </div>
          <div class="profile-row editable-row">
            <span class="profile-label">Số điện thoại</span>
            <a-input
              v-if="editingField === 'phone_number'"
              ref="phoneInput"
              v-model:value="profileDraft.phone_number"
              class="inline-input"
              size="small"
              :max-length="11"
              :disabled="savingField === 'phone_number'"
              @press-enter="saveField('phone_number')"
              @keydown.esc.stop.prevent="cancelField"
              @blur="cancelField"
            />
            <button
              v-else
              type="button"
              class="editable-value"
              @click="startFieldEdit('phone_number')"
            >
              {{ userStore.phoneNumber || 'Chưa thiết lập' }}
            </button>
          </div>
          <div class="profile-row">
            <span class="profile-label">UID</span>
            <span class="profile-value mono">{{ userStore.uid || 'Chưa thiết lập' }}</span>
          </div>
        </div>
      </div>

      <div class="identity-panel">
        <div class="identity-item">
          <span class="identity-icon"><ShieldCheck :size="15" /></span>
          <span class="profile-label">Quyền</span>
          <span class="profile-value" :style="{ color: getRoleColor(userStore.userRole) }">
            {{ userRoleText }}
          </span>
        </div>
        <div class="identity-item">
          <span class="identity-icon"><Building2 :size="15" /></span>
          <span class="profile-label">Bộ phận</span>
          <span class="profile-value">{{ userStore.departmentName || 'Phòng ban mặc định' }}</span>
        </div>
      </div>
    </div>

    <div class="account-card apikey-card">
      <ApiKeyManagementComponent />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { Building2, RefreshCw, ShieldCheck, Upload } from 'lucide-vue-next'
import ApiKeyManagementComponent from '@/components/ApiKeyManagementComponent.vue'
import FallbackAvatar from '@/components/common/FallbackAvatar.vue'
import { useUserStore } from '@/stores/user'
import { generatePixelAvatar } from '@/utils/pixelAvatar'

const userStore = useUserStore()
const avatarUploading = ref(false)
const refreshing = ref(false)
const savingField = ref('')
const editingField = ref('')
const usernameInput = ref(null)
const phoneInput = ref(null)
const profileDraft = reactive({
  username: '',
  phone_number: ''
})

const avatarDefaultSrc = computed(() => (userStore.uid ? generatePixelAvatar(userStore.uid) : ''))

const userRoleText = computed(() => {
  switch (userStore.userRole) {
    case 'superadmin':
      return 'Quản trị viên cấp cao'
    case 'admin':
      return 'Quản trị viên'
    case 'user':
      return 'người dùng thông thường'
    default:
      return 'Vai trò không xác định'
  }
})

const syncProfileDraft = () => {
  profileDraft.username = userStore.username || ''
  profileDraft.phone_number = userStore.phoneNumber || ''
}

const refreshProfile = async () => {
  refreshing.value = true
  try {
    await userStore.getCurrentUser()
    syncProfileDraft()
    message.success('Thông tin tài khoản đã được làm mới')
  } catch (error) {
    console.error('Làm mới thông tin người dùng thất bại:', error)
    message.error('Làm mới thất bại：' + (error.message || 'Vui lòng thử lại sau'))
  } finally {
    refreshing.value = false
  }
}

const startFieldEdit = async (field) => {
  syncProfileDraft()
  editingField.value = field
  await nextTick()
  const inputRef = field === 'username' ? usernameInput.value : phoneInput.value
  inputRef?.focus?.()
}

const cancelField = () => {
  if (savingField.value) return
  editingField.value = ''
  syncProfileDraft()
}

const saveField = async (field) => {
  const payload = {}
  if (field === 'username') {
    const username = profileDraft.username.trim()
    if (username.length < 2 || username.length > 20) {
      message.error('Độ dài tên người dùng phải nằm trong khoảng 2-20 Giữa các ký tự')
      return
    }
    if (username === userStore.username) {
      cancelField()
      return
    }
    payload.username = username
  }

  if (field === 'phone_number') {
    const phoneNumber = profileDraft.phone_number.trim()
    if (phoneNumber && !validatePhoneNumber(phoneNumber)) {
      message.error('Vui lòng nhập định dạng số điện thoại chính xác')
      return
    }
    if (phoneNumber === (userStore.phoneNumber || '')) {
      cancelField()
      return
    }
    payload.phone_number = phoneNumber
  }

  savingField.value = field
  try {
    await userStore.updateProfile(payload)
    syncProfileDraft()
    editingField.value = ''
    message.success('Cập nhật hồ sơ thành công')
  } catch (error) {
    console.error('Cập nhật hồ sơ cá nhân thất bại:', error)
    message.error('Cập nhật thất bại：' + (error.message || 'Vui lòng thử lại sau'))
  } finally {
    savingField.value = ''
  }
}

const getRoleColor = (role) => {
  switch (role) {
    case 'superadmin':
      return 'var(--color-error-700)'
    case 'admin':
      return 'var(--color-primary-500)'
    case 'user':
      return 'var(--color-success-500)'
    default:
      return 'var(--gray-600)'
  }
}

const validatePhoneNumber = (phone) => {
  if (!phone) return true
  const phoneRegex = /^1[3-9]\d{9}$/
  return phoneRegex.test(phone)
}

const beforeUpload = (file) => {
  const isImage = file.type.startsWith('image/')
  if (!isImage) {
    message.error('Chỉ có thể tải lên tệp hình ảnh！')
    return false
  }

  const isLt5M = file.size / 1024 / 1024 < 5
  if (!isLt5M) {
    message.error('Kích thước hình ảnh không được vượt quá 5MB！')
    return false
  }

  return true
}

const handleAvatarChange = async (info) => {
  if (info.file.status === 'uploading') {
    avatarUploading.value = true
    return
  }

  if (info.file.status === 'done') {
    avatarUploading.value = false
    return
  }

  try {
    avatarUploading.value = true
    await userStore.uploadAvatar(info.file.originFileObj || info.file)
    message.success('Tải lên ảnh đại diện thành công！')
  } catch (error) {
    console.error('Tải lên ảnh đại diện thất bại:', error)
    message.error('Tải lên ảnh đại diện thất bại：' + (error.message || 'Vui lòng thử lại sau'))
  } finally {
    avatarUploading.value = false
  }
}

watch(() => [userStore.username, userStore.phoneNumber], syncProfileDraft, { immediate: true })
</script>

<style lang="less" scoped>
.account-settings {
  display: flex;
  flex-direction: column;
  gap: 16px;

  .account-card {
    padding: 18px;
    border-radius: 12px;
    background: var(--gray-0);
    border: 1px solid var(--gray-150);
  }

  .profile-card {
    display: flex;
    align-items: stretch;
    justify-content: space-between;
    gap: 20px;
    background: var(--gray-25);

    @media (max-width: 760px) {
      flex-direction: column;
    }
  }

  .profile-left {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 18px;
    flex: 1;

    @media (max-width: 520px) {
      align-items: flex-start;
      flex-direction: column;
    }
  }

  .avatar-upload {
    width: 80px;
    height: 80px;
    position: relative;
    cursor: pointer;
    border-radius: 50%;
    overflow: hidden;
    flex: 0 0 auto;

    .account-avatar {
      width: 80px;
      height: 80px;
      border: 3px solid var(--gray-0);
    }

    &:hover .avatar-mask,
    &.uploading .avatar-mask {
      opacity: 1;
    }
  }

  .avatar-mask {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    color: var(--gray-0);
    font-size: 12px;
    background: rgba(0, 0, 0, 0.48);
    opacity: 0;
    transition: opacity 0.2s ease;
  }

  .profile-fields {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex: 1;
  }

  .profile-row {
    min-width: 0;
    display: grid;
    grid-template-columns: 56px minmax(0, 1fr);
    align-items: center;
    gap: 10px;
  }

  .profile-label {
    color: var(--gray-600);
    font-size: 13px;
    flex-shrink: 0;
  }

  .profile-value,
  .editable-value {
    min-width: 0;
    color: var(--gray-900);
    font-size: 14px;
    font-weight: 500;
    line-height: 24px;
    overflow: hidden;
    text-align: left;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .editable-value {
    width: fit-content;
    max-width: 100%;
    padding: 0 6px;
    margin-left: -6px;
    border: none;
    border-radius: 6px;
    background: transparent;
    cursor: pointer;

    &:hover {
      color: var(--main-color);
      background: var(--main-5);
    }
  }

  .inline-input {
    width: min(260px, 100%);
  }

  .identity-panel {
    min-width: 220px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 12px;
    padding: 14px;
    border-radius: 10px;
    background: var(--gray-0);

    @media (max-width: 760px) {
      min-width: 0;
    }
  }

  .identity-item {
    min-width: 0;
    display: grid;
    grid-template-columns: 20px 42px minmax(0, 1fr);
    align-items: center;
    gap: 8px;
  }

  .identity-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border-radius: 6px;
    background: var(--gray-50);
    color: var(--gray-500);
  }

  .mono {
    font-family: 'Monaco', 'Consolas', monospace;
  }

  .apikey-card {
    padding: 16px;
  }
}

:deep(.spin) {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}
</style>
