<template>
  <div class="login-view" :class="{ 'has-alert': serverStatus === 'error' }">
    <!-- Lời nhắc trạng thái dịch vụ -->
    <div v-if="serverStatus === 'error'" class="server-status-alert">
      <div class="alert-content">
        <exclamation-circle-icon class="alert-icon" size="20" />
        <div class="alert-text">
          <div class="alert-title">Kết nối máy chủ thất bại</div>
          <div class="alert-message">{{ serverError }}</div>
        </div>
        <a-button type="link" size="small" @click="checkServerHealth" :loading="healthChecking">
          Thử lại
        </a-button>
      </div>
    </div>

    <!-- điều hướng hàng đầu：thương hiệu & Nút hành động -->
    <nav class="login-navbar">
      <div class="navbar-content">
        <div class="brand-container" @click="goHome" style="cursor: pointer">
          <img v-if="brandLogo" :src="brandLogo" alt="logo" class="brand-logo" />
          <h1 class="brand-text">
            <span v-if="brandOrgName" class="brand-org">{{ brandOrgName }}</span>
            <span v-if="brandOrgName && brandName !== brandOrgName" class="brand-separator"></span>
            <span class="brand-main">{{ brandName }}</span>
          </h1>
        </div>
      </div>
    </nav>

    <!-- Khu vực nội dung chính：thẻ trung tâm -->
    <main class="login-main">
      <div class="login-card">
        <!-- Hình bên trái -->
        <div class="card-side is-image">
          <img :src="loginBgImage" alt="Nền đăng nhập" class="login-bg-image" />
        </div>

        <!-- Mẫu đúng -->
        <div class="card-side is-form">
          <div class="form-wrapper">
            <header class="form-header">
              <!-- Nếu nó đang khởi tạo，Hiển thị tiêu đề cụ thể -->
              <h2 v-if="isFirstRun" class="init-title">
                Khởi tạo hệ thống, vui lòng tạo tài khoản Quản trị viên tối cao
              </h2>
              <p v-else class="welcome-text">Chào mừng bạn đăng nhập</p>
            </header>

            <div class="login-content" :class="{ 'is-initializing': isFirstRun }">
              <!-- Khởi tạo biểu mẫu quản trị -->
              <div v-if="isFirstRun" class="login-form login-form--init">
                <a-form :model="adminForm" @finish="handleInitialize" layout="vertical">
                  <a-form-item
                    label="UID"
                    name="uid"
                    :rules="[
                      { required: true, message: 'Vui lòng nhập UID' },
                      {
                        pattern: /^[a-zA-Z0-9_]+$/,
                        message: 'UID chỉ được chứa chữ cái, số và dấu gạch dưới'
                      },
                      {
                        min: 3,
                        max: 20,
                        message: 'Độ dài UID phải từ 3 đến 20 ký tự'
                      }
                    ]"
                  >
                    <a-input
                      v-model:value="adminForm.uid"
                      placeholder="Vui lòng nhập UID (3-20 ký tự)"
                      :maxlength="20"
                    />
                  </a-form-item>

                  <a-form-item
                    label="Số điện thoại (tùy chọn)"
                    name="phone_number"
                    :rules="[
                      {
                        validator: async (rule, value) => {
                          if (!value || value.trim() === '') {
                            return // Cho phép giá trị NULL
                          }
                          const phoneRegex = /^1[3-9]\d{9}$/
                          if (!phoneRegex.test(value)) {
                            throw new Error('Vui lòng nhập định dạng số điện thoại chính xác')
                          }
                        }
                      }
                    ]"
                  >
                    <a-input
                      v-model:value="adminForm.phone_number"
                      placeholder="Có thể dùng để đăng nhập, có thể bỏ trống"
                      :max-length="11"
                    />
                  </a-form-item>

                  <a-form-item
                    label="Mật khẩu"
                    name="password"
                    :rules="[{ required: true, message: 'Vui lòng nhập mật khẩu' }]"
                  >
                    <a-input-password v-model:value="adminForm.password" prefix-icon="lock" />
                  </a-form-item>

                  <a-form-item
                    label="Xác nhận mật khẩu"
                    name="confirmPassword"
                    :rules="[
                      { required: true, message: 'Vui lòng xác nhận mật khẩu' },
                      { validator: validateConfirmPassword }
                    ]"
                  >
                    <a-input-password
                      v-model:value="adminForm.confirmPassword"
                      prefix-icon="lock"
                    />
                  </a-form-item>

                  <a-form-item v-if="showAgreementConsent" class="agreement-form-item">
                    <div class="agreement-row">
                      <a-checkbox v-model:checked="agreementAccepted">
                        Đăng nhập đồng nghĩa với việc bạn đồng ý với
                        <a
                          class="agreement-link"
                          :href="userAgreementUrl"
                          target="_blank"
                          rel="noopener noreferrer"
                          @click.stop
                          >《Điều khoản người dùng》</a
                        >
                        <a
                          class="agreement-link"
                          :href="privacyPolicyUrl"
                          target="_blank"
                          rel="noopener noreferrer"
                          @click.stop
                          >《Chính sách bảo mật》</a
                        >
                      </a-checkbox>
                    </div>
                  </a-form-item>

                  <a-form-item>
                    <a-button type="primary" html-type="submit" :loading="loading" block
                      >Tạo tài khoản Quản trị viên</a-button
                    >
                  </a-form-item>
                </a-form>
              </div>

              <!-- Mẫu đăng nhập -->
              <div v-else class="login-form">
                <a-form :model="loginForm" @finish="handleLogin" layout="vertical">
                  <a-form-item
                    label="Tài khoản đăng nhập"
                    name="loginId"
                    :rules="[{ required: true, message: 'Vui lòng nhập UID hoặc số điện thoại' }]"
                  >
                    <a-input v-model:value="loginForm.loginId" placeholder="UID hoặc số điện thoại">
                      <template #prefix>
                        <user-icon size="18" />
                      </template>
                    </a-input>
                  </a-form-item>

                  <a-form-item
                    label="Mật khẩu"
                    name="password"
                    :rules="[{ required: true, message: 'Vui lòng nhập mật khẩu' }]"
                  >
                    <a-input-password v-model:value="loginForm.password">
                      <template #prefix>
                        <lock-icon size="18" />
                      </template>
                    </a-input-password>
                  </a-form-item>

                  <a-form-item v-if="showAgreementConsent" class="agreement-form-item">
                    <div class="agreement-row">
                      <a-checkbox v-model:checked="agreementAccepted">
                        Đăng nhập đồng nghĩa với việc bạn đồng ý với
                        <a
                          class="agreement-link"
                          :href="userAgreementUrl"
                          target="_blank"
                          rel="noopener noreferrer"
                          @click.stop
                          >《Điều khoản người dùng》</a
                        >
                        <a
                          class="agreement-link"
                          :href="privacyPolicyUrl"
                          target="_blank"
                          rel="noopener noreferrer"
                          @click.stop
                          >《Chính sách bảo mật》</a
                        >
                      </a-checkbox>
                    </div>
                  </a-form-item>

                  <a-form-item>
                    <a-button
                      type="primary"
                      html-type="submit"
                      :loading="loading"
                      :disabled="isLocked"
                      block
                      size="large"
                    >
                      <span v-if="isLocked"
                        >Tài khoản đã bị khóa {{ formatTime(lockRemainingTime) }}</span
                      >
                      <span v-else>Đăng nhập</span>
                    </a-button>
                  </a-form-item>
                </a-form>

                <!-- OIDC Tùy chọn đăng nhập  -->
                <div v-if="oidcChecking || oidcEnabled" class="third-party-login">
                  <div class="divider">
                    <span>Hoặc sử dụng các phương thức sau để đăng nhập</span>
                  </div>
                  <div class="login-icons">
                    <!-- Màn hình bộ xương hiển thị trong quá trình kiểm tra -->
                    <div v-if="oidcChecking" class="login-skeleton">
                      <a-skeleton-button block size="large" :active="true" />
                    </div>
                    <!-- Nút hiển thị sau khi kiểm tra hoàn tất -->
                    <a-button
                      v-else
                      type="default"
                      size="large"
                      block
                      :loading="oidcLoading"
                      @click="handleOIDCLogin"
                    >
                      <template #icon>
                        <key-icon size="18" />
                      </template>
                      {{ oidcButtonText }}
                    </a-button>
                  </div>
                </div>
              </div>

              <!-- Thông báo lỗi -->
              <div v-if="errorMessage" class="error-message">
                {{ errorMessage }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- cuối trang：Thông tin bản quyền, v.v. -->
    <footer class="page-footer">
      <div class="footer-links">
        <a href="https://github.com/xerrors" target="_blank">Liên hệ với chúng tôi</a>
        <span class="divider">|</span>
        <a href="https://github.com/xerrors/Yuxi" target="_blank">Hướng dẫn sử dụng</a>
      </div>
      <div class="copyright">
        &copy; {{ new Date().getFullYear() }} {{ brandName }}. All Rights Reserved.
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useInfoStore } from '@/stores/info'
import { useAgentStore } from '@/stores/agent'
import { message } from 'ant-design-vue'
import { healthApi } from '@/apis/system_api'
import { authApi } from '@/apis/auth_api'
import {
  User as UserIcon,
  Lock as LockIcon,
  Key as KeyIcon,
  AlertCircle as ExclamationCircleIcon
} from 'lucide-vue-next'
import { tryAutoStartOIDC, sanitizeRedirect } from '@/utils/oidcAutoStart'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const infoStore = useInfoStore()
const agentStore = useAgentStore()

