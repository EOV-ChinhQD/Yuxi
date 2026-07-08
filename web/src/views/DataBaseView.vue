<template>
  <div class="database-container layout-container">
    <PageHeader
      v-if="!props.embedded"
      title="cơ sở tri thức"
      :active-key="knowledgeActiveView"
      :tabs="knowledgeViewItems"
      :loading="dbState.listLoading"
      :show-border="true"
      aria-label="Chuyển đổi chế độ xem cơ sở kiến thức"
    />

    <PageShoulder v-model:search="searchQuery" search-placeholder="Tìm kiếm cơ sở kiến thức...">
      <template #filters>
        <a-select
          v-model:value="typeFilter"
          style="width: 120px"
          placeholder="Tất cả các loại"
          allow-clear
        >
          <a-select-option :value="null">Tất cả các loại</a-select-option>
          <a-select-option v-for="t in kbTypes" :key="t" :value="t">
            {{ getKbTypeLabel(t) }}
          </a-select-option>
        </a-select>
      </template>
      <template #actions>
        <a-button
          type="primary"
          class="lucide-icon-btn"
          :disabled="!kbTypes.length"
          @click="state.openNewDatabaseModel = true"
        >
          <Plus :size="16" /> Tạo nền tảng kiến thức mới
        </a-button>
      </template>
    </PageShoulder>

    <a-modal
      :open="state.openNewDatabaseModel"
      title="Tạo nền tảng kiến thức mới"
      :confirm-loading="dbState.creating"
      @ok="handleCreateDatabase"
      @cancel="cancelCreateDatabase"
      class="new-database-modal"
      width="800px"
      destroyOnClose
    >
      <div class="new-database-form">
        <!-- Lựa chọn loại cơ sở kiến thức -->
        <div class="form-section">
          <h3 class="section-title">Loại cơ sở tri thức<span class="required-mark">*</span></h3>
          <div class="kb-type-cards">
            <div
              v-for="(typeInfo, typeKey) in orderedKbTypes"
              :key="typeKey"
              class="kb-type-card"
              :class="{ active: newDatabase.kb_type === typeKey }"
              :data-type="typeKey"
              @click="handleKbTypeChange(typeKey)"
            >
              <div class="card-header">
                <component :is="getKbTypeIcon(typeKey)" class="type-icon" />
                <span class="type-title">{{ getKbTypeLabel(typeKey) }}</span>
              </div>
              <div class="card-description">{{ getKbTypeDescription(typeInfo) }}</div>
            </div>
          </div>
        </div>

        <div class="form-section">
          <h3 class="section-title">Tên cơ sở kiến thức<span class="required-mark">*</span></h3>
          <a-input v-model:value="newDatabase.name" placeholder="Tạo tên cơ sở kiến thức mới" />
        </div>

        <div v-if="selectedKbTypeInfo?.requires_embedding_model" class="form-grid two-columns">
          <div class="form-section compact-section">
            <h3 class="section-title">mô hình nhúng</h3>
            <EmbeddingModelSelector
              v-model:value="newDatabase.embedding_model_spec"
              class="full-width"
              placeholder="Vui lòng chọn một mô hình để nhúng"
            />
          </div>

          <div class="form-section compact-section">
            <div class="chunk-preset-title-row">
              <h3 class="section-title">chiến lược phân chia</h3>
              <a-tooltip :title="selectedPresetDescription">
                <QuestionCircleOutlined class="chunk-preset-help-icon" />
              </a-tooltip>
            </div>
            <a-select
              v-model:value="newDatabase.chunk_preset_id"
              :options="chunkPresetOptions"
              :loading="chunkPresetLoading"
              class="full-width"
            />
          </div>
        </div>

        <div v-if="createParamOptions.length" class="form-grid three-columns">
          <div
            v-for="field in createParamOptions"
            :key="field.key"
            class="form-section compact-section"
          >
            <h3 class="section-title">
              {{ field.label || field.key
              }}<span v-if="field.required" class="required-mark">*</span>
            </h3>
            <a-input-password
              v-if="field.type === 'password'"
              v-model:value="newDatabase.additional_params[field.key]"
              :placeholder="field.placeholder"
            />
            <a-input-number
              v-else-if="field.type === 'number'"
              v-model:value="newDatabase.additional_params[field.key]"
              :min="field.min"
              :max="field.max"
              :step="field.step"
              class="full-width"
            />
            <a-switch
              v-else-if="field.type === 'boolean'"
              v-model:checked="newDatabase.additional_params[field.key]"
            />
            <a-select
              v-else-if="field.type === 'select'"
              v-model:value="newDatabase.additional_params[field.key]"
              :options="field.options || []"
              class="full-width"
            />
            <a-input
              v-else
              v-model:value="newDatabase.additional_params[field.key]"
              :placeholder="field.placeholder"
            />
            <p v-if="field.description" class="field-hint">{{ field.description }}</p>
          </div>
        </div>

        <div class="form-section">
          <h3 class="section-title">Mô tả cơ sở kiến thức</h3>
          <p class="field-hint description-hint">
            trong quá trình đại lý，Mô tả ở đây sẽ đóng vai trò là mô tả của công cụ。Tác nhân chọn công cụ thích hợp dựa trên tiêu đề và mô tả của cơ sở tri thức。Vì vậy, mô tả chi tiết hơn ở đây là，Đại lý càng dễ dàng lựa chọn công cụ phù hợp。
          </p>
          <AiTextarea
            v-model="newDatabase.description"
            :name="newDatabase.name"
            placeholder="Tạo mô tả cơ sở kiến thức mới"
            :auto-size="{ minRows: 3, maxRows: 10 }"
          />
        </div>

        <!-- Cấu hình chia sẻ -->
        <div class="form-section compact-section">
          <h3 class="section-title">Cài đặt chia sẻ</h3>
          <ShareConfigForm
            ref="shareConfigFormRef"
            v-model="shareConfig"
            :auto-select-user-dept="true"
          />
        </div>
      </div>
      <template #footer>
        <a-button key="back" @click="cancelCreateDatabase">Hủy bỏ</a-button>
        <a-button
          key="submit"
          type="primary"
          :loading="dbState.creating"
          :disabled="!selectedKbTypeInfo"
          @click="handleCreateDatabase"
          >tạo ra</a-button
        >
      </template>
    </a-modal>

    <!-- Trạng thái tải -->
    <div v-if="dbState.listLoading" class="loading-container">
      <a-spin size="large" />
      <p>Đang tải cơ sở kiến thức...</p>
    </div>

    <!-- Hiển thị trạng thái trống -->
    <ResourceEmptyState
      v-else-if="!databases || databases.length === 0"
      title="Chưa có nền tảng kiến thức"
      description="Sau khi tạo ra cơ sở kiến thức，Có thể tải tệp lên và định cấu hình truy xuất、Khả năng lập bản đồ và đánh giá。"
      :icon="getKbTypeIcon('milvus')"
    >
      <template #actions>
        <a-button
          type="primary"
          size="large"
          class="lucide-icon-btn"
          :disabled="!kbTypes.length"
          @click="state.openNewDatabaseModel = true"
        >
          <template #icon>
            <Plus :size="16" />
          </template>
          Tạo nền tảng kiến thức
        </a-button>
      </template>
    </ResourceEmptyState>

    <!-- Danh sách cơ sở dữ liệu -->
    <ExtensionCardGrid v-else>
      <InfoCard
        v-for="database in filteredDatabases"
        :key="database.kb_id"
        :title="database.name"
        :subtitle="cardSubtitle(database)"
        :description="database.description || 'Chưa có mô tả'"
        :tags="cardTags(database)"
        @click="navigateToDatabase(database)"
      >
        <template #icon>
          <component :is="getKbTypeIcon(database.kb_type || 'milvus')" :size="20" />
        </template>
        <template #status />
      </InfoCard>
    </ExtensionCardGrid>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useConfigStore } from '@/stores/config'
