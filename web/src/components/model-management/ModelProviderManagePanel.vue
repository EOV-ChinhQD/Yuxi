<script setup>
import { computed, onMounted, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  Globe,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  Trash2,
  CheckCircle2,
  TextInitial,
  Image,
  Video,
  AudioLines,
  FileText,
  LayersPlus,
  LoaderCircle,
  Zap
} from 'lucide-vue-next'

import { modelProviderApi } from '@/apis/system_api'
import { useConfigStore } from '@/stores/config'
import { modelAvatars } from '@/utils/modelIcon'
import {
  formatModelPriceDisplay,
  loadModelMetadataCatalog,
  resolveModelDisplayMetadata,
  USD_TO_CNY_RATE
} from '@/utils/modelMetadata'
import PageShoulder from '@/components/shared/PageShoulder.vue'
import InfoCard from '@/components/shared/InfoCard.vue'
import ExtensionCardGrid from '@/components/extensions/ExtensionCardGrid.vue'
import ProviderCatalogModal from './ProviderCatalogModal.vue'
import ProviderConfigModal from './ProviderConfigModal.vue'

const configStore = useConfigStore()
const loading = ref(false)
const remoteLoading = ref(false)
const saving = ref(false)
const providers = ref([])
const searchQuery = ref('')
const modelTestLoadingBySpec = ref({})
const modelTestResultBySpec = ref({})

// PORT-CONFLICT: giữ kiến thức quản lý provider bằng ProviderCatalogModal/ProviderConfigModal
// của bản fork; chỉ giữ lại từ upstream các hằng hiển thị dùng chung (modality, placeholder)
const showCatalogModal = ref(false)
const showConfigModal = ref(false)
const configModalMode = ref('quick') // 'quick' | 'full' | 'edit'
const selectedProviderForConfig = ref(null)

const MODALITY_DISPLAY = {
  text: { icon: TextInitial, label: 'Đầu vào văn bản' },
  image: { icon: Image, label: 'Đầu vào hình ảnh' },
  video: { icon: Video, label: 'Đầu vào video' },
  audio: { icon: AudioLines, label: 'Đầu vào âm thanh' },
  pdf: { icon: FileText, label: 'Đầu vào tài liệu PDF' }
}
const REQUEST_BODY_OVERRIDES_PLACEHOLDER = '{\n  "enable_thinking": false\n}'

// Model form state
const showModelModal = ref(false)
const isCreating = ref(false) // true=Thêm mô hình mới theo cách thủ công，false=Chỉnh sửa mô hình hiện có
const editingModel = ref({
  id: '',
  display_name: '',
  type: 'chat',
  source: 'remote',
  protocol_override: null,
  base_url_override: null,
  request_body_overrides: {},
  request_body_overrides_text: '{}',
  context_length: null,
  dimension: null,
  batch_size: null,
  supported_parameters: [],
  extra: {}
})

// Models modal state (per provider)
const showModelsModal = ref(false)
const currentProviderForModels = ref(null)

// Remote models per provider
const remoteModelsMap = ref({})

// Remote model loading state per provider
const remoteModelsLoaded = ref({})
const modelCatalogProviders = ref({})

// Remote model search state per provider
const remoteModelSearch = ref({})
const remoteModelTypeFilter = ref({})
const priceCurrency = ref('USD')
const filteredProviders = computed(() => {
  const keyword = searchQuery.value.trim().toLowerCase()
  const filtered = keyword
    ? providers.value.filter(
        (p) =>
          p.provider_id.toLowerCase().includes(keyword) ||
          p.display_name.toLowerCase().includes(keyword)
      )
    : providers.value
  return [...filtered].sort((a, b) => {
    if (a.is_enabled && b.is_enabled && a.credential_status !== b.credential_status) {
      return a.credential_status === 'warning' ? 1 : -1
    }
    return a.provider_id.localeCompare(b.provider_id)
  })
})

const enabledProviders = computed(() => filteredProviders.value.filter((p) => p.is_enabled))
const disabledProviders = computed(() => filteredProviders.value.filter((p) => !p.is_enabled))

const providerStats = computed(() => {
  let enabled = 0,
    warning = 0,
    models = 0
  for (const p of providers.value) {
    if (p.is_enabled) {
      enabled++
      if (p.credential_status === 'warning') warning++
    }
    models += p.enabled_models?.length || 0
  }
  return { total: providers.value.length, enabled, warning, models }
})

// ============ Helpers ============
const getProviderAvatar = (provider) => {
  const providerId = provider?.provider_id?.toLowerCase()
  const providerType = provider?.provider_type?.toLowerCase()
  return modelAvatars[providerId] || modelAvatars[providerType] || modelAvatars.default
}

const getModelDisplayName = (model) => {
  return model.name || model.display_name || model.id
}

const getModelId = (model) => {
  return model.id
}

const buildModelSpec = (providerId, modelId) => `${providerId}:${modelId}`

const defaultModelSpec = computed(() => configStore.config?.default_model || '')

const getDefaultModelProviderId = () => {
  const spec = defaultModelSpec.value
  const separatorIndex = spec.indexOf(':')
  return separatorIndex > 0 ? spec.slice(0, separatorIndex) : ''
}

const providerContainsDefaultModel = (providerId) => getDefaultModelProviderId() === providerId

const isDefaultModel = (providerId, modelId) =>
  defaultModelSpec.value === buildModelSpec(providerId, modelId)