// Dữ liệu hiển thị thương hiệu
const loginBgImage = computed(() => {
  return infoStore.organization?.login_bg || '/login-bg.jpg'
})
const brandLogo = computed(() => {
  return infoStore.organization?.logo || ''
})
const brandOrgName = computed(() => {
  return infoStore.organization?.name?.trim() || ''
})
const brandName = computed(() => {
  const orgName = brandOrgName.value
  const brandNameRaw = infoStore.branding?.name?.trim() || 'Yuxi'

  if (orgName && brandNameRaw && orgName !== brandNameRaw) {
    return brandNameRaw
  }

  return orgName || brandNameRaw
})
const userAgreementUrl = computed(() => {
  return infoStore.footer?.user_agreement_url?.trim() || ''
})
const privacyPolicyUrl = computed(() => {
  return infoStore.footer?.privacy_policy_url?.trim() || ''
})
const showAgreementConsent = computed(() => {
  return Boolean(userAgreementUrl.value && privacyPolicyUrl.value)
})

// Trạng thái
const isFirstRun = ref(false)
const loading = ref(false)
const errorMessage = ref('')
const agreementAccepted = ref(false)
const serverStatus = ref('loading')
const serverError = ref('')
const healthChecking = ref(false)

// OIDC Trạng thái liên quan
const oidcEnabled = ref(false)
const oidcLoading = ref(false)
const oidcChecking = ref(true)
const oidcButtonText = ref('OIDC Đăng nhập')

