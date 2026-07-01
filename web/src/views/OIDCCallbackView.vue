<template>
  <div class="oidc-callback-view">
    <div class="callback-container">
      <div v-if="loading" class="loading-section">
        <a-spin size="large" />
        <p class="loading-text">Đang xử lý đăng nhập...</p>
      </div>

      <div v-else-if="error" class="error-section">
        <a-result status="error" :title="errorTitle" :sub-title="errorMessage">
          <template #extra>
            <a-button type="primary" @click="goToLogin"> Quay lại trang đăng nhập </a-button>
          </template>
        </a-result>
      </div>

      <div v-else class="success-section">
        <a-result status="success" title="Đăng nhập thành công" sub-title="Chuyển hướng...">
          <template #icon>
            <a-spin />
          </template>
        </a-result>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useAgentStore } from '@/stores/agent'
import { authApi } from '@/apis/auth_api'
import { message } from 'ant-design-vue'
import { clearAutoStartAttempt } from '@/utils/oidcAutoStart'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const agentStore = useAgentStore()

// Trạng thái
const loading = ref(true)
const error = ref(false)
const errorTitle = ref('Đăng nhập không thành công')
const errorMessage = ref('Đã xảy ra lỗi khi xử lý yêu cầu đăng nhập')

// Quay lại trang đăng nhập
const goToLogin = () => {
  router.push('/login')
}

// Quy trình OIDC gọi lại - từ URL Nhận một lần từ các tham số code
const handleCallback = async () => {
  try {
    const code = route.query.code

    // Kiểm tra các thông số cần thiết
    if (!code || typeof code !== 'string') {
      loading.value = false
      error.value = true
      errorTitle.value = 'Lỗi tham số'
      errorMessage.value = 'Thiếu thông tin đăng nhập hợp lệ code，Vui lòng đăng nhập lại'
      return
    }

    const tokenData = await authApi.exchangeOIDCCode(code)

    await router.replace({ path: route.path, query: {} })

    // Cập nhật trạng thái người dùng
    userStore.token = tokenData.access_token
    userStore.userId = tokenData.uid
    userStore.username = tokenData.username
    userStore.uid = tokenData.uid || ''
    userStore.phoneNumber = tokenData.phone_number || ''
    userStore.avatar = tokenData.avatar || ''
    userStore.userRole = tokenData.role || 'user'
    userStore.departmentId = tokenData.department_id || null
    userStore.departmentName = tokenData.department_name || ''

    // lưu lại token Đến localStorage
    localStorage.setItem('user_token', tokenData.access_token)

    // Hiển thị thông báo thành công
    message.success('Đăng nhập thành công')

    // Nhận đường dẫn chuyển hướng và làm sạch nó OIDC Thẻ liên quan
    const redirectPath = sessionStorage.getItem('oidc_redirect') || '/'
    sessionStorage.removeItem('oidc_redirect')
    clearAutoStartAttempt()

    loading.value = false

    // nhảy chậm，Cho phép người dùng nhìn thấy lời nhắc thành công
    setTimeout(async () => {
      // Nhảy
      if (redirectPath === '/') {
        try {
          await agentStore.initialize()
          router.push('/agent')
        } catch (err) {
          console.error('Không thể lấy được thông tin đại lý:', err)
          router.push('/agent')
        }
      } else {
        router.push(redirectPath)
      }
    }, 500)
  } catch (err) {
    console.error('OIDC Xử lý cuộc gọi lại không thành công:', err)
    loading.value = false
    error.value = true
    errorTitle.value = 'Đăng nhập không thành công'
    errorMessage.value = err?.message || 'Đã xảy ra lỗi khi xử lý yêu cầu đăng nhập，Vui lòng thử lại'
  }
}

// Xử lý cuộc gọi lại khi thành phần được gắn kết
onMounted(async () => {
  // Nếu đăng nhập，Chuyển đến trang chủ
  if (userStore.isLoggedIn) {
    router.push('/')
    return
  }

  await handleCallback()
})
</script>

<style lang="less" scoped>
.oidc-callback-view {
  min-height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--gray-10);
  background-image: radial-gradient(var(--gray-200) 1px, transparent 1px);
  background-size: 24px 24px;
}

.callback-container {
  width: 100%;
  max-width: 500px;
  padding: 40px;
  background: var(--gray-0);
  border-radius: 16px;
  box-shadow: 0 4px 20px var(--shadow-1);
}

.loading-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;

  .loading-text {
    font-size: 16px;
    color: var(--gray-600);
    margin: 0;
  }
}

.error-section,
.success-section {
  :deep(.ant-result) {
    padding: 0;

    .ant-result-title {
      font-size: 20px;
      color: var(--gray-800);
    }

    .ant-result-subtitle {
      font-size: 14px;
      color: var(--gray-500);
    }
  }
}

@media (max-width: 576px) {
  .callback-container {
    margin: 20px;
    padding: 30px 20px;
  }
}
</style>
