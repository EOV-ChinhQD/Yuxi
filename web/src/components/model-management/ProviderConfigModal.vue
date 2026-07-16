<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { Trash2 } from 'lucide-vue-next'
import { modelProviderApi } from '@/apis/system_api'

const props = defineProps({
  open: {
    type: Boolean,
    required: true
  },
  mode: {
    type: String, // 'quick' | 'full' | 'edit'
    required: true
  },
  initialData: {
    type: Object,
    default: () => null
  },
  providerContainsDefaultModel: {
    type: Function,
    default: () => false
  },
  warnDefaultModelProtected: {
    type: Function,
    default: () => {}
  }
})

const emit = defineEmits(['update:open', 'saved', 'deleted'])

const saving = ref(false)
const fetching = ref(false)
const showAdvanced = ref(false)
const fetchError = ref(null)

const PROVIDER_TYPE_OPTIONS = [
  { value: 'openai', label: 'OpenAI Completions API' },
  { value: 'anthropic', label: 'Anthropic Messages API' }
]

const providerForm = reactive({
  provider_id: '',
  display_name: '',
  provider_type: 'openai',
  default_protocol: '',
  base_url: '',
  embedding_base_url: '',
  rerank_base_url: '',
  models_endpoint: '/models',
  embedding_models_endpoint: '/embeddings/models',
  rerank_models_endpoint: '',
  api_key_env: '',
  api_key: '',
  capabilities: ['chat'],
  is_enabled: true,
  headers_text: '{}',
  extra_text: '{}'
})

const isQuickLayout = computed(() => {
  return props.mode === 'quick' || (props.mode === 'edit' && props.initialData?.is_builtin)
})

const showDeleteBtn = computed(() => {
  return props.mode === 'edit' && !props.initialData?.is_builtin
})

const isSavingOrFetching = computed(() => saving.value || fetching.value)

const formatJsonText = (value) => JSON.stringify(value || {}, null, 2)

const parseJsonObject = (text, label) => {
  try {
    const parsed = JSON.parse(text || '{}')
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      throw new Error(`${label} phải là JSON object`)
    }
    return parsed
  } catch {
    throw new Error(`${label} định dạng JSON không chính xác`)
  }
}

const resetForm = () => {
  Object.assign(providerForm, {
    provider_id: '',
    display_name: '',
    provider_type: 'openai',
    default_protocol: '',
    base_url: '',
    embedding_base_url: '',
    rerank_base_url: '',
    models_endpoint: '/models',
    embedding_models_endpoint: '/embeddings/models',
    rerank_models_endpoint: '',
    api_key_env: '',
    api_key: '',
    capabilities: ['chat'],
    is_enabled: true,
    headers_text: '{}',
    extra_text: '{}'
  })
  showAdvanced.value = false
  fetchError.value = null
}

const initForm = (data) => {
  if (!data) {
    resetForm()
    return
  }
  Object.assign(providerForm, {
    provider_id: data.provider_id || '',
    display_name: data.display_name || '',
    provider_type: data.provider_type || 'openai',
    default_protocol: '',
    base_url: data.base_url || '',
    embedding_base_url: data.embedding_base_url || '',
    rerank_base_url: data.rerank_base_url || '',
    models_endpoint: data.models_endpoint ?? '',
    embedding_models_endpoint: data.embedding_models_endpoint ?? '',
    rerank_models_endpoint: data.rerank_models_endpoint ?? '',
    api_key_env: data.api_key_env || '',
    api_key: data.api_key || '',
    capabilities: data.capabilities?.length ? data.capabilities : ['chat'],
    is_enabled: data.is_enabled !== false,
    headers_text: formatJsonText(data.headers_json),
    extra_text: formatJsonText(data.extra_json)
  })
  showAdvanced.value = false
  fetchError.value = null
}

watch(
  () => props.open,
  (newVal) => {
    if (newVal) {
      initForm(props.initialData)
    }
  }
)

const buildProviderPayload = () => {
  return {
    provider_id: providerForm.provider_id || undefined,
    display_name: providerForm.display_name,
    provider_type: providerForm.provider_type,
    default_protocol: null,
    base_url: providerForm.base_url,
    embedding_base_url: providerForm.embedding_base_url || null,
    rerank_base_url: providerForm.rerank_base_url || null,
    models_endpoint: providerForm.models_endpoint || null,
    embedding_models_endpoint: providerForm.embedding_models_endpoint || null,
    rerank_models_endpoint: providerForm.rerank_models_endpoint || null,
    api_key_env: providerForm.api_key_env || null,
    api_key: providerForm.api_key || null,
    capabilities: providerForm.capabilities,
    is_enabled: providerForm.is_enabled,
    headers_json: parseJsonObject(providerForm.headers_text, 'Tiêu đề yêu cầu'),
    extra_json: parseJsonObject(providerForm.extra_text, 'cấu hình mở rộng')
  }
}

