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
          <button
            v-if="props.clearable && props.model_spec && !props.disabled"
            class="model-clear-btn"
            @mousedown.prevent.stop
            @click.stop="handleClear"
            title="Xóa sạchChọn"
          >
            <X :size="14" />
          </button>
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
            autocomplete="off"
            autocapitalize="none"
            autocorrect="off"
            spellcheck="false"
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
                <div class="model-option">
                  <span class="model-option-name">{{ model.display_name }}</span>
                  <div class="model-option-signals">
                    <a-tooltip v-if="getModelInfo(model).vision" title="Hỗ trợ đầu vào hình ảnh">
                      <span class="model-signal-icon" role="img" aria-label="Hỗ trợ đầu vào hình ảnh">
                        <Eye :size="13" />
                      </span>
                    </a-tooltip>
                    <a-tooltip
                      v-if="getModelInfo(model).isOneMillionContext"
                      title="Cửa sổ ngữ cảnh khoảng 1M tokens"
                    >
                      <span class="model-context-badge">1M</span>
                    </a-tooltip>
                  </div>
                </div>
              </a-menu-item>
            </a-menu-item-group>
          </template>
        </a-menu>
        <div
          v-if="!modelMetadataNoticeDismissed && (userStore.isAdmin || hasModelMetadata)"
          class="model-metadata-source"
        >
          <div class="model-metadata-source-content">
            <template v-if="userStore.isAdmin">
              Chưa có mô hình phù hợp?
              <RouterLink :to="{ path: '/agent-manage', query: { tab: 'providers' } }" @click.stop>
                Cấu hình mô hình
              </RouterLink>
            </template>
            <template v-if="hasModelMetadata">
              <span v-if="userStore.isAdmin">。 </span>
              Một số thông tin（giá, năng lực...）lấy từ
              <a href="https://models.dev" target="_blank" rel="noreferrer" @click.stop
                >models.dev</a
              >
              bổ sung. Chỉ mang tính tham khảo, có thể lệch với trang chính thức.
            </template>
          </div>
          <button
            type="button"
            class="model-metadata-source-close"
            title="Không hiển thị lại"
            aria-label="Đóng gợi ý thông tin mô hình"
            @click.stop="dismissModelMetadataNotice"
          >
            <X :size="13" />
          </button>
        </div>
      </div>
    </template>
  </a-dropdown>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { modelProviderApi } from '@/apis/system_api'
import { Eye, RefreshCw, X } from 'lucide-vue-next'
import { useModelStatus } from '@/composables/useModelStatus'
import { useUserStore } from '@/stores/user'
import { loadModelMetadataCatalog, resolveModelDisplayMetadata } from '@/utils/modelMetadata'

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
  clearable: {
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
const userStore = useUserStore()
const MODEL_METADATA_NOTICE_DISMISSED_KEY = 'yuxi_model_metadata_notice_dismissed'

// v2 dữ liệu mô hình：Kéo từ phần phụ trợ theo thời gian thực mỗi khi danh sách thả xuống được mở rộng
const v2Models = ref({})
const loadingV2Models = ref(false)
const dropdownOpen = ref(false)
const modelSearchKeyword = ref('')
const modelMetadataBySpec = ref({})
const modelMetadataNoticeDismissed = ref(
  localStorage.getItem(MODEL_METADATA_NOTICE_DISMISSED_KEY) === 'true'
)
let fetchV2ModelsPromise = null

const dismissModelMetadataNotice = () => {
  modelMetadataNoticeDismissed.value = true
  localStorage.setItem(MODEL_METADATA_NOTICE_DISMISSED_KEY, 'true')
}

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

const hasModelMetadata = computed(() => Object.keys(modelMetadataBySpec.value).length > 0)

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
      const catalogRequest = loadModelMetadataCatalog().catch((error) => {
        console.warn('Failed to load model metadata catalog:', error)
        return null
      })
      const response = await modelProviderApi.getV2Models('chat')
      if (response.success) {
        v2Models.value = response.data || {}
        const catalog = await catalogRequest
        modelMetadataBySpec.value = catalog
          ? buildModelMetadataBySpec(v2Models.value, catalog.providers)
          : {}
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

const buildModelMetadataBySpec = (modelsByProvider, providers) => {
  return Object.entries(modelsByProvider).reduce((result, [providerId, providerData]) => {
    for (const model of providerData.models || []) {
      const info = resolveModelDisplayMetadata(providers, providerId, model)
      if (info.matched) result[model.spec] = info
    }
    return result
  }, {})
}

const getModelInfo = (model) => modelMetadataBySpec.value[model.spec] || {}

// Làm mới danh sách model trước khi kéo xuống để mở rộng.，Tránh nhảy độ cao do tải dữ liệu sau khi mở lớp đàn hồi。
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

watch(
  () => props.model_spec,
  (spec, previousSpec) => {
    if (spec !== previousSpec) {
      state.currentModelStatus = null
    }
  }
)

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

// Xóa sạchChọn
const handleClear = () => {
  if (props.disabled) return
  state.currentModelStatus = null
  emit('select-model', '')
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
  color: var(--gray-400);
  cursor: pointer;
  transition: color 0.15s ease;

  &:hover:not(:disabled) {
    color: var(--gray-600);
  }
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

.model-clear-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  margin-left: 2px;
  padding: 0;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--gray-400);
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    color: var(--gray-700);
    background: var(--gray-100);
  }
}

.model-select--disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.model-dropdown {
  width: min(360px, calc(100vw - 24px));
  padding: 8px 0;
  overflow: hidden;
  background: var(--gray-0);
  border-radius: 8px;
  box-shadow: 0 0 18px rgba(0, 0, 0, 0.1);
}

.model-search {
  padding: 8px;
}

.model-search :deep(.ant-input-affix-wrapper) {
  border-color: var(--gray-0);
  background: var(--gray-25);
}

.model-search :deep(.ant-input) {
  background: transparent;
}

:deep(.ant-dropdown-menu) {
  &.scrollable-menu {
    max-height: 260px;
    overflow-y: auto;
    box-shadow: none;
  }

  .ant-dropdown-menu-item-group-list {
    margin: 0;
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

.model-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.model-option-name {
  display: block;
  min-width: 0;
  overflow: hidden;
  color: var(--gray-1000);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-option-signals {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  color: var(--gray-500);
}

.model-context-badge {
  display: inline-flex;
  align-items: center;
  height: 17px;
  padding: 0 5px;
  border-radius: 4px;
  color: var(--gray-600);
  background: var(--gray-100);
  font-size: 10px;
  font-weight: 600;
}

.model-signal-icon {
  display: inline-flex;
  align-items: center;
}

.model-metadata-source {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 7px 10px;
  border-top: 1px solid var(--gray-100);
  color: var(--gray-500);
  background: var(--gray-25);
  font-size: 11px;
  line-height: 16px;

  a {
    color: var(--main-600);
  }
}

.model-metadata-source-content {
  flex: 1;
  min-width: 0;
}

.model-metadata-source-close {
  appearance: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  margin: -2px -3px 0 0;
  padding: 0;
  border: none;
  border-radius: 4px;
  color: var(--gray-500);
  background: transparent;
  cursor: pointer;
  transition:
    color 0.15s ease,
    background-color 0.15s ease;

  &:hover {
    color: var(--gray-800);
    background: var(--gray-100);
  }

  &:focus-visible {
    outline: 2px solid var(--main-400);
    outline-offset: 1px;
  }
}
</style>