const warnDefaultModelProtected = () => {
  message.warning(
    'Mô hình mặc định hiện tại đang sử dụng nhà cung cấp hoặc mô hình này, vui lòng chuyển đổi mô hình mặc định trước'
  )
}

const isModelTesting = (providerId, modelId) =>
  !!modelTestLoadingBySpec.value[buildModelSpec(providerId, modelId)]

const getModelTestTitle = (providerId, model) => {
  const spec = buildModelSpec(providerId, model.id)
  const result = modelTestResultBySpec.value[spec]
  if (!result) return 'kết nối thử nghiệm'

  const statusText =
    {
      available: 'Có sẵn',
      unavailable: 'Không có sẵn',
      unsupported: 'Chưa được hỗ trợ',
      error: 'Lỗi'
    }[result.status] || 'không rõ'
  return `${statusText}: ${result.message || 'Không có chi tiết'}`
}

const getProviderModelInfo = (providerId, model) =>
  resolveModelDisplayMetadata(modelCatalogProviders.value, providerId, model)

const getRemoteModelPriceDisplay = (providerId, model) =>
  formatModelPriceDisplay(getProviderModelInfo(providerId, model).price, priceCurrency.value)

const togglePriceCurrency = () => {
  priceCurrency.value = priceCurrency.value === 'CNY' ? 'USD' : 'CNY'
}

const getModalityDisplay = (modality) =>
  MODALITY_DISPLAY[modality] || { icon: FileText, label: modality }

const loadModelMetadata = async () => {
  if (Object.keys(modelCatalogProviders.value).length) return
  try {
    const catalog = await loadModelMetadataCatalog()
    modelCatalogProviders.value = catalog.providers
  } catch (error) {
    console.warn('Failed to load model metadata catalog:', error)
  }
}

const remoteIdsMap = computed(() => {
  const map = {}
  for (const [providerId, models] of Object.entries(remoteModelsMap.value)) {
    map[providerId] = new Set(models.map((m) => m.id))
  }
  return map
})

const isModelStale = (model, providerId) => {
  if (model.source === 'manual') return false
  if (!remoteModelsLoaded.value[providerId]) return false
  return model.enabled && !remoteIdsMap.value[providerId]?.has(model.id)
}

// Remote models filtered by search query per provider
const filteredRemoteModels = computed(() => {
  if (!currentProviderForModels.value) return []
  const providerId = currentProviderForModels.value.provider_id
  const query = (remoteModelSearch.value[providerId] || '').trim().toLowerCase()
  const typeFilter = remoteModelTypeFilter.value[providerId] || 'all'
  const models = remoteModelsMap.value[providerId] || []
  return models.filter((m) => {
    const matchesType = typeFilter === 'all' || (m.type || 'chat') === typeFilter
    const matchesQuery = !query || m.id.toLowerCase().includes(query)
    return matchesType && matchesQuery
  })
})

const remoteModelTypeOptions = computed(() => {
  if (!currentProviderForModels.value) return [{ label: 'Tất cả', value: 'all' }]
  const providerId = currentProviderForModels.value.provider_id
  const models = remoteModelsMap.value[providerId] || []
  const counts = models.reduce((acc, model) => {
    const type = model.type || 'chat'
    acc[type] = (acc[type] || 0) + 1
    return acc
  }, {})
  return [
    { label: `Tất cả ${models.length}`, value: 'all' },
    { label: `Chat ${counts.chat || 0}`, value: 'chat' },
    { label: `Embedding ${counts.embedding || 0}`, value: 'embedding' },
    { label: `Rerank ${counts.rerank || 0}`, value: 'rerank' }
  ]
})

// Model Config Modal của type tùy chọn thả xuống：Dựa trên provider.capabilities hạn chế
// dữ liệu cũ capabilities Quay lại bộ sưu tập đầy đủ khi trống，duy trì hiện trạng
const editingModelTypeOptions = computed(() => {
  const caps = currentProviderForModels.value?.capabilities
  const types = Array.isArray(caps) && caps.length ? caps : ['chat', 'embedding', 'rerank']
  return types.map((c) => ({ value: c, label: c }))
})

const parseJsonObject = (text, label) => {
  let parsed
  try {
    const source = typeof text === 'string' && text.trim() ? text : '{}'
    parsed = JSON.parse(source)
  } catch (error) {
    const reason = error?.message ? `：${error.message}` : ''
    throw new Error(`${label} có định dạng không đúng${reason}`, { cause: error })
  }
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error(`${label} phải là một đối tượng JSON`)
  }
  return parsed
}

const formatJsonText = (value) => JSON.stringify(value || {}, null, 2)
const loadProviders = async () => {
  loading.value = true
  try {
    if (!configStore.config?.default_model) {
      await configStore.refreshConfig()
    }
    const result = await modelProviderApi.getProviders()
    providers.value = result.data || []
  } catch (error) {
    message.error(error.message || 'Không tải được nhà cung cấp mô hình')
  } finally {
    loading.value = false
  }
}

function getProviderInfo(provider) {
  return [
    { label: 'Base URL', value: provider.base_url || '-' },
    { label: 'khả năng', value: provider.capabilities?.join(', ') || 'chat' }
  ]
}

function getProviderStatus(provider) {
  if (!provider.is_enabled) return { label: 'Chưa bật', level: 'info' }
  if (provider.credential_status === 'warning')
    return { label: 'Thiếu thông tin xác thực', level: 'warning' }
  return { label: '', level: 'success' }
}

