<template>
  <a-modal
    v-model:open="visible"
    title="Tự động tạo điểm chuẩn đánh giá"
    width="600px"
    :mask-closable="!generating"
    :closable="!generating"
    @cancel="handleCancel"
  >
    <a-form ref="formRef" :model="formState" :rules="rules" layout="vertical">
      <a-form-item label="Tên điểm chuẩn" name="name">
        <a-input
          v-model:value="formState.name"
          placeholder="Vui lòng nhập tên điểm chuẩn đánh giá"
        />
      </a-form-item>

      <a-form-item label="Mô tả" name="description">
        <a-textarea
          v-model:value="formState.description"
          placeholder="Vui lòng nhập mô tả về điểm chuẩn đánh giá（Tùy chọn）"
          :rows="3"
        />
      </a-form-item>

      <a-form-item label="Cách xây dựng" name="generation_mode">
        <div class="generation-mode-cards" role="radiogroup" aria-label="Cách xây dựng">
          <div
            v-for="option in generationModeOptions"
            :key="option.value"
            class="generation-mode-card"
            :class="{
              active: formState.generation_mode === option.value,
              disabled: option.disabled
            }"
            role="radio"
            :aria-checked="formState.generation_mode === option.value"
            :aria-disabled="option.disabled"
            :tabindex="option.disabled ? -1 : 0"
            @click="selectGenerationMode(option)"
            @keydown.enter.prevent="selectGenerationMode(option)"
            @keydown.space.prevent="selectGenerationMode(option)"
          >
            <div class="card-header">
              <component :is="option.icon" class="mode-icon" />
              <span class="mode-title">{{ option.label }}</span>
              <a-tag v-if="option.tag" class="mode-tag" size="small">{{ option.tag }}</a-tag>
            </div>
            <div class="card-description">{{ option.description }}</div>
            <div v-if="option.helper" class="card-helper" :class="{ warning: option.disabled }">
              {{ option.helper }}
            </div>
          </div>
        </div>
      </a-form-item>

      <a-form-item
        label="LLMCấu hình mô hình"
        name="llm_model_spec"
        :rules="[{ required: true, message: 'Vui lòng chọnLLMngười mẫu' }]"
      >
        <ModelSelectorComponent
          :model_spec="formState.llm_model_spec"
          placeholder="Chọn câu hỏi được sử dụng để tạo câu hỏiLLMngười mẫu"
          @select-model="handleSelectLLMModel"
        />
      </a-form-item>

      <a-form-item label="Tạo tham số" name="params">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item
              label="Số lượng câu hỏi"
              name="count"
              :labelCol="{ span: 24 }"
              :wrapperCol="{ span: 24 }"
            >
              <a-input-number
                v-model:value="formState.count"
                :min="1"
                :max="100"
                style="width: 100%"
                placeholder="Số lượng câu hỏi được tạo"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item name="neighbors_count" :labelCol="{ span: 24 }" :wrapperCol="{ span: 24 }">
              <template #label>
                <span class="field-label-with-help">
                  ứng cử viên Chunk số lượng
                  <a-tooltip title="Thí sinh tham khảo mỗi khi có câu hỏi Chunk tổng cộng">
                    <CircleHelp class="help-icon" />
                  </a-tooltip>
                </span>
              </template>
              <a-input-number
                v-model:value="formState.neighbors_count"
                :min="0"
                :max="10"
                style="width: 100%"
                placeholder="Mặc định 1"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item
              name="concurrency_count"
              :labelCol="{ span: 24 }"
              :wrapperCol="{ span: 24 }"
            >
              <template #label>
                <span class="field-label-with-help">
                  Số lượng bản dựng đồng thời
                  <a-tooltip
                    title="Tạo câu hỏi đánh giá cùng một lúc worker con số，Quá cao có thể kích hoạt giới hạn hiện tại của dịch vụ mô hình"
                  >
                    <CircleHelp class="help-icon" />
                  </a-tooltip>
                </span>
              </template>
              <a-input-number
                v-model:value="formState.concurrency_count"
                :min="1"
                :max="20"
                style="width: 100%"
                placeholder="Mặc định 10"
              />
            </a-form-item>
          </a-col>
          <a-col v-if="formState.generation_mode === 'graph_enhanced'" :span="12">
            <a-form-item
              name="graph_expand_top_k"
              :labelCol="{ span: 24 }"
              :wrapperCol="{ span: 24 }"
            >
              <template #label>
                <span class="field-label-with-help">
                  Mở rộng mỗi vòng Chunk con số
                  <a-tooltip
                    title="PPR Điểm cao nhất được thêm vào trong mỗi vòng sau khi phổ biến Chunk con số"
                  >
                    <CircleHelp class="help-icon" />
                  </a-tooltip>
                </span>
              </template>
              <a-input-number
                v-model:value="formState.graph_expand_top_k"
                :min="1"
                :max="3"
                style="width: 100%"
                placeholder="Mặc định 1"
              />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form-item>
    </a-form>
    <template #footer>
      <div class="benchmark-modal-footer">
        <div class="benchmark-help-text">
          Cần nắm rõ nguyên tắc tạo chuẩn đánh giá？Xem
          <a
            class="benchmark-help-link"
            href="https://xerrors.github.io/Yuxi/intro/evaluation.html"
            target="_blank"
            rel="noopener noreferrer"
          >
            Hướng dẫn sử dụng
          </a>
        </div>
        <div class="footer-actions">
          <a-button :disabled="generating" @click="handleCancel">Hủy bỏ</a-button>
          <a-button
            type="primary"
            :loading="generating"
            :disabled="generating"
            @click="handleGenerate"
          >
            được rồi
          </a-button>
        </div>
      </div>
    </template>
  </a-modal>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import { CircleHelp, Database, Network } from 'lucide-vue-next'
