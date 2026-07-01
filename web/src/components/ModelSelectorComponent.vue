<template>
  <a-dropdown
    trigger="click"
    :open="dropdownOpen"
    :disabled="props.disabled"
    @open-change="handleOpenChange"
  >
    <div class="model-select" :class="modelSelectClasses" @click.prevent.stop @mousedown.stop>
      <div class="model-select-content">
        <div class="model-info">
          <span class="model-text text" :title="displayModelTitle">{{ displayModelText }}</span>
        </div>
        <div v-if="resolvedSize !== 'nano'" class="model-status-controls">
          <span
            v-if="state.currentModelStatus"
            class="model-status-indicator"
            :class="state.currentModelStatus.status"
            :title="getCurrentModelStatusTitle()"
          >
            {{ modelStatusIcon }}
          </span>
          <a-button
            :size="buttonSize"
            type="text"
            :loading="state.checkingStatus"
            @click.stop="checkCurrentModelStatus"
            :disabled="props.disabled || state.checkingStatus"
            class="status-check-button"
          >
            {{ state.checkingStatus ? 'Đang được kiểm tra...' : 'Kiểm tra' }}
          </a-button>
        </div>
      </div>
    </div>
    <template #overlay>
      <div class="model-dropdown" @click.stop>
        <div class="model-search">
          <a-input
            v-model:value="modelSearchKeyword"
            placeholder="Tìm kiếm mô hình"
            allow-clear
            @keydown.stop
          >
            <template #suffix>
              <button
                :disabled="props.disabled || state.refreshingCache"
                :title="state.refreshingCache ? 'Làm mới...' : 'làm mới bộ đệm'"
                class="cache-refresh-button"
                @mousedown.prevent.stop
                @click.stop="refreshCache"
              >
                <RefreshCw :size="13" :class="{ spin: state.refreshingCache }" />
              </button>
            </template>
          </a-input>
        </div>
        <a-menu class="scrollable-menu">
          <a-menu-item v-if="loadingV2Models" key="loading" disabled>Đang tải...</a-menu-item>
          <a-menu-item v-else-if="!hasFilteredModels" key="empty" disabled
            >Chưa có mô hình phù hợp</a-menu-item
          >
          <template v-else>
            <a-menu-item-group
              v-for="(providerData, providerId) in filteredV2Models"
              :key="`v2-${providerId}`"
            >
              <template #title>
                <span :title="providerId">{{
                  getProviderDisplayName(providerId, providerData)
                }}</span>
              </template>
              <a-menu-item
                v-for="model in providerData.models"
                :key="model.spec"
                @click="handleSelectV2Model(model.spec)"
              >
                {{ model.display_name }}
              </a-menu-item>
            </a-menu-item-group>
          </template>
        </a-menu>
      </div>
    </template>
  </a-dropdown>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { modelProviderApi } from '@/apis/system_api'
import { RefreshCw } from 'lucide-vue-next'
import { useModelStatus } from '@/composables/useModelStatus'

const props = defineProps({
  model_spec: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: 'Vui lòng chọn một mẫu'
  },
  size: {
    type: String,
    default: 'small',
    validator: (value) => ['nano', 'small', 'middle', 'large'].includes(value)
  },
  disabled: {
    type: Boolean,
    default: false
  },
  displayName: {
    type: String,
    default: 'full',
    validator: (value) => ['full', 'short', 'mini'].includes(value)
  }
})

const emit = defineEmits(['select-model'])

// v2 dữ liệu mô hình：Kéo từ phần phụ trợ theo thời gian thực mỗi khi danh sách thả xuống được mở rộng
const v2Models = ref({})
const loadingV2Models = ref(false)
const dropdownOpen = ref(false)
const modelSearchKeyword = ref('')
let fetchV2ModelsPromise = null

const filteredV2Models = computed(() => {
  const keyword = modelSearchKeyword.value.trim().toLowerCase()
  if (!keyword) return v2Models.value

  return Object.entries(v2Models.value).reduce((result, [providerId, providerData]) => {
    const models = (providerData.models || []).filter((model) => {
      return [
        providerId,
        getProviderDisplayName(providerId, providerData),
        model.spec,
        model.model_id,
        model.display_name
      ].some((value) =>
        String(value || '')
          .toLowerCase()
          .includes(keyword)
      )
    })

    if (models.length) {
      result[providerId] = { ...providerData, models }
    }

    return result
  }, {})
})

const hasFilteredModels = computed(() => {
  return Object.values(filteredV2Models.value).some((providerData) => providerData.models?.length)
})

const getProviderDisplayName = (providerId, providerData = {}) => {
  return (
    providerData.provider_display_name ||
    providerData.display_name ||
    providerData.name ||
    providerId
  )
}

// kéo v2 Danh sách người mẫu
const fetchV2Models = async () => {
  if (fetchV2ModelsPromise) return fetchV2ModelsPromise

  loadingV2Models.value = true
  fetchV2ModelsPromise = (async () => {
    try {
      const response = await modelProviderApi.getV2Models('chat')
      if (response.success) {
        v2Models.value = response.data || {}
      }
    } catch (error) {
      console.warn('Failed to load v2 models:', error)
    } finally {
      loadingV2Models.value = false
      fetchV2ModelsPromise = null
    }
  })()

  return fetchV2ModelsPromise
}