const handleSelectCatalogProvider = ({ mode, provider }) => {
  if (mode === 'quick' && provider) {
    selectedProviderForConfig.value = {
      provider_id: provider.provider_id,
      display_name: provider.display_name,
      provider_type: provider.provider_type || 'openai',
      default_protocol: '',
      base_url: provider.base_url || '',
      embedding_base_url: provider.embedding_base_url || '',
      rerank_base_url: provider.rerank_base_url || '',
      models_endpoint: provider.models_endpoint || '/models',
      embedding_models_endpoint: provider.embedding_models_endpoint || '/embeddings/models',
      rerank_models_endpoint: provider.rerank_models_endpoint || '',
      api_key_env: provider.api_key_env || '',
      api_key: '',
      capabilities: provider.capabilities || ['chat'],
      is_enabled: true,
      is_builtin: true,
      headers_json: {},
      extra_json: {}
    }
  } else {
    selectedProviderForConfig.value = null
  }
  configModalMode.value = mode
  showConfigModal.value = true
}

const openCreateProviderModal = () => {
  showCatalogModal.value = true
}

const openEditProviderModal = (provider) => {
  selectedProviderForConfig.value = provider
  configModalMode.value = 'edit'
  showConfigModal.value = true
}

const handleDeletedProvider = (providerId) => {
  if (currentProviderForModels.value?.provider_id === providerId) {
    showModelsModal.value = false
    currentProviderForModels.value = null
  }
  loadProviders()
}

const handleSavedProvider = async (eventData = {}) => {
  await loadProviders()
  const providerId = eventData?.providerId
  if (providerId) {
    const provider = providers.value.find((p) => p.provider_id === providerId)
    if (provider && (!provider.enabled_models || provider.enabled_models.length === 0)) {
      message.info(
        `Nhà cung cấp ${provider.display_name} đã sẵn sàng. Hãy bấm kích hoạt mô hình để sử dụng.`
      )
      openModelsModal(provider)
    }
  }
}

// ============ Models Modal Operations ============
const openModelsModal = (provider) => {
  currentProviderForModels.value = provider
  if (!remoteModelsLoaded.value[provider.provider_id]) {
    remoteModelsMap.value[provider.provider_id] = []
  }
  remoteModelSearch.value[provider.provider_id] =
    remoteModelSearch.value[provider.provider_id] || ''
  remoteModelTypeFilter.value[provider.provider_id] = 'all'
  showModelsModal.value = true
  loadModelMetadata()
}

// ============ Remote Models Operations ============
const fetchRemoteModels = async (providerId) => {
  remoteLoading.value = true
  try {
    const result = await modelProviderApi.fetchRemoteModels(providerId)
    remoteModelsMap.value = {
      ...remoteModelsMap.value,
      [providerId]: result.data || []
    }
    remoteModelsLoaded.value[providerId] = true
    message.success(`thu được ${result.data?.length || 0} mô hình từ xa`)
  } catch (error) {
    message.error(error.message || 'Không lấy được mô hình từ xa')
  } finally {
    remoteLoading.value = false
  }
}

// ============ Model Operations ============
const normalizeModel = (model = {}) => ({
  id: model.id || '',
  display_name: model.display_name || model.name || model.id || '',
  type: model.type && model.type !== 'unknown' ? model.type : 'chat',
  source: model.source || 'remote',
  protocol_override: model.protocol_override || null,
  base_url_override: model.base_url_override || null,
  request_body_overrides:
    model.request_body_overrides &&
    typeof model.request_body_overrides === 'object' &&
    !Array.isArray(model.request_body_overrides)
      ? model.request_body_overrides
      : {},
  context_length: model.context_length || null,
  dimension: model.dimension || null,
  batch_size: model.batch_size || null,
  supported_parameters: model.supported_parameters || [],
  extra: model.extra || {}
})

const testModelConnection = async (providerId, model) => {
  const spec = buildModelSpec(providerId, model.id)
  if (modelTestLoadingBySpec.value[spec]) return

  modelTestLoadingBySpec.value = { ...modelTestLoadingBySpec.value, [spec]: true }
  try {
    const result = await modelProviderApi.getModelStatusBySpec(spec)
    const status = result.data || { spec, status: 'error', message: 'Kiểm tra không thành công' }
    modelTestResultBySpec.value = { ...modelTestResultBySpec.value, [spec]: status }

    if (status.status === 'available') {
      message.success(`${getModelDisplayName(model)} Kết nối vẫn bình thường`)
    } else if (status.status === 'unsupported') {
      message.warning(status.message || 'Việc thử nghiệm loại mô hình này hiện không được hỗ trợ.')
    } else if (status.status === 'unavailable') {
      message.warning(status.message || 'Kết nối mô hình không có sẵn')
    } else {
      message.error(status.message || 'Kiểm tra kết nối mô hình không thành công')
    }
  } catch (error) {
    modelTestResultBySpec.value = {
      ...modelTestResultBySpec.value,
      [spec]: { spec, status: 'error', message: error.message || 'Kiểm tra không thành công' }
    }
    message.error(error.message || 'Kiểm tra kết nối mô hình không thành công')
  } finally {
    modelTestLoadingBySpec.value = { ...modelTestLoadingBySpec.value, [spec]: false }
  }
}

