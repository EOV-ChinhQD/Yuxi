<template>
  <main class="cli-auth-view">
    <section class="cli-auth-panel">
      <div class="cli-auth-header">
        <p class="eyebrow">Yuxi CLI</p>
        <h1>Xác nhận đăng nhập dòng lệnh</h1>
      </div>

      <a-alert v-if="errorMessage" type="error" :message="errorMessage" show-icon />

      <a-spin v-else-if="loading" />

      <template v-else>
        <a-result
          v-if="approved"
          status="success"
          title="Được ủy quyền"
          sub-title="Bạn có thể đóng trang này và quay lại terminal。"
        />

        <div v-else class="session-summary">
          <div class="code-block">{{ userCode }}</div>
          <a-alert
            type="warning"
            show-icon
            message="Vui lòng xác nhận rằng đây là lần đăng nhập bằng dòng lệnh do bạn thực hiện."
            description="Sau khi xác nhận, một tài khoản sẽ được tạo với danh tính hiện tại của bạn API Key và quay trở lại thiết bị đầu cuối。Nếu người khởi xướng không phải là bạn，Không xác nhận và đóng trang này。"
          />
          <dl>
            <div>
              <dt>Tên thông tin xác thực</dt>
              <dd>{{ session?.key_name || 'Yuxi CLI' }}</dd>
            </div>
            <div>
              <dt>Trạng thái</dt>
              <dd>{{ session?.status || '-' }}</dd>
            </div>
            <div>
              <dt>Thời gian hết hạn</dt>
              <dd>{{ session?.expires_at || '-' }}</dd>
            </div>
          </dl>
          <a-button type="primary" size="large" :loading="approving" @click="approveSession">
            Xác nhận ủy quyền
          </a-button>
        </div>
      </template>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { authApi } from '@/apis/auth_api'

const route = useRoute()
const loading = ref(true)
const approving = ref(false)
const approved = ref(false)
const errorMessage = ref('')
const session = ref(null)

const userCode = computed(() =>
  String(route.query.user_code || '')
    .trim()
    .toUpperCase()
)

async function loadSession() {
  if (!userCode.value) {
    errorMessage.value = 'mất tích CLI Mã ủy quyền'
    loading.value = false
    return
  }
  try {
    loading.value = true
    session.value = await authApi.getCLIAuthSession(userCode.value)
  } catch (error) {
    errorMessage.value = error.message || 'Nhận CLI Phiên ủy quyền không thành công'
  } finally {
    loading.value = false
  }
}

async function approveSession() {
  try {
    approving.value = true
    await authApi.approveCLIAuthSession(userCode.value)
    approved.value = true
  } catch (error) {
    errorMessage.value = error.message || 'Xác nhận CLI Ủy quyền không thành công'
  } finally {
    approving.value = false
  }
}

onMounted(loadSession)
</script>

<style scoped lang="less">
.cli-auth-view {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px 16px;
  background: var(--gray-50);
}

.cli-auth-panel {
  width: min(520px, 100%);
  padding: 32px;
  border: 1px solid var(--dark-10);
  border-radius: 8px;
  background: var(--color-bg-container);
}

.cli-auth-header {
  margin-bottom: 24px;

  .eyebrow {
    margin: 0 0 8px;
    color: var(--color-text-secondary);
    font-size: 13px;
  }

  h1 {
    margin: 0;
    color: var(--color-text);
    font-size: 26px;
    font-weight: 650;
  }
}

.session-summary {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.code-block {
  padding: 16px;
  border: 1px solid var(--dark-10);
  border-radius: 8px;
  background: var(--color-bg-elevated);
  color: var(--color-text);
  font-size: 24px;
  font-weight: 650;
  letter-spacing: 0;
  text-align: center;
}

dl {
  display: grid;
  gap: 12px;
  margin: 0;

  div {
    display: grid;
    grid-template-columns: 88px 1fr;
    gap: 16px;
  }

  dt {
    color: var(--color-text-secondary);
  }

  dd {
    margin: 0;
    color: var(--color-text);
    overflow-wrap: anywhere;
  }
}

@media (max-width: 560px) {
  .cli-auth-panel {
    padding: 24px;
  }

  dl div {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