// Trạng thái liên quan đến khóa đăng nhập
const isLocked = ref(false)
const lockRemainingTime = ref(0)
const lockCountdown = ref(null)

// Mẫu đăng nhập
const loginForm = reactive({
  loginId: '', // hỗ trợuidhoặcphone_numberĐăng nhập
  password: ''
})

// Biểu mẫu khởi tạo quản trị viên
const adminForm = reactive({
  uid: '', // Nhập trực tiếp thay thếuid
  password: '',
  confirmPassword: '',
  phone_number: '' // Trường số điện thoại di động（Tùy chọn）
})

const goHome = () => {
  router.push('/')
}

// Dọn dẹp đồng hồ đếm ngược
const clearLockCountdown = () => {
  if (lockCountdown.value) {
    clearInterval(lockCountdown.value)
    lockCountdown.value = null
  }
}

// Bắt đầu đếm ngược khóa
const startLockCountdown = (remainingSeconds) => {
  clearLockCountdown()
  isLocked.value = true
  lockRemainingTime.value = remainingSeconds

  lockCountdown.value = setInterval(() => {
    lockRemainingTime.value--
    if (lockRemainingTime.value <= 0) {
      clearLockCountdown()
      isLocked.value = false
      errorMessage.value = ''
    }
  }, 1000)
}