const addModelFromRemote = async (providerId, remoteModel) => {
  const provider = providers.value.find((p) => p.provider_id === providerId)
  if (!provider) return

  const enabledModels = provider.enabled_models || []
  if (enabledModels.some((m) => m.id === remoteModel.id)) {
    message.info('Mô hình đã tồn tại')
    return
  }

  const newModel = normalizeModel(remoteModel)
  newModel.source = 'remote' // Chú thích rõ ràng của các mô hình được kéo từ xa，Tránh đánh giá sai về sau vì dữ liệu cũ
  newModel.enabled = true
  const newEnabledModels = [...enabledModels, newModel]

  try {
    await modelProviderApi.updateProvider(providerId, { enabled_models: newEnabledModels })
    message.success(`Đã thêm mô hình ${remoteModel.id}`)
    await loadProviders()
    // Refresh current provider reference if modal is open
    if (currentProviderForModels.value?.provider_id === providerId) {
      currentProviderForModels.value = providers.value.find((p) => p.provider_id === providerId)
    }
  } catch (error) {
    message.error(error.message || 'Không thể thêm mô hình')
  }
}

const openModelConfigModal = (model) => {
  const normalized = normalizeModel(model)
  normalized.request_body_overrides_text = formatJsonText(normalized.request_body_overrides)
  Object.assign(editingModel.value, normalized)
  isCreating.value = false
  showModelModal.value = true
}

// Thêm mô hình theo cách thủ công：Cửa sổ bật lên được chia sẻ với người chỉnh sửa Model Config Modal，Nhưng id Các trường có thể chỉnh sửa、type Tùy chọn theo provider Hạn chế về năng lực
const openCreateModal = (provider) => {
  if (!provider) return
  const types = provider.capabilities?.length ? provider.capabilities : ['chat']
  const defaultType = types[0]
  Object.assign(editingModel.value, {
    id: '',
    display_name: '',
    type: defaultType,
    source: 'manual',
    protocol_override: null,
    base_url_override: null,
    request_body_overrides: {},
    request_body_overrides_text: '{}',
    context_length: null,
    dimension: null,
    batch_size: null,
    supported_parameters: [],
    extra: {}
  })
  isCreating.value = true
  showModelModal.value = true
}

const buildModelConfigPayload = () => {
  const requestBodyOverrides = parseJsonObject(
    editingModel.value.request_body_overrides_text,
    'Tham số yêu cầu mô hình'
  )
  const modelPayload = { ...editingModel.value }
  delete modelPayload.request_body_overrides_text
  return {
    ...modelPayload,
    request_body_overrides: requestBodyOverrides
  }
}

const saveModelConfig = async () => {
  if (!currentProviderForModels.value) return
  saving.value = true
  try {
    const provider = providers.value.find(
      (p) => p.provider_id === currentProviderForModels.value.provider_id
    )
    if (!provider) return

    const modelPayload = buildModelConfigPayload()
    let enabledModels
    if (isCreating.value) {
      const newId = (modelPayload.id || '').trim()
      if (!newId) {
        message.error('Vui lòng điền vào mẫu ID')
        return
      }
      if ((provider.enabled_models || []).some((m) => m.id === newId)) {
        message.error('người mẫu ID Đã tồn tại')
        return
      }
      const newModel = { ...modelPayload, id: newId, source: 'manual', enabled: true }
      enabledModels = [...(provider.enabled_models || []), newModel]
    } else {
      enabledModels = (provider.enabled_models || []).map((m) =>
        m.id === modelPayload.id ? { ...modelPayload } : m
      )
    }

    await modelProviderApi.updateProvider(currentProviderForModels.value.provider_id, {
      enabled_models: enabledModels
    })
    message.success(isCreating.value ? 'Đã thêm mô hình' : 'Đã lưu cấu hình mô hình')
    showModelModal.value = false
    isCreating.value = false
    await loadProviders()
    // Refresh current provider reference
    currentProviderForModels.value = providers.value.find(
      (p) => p.provider_id === currentProviderForModels.value.provider_id
    )
  } catch (error) {
    message.error(error.message || 'Lưu không thành công')
  } finally {
    saving.value = false
  }
}

const removeModel = async (providerId, modelId) => {
  const provider = providers.value.find((p) => p.provider_id === providerId)
  if (!provider) return
  if (isDefaultModel(providerId, modelId)) {
    warnDefaultModelProtected()
    return
  }

  Modal.confirm({
    title: 'Xóa mô hình',
    content: `Xác nhận bạn muốn xóa mô hình ${modelId} ?？`,
    okText: 'Xóa',
    okType: 'danger',
    cancelText: 'Hủy bỏ',
    async onOk() {
      try {
        const enabledModels = (provider.enabled_models || []).filter((m) => m.id !== modelId)
        await modelProviderApi.updateProvider(providerId, { enabled_models: enabledModels })
        message.success('Đã xóa mô hình')
        await loadProviders()
        // Refresh current provider reference if modal is open
        if (currentProviderForModels.value?.provider_id === providerId) {
          currentProviderForModels.value = providers.value.find((p) => p.provider_id === providerId)
        }
      } catch (error) {
        message.error(error.message || 'Xóa không thành công')
      }
    }
  })
}

onMounted(loadProviders)

defineExpose({
  loading,
  stats: providerStats,
  refresh: loadProviders
})
</script>

