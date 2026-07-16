<template>
  <div class="user-config-settings">
    <div class="header-section">
      <div class="header-content">
        <div class="section-title">Cấu hình người dùng(Beta)</div>
        <p class="section-description">
          Cấu hình cài đặt riêng cho người dùng hiện tại. Hiện tại là phiên bản preview thử nghiệm,
          chưa đưa vào tính năng mới, chỉ mở rộng khả năng kỹ thuật.。
        </p>
      </div>
      <div class="header-actions">
        <a-button class="lucide-icon-btn" :loading="loading" @click="loadUserConfig">
          <template #icon><RefreshCw :size="16" :class="{ spin: loading }" /></template>
          Làm mới
        </a-button>
        <a-button type="primary" :loading="saving" @click="saveUserConfig">
          {{ saveButtonText }}
        </a-button>
      </div>
    </div>

    <a-spin :spinning="loading">
      <div class="config-panel">
        <div class="config-row">
          <div class="config-meta">
            <div class="config-title-line">
              <span class="config-title">Có bật không Memory</span>
              <span class="reserved-badge">Công tắc dự trữ</span>
            </div>
            <p class="config-description">
              Hiện tại chỉ lưu giá trị cấu hình, chưa kết nối với logic vận hành của trợ lý thông
              minh。
            </p>
          </div>
          <a-switch :checked="draftEnableMemory" @change="draftEnableMemory = Boolean($event)" />
        </div>
      </div>
    </a-spin>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { RefreshCw } from 'lucide-vue-next'
import { userConfigApi } from '@/apis/user_config_api'

const loading = ref(false)
const saving = ref(false)
const draftEnableMemory = ref(false)
const savedEnableMemory = ref(false)

const hasUnsavedChanges = computed(() => draftEnableMemory.value !== savedEnableMemory.value)
const saveButtonText = computed(() => (hasUnsavedChanges.value ? 'Lưu (có thay đổi)）' : 'Lưu'))

const applyResponse = (res) => {
  draftEnableMemory.value = res.enable_memory
  savedEnableMemory.value = res.enable_memory
}

const loadUserConfig = async () => {
  loading.value = true
  try {
    const res = await userConfigApi.get()
    applyResponse(res)
  } catch (error) {
    message.error(error.message || 'Tải cấu hình người dùng thất bại')
  } finally {
    loading.value = false
  }
}

const saveUserConfig = async () => {
  if (!hasUnsavedChanges.value) {
    message.info('Cấu hình người dùng chưa thay đổi')
    return
  }

  saving.value = true
  try {
    const res = await userConfigApi.update({ enable_memory: draftEnableMemory.value })
    applyResponse(res)
    message.success('Cấu hình người dùng đã được lưu')
  } catch (error) {
    message.error(error.message || 'Lưu cấu hình người dùng thất bại')
  } finally {
    saving.value = false
  }
}

onMounted(loadUserConfig)
</script>

<style lang="less" scoped>
.user-config-settings {
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

  .config-panel {
    border: 1px solid var(--gray-150);
    border-radius: 8px;
    background: var(--gray-0);
    overflow: hidden;
  }

  .config-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    padding: 14px 16px;

    @media (max-width: 560px) {
      align-items: flex-start;
      flex-direction: column;
    }
  }

  .config-meta {
    min-width: 0;
  }

  .config-title-line {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .config-title {
    color: var(--gray-900);
    font-size: 14px;
    font-weight: 500;
    line-height: 1.4;
  }

  .reserved-badge {
    display: inline-flex;
    align-items: center;
    height: 22px;
    padding: 0 8px;
    border-radius: 999px;
    border: 1px solid var(--color-warning-100);
    background: var(--color-warning-10);
    color: var(--color-warning-700);
    font-size: 12px;
    line-height: 1;
    white-space: nowrap;
  }

  .config-description {
    margin: 6px 0 0;
    color: var(--gray-600);
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