// Định dạng hiển thị thời gian
const formatTime = (seconds) => {
  if (seconds < 60) {
    return `${seconds} giây`
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes} phút ${remainingSeconds} giây`
  } else if (seconds < 86400) {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours} giờ ${minutes} phút`
  } else {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    return `${days} ngày ${hours} giờ`
  }
}

// Xác minh xác nhận mật khẩu
const validateConfirmPassword = async (rule, value) => {
  if (value === '') {
    throw new Error('Vui lòng xác nhận mật khẩu')
  }
  if (value !== adminForm.password) {
    throw new Error('Hai mật khẩu đã nhập không khớp')
  }
}

const ensureAgreementAccepted = () => {
  if (!showAgreementConsent.value || agreementAccepted.value) {
    return true
  }

  const warningMessage =
    'Vui lòng đọc và đồng ý với 《Điều khoản người dùng》 và 《Chính sách bảo mật》 trước'
  message.warning(warningMessage)
  return false
}

// Xử lý đăng nhập
const handleLogin = async () => {
  // nếu hiện đang bị khóa，Đăng nhập không được phép
  if (isLocked.value) {
    message.warning(`Tài khoản bị khóa, vui lòng đợi ${formatTime(lockRemainingTime.value)}`)
    return
  }

  if (!ensureAgreementAccepted()) {
    return
  }

  try {
    loading.value = true
    errorMessage.value = ''
    clearLockCountdown()

    await userStore.login({
      loginId: loginForm.loginId,
      password: loginForm.password
    })

    message.success('Đăng nhập thành công')

    // Nhận đường dẫn chuyển hướng
    const redirectPath = sessionStorage.getItem('redirect') || '/'
    sessionStorage.removeItem('redirect') // Xóa thông tin chuyển hướng

    // Xác định mục tiêu chuyển hướng dựa trên vai trò của người dùng
    if (redirectPath === '/') {
      // Chuyển đến trang trò chuyện một cách thống nhất（Quản trị viên chia sẻ cùng giao diện trò chuyện với người dùng thông thường）
      try {
        await agentStore.initialize()
        router.push('/agent')
      } catch (error) {
        console.error('Không thể lấy được thông tin đại lý:', error)
        router.push('/agent')
      }
    } else {
      // Chuyển đến các đường dẫn đặt trước khác
      router.push(redirectPath)
    }
  } catch (error) {
    console.error('Đăng nhập không thành công:', error)

    // Kiểm tra xem đó có phải là lỗi khóa không（HTTP 423）
    if (error.status === 423) {
      // Cố gắng lấy thời gian còn lại từ tiêu đề phản hồi
      let remainingTime = 0
      if (error.headers && error.headers.get) {
        const lockRemainingHeader = error.headers.get('X-Lock-Remaining')
        if (lockRemainingHeader) {
          remainingTime = parseInt(lockRemainingHeader)
        }
      }

      // Nếu nó không được lấy từ đầu，Cố gắng phân tích từ thông báo lỗi
      if (remainingTime === 0) {
        const lockTimeMatch = error.message.match(/(\d+)\s*giây/)
        if (lockTimeMatch) {
          remainingTime = parseInt(lockTimeMatch[1])
        }
      }

      if (remainingTime > 0) {
        startLockCountdown(remainingTime)
        errorMessage.value = `Do đăng nhập thất bại nhiều lần, tài khoản đã bị khóa ${formatTime(remainingTime)}`
      } else {
        errorMessage.value = error.message || 'Tài khoản bị khóa, vui lòng thử lại sau'
      }
    } else {
      errorMessage.value =
        error.message || 'Đăng nhập thất bại, vui lòng kiểm tra tài khoản và mật khẩu'
    }
  } finally {
    loading.value = false
  }
}