<template>
  <div class="model-provider-manage-panel">
    <PageShoulder v-model:search="searchQuery" search-placeholder="Tìm kiếm nhà cung cấp...">
      <template #actions>
        <a-button type="primary" class="lucide-icon-btn" @click="openCreateProviderModal">
          <Plus :size="14" />
          Thêm nhà cung cấp mới
        </a-button>
        <a-button class="lucide-icon-btn" @click="loadProviders" :loading="loading">
          <RefreshCw :size="14" :class="{ spinning: loading }" />
        </a-button>
      </template>
    </PageShoulder>

    <div
      v-if="!loading && enabledProviders.length === 0 && disabledProviders.length === 0"
      class="provider-empty-state"
    >
      <a-empty
        :image="false"
        :description="searchQuery ? 'Không có nhà cung cấp phù hợp' : 'Chưa có nhà cung cấp, bấm nút phía trên để thêm'"
      />
    </div>

    <template v-else>
      <div v-if="enabledProviders.length" class="provider-section-header">
        Đã bật ({{ enabledProviders.length }})
      </div>
      <ExtensionCardGrid v-if="enabledProviders.length" :min-width="320">
        <InfoCard
          v-for="provider in enabledProviders"
          :key="provider.provider_id"
          :title="provider.display_name"
          :subtitle="provider.provider_id"
          :default-icon="Globe"
          :info="getProviderInfo(provider)"
          :status="getProviderStatus(provider)"
          @click="openEditProviderModal(provider)"
        >
          <template #icon>
            <span
              class="provider-avatar"
              role="img"
              :aria-label="`Biểu tượng ${provider.display_name}`"
              :style="{
                background: getProviderAvatar(provider).background,
                '--provider-avatar-scale': getProviderAvatar(provider).scale,
                '--provider-avatar-filter': getProviderAvatar(provider).filter
              }"
            >
              <img :src="getProviderAvatar(provider).icon" alt="" />
            </span>
          </template>
          <template #footer>
            <button class="view-models-btn" type="button" @click.stop="openModelsModal(provider)">
              <Settings2 :size="14" />
              Quản lý mô hình
              <span v-if="provider.enabled_models?.length" class="enabled-count"
                >（Đã bật {{ provider.enabled_models.length }} mô hình）</span
              >
            </button>
          </template>
        </InfoCard>
      </ExtensionCardGrid>

      <div v-if="disabledProviders.length" class="provider-section-header">
        Chưa bật ({{ disabledProviders.length }})
      </div>
      <ExtensionCardGrid v-if="disabledProviders.length" :min-width="320">
        <InfoCard
          v-for="provider in disabledProviders"
          :key="provider.provider_id"
          variant="mini"
          :title="provider.display_name"
          :description="provider.provider_id"
          @click="openEditProviderModal(provider)"
        >
          <template #icon>
            <span
              class="provider-avatar"
              role="img"
              :aria-label="`Biểu tượng ${provider.display_name}`"
              :style="{
                background: getProviderAvatar(provider).background,
                '--provider-avatar-scale': getProviderAvatar(provider).scale,
                '--provider-avatar-filter': getProviderAvatar(provider).filter
              }"
            >
              <img :src="getProviderAvatar(provider).icon" alt="" />
            </span>
          </template>
        </InfoCard>
      </ExtensionCardGrid>
    </template>

    <!-- Provider Catalog Modal -->
    <ProviderCatalogModal
      v-model:open="showCatalogModal"
      :active-providers="providers"
      @select="handleSelectCatalogProvider"
    />

    <!-- Provider Setup/Config Modal -->
    <ProviderConfigModal
      v-model:open="showConfigModal"
      :mode="configModalMode"
      :initial-data="selectedProviderForConfig"
      :provider-contains-default-model="providerContainsDefaultModel"
      :warn-default-model-protected="warnDefaultModelProtected"
      @saved="handleSavedProvider"
      @deleted="handleDeletedProvider"
    />
    <a-modal
      v-model:open="showModelsModal"
      :title="
        currentProviderForModels
          ? `${currentProviderForModels.display_name} - Cấu hình mô hình`
          : 'Cấu hình mô hình'
      "
      :width="800"
      :footer="null"
    >
      <div v-if="currentProviderForModels" class="models-modal-content">
        <!-- Enabled Models Section -->
        <div class="models-section">
          <div class="enabled-header">
            <h4 class="models-section-title">
              Đã bật mô hình ({{ currentProviderForModels.enabled_models?.length || 0 }})
            </h4>
            <div class="actions">
              <a-button
                size="small"
                type="primary"
                class="lucide-icon-btn"
                :loading="remoteLoading"
                @click="fetchRemoteModels(currentProviderForModels.provider_id)"
              >
                Nhận mô hình từ xa
              </a-button>
              <a-button
                size="small"
                class="lucide-icon-btn"
                @click="openCreateModal(currentProviderForModels)"
              >
                <Plus :size="14" />
                <span>Thêm thủ công</span>
              </a-button>
            </div>
          </div>
          <div class="models-table" v-if="currentProviderForModels.enabled_models?.length">
            <div class="table-head">
              <span class="col-name">người mẫu</span>
              <span class="col-type">Loại</span>
              <span class="col-context">bối cảnh</span>
              <span class="col-dim">Kích thước</span>
              <span class="col-ops">hoạt động</span>
            </div>
            <div
              v-for="model in currentProviderForModels.enabled_models"
              :key="model.id"
              class="table-row"
              :class="{ stale: isModelStale(model, currentProviderForModels.provider_id) }"
            >
              <div class="model-info">
                <span class="model-name">{{ getModelDisplayName(model) }}</span>
                <span class="model-id">{{ getModelId(model) }}</span>
              </div>
              <span class="col-type">
                <span class="type-tag" :class="model.type">{{ model.type }}</span>
                <span
                  v-if="model.source === 'manual'"
                  class="type-tag manual"
                  title="Quản trị viên thêm thủ công"
                  aria-label="Quản trị viên thêm thủ công"
                >
                  <LayersPlus :size="12" />
                </span>
              </span>
              <span class="col-context">
                {{
                  getProviderModelInfo(currentProviderForModels.provider_id, model).contextLabel ||
                  '-'
                }}
              </span>
              <span class="col-dim">
                <span
                  v-if="model.type === 'embedding' && !model.dimension"
                  class="dim-warning"
                  title="Thiếu cấu hình thứ nguyên"
                  >⚠</span
                >
                <span v-else>{{ model.dimension || '-' }}</span>
              </span>
              <span class="col-ops">
                <a-button
                  size="small"
                  class="model-test-button"
                  :class="{
                    'is-testing': isModelTesting(currentProviderForModels.provider_id, model.id)
                  }"
                  aria-label="Kết nối mô hình thử nghiệm"
                  :aria-busy="isModelTesting(currentProviderForModels.provider_id, model.id)"
                  :title="getModelTestTitle(currentProviderForModels.provider_id, model)"
                  @click="testModelConnection(currentProviderForModels.provider_id, model)"
                >
                  <LoaderCircle
                    v-if="isModelTesting(currentProviderForModels.provider_id, model.id)"
                    :size="13"
                    class="spinning"
                  />
                  <Zap v-else :size="13" />
                </a-button>
                <a-button
                  size="small"
                  class="lucide-icon-btn"
                  :title="`Cấu hình ${getModelDisplayName(model)}`"
                  :aria-label="`Cấu hình ${getModelDisplayName(model)}`"
                  @click="openModelConfigModal(model)"
                >
                  <Settings2 :size="13" />
                </a-button>
                <a-button
                  size="small"
                  danger
                  class="lucide-icon-btn"
                  :title="`Gỡ bỏ ${getModelDisplayName(model)}`"
                  :aria-label="`Gỡ bỏ ${getModelDisplayName(model)}`"
                  @click="removeModel(currentProviderForModels.provider_id, model.id)"
                >
                  <Trash2 :size="13" />
                </a-button>
              </span>
            </div>
          </div>
          <a-empty v-else description="Chưa có mô hình nào được kích hoạt" />
        </div>

        <!-- Remote Models Section -->
        <div class="models-section">
          <div class="remote-header">
            <h4 class="models-section-title">Mô hình ứng viên từ xa ({{ filteredRemoteModels.length }})</h4>
            <div
              v-if="remoteModelsMap[currentProviderForModels.provider_id]?.length"
              class="remote-controls"
            >
              <a-input
                v-model:value="remoteModelSearch[currentProviderForModels.provider_id]"
                class="remote-search-input"
                placeholder="Tìm kiếm mô hình..."
                allow-clear
                autocomplete="off"
                autocapitalize="none"
                autocorrect="off"
                spellcheck="false"
              >
                <template #prefix><Search :size="12" /></template>
              </a-input>
              <button
                type="button"
                class="currency-toggle"
                :title="
                  priceCurrency === 'CNY'
                    ? `Đang hiển thị theo NDT, bấm để chuyển sang USD (1 USD ≈ ¥${USD_TO_CNY_RATE})`
                    : `Đang hiển thị theo USD, bấm để chuyển sang NDT (1 USD ≈ ¥${USD_TO_CNY_RATE})`
                "
                :aria-label="priceCurrency === 'CNY' ? 'Chuyển sang tính giá bằng USD' : 'Chuyển sang tính giá bằng NDT'"
                @click="togglePriceCurrency"
              >
                {{ priceCurrency === 'CNY' ? '¥' : '$' }}
              </button>
              <a-segmented
                v-model:value="remoteModelTypeFilter[currentProviderForModels.provider_id]"
                :options="remoteModelTypeOptions"
                class="remote-type-filter"
              />
            </div>
          </div>
          <div
            class="remote-list"
            v-if="remoteModelsMap[currentProviderForModels.provider_id]?.length"
          >
            <div
              v-for="remoteModel in filteredRemoteModels"
              :key="remoteModel.id"
              class="remote-row"
            >
              <span class="remote-name">{{ getModelDisplayName(remoteModel) }}</span>
              <div class="remote-tags">
                <template
                  v-for="mod in getProviderModelInfo(
                    currentProviderForModels.provider_id,
                    remoteModel
                  ).inputModalities"
                  :key="mod"
                >
                  <a-tooltip :title="getModalityDisplay(mod).label">
                    <span
                      class="modality-tag"
                      role="img"
                      :aria-label="getModalityDisplay(mod).label"
                    >
                      <component :is="getModalityDisplay(mod).icon" :size="13" />
                    </span>
                  </a-tooltip>
                </template>
                <span class="type-tag" :class="remoteModel.type || 'chat'">
                  {{ remoteModel.type || 'chat' }}
                </span>
              </div>
              <span class="remote-context">{{
                getProviderModelInfo(currentProviderForModels.provider_id, remoteModel)
                  .contextLabel || '-'
              }}</span>
              <span
                v-if="getRemoteModelPriceDisplay(currentProviderForModels.provider_id, remoteModel)"
                class="remote-price"
              >
                {{ getRemoteModelPriceDisplay(currentProviderForModels.provider_id, remoteModel) }}
              </span>
              <span v-else class="remote-price placeholder">N/A</span>
              <a-button
                size="small"
                :type="
                  currentProviderForModels.enabled_models?.some((m) => m.id === remoteModel.id)
                    ? 'primary'
                    : 'default'
                "
                class="lucide-icon-btn"
                :title="
                  currentProviderForModels.enabled_models?.some((m) => m.id === remoteModel.id)
                    ? `${getModelDisplayName(remoteModel)} đã được bật`
                    : `Bật ${getModelDisplayName(remoteModel)}`
                "
                :aria-label="
                  currentProviderForModels.enabled_models?.some((m) => m.id === remoteModel.id)
                    ? `${getModelDisplayName(remoteModel)} đã được bật`
                    : `Bật ${getModelDisplayName(remoteModel)}`
                "
                :disabled="
                  currentProviderForModels.enabled_models?.some((m) => m.id === remoteModel.id)
                "
                @click="addModelFromRemote(currentProviderForModels.provider_id, remoteModel)"
              >
                <CheckCircle2
                  :size="13"
                  v-if="
                    currentProviderForModels.enabled_models?.some((m) => m.id === remoteModel.id)
                  "
                />
                <Plus :size="13" v-else />
              </a-button>
            </div>
          </div>
          <div v-if="Object.keys(modelCatalogProviders).length" class="model-metadata-source">
            Một số thông tin (giá, khả năng, v.v.) lấy từ
            <a href="https://models.dev" target="_blank" rel="noreferrer">models.dev</a>
            . Giá theo NDT quy đổi theo tỷ giá cố định 1 USD = ¥{{ USD_TO_CNY_RATE }}. Thông tin
            trên chỉ để tham khảo, có thể chênh lệch với trang chủ hoặc tỷ giá thực tế.
          </div>
          <div class="remote-fetch-actions"></div>
        </div>
      </div>
    </a-modal>
    <!-- Model Config Modal -->
    <a-modal
      v-model:open="showModelModal"
      :title="isCreating ? 'Thêm mô hình theo cách thủ công' : 'Cấu hình mô hình'"
      :width="520"
      :confirm-loading="saving"
      @ok="saveModelConfig"
    >
      <div class="modal-form">
        <div v-if="isCreating" class="form-row">
          <label class="form-label">
            <span>người mẫu ID <span class="required-mark">*</span></span>
            <a-input v-model:value="editingModel.id" placeholder="Ví dụ BAAI/bge-m3" allow-clear />
          </label>
        </div>
        <div v-else class="model-id-display">
          <span class="info-label">người mẫu ID</span>
          <code>{{ editingModel.id }}</code>
        </div>

        <div class="form-row">
          <label class="form-label">
            <span>tên hiển thị</span>
            <a-input v-model:value="editingModel.display_name" />
          </label>
          <label class="form-label">
            <span>Loại mô hình</span>
            <a-select
              v-model:value="editingModel.type"
              :options="editingModelTypeOptions"
              :disabled="editingModelTypeOptions.length === 1"
            />
          </label>
        </div>

        <div class="form-row">
          <label class="form-label">
            <span>Phạm vi thỏa thuận</span>
            <a-input v-model:value="editingModel.protocol_override" placeholder="Tùy chọn" />
          </label>
          <label class="form-label">
            <span>Base URL Bìa</span>
            <a-input v-model:value="editingModel.base_url_override" placeholder="Tùy chọn" />
          </label>
        </div>

        <label class="form-label full-width">
          <span>Tham số yêu cầu mô hình (JSON)</span>
          <a-textarea
            v-model:value="editingModel.request_body_overrides_text"
            :rows="6"
            :placeholder="REQUEST_BODY_OVERRIDES_PLACEHOLDER"
          />
          <small class="form-help">
            Chỉ các mô hình chat của nhà cung cấp tương thích OpenAI (bao gồm OpenRouter) mới
            được truyền qua extra_body; hỗ trợ enable_thinking, thinking_budget, thinking,
            reasoning và reasoning_effort.
          </small>
        </label>

        <div class="form-row">
          <label class="form-label" v-if="editingModel.type === 'embedding'">
            <span>Kích thước</span>
            <a-input-number v-model:value="editingModel.dimension" :min="1" />
          </label>
          <label
            class="form-label"
            v-if="editingModel.type === 'embedding' || editingModel.type === 'rerank'"
          >
            <span>Batch Size</span>
            <a-input-number v-model:value="editingModel.batch_size" :min="1" />
          </label>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<style lang="less" scoped>