const saveAndFetch = async () => {
  saving.value = true
  fetchError.value = null
  let providerId = providerForm.provider_id

  try {
    const payload = buildProviderPayload()
    if (props.mode === 'quick' || props.mode === 'full') {
      await modelProviderApi.createProvider(payload)
      message.success('Nhà cung cấp đã được tạo')
    } else {
      // mode === 'edit'
      if (
        props.providerContainsDefaultModel(providerForm.provider_id) &&
        providerForm.is_enabled === false
      ) {
        props.warnDefaultModelProtected()
        saving.value = false
        return
      }
      await modelProviderApi.updateProvider(providerForm.provider_id, payload)
      message.success('Đã lưu cấu hình nhà cung cấp')
    }
    saving.value = false

    // Lập tức fetch models
    fetching.value = true
    const fetchResult = await modelProviderApi.fetchRemoteModels(providerId)
    const modelsCount = fetchResult.data?.length || 0
    message.success(`Đã đồng bộ thành công ${modelsCount} mô hình`)
    fetching.value = false

    emit('saved')
    emit('update:open', false)
  } catch (error) {
    saving.value = false
    fetching.value = false
    fetchError.value = error.message || 'Thao tác thất bại'
    message.error(fetchError.value)
  }
}

const deleteProvider = () => {
  if (props.providerContainsDefaultModel(providerForm.provider_id)) {
    props.warnDefaultModelProtected()
    return
  }

  Modal.confirm({
    title: `Xóa ${providerForm.display_name}`,
    content: 'Việc xóa sẽ không ảnh hưởng đến cấu hình model cũ hiện đang được hệ thống sử dụng.',
    okText: 'Xóa',
    okType: 'danger',
    cancelText: 'Hủy bỏ',
    async onOk() {
      try {
        await modelProviderApi.deleteProvider(providerForm.provider_id)
        message.success('Đã xóa')
        emit('deleted', providerForm.provider_id)
        emit('update:open', false)
      } catch (error) {
        message.error(error.message || 'Xóa không thành công')
      }
    }
  })
}
</script>

<template>
  <a-modal
    :open="open"
    :title="mode === 'edit' ? 'Chỉnh sửa nhà cung cấp' : 'Cấu hình nhà cung cấp mới'"
    :width="560"
    :footer="null"
    :maskClosable="!isSavingOrFetching"
    :keyboard="!isSavingOrFetching"
    @cancel="() => !isSavingOrFetching && emit('update:open', false)"
    class="provider-config-modal"
  >
    <div class="modal-form">
      <div v-if="isQuickLayout" class="quick-header-info">
        Thiết lập nhanh cho nhà cung cấp <strong>{{ providerForm.display_name }}</strong
        >.
      </div>

      <!-- General Info -->
      <div class="form-row" v-show="!isQuickLayout">
        <label class="form-label">
          <span>Provider ID</span>
          <a-input
            v-model:value="providerForm.provider_id"
            :disabled="mode === 'edit'"
            placeholder="my-provider"
          />
        </label>
        <label class="form-label">
          <span>Tên hiển thị</span>
          <a-input v-model:value="providerForm.display_name" placeholder="My Provider" />
        </label>
      </div>

      <div class="form-row" v-show="!isQuickLayout">
        <label class="form-label">
          <span>Base URL</span>
          <a-input v-model:value="providerForm.base_url" placeholder="https://api.example.com/v1" />
        </label>
        <label class="form-label">
          <span>Provider Type</span>
          <a-select v-model:value="providerForm.provider_type">
            <a-select-option
              v-for="option in PROVIDER_TYPE_OPTIONS"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </a-select-option>
          </a-select>
        </label>
      </div>

      <!-- API Key Field - ALWAYS visible -->
      <div class="form-row">
        <label class="form-label" v-show="!isQuickLayout">
          <span>API Key Env</span>
          <a-input v-model:value="providerForm.api_key_env" placeholder="Tên biến môi trường" />
        </label>
        <label class="form-label" :class="{ 'full-width': isQuickLayout }">
          <span>API Key</span>
          <a-input-password
            v-model:value="providerForm.api_key"
            placeholder="Nhập API Key để kết nối..."
            :disabled="isSavingOrFetching"
          />
        </label>
      </div>

      <!-- Models Configuration -->
      <div class="form-row" v-show="!isQuickLayout">
        <label class="form-label">
          <span>Models Endpoint</span>
          <a-input v-model:value="providerForm.models_endpoint" placeholder="/models" />
        </label>
      </div>

      <template v-if="!isQuickLayout && providerForm.capabilities.includes('embedding')">
        <div class="form-row">
          <label class="form-label">
            <span>Embedding Base URL</span>
            <a-input
              v-model:value="providerForm.embedding_base_url"
              placeholder="https://api.example.com/v1/embeddings"
            />
          </label>
          <label class="form-label">
            <span>Embedding Endpoint</span>
            <a-input
              v-model:value="providerForm.embedding_models_endpoint"
              placeholder="/embeddings/models"
            />
          </label>
        </div>
      </template>

      <template v-if="!isQuickLayout && providerForm.capabilities.includes('rerank')">
        <div class="form-row">
          <label class="form-label">
            <span>Rerank Base URL</span>
            <a-input
              v-model:value="providerForm.rerank_base_url"
              placeholder="https://api.example.com/v1/rerank"
            />
          </label>
          <label class="form-label">
            <span>Rerank Endpoint</span>
            <a-input
              v-model:value="providerForm.rerank_models_endpoint"
              placeholder="Điền theo tài liệu của nhà cung cấp"
            />
          </label>
        </div>
      </template>

      <label class="form-label full-width" v-show="!isQuickLayout">
        <span>Khả năng hỗ trợ</span>
        <a-select v-model:value="providerForm.capabilities" mode="multiple">
          <a-select-option value="chat">chat</a-select-option>
          <a-select-option value="embedding">embedding</a-select-option>
          <a-select-option value="rerank">rerank</a-select-option>
        </a-select>
      </label>

      <div class="form-switch" v-show="!isQuickLayout">
        <span>Trạng thái</span>
        <a-switch
          v-model:checked="providerForm.is_enabled"
          checked-children="kích hoạt"
          un-checked-children="vô hiệu hóa"
        />
      </div>

      <!-- Advanced Collapse (Locked but kept in DOM) -->
      <a-collapse
        v-if="!isQuickLayout || showAdvanced"
        expand-icon-position="end"
        :ghost="true"
        class="advanced-collapse"
      >
        <a-collapse-panel key="advanced" header="Cấu hình nâng cao">
          <label class="form-label full-width">
            <span>Tiêu đề yêu cầu JSON</span>
            <a-textarea
              v-model:value="providerForm.headers_text"
              :rows="4"
              placeholder="{}"
              :disabled="isSavingOrFetching"
            />
          </label>

          <label class="form-label full-width">
            <span>Cấu hình mở rộng JSON</span>
            <a-textarea
              v-model:value="providerForm.extra_text"
              :rows="4"
              placeholder="{}"
              :disabled="isSavingOrFetching"
            />
          </label>
        </a-collapse-panel>
      </a-collapse>

      <!-- Sync Error Alert with Retry button -->
      <div v-if="fetchError" class="sync-error-alert">
        <div class="error-msg"><strong>Lỗi kết nối:</strong> {{ fetchError }}</div>
        <div class="error-tip">Vui lòng kiểm tra lại API Key hoặc cấu hình mạng và thử lại.</div>
      </div>

      <!-- Custom footer inside body -->
      <div class="provider-modal-footer">
        <a-button
          v-if="showDeleteBtn"
          danger
          class="lucide-icon-btn"
          @click="deleteProvider"
          :disabled="isSavingOrFetching"
        >
          <Trash2 :size="14" />
          Xóa nhà cung cấp
        </a-button>
        <span v-else></span>
        <div class="provider-modal-footer-actions">
          <a-button @click="emit('update:open', false)" :disabled="isSavingOrFetching">
            Hủy bỏ
          </a-button>
          <a-button type="primary" :loading="isSavingOrFetching" @click="saveAndFetch">
            {{ fetchError ? 'Thử lại' : 'Xác nhận' }}
          </a-button>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<style lang="less" scoped>
