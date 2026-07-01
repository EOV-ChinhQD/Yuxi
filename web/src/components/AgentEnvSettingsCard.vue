<template>
  <div class="agent-env-settings">
    <div class="header-section">
      <div class="header-content">
        <div class="section-title">Biến môi trường hộp cát</div>
        <p class="section-description">
          Định cấu hình người dùng hiện tại Agent Biến môi trường hộp cát。Các biến này sẽ được chèn khi tạo hộp cát mới，và ghi đè toàn cầu có cùng tên sandbox.env。
        </p>
      </div>
      <div class="header-actions">
        <a-button class="lucide-icon-btn" :loading="loading" @click="loadAgentEnv">
          <template #icon><RefreshCw :size="16" :class="{ spin: loading }" /></template>
          Làm mới
        </a-button>
        <a-button type="primary" :loading="saving" @click="saveAgentEnv">lưu lại</a-button>
      </div>
    </div>

    <div class="env-tip">Sau khi lưu, nó sẽ chỉ có hiệu lực đối với các sandbox mới.，Sandbox đang chạy sẽ không được cập nhật nóng。</div>

    <a-spin :spinning="loading">
      <McpEnvEditor :modelValue="draftEnv" @update:modelValue="updateDraftEnv" />
    </a-spin>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { RefreshCw } from 'lucide-vue-next'
import { agentEnvApi } from '@/apis/agent_env_api'
import McpEnvEditor from '@/components/McpEnvEditor.vue'

const ENV_KEY_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/
const MAX_ENV_COUNT = 200
const MAX_ENV_KEY_LENGTH = 128
const MAX_ENV_VALUE_LENGTH = 32768

const loading = ref(false)
const saving = ref(false)
const draftEnv = ref({})
const lastSavedEnv = ref({})

const normalizeEnv = (env) => {
  if (!env || typeof env !== 'object' || Array.isArray(env)) {
    return {}
  }
  return Object.fromEntries(
    Object.entries(env)
      .map(([key, value]) => [key.trim(), value == null ? '' : String(value)])
      .filter(([key]) => key)
  )
}

const isSameEnv = (left, right) => {
  const leftEntries = Object.entries(left)
  const rightEntries = Object.entries(right)
  if (leftEntries.length !== rightEntries.length) return false
  return leftEntries.every(([key, value]) => right[key] === value)
}

const updateDraftEnv = (value) => {
  const nextEnv = normalizeEnv(value)
  if (!isSameEnv(draftEnv.value, nextEnv)) {
    draftEnv.value = nextEnv
  }
}

const validateEnv = (env) => {
  const entries = Object.entries(env)
  if (entries.length > MAX_ENV_COUNT) {
    message.error(`Số lượng biến môi trường không thể vượt quá ${MAX_ENV_COUNT} một`)
    return false
  }

  for (const [key, value] of entries) {
    if (key.length > MAX_ENV_KEY_LENGTH) {
      message.error(`Độ dài của tên biến môi trường không thể vượt quá ${MAX_ENV_KEY_LENGTH}`)
      return false
    }
    if (!ENV_KEY_PATTERN.test(key)) {
      message.error(`Tên biến môi trường ${key} Định dạng không chính xác`)
      return false
    }
    if (value.length > MAX_ENV_VALUE_LENGTH) {
      message.error(`biến môi trường ${key} Giá trị quá dài`)
      return false
    }
  }
  return true
}

const loadAgentEnv = async () => {
  loading.value = true
  try {
    const res = await agentEnvApi.get()
    const env = normalizeEnv(res.env)
    draftEnv.value = env
    lastSavedEnv.value = env
  } catch (error) {
    message.error(error.message || 'Không thể tải các biến môi trường')
  } finally {
    loading.value = false
  }
}

const saveAgentEnv = async () => {
  const env = normalizeEnv(draftEnv.value)
  if (!validateEnv(env)) return
  if (isSameEnv(env, lastSavedEnv.value)) {
    message.info('Biến môi trường không thay đổi')
    return
  }

  saving.value = true
  try {
    await agentEnvApi.update(env)
    draftEnv.value = env
    lastSavedEnv.value = env
    message.success('Đã lưu các biến môi trường')
  } catch (error) {
    message.error(error.message || 'Không lưu được biến môi trường')
  } finally {
    saving.value = false
  }
}

onMounted(loadAgentEnv)
</script>

<style lang="less" scoped>
.agent-env-settings {
  .header-section {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 16px;
    margin-bottom: 12px;

    @media (max-width: 760px) {
      align-items: stretch;
      flex-direction: column;
    }
  }

  .header-content {
    flex: 1;
    min-width: 0;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  .env-tip {
    margin-bottom: 14px;
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--main-10);
    border: 1px solid var(--main-300);
    color: var(--main-700);
    font-size: 13px;
    line-height: 1.5;
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