.model-provider-manage-panel {
  height: 100%;
  min-height: 0;

  :deep(.info-card-icon) {
    border: none;
    background: transparent;
  }
}

.provider-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  overflow: hidden;
  border: 1px solid rgb(0 0 0 / 6%);
  border-radius: 8px;

  img {
    width: calc(100% * var(--provider-avatar-scale));
    height: calc(100% * var(--provider-avatar-scale));
    object-fit: contain;
    filter: var(--provider-avatar-filter);
  }
}

.view-models-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border: none;
  background: transparent;
  color: var(--gray-700);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.15s;

  &:hover {
    background: var(--gray-50);
    color: var(--gray-800);
  }
}

.provider-section-header {
  padding: 12px var(--page-padding) 0;
  color: var(--gray-500);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.4px;
}

.provider-empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 100px 20px;
  text-align: center;
}

.enabled-count {
  color: var(--gray-500);
  font-size: 12px;
  font-weight: 400;
}

.spinning {
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

.models-modal-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.models-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.models-section-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-700);
}

.models-table {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--gray-150);
  border-radius: 6px;
  overflow: hidden;
}

.table-head,
.table-row {
  display: grid;
  grid-template-columns: 1fr 80px 70px 60px 150px;
  gap: 8px;
  align-items: center;
}