// Quy trình OIDC Đăng nhập
const handleOIDCLogin = async () => {
  if (!ensureAgreementAccepted()) {
    return
  }

  try {
    oidcLoading.value = true
    errorMessage.value = ''

    // Nhận OIDC Đăng nhập URL
    const response = await authApi.getOIDCLoginUrl()
    if (response.login_url) {
      // Lưu đường dẫn hiện tại，để quay lại sau khi đăng nhập
      const redirectPath =
        sessionStorage.getItem('redirect') || router.currentRoute.value.query.redirect || '/'
      sessionStorage.setItem('oidc_redirect', redirectPath)

      // nhảy tới OIDC Provider
      window.location.href = response.login_url
    } else {
      errorMessage.value = 'Lấy địa chỉ đăng nhập OIDC thất bại'
    }
  } catch (error) {
    console.error('OIDC Đăng nhập không thành công:', error)
    errorMessage.value = error.message || 'Đăng nhập OIDC thất bại, vui lòng thử lại'
  } finally {
    oidcLoading.value = false
  }
}

// Kiểm tra OIDC Cấu hình
const checkOIDCConfig = async () => {
  oidcChecking.value = true
  try {
    const config = await authApi.getOIDCConfig()
    oidcEnabled.value = config.enabled
    if (config.provider_name) {
      oidcButtonText.value = config.provider_name
    }
    return config
  } catch (error) {
    console.error('Kiểm tra OIDC Cấu hình không thành công:', error)
    oidcEnabled.value = false
    return null
  } finally {
    oidcChecking.value = false
  }
}

// Xử lý quản trị viên khởi tạo
const handleInitialize = async () => {
  if (!ensureAgreementAccepted()) {
    return
  }

  try {
    loading.value = true
    errorMessage.value = ''

    if (adminForm.password !== adminForm.confirmPassword) {
      errorMessage.value = 'Hai mật khẩu đã nhập không khớp'
      return
    }

    await userStore.initialize({
      uid: adminForm.uid,
      password: adminForm.password,
      phone_number: adminForm.phone_number || null // Chuyển đổi chuỗi trống thànhnull
    })

    message.success('Tạo tài khoản quản trị viên thành công')
    router.push('/')
  } catch (error) {
    console.error('Khởi tạo không thành công:', error)
    errorMessage.value = error.message || 'Khởi tạo thất bại, vui lòng thử lại'
  } finally {
    loading.value = false
  }
}

// Kiểm tra xem đây có phải là lần chạy đầu tiên không
const checkFirstRunStatus = async () => {
  try {
    loading.value = true
    const isFirst = await userStore.checkFirstRun()
    isFirstRun.value = isFirst
  } catch (error) {
    console.error('Kiểm tra trạng thái lần chạy đầu tiên không thành công:', error)
    errorMessage.value = 'Hệ thống có lỗi, vui lòng thử lại sau'
  } finally {
    loading.value = false
  }
}

// Kiểm tra tình trạng sức khỏe của máy chủ
const checkServerHealth = async () => {
  try {
    healthChecking.value = true
    const response = await healthApi.checkHealth()
    if (response.status === 'ok') {
      serverStatus.value = 'ok'
    } else {
      serverStatus.value = 'error'
      serverError.value = response.message || 'Trạng thái máy chủ bất thường'
    }
  } catch (error) {
    console.error('Không thể kiểm tra tình trạng sức khỏe của máy chủ:', error)
    serverStatus.value = 'error'
    serverError.value =
      error.message || 'Không thể kết nối đến máy chủ, vui lòng kiểm tra kết nối mạng'
  } finally {
    healthChecking.value = false
  }
}