import { evaluationApi, graphBuildApi } from '@/apis/knowledge_api'
import { useConfigStore } from '@/stores/config'
import ModelSelectorComponent from '@/components/ModelSelectorComponent.vue'

const configStore = useConfigStore()

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  kbId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['update:visible', 'success'])

// Tên cơ sở mặc định
const defaultBenchmarkName = () => {
  const today = new Date().toISOString().slice(0, 10)
  const suffix = Array.from(
    { length: 4 },
    () => '0123456789abcdefghijklmnopqrstuvwxyz'[Math.floor(Math.random() * 36)]
  ).join('')
  return `Test-${today}-${suffix}`
}

// Dữ liệu đáp ứng
const formRef = ref()
const generating = ref(false)
const graphIndexedChunks = ref(0)

const formState = reactive({
  name: defaultBenchmarkName(),
  description: '',
  count: 10,
  neighbors_count: 1,
  concurrency_count: 10,
  generation_mode: 'vector',
  graph_expand_top_k: 1,
  llm_model_spec: configStore.config?.default_model || ''
})

// quy tắc xác thực biểu mẫu
const rules = {
  name: [
    { required: true, message: 'Vui lòng nhập tên điểm chuẩn', trigger: 'blur' },
    {
      min: 2,
      max: 100,
      message: 'Độ dài tên cơ sở phải nằm trong2-100giữa các ký tự',
      trigger: 'blur'
    }
  ],
  count: [{ required: true, message: 'Vui lòng nhập số lượng câu hỏi được tạo', trigger: 'blur' }],
  concurrency_count: [
    { required: true, message: 'Vui lòng nhập số lượng bản dựng đồng thời', trigger: 'blur' }
  ]
}

// Ràng buộc hai chiềuvisible
const visible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const graphEnhancedDisabled = computed(() => graphIndexedChunks.value <= 0)

const generationModeOptions = computed(() => [
  {
    value: 'vector',
    label: 'xây dựng vector',
    tag: 'Mặc định',
    description: 'Nhớ lại dựa trên độ tương tự của vectơ chunks，Ổn định cho mọi cơ sở kiến thức。',
    helper: 'Thích hợp để nhanh chóng tạo ra các tiêu chuẩn đánh giá chung。',
    icon: Database,
    disabled: false
  },
  {
    value: 'graph_enhanced',
    label: 'Xây dựng tăng cường đồ thị',
    tag: 'tập bản đồ',
    description:
      'Dựa trên việc thu hồi vectơ và kết hợp với biểu đồ tri thức để mở rộng mối tương quan chunks。',
    helper: graphEnhancedDisabled.value
      ? 'Cơ sở tri thức hiện tại vẫn chưa hoàn thiện việc xây dựng đồ thị.，Không thể sử dụng phép tăng đồ thị để xây dựng'
      : `Bản đồ đã được xây dựng chunks：${graphIndexedChunks.value}`,
    icon: Network,
    disabled: graphEnhancedDisabled.value
  }
])