.table-head {
  padding: 10px 12px;
  background: var(--gray-50);
  font-size: 11px;
  font-weight: 600;
  color: var(--gray-500);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.table-row {
  padding: 10px 12px;
  border-top: 1px solid var(--gray-100);
  font-size: 13px;
  transition: background 0.1s;

  &:hover {
    background: var(--gray-10);
  }

  &.stale {
    background: var(--color-warning-50);
  }
}

.model-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.model-name {
  font-weight: 500;
  color: var(--gray-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-id {
  font-size: 11px;
  color: var(--gray-500);
  font-family: monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-type {
  display: flex;
  align-items: center;
}

.col-context,
.col-dim {
  color: var(--gray-600);
  font-size: 12px;
}

.col-ops {
  display: flex;
  gap: 4px;
  justify-content: flex-end;
}

.model-test-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  min-width: 28px;
  padding: 0;
  color: var(--main-700);

  &.is-testing {
    color: var(--main-600);
    cursor: wait;
  }
}

.type-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;

  & + & {
    margin-left: 4px;
  }

  &.chat {
    background: var(--color-info-50);
    color: var(--color-info-700);
  }

  &.embedding {
    background: var(--color-success-50);
    color: var(--color-success-700);
  }

  &.rerank {
    background: var(--color-warning-50);
    color: var(--color-warning-900);
  }

  &.manual {
    background: var(--gray-200);
    color: var(--gray-700);
  }
}

.enabled-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;

  .models-section-title {
    margin: 0;
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.remote-header {
  display: flex;
  align-items: center;
  gap: 12px;

  .models-section-title {
    margin: 0;
    flex-shrink: 0;
  }
}

.remote-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-left: auto;
}

.remote-search-input {
  width: 180px;
}

.currency-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-0);
  color: var(--gray-700);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;

  &:hover {
    border-color: var(--gray-200);
    background: var(--gray-25);
    color: var(--gray-900);
  }

  &:focus-visible {
    outline: 2px solid var(--main-200);
    outline-offset: 1px;
  }
}