// Khi thành phần được gắn
onMounted(async () => {
  // Nếu đăng nhập，nhấn redirect Nhảy tham số（Không phải lúc nào cũng nhảy về trang chủ）
  if (userStore.isLoggedIn) {
    router.push(sanitizeRedirect(route.query.redirect))
    return
  }

  // hiển thị OIDC Thông báo lỗi xác thực thất bại（Được thực hiện bởi chuyển hướng phụ trợ）
  if (route.query.oidc_error) {
    errorMessage.value = String(route.query.oidc_error)
  }

  // Đầu tiên hãy kiểm tra tình trạng sức khỏe của máy chủ
  await checkServerHealth()

  // Kiểm tra xem đây có phải là lần chạy đầu tiên không
  await checkFirstRunStatus()

  // Nếu ở trạng thái chạy đầu tiên，không cần OIDC Đăng nhập tự động
  if (isFirstRun.value) {
    return
  }

  // Kiểm tra OIDC Sau khi cấu hình xong，Cố gắng kích hoạt tự động OIDC Đăng nhập（Kịch bản nhảy xuyên hệ thống）
  const config = await checkOIDCConfig()
  if (config && config.enabled) {
    const autoStarted = await tryAutoStartOIDC(async () => await authApi.getOIDCLoginUrl(), config)
    // Nếu khởi xướng OIDC Nhảy，Trang sẽ được chuyển hướng，Không cần phải tiếp tục
    if (autoStarted) return
  }
})

// Hẹn giờ dọn dẹp khi thành phần được gỡ cài đặt
onUnmounted(() => {
  clearLockCountdown()
})
</script>

<style lang="less" scoped>
.login-view {
  min-height: 100vh;
  width: 100%;
  position: relative;
  display: flex;
  flex-direction: column;
  background-color: var(--gray-10);
  background-image: radial-gradient(var(--gray-200) 1px, transparent 1px);
  background-size: 24px 24px;

  &.has-alert {
    padding-top: 60px;
  }
}

/* Unified Navbar */
.login-navbar {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  padding: 32px 0;
  z-index: 10;

  .navbar-content {
    max-width: 1500px; /* Constraint the width */
    margin: 0 auto;
    padding: 0 40px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    .brand-container {
      display: flex;
      align-items: center;
      gap: 12px;
    }
  }
}

.brand-text {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1;
  display: flex;
  align-items: center;
  gap: 12px;

  .brand-org {
    color: var(--gray-700);
    font-weight: 600;
  }

  .brand-separator {
    width: 4px;
    height: 4px;
    background-color: var(--gray-400);
    border-radius: 50%;
    font-weight: 600;
  }

  .brand-main {
    color: var(--main-color);
    font-weight: 600;
  }
}

.brand-logo {
  height: 32px;
  width: auto;
  object-fit: contain;
}

.top-logo {
  height: 32px;
  width: auto;
  object-fit: contain;
}

.back-home-btn {
  color: var(--gray-600);
  font-size: 14px;
  &:hover {
    color: var(--main-color);
    background-color: transparent;
  }
}

/* Main Content: Card Layout */
.login-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  padding-top: 80px; /* Add space for navbar */
}

.login-card {
  width: 900px;
  max-width: 95vw;
  height: 560px;
  background: var(--gray-0);
  border-radius: 16px;
  box-shadow: 0 0px 40px var(--shadow-1);
  display: flex;
  overflow: hidden;
}

.card-side {
  position: relative;
}

/* Image Side */
.card-side.is-image {
  flex: 1.4;
  background-color: var(--main-10);
  overflow: hidden;

  .login-bg-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
  }
}