// Làm mới danh sách model trước khi kéo xuống để mở rộng.，Tránh nhảy độ cao do tải dữ liệu sau khi mở lớp đàn hồi.。
const handleOpenChange = async (open) => {
  if (props.disabled) {
    dropdownOpen.value = false
    return
  }

  if (!open) {
    dropdownOpen.value = false
    return
  }

  await fetchV2Models()
  if (!props.disabled) {
    dropdownOpen.value = true
  }
}

// Buộc làm mới bộ đệm
const refreshCache = async () => {
  if (props.disabled || state.refreshingCache) return
  state.refreshingCache = true
  try {
    await modelProviderApi.refreshModelCache()
    // Kéo lại danh sách mô hình sau khi làm mới
    await fetchV2Models()
  } catch (error) {
    console.error('Failed to refresh cache:', error)
  } finally {
    state.refreshingCache = false
  }
}

// Quản lý trạng thái
useModelStatus()
const state = reactive({
  currentModelStatus: null,
  checkingStatus: false,
  refreshingCache: false
})

const resolvedSize = computed(() => props.size || 'small')
const modelSelectClasses = computed(() => ({
  'model-select--nano': resolvedSize.value === 'nano',
  'model-select--middle': resolvedSize.value === 'middle',
  'model-select--large': resolvedSize.value === 'large',
  'model-select--disabled': props.disabled
}))
const buttonSize = computed(() => {
  if (resolvedSize.value === 'large') return 'large'
  if (resolvedSize.value === 'middle') return 'middle'
  return 'small'
})

const extractModelName = (spec) => {
  const separatorIndex = spec.indexOf(':')
  return separatorIndex >= 0 ? spec.slice(separatorIndex + 1) : spec
}

const displayModelText = computed(() => {
  const spec = props.model_spec
  if (!spec) return props.placeholder

  const modelName = extractModelName(spec)
  if (props.displayName === 'mini') {
    return modelName.includes('/') ? modelName.split('/').pop() : modelName
  }
  if (props.displayName === 'short') return modelName
  return spec
})

const displayModelTitle = computed(() => props.model_spec || props.placeholder)

// Kiểm tra trạng thái mô hình hiện tại
const checkCurrentModelStatus = async () => {
  if (props.disabled) return
  const spec = props.model_spec
  if (!spec) return

  try {
    state.checkingStatus = true
    const response = await modelProviderApi.getModelStatusBySpec(spec)
    if (response.data) {
      state.currentModelStatus = response.data
    } else {
      state.currentModelStatus = null
    }
  } catch (error) {
    console.error(`Kiểm tra mô hình ${spec} trạng thái không thành công:`, error)
    state.currentModelStatus = { status: 'error', message: error.message }
  } finally {
    state.checkingStatus = false
  }
}

const modelStatusIcon = computed(() => {
  const status = state.currentModelStatus
  if (!status) return '○'
  if (status.status === 'available') return '✓'
  if (status.status === 'unavailable') return '✗'
  if (status.status === 'error') return '⚠'
  return '○'
})

const getCurrentModelStatusTitle = () => {
  const status = state.currentModelStatus
  if (!status) return 'Trạng thái không xác định'

  let statusText = ''
  if (status.status === 'available') statusText = 'Có sẵn'
  else if (status.status === 'unavailable') statusText = 'Không có sẵn'
  else if (status.status === 'error') statusText = 'Lỗi'

  const message = status.message || 'Không có chi tiết'
  return `${statusText}: ${message}`
}

// chọn v2 cách tiếp cận mô hình
const handleSelectV2Model = (spec) => {
  if (props.disabled) return
  emit('select-model', spec)
  dropdownOpen.value = false
}
</script>

<style lang="less" scoped>
@import '@/assets/css/model-selector-common.less';

// nút kiểm tra trạng thái
.status-check-button {
  font-size: 12px;
  padding: 0 4px;
}

// Nút làm mới bộ đệm
.cache-refresh-button {
  font-size: 12px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background-color: transparent;
  border: none;
  outline: none;
  cursor: pointer;
}

.model-select--nano {
  max-width: 100%;
  height: 30px;
  padding: 6px 8px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1;
  color: var(--gray-600);
  background: transparent;
  transition: all 0.2s ease;
  user-select: none;
}

.model-select--nano:hover {
  color: var(--gray-900);
  background: var(--gray-50);
}

.model-select--nano .model-text {
  color: currentColor;
}

.model-select--disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.model-dropdown {
  min-width: 280px;
  max-width: 420px;
  overflow: hidden;
  background: var(--gray-0);
  border-radius: 8px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
}

.model-search {
  padding: 8px;
  border-bottom: 1px solid var(--gray-100);
}

:deep(.ant-dropdown-menu) {
  &.scrollable-menu {
    max-height: 260px;
    overflow-y: auto;
    box-shadow: none;
  }

  .ant-dropdown-menu-item,
  .ant-dropdown-menu-submenu-title {
    border-radius: 6px;
  }

  .ant-dropdown-menu-item:hover,
  .ant-dropdown-menu-submenu-title:hover,
  .ant-dropdown-menu-item-active,
  .ant-dropdown-menu-submenu-title-active {
    background: var(--gray-50);
  }

  .ant-dropdown-menu-item-selected,
  .ant-dropdown-menu-item-selected:hover,
  .ant-dropdown-menu-item-selected.ant-dropdown-menu-item-active {
    color: var(--gray-1000);
    background: var(--main-50);
  }
}
</style>