const loadGraphBuildStatus = async () => {
  if (!props.kbId) return
  try {
    const status = await graphBuildApi.getStatus(props.kbId)
    graphIndexedChunks.value = Number(status?.indexed_chunks || 0)
    if (graphEnhancedDisabled.value && formState.generation_mode === 'graph_enhanced') {
      formState.generation_mode = 'vector'
    }
  } catch (error) {
    console.error('Không thể tải trạng thái xây dựng bản đồ:', error)
    graphIndexedChunks.value = 0
    if (formState.generation_mode === 'graph_enhanced') {
      formState.generation_mode = 'vector'
    }
  }
}

const selectGenerationMode = (option) => {
  if (option.disabled) return
  formState.generation_mode = option.value
}

// Tạo điểm chuẩn
const handleGenerate = async () => {
  if (generating.value) return

  try {
    // xác nhận mẫu
    await formRef.value.validate()

    generating.value = true

    const params = {
      name: formState.name,
      description: formState.description,
      count: formState.count,
      neighbors_count: formState.neighbors_count,
      concurrency_count: formState.concurrency_count,
      generation_mode: formState.generation_mode,
      graph_expand_top_k: formState.graph_expand_top_k,
      llm_model_spec: formState.llm_model_spec
    }

    const response = await evaluationApi.generateDataset(props.kbId, params)

    if (response.message === 'success') {
      message.success('Nhiệm vụ xây dựng đã được gửi')
      visible.value = false
      resetForm()
      emit('success')
    } else {
      generating.value = false
      message.error(response.message || 'Xây dựng không thành công')
    }
  } catch (error) {
    console.error('Xây dựng không thành công:', error)
    generating.value = false
    message.error(error?.response?.data?.detail || 'Xây dựng không thành công')
  }
}

// Hủy thao tác
const handleCancel = () => {
  if (generating.value) return
  visible.value = false
  resetForm()
}

// Đặt lại biểu mẫu
const resetForm = () => {
  formRef.value?.resetFields()
  Object.assign(formState, {
    name: defaultBenchmarkName(),
    description: '',
    count: 10,
    neighbors_count: 1,
    concurrency_count: 10,
    generation_mode: 'vector',
    graph_expand_top_k: 1,
    llm_model_spec: configStore.config?.default_model || ''
  })
  generating.value = false
}

// chọnLLMngười mẫu
const handleSelectLLMModel = (modelSpec) => {
  formState.llm_model_spec = modelSpec
}

// màn hìnhvisiblethay đổi
watch(visible, (val) => {
  if (val && !generating.value) {
    resetForm()
    loadGraphBuildStatus()
  }
})
</script>

<style scoped lang="less">
.generation-mode-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.field-label-with-help {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.help-icon {
  width: 14px;
  height: 14px;
  color: var(--gray-500);
  cursor: help;
}

.benchmark-modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.benchmark-help-text {
  font-size: 13px;
  line-height: 1.5;
  color: var(--gray-600);
}

.benchmark-help-link {
  margin-left: 2px;
}

.footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.generation-mode-card {
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--gray-0);
  outline: none;

  &:hover,
  &:focus-visible {
    border-color: var(--main-color);
  }

  &:focus-visible {
    box-shadow: 0 0 0 2px var(--main-20);
  }

  &.active {
    border-color: var(--main-color);
    background: var(--main-10);
    box-shadow: 0 0 0 1px var(--main-20);

    .mode-icon {
      color: var(--main-color);
    }
  }

  &.disabled {
    cursor: not-allowed;
    opacity: 0.72;
    background: var(--gray-50);

    &:hover {
      border-color: var(--gray-150);
    }
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
  }

  .mode-icon {
    width: 20px;
    height: 20px;
    color: var(--main-color);
    flex-shrink: 0;
  }

  .mode-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--gray-800);
  }

  .mode-tag {
    margin-left: auto;
    margin-right: 0;
  }

  .card-description {
    font-size: 13px;
    color: var(--gray-600);
    line-height: 1.5;
  }

  .card-helper {
    margin-top: 10px;
    font-size: 12px;
    line-height: 1.5;
    color: var(--gray-500);

    &.warning {
      color: var(--color-warning-500);
    }
  }
}

@media (max-width: 640px) {
  .generation-mode-cards {
    grid-template-columns: 1fr;
  }

  .benchmark-modal-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .footer-actions {
    align-self: flex-end;
  }
}
</style>