.provider-config-modal {
  :deep(.ant-modal-body) {
    padding: 24px;
  }
}

.quick-header-info {
  margin-bottom: 20px;
  padding: 10px 14px;
  background: var(--main-5);
  border-left: 4px solid var(--main-color);
  border-radius: 4px;
  font-size: 13px;
  color: var(--gray-700);
}

.modal-form {
  display: flex;
  flex-direction: column;
  gap: 16px;

  .form-row {
    display: flex;
    gap: 16px;
    width: 100%;

    .form-label {
      flex: 1;
      min-width: 0;
    }
  }

  .form-label {
    display: flex;
    flex-direction: column;
    gap: 6px;

    span {
      font-size: 13px;
      font-weight: 550;
      color: var(--gray-800);
    }

    &.full-width {
      width: 100%;
    }
  }

  .form-switch {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid var(--gray-100);

    span {
      font-size: 13px;
      font-weight: 550;
      color: var(--gray-800);
    }
  }

  .advanced-collapse {
    border: 1px solid var(--gray-150);
    border-radius: 8px;
    background: var(--gray-5);

    :deep(.ant-collapse-header) {
      padding: 10px 16px;
      font-size: 13px;
      font-weight: 600;
      color: var(--gray-700);
    }

    :deep(.ant-collapse-content-box) {
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      background: var(--gray-0);
      border-top: 1px solid var(--gray-150);
    }
  }
}

.sync-error-alert {
  padding: 12px 16px;
  background: var(--color-error-50, #fff2f0);
  border: 1px solid var(--color-error-100, #ffccc7);
  border-radius: 8px;
  color: var(--color-error-900, #a8071a);
  font-size: 13px;
  line-height: 18px;

  .error-msg {
    margin-bottom: 4px;
  }

  .error-tip {
    font-size: 12px;
    color: var(--gray-600);
  }
}

.provider-modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--gray-100);

  .provider-modal-footer-actions {
    display: flex;
    gap: 8px;
  }
}

.lucide-icon-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
</style>