/* Form Side */
.card-side.is-form {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.form-wrapper {
  width: 100%;
  max-width: 320px;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.form-header {
  text-align: left;
  .welcome-text {
    font-size: 14px;
    font-weight: 600;
    color: var(--gray-500);
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  .init-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--main-color);
    margin: 0;
    line-height: 1.4;
  }
}

.login-form {
  :deep(.ant-input-affix-wrapper) {
    padding: 10px 12px;
    border-radius: 8px;
  }
  :deep(.ant-btn) {
    height: 44px;
    font-size: 16px;
    border-radius: 8px;
  }
  :deep(.ant-input-prefix) {
    margin-right: 8px;
    color: var(--gray-500);
  }
}

.login-form.login-form--init :deep(.ant-form-item) {
  margin-bottom: 14px;
}

.third-party-login {
  margin-top: 16px;
  .divider {
    position: relative;
    text-align: center;
    margin: 24px 0 16px;
    &::before,
    &::after {
      content: '';
      position: absolute;
      top: 50%;
      width: 30%;
      height: 1px;
      background-color: var(--gray-200);
    }
    &::before {
      left: 0;
    }
    &::after {
      right: 0;
    }
    span {
      display: inline-block;
      padding: 0 8px;
      background-color: var(--gray-0);
      color: var(--gray-400);
      font-size: 12px;
    }
  }

  .login-icons {
    :deep(.ant-btn) {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      border-color: var(--gray-300);
      color: var(--gray-700);

      &:hover {
        border-color: var(--main-color);
        color: var(--main-color);
        background-color: var(--main-10);
      }

      .anticon,
      svg {
        color: var(--main-color);
      }
    }
  }

  /* sửa chữa：Thêm kiểu màn hình khung xương */
  .login-skeleton {
    :deep(.ant-skeleton-button) {
      width: 100% !important;
      height: 44px;
      border-radius: 8px;
    }
  }
}

.agreement-form-item {
  margin-bottom: 12px;
}

.agreement-row {
  font-size: 13px;
  color: var(--gray-600);
  line-height: 1.6;

  :deep(.ant-checkbox-wrapper) {
    display: inline-flex;
    align-items: flex-start;
  }

  :deep(.ant-checkbox + span) {
    padding-inline-start: 8px;
  }
}

.agreement-link {
  color: var(--main-color);

  &:hover {
    text-decoration: underline;
  }
}

.error-message {
  margin-top: 16px;
  padding: 10px 12px;
  background-color: var(--color-error-50);
  border: 1px solid color-mix(in srgb, var(--color-error-500) 25%, transparent);
  border-radius: 6px;
  color: var(--color-error-700);
  font-size: 13px;
  text-align: center;
}

/* Page Footer */
.page-footer {
  padding: 24px;
  text-align: center;
}

.footer-links {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-bottom: 8px;

  a {
    color: var(--gray-500);
    font-size: 13px;
    &:hover {
      color: var(--main-color);
    }
  }

  .divider {
    color: var(--gray-300);
    font-size: 12px;
  }
}

.copyright {
  font-size: 12px;
  color: var(--gray-400);
}

/* Server Status Alert */
.server-status-alert {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 12px 20px;
  background: var(--color-error-500);
  color: var(--gray-0);
  z-index: 1000;

  .alert-content {
    display: flex;
    align-items: center;
    max-width: 1500px;
    margin: 0 auto;

    .alert-icon {
      font-size: 20px;
      margin-right: 12px;
      color: var(--gray-0);
    }

    .alert-text {
      flex: 1;

      .alert-title {
        font-weight: 600;
        font-size: 16px;
        margin-bottom: 2px;
      }

      .alert-message {
        font-size: 14px;
        opacity: 0.9;
      }
    }

    :deep(.ant-btn-link) {
      color: var(--gray-0);
      border-color: var(--gray-0);

      &:hover {
        color: var(--gray-0);
        background-color: color-mix(in srgb, var(--gray-0) 10%, transparent);
      }
    }
  }
}

/* Responsive */
@media (max-width: 1280px) {
  .login-navbar .navbar-content {
    padding: 0 40px;
  }
}

@media (max-width: 768px) {
  .login-navbar .navbar-content {
    padding: 0 20px;
  }

  .brand-text {
    font-size: 20px;
  }

  .login-card {
    flex-direction: column;
    height: auto;
    max-height: none;
    width: 100%;
    margin-top: 20px;
  }

  .card-side.is-image {
    display: none;
  }

  .card-side.is-form {
    padding: 40px 20px;
  }
}
</style>