import { useDatabaseStore } from '@/stores/database'
import { QuestionCircleOutlined } from '@ant-design/icons-vue'
import { Plus } from 'lucide-vue-next'
import { message } from 'ant-design-vue'
import { typeApi } from '@/apis/knowledge_api'
import PageHeader from '@/components/shared/PageHeader.vue'
import PageShoulder from '@/components/shared/PageShoulder.vue'
import ResourceEmptyState from '@/components/shared/ResourceEmptyState.vue'
import EmbeddingModelSelector from '@/components/EmbeddingModelSelector.vue'
import ShareConfigForm from '@/components/ShareConfigForm.vue'
import ExtensionCardGrid from '@/components/extensions/ExtensionCardGrid.vue'
import InfoCard from '@/components/shared/InfoCard.vue'
import dayjs, { parseToShanghai } from '@/utils/time'
import AiTextarea from '@/components/AiTextarea.vue'
import { useChunkPresetOptions } from '@/composables/useChunkPresetOptions'
import { getKbTypeLabel, getKbTypeIcon, getKbTypeColor, kbUtils } from '@/utils/kb_utils'
import { DEFAULT_CHUNK_PRESET_ID } from '@/utils/chunkUtils'

const route = useRoute()
const router = useRouter()
const configStore = useConfigStore()
const databaseStore = useDatabaseStore()
const {
  chunkPresetSelectOptions: chunkPresetOptions,
  chunkPresetLoading,
  loadChunkPresetOptions,
  getChunkPresetDescription
} = useChunkPresetOptions()