.remote-type-filter {
  flex-shrink: 0;
}

.remote-list {
  border-top: 1px solid var(--gray-100);
}

.remote-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-top: 1px solid var(--gray-100);
  font-size: 13px;

  &:first-child {
    border-top: none;
  }
}

.remote-name {
  flex: 1;
  min-width: 0;
  font-weight: 500;
  color: var(--gray-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remote-tags {
  display: flex;
  align-items: center;
  gap: 4px;
}

.modality-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 3px;
  background: var(--color-accent-50);
  color: var(--color-accent-700);
}

.dim-warning {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: 3px;
  background: var(--color-warning-50);
  color: var(--color-warning-700);
  font-size: 10px;
  font-weight: 500;
}

.remote-context {
  width: 60px;
  color: var(--gray-500);
  font-size: 12px;
}

.remote-price {
  width: 100px;
  font-size: 11px;
  color: var(--gray-600);
  font-family: monospace;

  &.placeholder {
    color: var(--gray-400);
  }
}

.model-metadata-source {
  color: var(--gray-500);
  font-size: 11px;
  line-height: 1.5;

  a {
    color: var(--main-600);
  }
}

.modal-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.form-label {
  display: flex;
  flex-direction: column;
  gap: 6px;

  > span {
    color: var(--gray-700);
    font-size: 12px;
    font-weight: 500;
  }
}

.form-help {
  color: var(--gray-500);
  font-size: 11px;
  line-height: 1.5;
}

.full-width {
  grid-column: 1 / -1;
}

.form-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;

  > span {
    color: var(--gray-700);
    font-size: 12px;
    font-weight: 500;
  }
}

.advanced-collapse {
  :deep(.ant-collapse-content-box) {
    padding-inline: 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  :deep(.ant-collapse-header) {
    padding-inline: 0;
  }
}

.provider-modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.provider-modal-footer-actions {
  display: flex;
  gap: 8px;
}

.model-id-display {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  background: var(--gray-50);
  border-radius: 6px;
  margin-bottom: 4px;

  .info-label {
    color: var(--gray-500);
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
  }

  code {
    font-family: monospace;
    font-size: 13px;
    color: var(--gray-800);
  }
}

@media (max-width: 768px) {
  .form-row {
    grid-template-columns: 1fr;
  }

  .table-head,
  .table-row {
    grid-template-columns: 1fr 60px 60px;
    font-size: 12px;
  }

  .col-context,
  .col-dim {
    display: none;
  }
}
</style>