const props = defineProps({
  embedded: { type: Boolean, default: false }
})

// sử dụng store trạng thái
const { databases, state: dbState } = storeToRefs(databaseStore)

const knowledgeActiveView = 'documents'
const knowledgeViewItems = [
  { key: 'documents', label: 'Cơ sở kiến thức tài liệu', path: '/extensions?tab=knowledge' }
]

const kbTypes = computed(() => Object.keys(supportedKbTypes.value))
const searchQuery = ref('')
const typeFilter = ref(null)

const filteredDatabases = computed(() => {
  let list = databases.value
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(
      (db) =>
        db.name.toLowerCase().includes(q) ||
        (db.description && db.description.toLowerCase().includes(q))
    )
  }
  if (typeFilter.value) {
    list = list.filter((db) => (db.kb_type || 'milvus') === typeFilter.value)
  }
  return list
})

const state = reactive({
  openNewDatabaseModel: false
})

const createDefaultShareConfig = () => ({
  access_level: 'global',
  department_ids: [],
  user_uids: []
})

const shareConfig = ref(createDefaultShareConfig())
const shareConfigFormRef = ref(null)

const createEmptyDatabaseForm = () => ({
  name: '',
  description: '',
  embedding_model_spec: configStore.config?.embed_model,
  kb_type: '',
  storage: '',
  chunk_preset_id: DEFAULT_CHUNK_PRESET_ID,
  additional_params: {}
})

const newDatabase = reactive(createEmptyDatabaseForm())

const selectedPresetDescription = computed(() =>
  getChunkPresetDescription(newDatabase.chunk_preset_id)
)

// Các loại cơ sở kiến thức được hỗ trợ
const supportedKbTypes = ref({})

// Loại cơ sở tri thức được sắp xếp
const orderedKbTypes = computed(() => supportedKbTypes.value)

const selectedKbTypeInfo = computed(() => supportedKbTypes.value[newDatabase.kb_type] || null)

const createParamOptions = computed(() => selectedKbTypeInfo.value?.create_params?.options || [])

const getKbTypeDescription = (typeInfo) => typeInfo?.description || ''

const resetCreateParamValues = () => {
  newDatabase.additional_params = {}
  for (const field of createParamOptions.value) {
    if ('default' in field) {
      newDatabase.additional_params[field.key] = field.default
    } else if (field.type === 'boolean') {
      newDatabase.additional_params[field.key] = false
    } else {
      newDatabase.additional_params[field.key] = ''
    }
  }
}

// Tải các loại cơ sở kiến thức được hỗ trợ
const loadSupportedKbTypes = async () => {
  try {
    const data = await typeApi.getKnowledgeBaseTypes()
    supportedKbTypes.value = data.kb_types || {}
    newDatabase.kb_type = kbTypes.value[0] || ''
    resetCreateParamValues()
  } catch (error) {
    console.error('Không thể tải loại cơ sở kiến thức:', error)
    supportedKbTypes.value = {}
    newDatabase.kb_type = ''
    resetCreateParamValues()
    message.error('Không thể tải loại cơ sở kiến thức，Vui lòng thử lại sau')
  }
}

const resetNewDatabase = () => {
  Object.assign(newDatabase, createEmptyDatabaseForm())
  newDatabase.kb_type = kbTypes.value[0] || ''
  resetCreateParamValues()
  shareConfig.value = createDefaultShareConfig()
}

const cancelCreateDatabase = () => {
  state.openNewDatabaseModel = false
  resetNewDatabase()
}

// Thời gian tạo định dạng
const formatCreatedTime = (createdAt) => {
  if (!createdAt) return ''
  const parsed = parseToShanghai(createdAt)
  if (!parsed) return ''

  const today = dayjs().startOf('day')
  const createdDay = parsed.startOf('day')
  const diffInDays = today.diff(createdDay, 'day')

  if (diffInDays === 0) {
    return 'Được tạo hôm nay'
  }
  if (diffInDays === 1) {
    return 'Đã tạo ngày hôm qua'
  }
  if (diffInDays < 7) {
    return `${diffInDays} Đã tạo vài ngày trước`
  }
  if (diffInDays < 30) {
    const weeks = Math.floor(diffInDays / 7)
    return `${weeks} Đã tạo vài tuần trước`
  }
  if (diffInDays < 365) {
    const months = Math.floor(diffInDays / 30)
    return `${months} Đã tạo vài tháng trước`
  }
  const years = Math.floor(diffInDays / 365)
  return `${years} Được tạo cách đây nhiều năm`
}

// Xử lý các thay đổi về loại cơ sở kiến thức
const handleKbTypeChange = (type) => {
  console.log('Thay đổi loại cơ sở kiến thức:', type)
  resetNewDatabase()
  newDatabase.kb_type = type
  resetCreateParamValues()
}

// Xây dựng dữ liệu yêu cầu（Chỉ chịu trách nhiệm chuyển đổi dữ liệu biểu mẫu）
const buildRequestData = () => {
  const requestData = {
    database_name: newDatabase.name.trim(),
    description: newDatabase.description?.trim() || '',
    kb_type: newDatabase.kb_type,
    additional_params: {}
  }

  if (selectedKbTypeInfo.value?.requires_embedding_model) {
    requestData.embedding_model_spec =
      newDatabase.embedding_model_spec || configStore.config.embed_model
    requestData.additional_params.chunk_preset_id =
      newDatabase.chunk_preset_id || DEFAULT_CHUNK_PRESET_ID
  }

  requestData.share_config = {
    access_level: shareConfig.value.access_level,
    department_ids:
      shareConfig.value.access_level === 'department' ? shareConfig.value.department_ids || [] : [],
    user_uids: shareConfig.value.access_level === 'user' ? shareConfig.value.user_uids || [] : []
  }

  // Thêm cấu hình cụ thể dựa trên loại
  if (['milvus'].includes(newDatabase.kb_type)) {
    if (newDatabase.storage) {
      requestData.additional_params.storage = newDatabase.storage
    }
  }

  for (const field of createParamOptions.value) {
    const value = newDatabase.additional_params[field.key]
    requestData.additional_params[field.key] = typeof value === 'string' ? value.trim() : value
  }

  return requestData
}

// Tạo trình xử lý nút
const handleCreateDatabase = async () => {
  if (!selectedKbTypeInfo.value) {
    message.error('Tải loại cơ sở kiến thức không thành công，Không thể tạo cơ sở kiến thức')
    return
  }

  for (const field of createParamOptions.value) {
    if (!field.required) continue
    const value = newDatabase.additional_params[field.key]
    if (value === undefined || value === null || (typeof value === 'string' && !value.trim())) {
      message.error(`Vui lòng điền vào${field.label || field.key}`)
      return
    }
  }

  if (shareConfigFormRef.value) {
    const validation = shareConfigFormRef.value.validate()
    if (!validation.valid) {
      message.warning(validation.message)
      return
    }
  }

  const requestData = buildRequestData()
  try {
    await databaseStore.createDatabase(requestData)
    resetNewDatabase()
    state.openNewDatabaseModel = false
  } catch {
    // Lỗi đã có rồi store xử lý trung bình
  }
}

const cardSubtitle = (database) => {
  const parts = []
  if (database.created_at) {
    parts.push(formatCreatedTime(database.created_at))
  }
  if (!kbUtils.isReadOnlyDatabase(database)) {
    parts.push(`${database.row_count || 0} tập tin`)
  }
  return parts.join(' · ')
}

const cardTags = (database) => {
  const tags = [
    {
      name: getKbTypeLabel(database.kb_type || 'milvus'),
      color: getKbTypeColor(database.kb_type || 'milvus')
    }
  ]
  if (database.embedding_model_spec) {
    tags.push({
      name: database.embedding_model_spec.split('/').slice(-1)[0],
      color: 'blue'
    })
  }
  return tags
}

const navigateToDatabase = (database) => {
  router.push({ path: `/extensions/knowledgebase/${database.kb_id}` })
}

watch(
  () => route.path,
  (newPath) => {
    if (newPath === '/extensions' && route.query.tab === 'knowledge') {
      databaseStore.loadDatabases()
    }
  }
)

onMounted(() => {
  loadChunkPresetOptions()
  loadSupportedKbTypes()
  databaseStore.loadDatabases()
})

defineExpose({
  loading: computed(() => dbState.value.listLoading)
})
</script>

<style lang="less" scoped>
.database-container {
  :deep(.info-card-icon) {
    background: var(--gray-0);
  }
}

.new-database-modal {
  .new-database-form {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .form-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .form-section.compact-section {
    gap: 6px;
  }

  .form-grid {
    display: grid;
    gap: 16px;

    &.two-columns {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    &.three-columns {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    @media (max-width: 768px) {
      &.two-columns,
      &.three-columns {
        grid-template-columns: 1fr;
      }
    }
  }

  .full-width {
    width: 100%;
  }

  .compact-model-selector {
    height: 40px;
  }

  .section-title {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: var(--gray-800);
  }

  .required-mark {
    margin-left: 2px;
    color: var(--color-error-500);
  }

  .field-hint {
    margin: 0;
    font-size: 13px;
    line-height: 1.5;
    color: var(--gray-600);
  }

  .description-hint {
    margin-top: -2px;
  }

  .chunk-preset-title-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .chunk-preset-help-icon {
    color: var(--gray-500);
    cursor: help;
    font-size: 14px;
  }

  .kb-type-guide {
    margin: 12px 0;
  }

  .privacy-config {
    display: flex;
    align-items: center;
    margin-bottom: 12px;
  }

  .kb-type-cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin: 4px 0 0;

    @media (max-width: 768px) {
      grid-template-columns: 1fr;
      gap: 10px;
    }

    .kb-type-card {
      border: 1px solid var(--gray-150);
      border-radius: 12px;
      padding: 14px;
      cursor: pointer;
      transition: all 0.2s ease;
      background: var(--gray-0);
      position: relative;
      overflow: hidden;

      &:hover {
        border-color: var(--main-color);
      }

      &.active {
        border-color: var(--main-color);
        background: var(--main-10);
        box-shadow: 0 0 0 1px var(--main-20);

        .type-icon {
          color: var(--main-color);
        }
      }

      .card-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;

        .type-icon {
          width: 20px;
          height: 20px;
          color: var(--main-color);
          flex-shrink: 0;
        }

        .type-title {
          font-size: 15px;
          font-weight: 600;
          color: var(--gray-800);
        }
      }

      .card-description {
        font-size: 13px;
        color: var(--gray-600);
        line-height: 1.5;
        margin-bottom: 0;
      }

      .deprecated-badge {
        background: var(--color-error-100);
        color: var(--color-error-600);
        font-size: 10px;
        font-weight: 600;
        padding: 2px 6px;
        border-radius: 4px;
        margin-left: auto;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        cursor: help;
        transition: all 0.2s ease;

        &:hover {
          background: var(--color-error-200);
          color: var(--color-error-700);
        }
      }
    }
  }

  .chunk-config {
    margin-top: 16px;
    padding: 12px 16px;
    background-color: var(--gray-25);
    border-radius: 6px;
    border: 1px solid var(--gray-150);

    h3 {
      margin-top: 0;
      margin-bottom: 12px;
      color: var(--gray-800);
    }

    .chunk-params {
      display: flex;
      flex-direction: column;
      gap: 12px;

      .param-row {
        display: flex;
        align-items: center;
        gap: 12px;

        label {
          min-width: 80px;
          font-weight: 500;
          color: var(--gray-700);
        }

        .param-hint {
          font-size: 12px;
          color: var(--gray-500);
          margin-left: 8px;
        }
      }
    }
  }
}

.database-container {
  padding: 0;
}

.loading-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 300px;
  gap: 16px;
}

.new-database-modal {
  h3 {
    margin-top: 10px;
  }
}
</style>
