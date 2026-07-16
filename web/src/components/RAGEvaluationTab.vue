<template>
  <div class="rag-evaluation-container">
    <!-- Khu vực kết quả đánh giá -->
    <div class="evaluation-results">
      <template v-if="!selectedDataset">
        <ResourceEmptyState
          class="rag-evaluation-empty"
          title="Chưa có điểm chuẩn đánh giá"
          description="Tải lên hoặc tạo điểm chuẩn đánh giá trước，Chạy lại RAG Đánh giá。"
          :icon="BarChart3"
        >
          <template #actions>
            <a-button type="primary" class="lucide-icon-btn" @click="$emit('switch-to-benchmarks')">
              <ClipboardList :size="16" />
              Đi đến quản lý điểm chuẩn
            </a-button>
          </template>
        </ResourceEmptyState>
      </template>
      <template v-else>
        <div class="last-evaluation-section">
          <div class="section-header">
            <h4 class="section-title">đánh giá cuối cùng</h4>
            <a-dropdown
              v-model:open="evaluationDropdownOpen"
              :trigger="['click']"
              :disabled="availableDatasets.length === 0"
              placement="bottomRight"
            >
              <a-button
                type="primary"
                :loading="startingEvaluation"
                :disabled="availableDatasets.length === 0"
                class="lucide-icon-btn"
              >
                Bắt đầu đánh giá
                <ChevronDown :size="14" />
              </a-button>
              <template #overlay>
                <div class="evaluation-start-dropdown" @click.stop>
                  <div class="dropdown-header">
                    <div class="dropdown-title">Cấu hình đánh giá này</div>
                    <div class="dropdown-subtitle">
                      Bắt đầu đánh giá sau khi chọn đường cơ sở đánh giá và các mô hình tùy chọn
                    </div>
                  </div>

                  <div class="dropdown-model-fields">
                    <a-form-item label="Tên đánh giá">
                      <a-input
                        v-model:value="configForm.name"
                        placeholder="Vui lòng nhập tên đánh giá"
                        :maxlength="100"
                        show-count
                      />
                    </a-form-item>

                    <a-form-item label="Đường cơ sở đánh giá">
                      <div class="dropdown-benchmark-row">
                        <a-select
                          v-model:value="selectedDatasetId"
                          placeholder="Hãy chọn cơ sở đánh giá"
                          style="width: 100%"
                          :loading="datasetsLoading"
                          @change="onDatasetChanged"
                        >
                          <a-select-option
                            v-for="benchmark in availableDatasets"
                            :key="benchmark.dataset_id"
                            :value="benchmark.dataset_id"
                          >
                            {{ benchmark.name }} ({{ benchmark.item_count }} câu hỏi)
                          </a-select-option>
                        </a-select>
                        <a-button
                          size="middle"
                          :loading="datasetsLoading"
                          :icon="h(RefreshCw, { size: 16 })"
                          class="refresh-benchmarks-btn lucide-icon-btn"
                          title="Làm mới danh sách điểm chuẩn đánh giá"
                          @click="() => loadDatasets(true)"
                        />
                      </div>
                    </a-form-item>

                    <a-form-item
                      :label="
                        selectedDataset?.has_gold_answers
                          ? 'mô hình tạo câu trả lời（Tùy chọn）'
                          : 'mô hình tạo câu trả lời（Không bắt buộc đối với điểm chuẩn hiện tại）'
                      "
                    >
                      <ModelSelectorComponent
                        v-model:model_spec="configForm.answer_llm"
                        size="small"
                        displayName="mini"
                        :disabled="!selectedDataset || !selectedDataset.has_gold_answers"
                        @select-model="(value) => (configForm.answer_llm = value)"
                        style="width: 100%"
                      />
                    </a-form-item>

                    <a-form-item
                      :label="
                        selectedDataset?.has_gold_answers
                          ? 'mô hình phán đoán câu trả lời（Tùy chọn）'
                          : 'mô hình phán đoán câu trả lời（Không bắt buộc đối với điểm chuẩn hiện tại）'
                      "
                    >
                      <ModelSelectorComponent
                        v-model:model_spec="configForm.judge_llm"
                        size="small"
                        displayName="mini"
                        :disabled="!selectedDataset || !selectedDataset.has_gold_answers"
                        @select-model="(value) => (configForm.judge_llm = value)"
                        style="width: 100%"
                      />
                    </a-form-item>
                  </div>

                  <div class="dropdown-hint">
                    {{ evaluationStartHint }}
                  </div>

                  <a-button
                    type="primary"
                    block
                    :loading="startingEvaluation"
                    :disabled="!selectedDataset"
                    @click="startEvaluation"
                  >
                    Bắt đầu đánh giá
                  </a-button>
                </div>
              </template>
            </a-dropdown>
          </div>

          <div v-if="latestEvaluation" class="last-evaluation-card">
            <div class="last-evaluation-main">
              <div class="score-ring" :class="getLatestRingClass(latestEvaluation)">
                {{ formatLatestRingValue(latestEvaluation) }}
              </div>
              <div class="last-evaluation-info">
                <div class="last-evaluation-title">
                  {{ getRunName(latestEvaluation) }}
                  <a-tag :color="getStatusColor(latestEvaluation.status)" :bordered="false">
                    {{ getStatusText(latestEvaluation.status) }}
                  </a-tag>
                </div>
                <div class="last-evaluation-meta">
                  {{ getDatasetName(latestEvaluation.dataset_id) }} ·
                  {{ formatTime(latestEvaluation.started_at) }} ·
                  <button
                    v-if="latestEvaluation.status === 'completed'"
                    type="button"
                    class="run-id-link"
                    @click="viewResults(latestEvaluation.run_id)"
                  >
                    Run {{ latestEvaluation.run_id }}
                  </button>
                  <span v-else>Run {{ latestEvaluation.run_id }}</span>
                </div>
                <div v-if="latestEvaluation.status === 'running'" class="last-evaluation-progress">
                  <a-progress
                    :percent="getRunProgress(latestEvaluation)"
                    size="small"
                    status="active"
                    :show-info="false"
                  />
                  <span class="run-progress-message">{{
                    getRunProgressMessage(latestEvaluation)
                  }}</span>
                </div>
              </div>
            </div>
            <div class="last-evaluation-metrics">
              <div class="metric-card">
                <span class="metric-label">Recall@10</span>
                <strong :style="{ color: getMetricColor(getRecall10(latestEvaluation)) }">
                  {{ formatMetricValue(getRecall10(latestEvaluation)) }}
                </strong>
              </div>
              <div class="metric-card">
                <span class="metric-label">Tốn thời gian</span>
                <strong>{{ formatRunDuration(latestEvaluation) }}</strong>
              </div>
              <div class="metric-card">
                <span class="metric-label">Khối lượng dữ liệu</span>
                <strong>{{ formatRunItems(latestEvaluation) }}</strong>
              </div>
              <div class="metric-card">
                <span class="metric-label">tỷ lệ hoàn thành</span>
                <strong>{{ formatCompletionRate(latestEvaluation) }}</strong>
              </div>
            </div>
          </div>

          <div v-else class="last-evaluation-empty">
            Chưa có hồ sơ đánh giá，Sau khi bắt đầu đánh giá, kết quả mới nhất sẽ được hiển thị tại
            đây.。
          </div>
        </div>

        <div class="history-section">
          <div class="section-header">
            <h4 class="section-title">Hồ sơ đánh giá lịch sử</h4>
            <a-button
              type="text"
              size="small"
              :loading="refreshingHistory"
              @click="refreshHistory"
              :icon="h(RefreshCw, { size: 14 })"
              class="refresh-btn lucide-icon-btn"
            >
              Làm mới
            </a-button>
          </div>
          <a-table
            class="history-table"
            :columns="historyColumns"
            :data-source="evaluationHistory"
            :pagination="{ pageSize: 10, showSizeChanger: false }"
            row-key="run_id"
            size="small"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'actions'">
                <a-space>
                  <a
                    v-if="record.status === 'completed'"
                    href=""
                    class="history-action-link"
                    @click.prevent="viewResults(record.run_id)"
                  >
                    Xem
                  </a>
                  <a-popconfirm
                    title="Bạn có chắc chắn muốn xóa bản ghi đánh giá này không?？"
                    description="Việc xóa không thể được khôi phục"
                    @confirm="deleteEvaluationRecord(record.run_id)"
                    ok-text="được rồi"
                    cancel-text="Hủy bỏ"
                  >
                    <a
                      href=""
                      class="history-action-link history-action-link-danger"
                      @click.prevent
                    >
                      Xóa
                    </a>
                  </a-popconfirm>
                </a-space>
              </template>
            </template>
          </a-table>
        </div>
      </template>
    </div>
  </div>

  <Teleport to="body">
    <div v-if="resultModalVisible" class="evaluation-detail-overlay">
      <div class="evaluation-detail-panel">
        <div class="evaluation-detail-titlebar">
          <div class="evaluation-detail-title">
            Kết quả đánh giá - {{ getRunName(selectedResult) }}
          </div>
          <a-button
            type="text"
            size="small"
            class="lucide-icon-btn"
            title="đóng"
            @click="resultModalVisible = false"
          >
            <X :size="16" />
          </a-button>
        </div>

        <div v-if="resultsLoading" class="loading-container">
          <a-spin size="large" />
          <p style="margin-top: 16px; color: var(--gray-600)">Đang tải kết quả đánh giá...</p>
        </div>

        <div v-else-if="selectedResult && detailedResults.length > 0" class="result-detail-content">
          <div class="result-summary-bar">
            <div class="summary-items">
              <span class="summary-item summary-run-id" :title="selectedResult.run_id">
                chạyID：{{ selectedResult.run_id }}
              </span>
              <span class="summary-item">
                Trạng thái：
                <a-tag :color="getStatusColor(selectedResult.status)">
                  {{ getStatusText(selectedResult.status) }}
                </a-tag>
              </span>
              <span class="summary-item">
                Đánh giá chung：
                <a-tag
                  v-if="selectedResult.overall_score != null"
                  :color="getScoreTagColor(selectedResult.overall_score)"
                >
                  {{ (selectedResult.overall_score * 100).toFixed(1) }}%
                </a-tag>
                <span v-else>-</span>
              </span>
              <span class="summary-item">Tổng số câu hỏi：{{ selectedResult.total_items }}</span>
              <span class="summary-item"
                >Số lần hoàn thành：{{ selectedResult.completed_items }}</span
              >
              <span class="summary-item">
                Tổng thời gian sử dụng：{{
                  evaluationStats.totalDuration
                    ? formatDuration(evaluationStats.totalDuration)
                    : '-'
                }}
              </span>
            </div>
            <a-button
              type="default"
              size="small"
              @click="toggleErrorOnly"
              :class="{ 'error-only-active': showErrorsOnly }"
            >
              {{ showErrorsOnly ? 'Hiển thị tất cả' : 'Chỉ xem lỗi' }}
            </a-button>
          </div>

          <div class="result-metrics-bar">
            <div class="metric-items">
              <span class="result-count">
                {{
                  showErrorsOnly
                    ? `Chỉ hiển thị kết quả lỗi，tổng cộng ${paginationTotal} Bài viết`
                    : `Hiển thị tất cả kết quả，tổng cộng ${paginationTotal} Bài viết`
                }}
              </span>
              <template v-if="Object.keys(evaluationStats.retrievalMetrics || {}).length > 0">
                <span
                  v-for="(value, key) in evaluationStats.retrievalMetrics"
                  :key="key"
                  class="compact-metric"
                >
                  {{ getMetricTitle(key) }}：<strong :style="{ color: getScoreColor(value) }">
                    {{ formatMetricValue(value) }}
                  </strong>
                </span>
              </template>
              <span v-if="evaluationStats.totalQuestions" class="compact-metric">
                Trả lời chính xác：<strong
                  :style="{ color: getScoreColor(evaluationStats.answerAccuracy) }"
                >
                  {{ (evaluationStats.answerAccuracy * 100).toFixed(1) }}%
                </strong>
              </span>
            </div>
            <a-switch
              v-model:checked="resultAutoWrap"
              checked-children="dòng mới"
              un-checked-children="Không ngắt dòng"
            />
          </div>

          <a-table
            :columns="resultColumns"
            :data-source="detailedResults"
            :pagination="{
              current: currentPage,
              pageSize: pageSize,
              total: paginationTotal,
              showSizeChanger: true,
              pageSizeOptions: ['10', '20', '50', '100'],
              showQuickJumper: true,
              showTotal: (total, range) =>
                `Không. ${range[0]}-${range[1]} Bài viết，tổng cộng ${total} Bài viết`,
              onChange: handlePageChange,
              onShowSizeChange: handlePageSizeChange
            }"
            :scroll="{ x: resultTableScrollX, y: 'calc(100dvh - 254px)' }"
            :class="{ 'table-nowrap': !resultAutoWrap }"
            size="small"
            :loading="resultsLoading"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'query'">
                <div class="query-text" :title="record.query">{{ record.query }}</div>
              </template>
              <template v-else-if="column.key === 'generated_answer'">
                <div class="answer-text" :title="record.generated_answer">
                  {{ record.generated_answer || '-' }}
                </div>
              </template>
              <template v-else-if="column.key === 'retrieval_score'">
                <div
                  v-if="
                    record.metrics &&
                    Object.keys(record.metrics).some(
                      (k) =>
                        k.startsWith('recall') ||
                        k.startsWith('precision') ||
                        k === 'map' ||
                        k === 'ndcg'
                    )
                  "
                  class="retrieval-metrics"
                >
                  <template v-for="(val, key) in record.metrics" :key="key">
                    <span
                      v-if="
                        key.startsWith('recall') ||
                        key.startsWith('precision') ||
                        key === 'map' ||
                        key === 'ndcg'
                      "
                      class="metric-content"
                      :class="`metric-${getMetricType(key)}`"
                    >
                      <span class="metric-name">{{ getMetricShortName(key) }}</span>
                      <span class="metric-value">{{ formatMetricValue(val) }}</span>
                    </span>
                  </template>
                </div>
                <span v-else class="no-metrics">-</span>
              </template>
              <template v-else-if="column.key === 'answer_score'">
                <div
                  v-if="record.metrics && record.metrics.score !== undefined"
                  class="answer-judgement"
                >
                  <a-tag :color="record.metrics.score > 0.5 ? 'green' : 'red'">
                    {{ record.metrics.score === 1.0 ? 'đúng' : 'Lỗi' }}
                  </a-tag>
                  <div
                    v-if="record.metrics.reasoning"
                    class="answer-reasoning"
                    :title="record.metrics.reasoning"
                  >
                    {{ record.metrics.reasoning }}
                  </div>
                </div>
                <span v-else>-</span>
              </template>
            </template>
          </a-table>
        </div>

        <div v-else-if="selectedResult" class="empty-results">
          <a-empty description="Chưa có dữ liệu kết quả chi tiết">
            <a-button @click="viewDetails(selectedResult)">Xem thông tin cơ bản</a-button>
          </a-empty>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch, h } from 'vue'
import { message } from 'ant-design-vue'
import { evaluationApi } from '@/apis/knowledge_api'
import ModelSelectorComponent from '@/components/ModelSelectorComponent.vue'
import { BarChart3, ChevronDown, ClipboardList, RefreshCw, X } from 'lucide-vue-next'
import ResourceEmptyState from '@/components/shared/ResourceEmptyState.vue'
import { useTaskerStore } from '@/stores/tasker'

const props = defineProps({
  kbId: {
    type: String,
    required: true
  }
})

defineEmits(['switch-to-benchmarks'])

// Sử dụng trung tâm tác vụ store
const taskerStore = useTaskerStore()

// Trạng thái
const selectedDatasetId = ref(null)
const selectedDataset = ref(null)
const datasetsLoading = ref(false)
const availableDatasets = ref([])
const startingEvaluation = ref(false)
const evaluationDropdownOpen = ref(false)
const evaluationHistory = ref([])
const resultModalVisible = ref(false)
const selectedResult = ref(null)
const detailedResults = ref([])
const evaluationStats = ref({})
const resultsLoading = ref(false)
const refreshingHistory = ref(false)
const showErrorsOnly = ref(false)
const resultAutoWrap = ref(false)
const currentPage = ref(1)
const pageSize = ref(50)
const paginationTotal = ref(0)
const paginationTotalPages = ref(0)
let evaluationRefreshTimer = null
let stopColumnResize = null

const resultColumnWidths = reactive({
  query: 360,
  generated_answer: 420,
  retrieval_score: 260,
  answer_score: 320
})

const isDatasetCompleted = (dataset) =>
  (dataset?.build_metadata?.status || 'completed') === 'completed'

const latestEvaluation = computed(() => evaluationHistory.value[0] || null)

const createDefaultNameHash = () => {
  const cryptoApi = globalThis.crypto
  if (cryptoApi?.getRandomValues) {
    const values = new Uint32Array(1)
    cryptoApi.getRandomValues(values)
    return values[0].toString(16).padStart(6, '0').slice(0, 6)
  }
  return Math.floor(Math.random() * 0xffffff)
    .toString(16)
    .padStart(6, '0')
}

const buildDefaultEvaluationName = () => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `eval-${year}${month}${day}-${createDefaultNameHash()}`
}

// Mẫu cấu hình đánh giá（Sử dụng cấu hình mặc định của cơ sở kiến thức）
const configForm = reactive({
  name: buildDefaultEvaluationName(),
  answer_llm: '', // mô hình tạo câu trả lời
  judge_llm: '' // Mô hình phán đoán
})

const evaluationStartHint = computed(() => {
  if (!selectedDataset.value?.has_gold_answers)
    return 'Điểm chuẩn hiện tại chỉ thực hiện đánh giá truy xuất，Không cần chọn mẫu。'
  if (!configForm.answer_llm && !configForm.judge_llm)
    return 'Khi không chọn mẫu，Chỉ đánh giá tìm kiếm sẽ được thực hiện。'
  if (configForm.answer_llm && configForm.judge_llm)
    return 'Đánh giá tìm kiếm và đánh giá câu trả lời sẽ được thực hiện。'
  return 'Mô hình tạo câu trả lời và mô hình đánh giá câu trả lời cần được lựa chọn đồng thời。'
})

// định nghĩa cột trong bảng
const resultColumns = computed(() => {
  const columns = [
    {
      title: 'câu hỏi',
      dataIndex: 'query',
      key: 'query',
      width: resultColumnWidths.query
    },
    {
      title: 'tạo câu trả lời',
      key: 'generated_answer',
      width: resultColumnWidths.generated_answer
    },
    {
      title: 'Đánh giá câu trả lời',
      key: 'answer_score',
      width: resultColumnWidths.answer_score
    }
  ]

  // Kiểm tra xem có dữ liệu chỉ báo truy xuất hay không
  const hasRetrievalMetrics = detailedResults.value.some((item) => {
    if (!item.metrics) return false
    return Object.keys(item.metrics).some(
      (key) =>
        key.startsWith('recall') || key.startsWith('precision') || key === 'map' || key === 'ndcg'
    )
  })

  // Nếu có dữ liệu chỉ báo truy xuất，Thêm cột chỉ mục tìm kiếm
  if (hasRetrievalMetrics) {
    columns.splice(2, 0, {
      title: 'Chỉ mục tìm kiếm',
      key: 'retrieval_score',
      width: resultColumnWidths.retrieval_score
    })
  }

  return columns.map(withResizableTitle)
})

const resultTableScrollX = computed(() =>
  resultColumns.value.reduce((total, column) => total + Number(column.width || 0), 0)
)

const startColumnResize = (event, key, minWidth = 120) => {
  stopColumnResize?.()

  const startX = event.clientX
  const startWidth = resultColumnWidths[key]
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'

  const onMouseMove = (moveEvent) => {
    resultColumnWidths[key] = Math.max(minWidth, startWidth + moveEvent.clientX - startX)
  }

  const onMouseUp = () => {
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
    stopColumnResize = null
  }

  stopColumnResize = onMouseUp
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

const withResizableTitle = (column) => ({
  ...column,
  customHeaderCell: () => ({
    class: 'resizable-table-header'
  }),
  title: h('div', { class: 'resizable-table-title' }, [
    h('span', { class: 'resizable-table-title-text' }, column.title),
    h('span', {
      class: 'column-resize-handle',
      onMousedown: (event) => {
        event.preventDefault()
        event.stopPropagation()
        startColumnResize(event, column.key)
      }
    })
  ])
})

const historyColumns = [
  {
    title: 'Tên đánh giá',
    dataIndex: 'name',
    key: 'name',
    width: 180,
    ellipsis: true,
    customRender: ({ record }) => getRunName(record)
  },
  {
    title: 'Đường cơ sở đánh giá',
    key: 'dataset_name',
    width: 180,
    ellipsis: true,
    customRender: ({ record }) => getDatasetName(record.dataset_id)
  },
  {
    title: 'Khối lượng dữ liệu',
    key: 'items',
    width: 92,
    customRender: ({ record }) => formatRunItems(record)
  },
  {
    title: 'Tốn thời gian',
    key: 'duration',
    width: 100,
    customRender: ({ record }) => formatRunDuration(record)
  },
  {
    title: 'Recall@10',
    key: 'recall_10',
    width: 100,
    customRender: ({ record }) => renderMetricTag(getRecall10(record), record.status)
  },
  {
    title: 'Đánh giá chung',
    key: 'overall_score',
    width: 100,
    customRender: ({ record }) => renderMetricTag(record.overall_score, record.status, 0)
  },
  {
    title: 'Trạng thái',
    key: 'status',
    width: 86,
    customRender: ({ record }) =>
      h('a-tag', { color: getStatusColor(record.status) }, getStatusText(record.status))
  },
  {
    title: 'hoạt động',
    key: 'actions',
    width: 120
  }
]

// Chuyển chế độ hiển thị lỗi
const toggleErrorOnly = async () => {
  resultsLoading.value = true
  showErrorsOnly.value = !showErrorsOnly.value
  currentPage.value = 1 // Đặt lại về trang đầu tiên khi chuyển chế độ

  // Tải dữ liệu được phân trang mới ngay lập tức
  await loadResultsWithPagination()
}

// Xử lý các thay đổi về phân trang
const handlePageChange = (page, size) => {
  currentPage.value = page
  if (size !== pageSize.value) {
    pageSize.value = size
  }
  loadResultsWithPagination()
}

// Xử lý các thay đổi kích thước trang
const handlePageSizeChange = (current, size) => {
  currentPage.value = 1
  pageSize.value = size
  loadResultsWithPagination()
}

// Tải kết quả được phân trang
const loadResultsWithPagination = async () => {
  if (!selectedResult.value) return

  try {
    resultsLoading.value = true
    const response = await evaluationApi.getRunResults(props.kbId, selectedResult.value.run_id, {
      page: currentPage.value,
      pageSize: pageSize.value,
      errorOnly: showErrorsOnly.value
    })

    if (response.message === 'success' && response.data) {
      const resultData = response.data

      // Cập nhật kết quả chi tiết
      detailedResults.value = resultData.items || []

      // Cập nhật thông tin phân trang
      paginationTotal.value = resultData.pagination.total
      paginationTotalPages.value = resultData.pagination.total_pages

      // Cập nhật số liệu thống kê
      // Nếu là chế độ lọc，Cần tính toán số liệu thống kê dựa trên tổng số đã lọc
      if (showErrorsOnly.value) {
        // ở chế độ lọc，Chỉ tính toán số liệu thống kê cho trang hiện tại（Tránh tính hai lần）
        evaluationStats.value = {
          ...evaluationStats.value,
          totalQuestions: paginationTotal.value
          // Số liệu thống kê bổ sung dựa trên dữ liệu đã lọc có thể được thêm vào đây
        }
      } else if (currentPage.value === 1) {
        // Khi ở chế độ không lọc và ở trang đầu tiên，Tính toán thống kê đầy đủ
        evaluationStats.value = calculateEvaluationStats(detailedResults.value)
      }

      // Cập nhật các thông tin cơ bản khác（Giữ nguyên thông tin ban đầu）
      if (resultData.started_at && resultData.completed_at) {
        const startTime = new Date(resultData.started_at)
        const endTime = new Date(resultData.completed_at)
        evaluationStats.value.totalDuration = (endTime - startTime) / 1000
      }
    }
  } catch (error) {
    console.error('Không tải được kết quả đánh giá:', error)
    message.error('Không tải được kết quả đánh giá')
  } finally {
    resultsLoading.value = false
  }
}

// Tải danh sách điểm chuẩn
const loadDatasets = async (showSuccessMessage = false) => {
  if (!props.kbId) return

  datasetsLoading.value = true
  try {
    const response = await evaluationApi.listDatasets(props.kbId)

    if (response && response.message === 'success' && Array.isArray(response.data)) {
      const completedDatasets = response.data.filter(isDatasetCompleted)
      availableDatasets.value = completedDatasets

      // Nếu không có mốc thời gian nào được chọn，và có sẵn các điểm chuẩn，Cái đầu tiên được chọn theo mặc định
      if (!selectedDatasetId.value && completedDatasets.length > 0) {
        selectedDatasetId.value = completedDatasets[0].dataset_id
        selectedDataset.value = completedDatasets[0]
      } else if (selectedDatasetId.value) {
        // Nếu có một điểm chuẩn được chọn trước đó，Xác minh lại tính hợp lệ của nó
        const exists = completedDatasets.some((b) => b.dataset_id === selectedDatasetId.value)
        if (!exists) {
          selectedDatasetId.value = null
          selectedDataset.value = null
        } else {
          // Cập nhật các đối tượng cơ sở đã chọn
          selectedDataset.value = completedDatasets.find(
            (b) => b.dataset_id === selectedDatasetId.value
          )
        }
      }

      // Nếu bạn làm mới theo cách thủ công，Hiển thị thông báo thành công
      if (showSuccessMessage) {
        message.success(
          `Đã làm mới，tìm thấy ${completedDatasets.length} một điểm chuẩn có thể đánh giá được`
        )
      }
    } else {
      console.error('Định dạng phản hồi không như mong đợi:', response)
      message.error('Lỗi định dạng dữ liệu điểm chuẩn')
    }
  } catch (error) {
    console.error('Không tải được điểm chuẩn đánh giá:', error)
    message.error('Không tải được điểm chuẩn đánh giá')
  } finally {
    datasetsLoading.value = false
  }
}

// Thay đổi lựa chọn hộp thả xuống
const onDatasetChanged = (datasetId) => {
  const benchmark = availableDatasets.value.find((b) => b.dataset_id === datasetId)
  selectedDataset.value = benchmark || null
  if (!selectedDataset.value?.has_gold_answers) {
    configForm.answer_llm = ''
    configForm.judge_llm = ''
  }
}

const hasRunningEvaluation = () =>
  evaluationHistory.value.some((record) => record.status === 'running')

const stopEvaluationRefresh = () => {
  if (evaluationRefreshTimer) {
    window.clearInterval(evaluationRefreshTimer)
    evaluationRefreshTimer = null
  }
}

const syncEvaluationRefresh = () => {
  if (!hasRunningEvaluation()) {
    stopEvaluationRefresh()
    return
  }
  if (!evaluationRefreshTimer) {
    evaluationRefreshTimer = window.setInterval(() => loadEvaluationHistory(true), 3000)
  }
}

// Làm mới hồ sơ đánh giá lịch sử
const refreshHistory = async () => {
  refreshingHistory.value = true
  try {
    await loadEvaluationHistory()
    message.success('Lịch sử đã được làm mới')
  } catch (error) {
    console.error('Không thể làm mới lịch sử:', error)
    message.error('Không thể làm mới lịch sử')
  } finally {
    refreshingHistory.value = false
  }
}

// Bắt đầu đánh giá
const startEvaluation = async () => {
  if (!selectedDataset.value) {
    message.error('Vui lòng chọn cơ sở đánh giá trước')
    return
  }

  const answerModel = selectedDataset.value.has_gold_answers ? configForm.answer_llm : ''
  const judgeModel = selectedDataset.value.has_gold_answers ? configForm.judge_llm : ''
  const hasAnswerModel = !!answerModel
  const hasJudgeModel = !!judgeModel
  const runName = configForm.name.trim()

  if (hasAnswerModel !== hasJudgeModel) {
    message.warning(
      'Mô hình phát điện và mô hình đánh giá phải được chọn cùng lúc hoặc không được chọn cùng lúc.'
    )
    return
  }
  if (!runName) {
    message.warning('Vui lòng nhập tên đánh giá')
    return
  }

  startingEvaluation.value = true

  const params = {
    dataset_id: selectedDataset.value.dataset_id,
    name: runName,
    model_config: {
      answer_llm: answerModel,
      judge_llm: judgeModel
    }
  }

  try {
    const response = await evaluationApi.runEvaluation(props.kbId, params)

    if (response.message === 'success') {
      message.success('Nhiệm vụ đánh giá đã bắt đầu')
      evaluationDropdownOpen.value = false
      configForm.name = buildDefaultEvaluationName()
      loadEvaluationHistory()
      taskerStore.loadTasks()
    } else {
      message.error(response.message || 'Đánh giá khởi động không thành công')
    }
  } catch (error) {
    console.error('Đánh giá khởi động không thành công:', error)
    message.error('Đánh giá khởi động không thành công')
  } finally {
    startingEvaluation.value = false
  }
}

// Tải lịch sử đánh giá
const loadEvaluationHistory = async (silent = false) => {
  try {
    const response = await evaluationApi.listRuns(props.kbId)
    if (response.message === 'success') {
      evaluationHistory.value = response.data || []
    }
  } catch (error) {
    console.error('Tải lịch sử đánh giá không thành công:', error)
    if (!silent) message.error('Tải lịch sử đánh giá không thành công')
  } finally {
    syncEvaluationRefresh()
  }
}

// Tính toán thống kê đánh giá
const calculateEvaluationStats = (results) => {
  if (!results || results.length === 0) {
    return {}
  }

  const stats = {
    totalQuestions: results.length,
    retrievalMetrics: {},
    answerAccuracy: 0,
    correctAnswers: 0,
    averageResponseTime: 0,
    totalResponseTime: 0
  }

  const metricSums = {}
  const metricCounts = {}

  results.forEach((item) => {
    // Trả lời chính xác
    if (item.metrics && item.metrics.score !== undefined) {
      if (item.metrics.score > 0.5) {
        stats.correctAnswers++
      }
    }

    // Thống kê chỉ mục tìm kiếm
    if (item.metrics) {
      Object.keys(item.metrics).forEach((key) => {
        if (
          key.startsWith('recall') ||
          key.startsWith('precision') ||
          key === 'map' ||
          key === 'ndcg'
        ) {
          if (!metricSums[key]) {
            metricSums[key] = 0
            metricCounts[key] = 0
          }
          metricSums[key] += item.metrics[key]
          metricCounts[key]++
        }
      })
    }
  })

  // Tính trung bình
  Object.keys(metricSums).forEach((key) => {
    stats.retrievalMetrics[key] = metricSums[key] / metricCounts[key]
  })

  // Tính toán độ chính xác của câu trả lời
  stats.answerAccuracy = stats.totalQuestions > 0 ? stats.correctAnswers / stats.totalQuestions : 0

  return stats
}

// Xem kết quả
const viewResults = async (runId) => {
  try {
    resultsLoading.value = true

    // Đặt lại trạng thái phân trang
    currentPage.value = 1
    showErrorsOnly.value = false

    // Nhận thông tin cơ bản đầu tiên（Không phân trang）
    const response = await evaluationApi.getRunResults(props.kbId, runId)

    if (response.message === 'success' && response.data) {
      const resultData = response.data

      // Tìm thông tin nhiệm vụ tương ứng từ hồ sơ lịch sử，Nếu không thì sử dụngAPIDữ liệu trả về
      selectedResult.value = evaluationHistory.value.find((r) => r.run_id === runId) || {
        run_id: resultData.run_id,
        name: resultData.name,
        status: resultData.status,
        started_at: resultData.started_at,
        completed_at: resultData.completed_at,
        total_items: resultData.total_items || 0,
        completed_items: resultData.completed_items || 0,
        overall_score: resultData.overall_score,
        retrieval_config: resultData.retrieval_config
      }

      // Nếu nó được lấy từ hồ sơ lịch sử，Hãy chắc chắn rằng cũng có retrieval_config
      if (selectedResult.value && !selectedResult.value.retrieval_config) {
        selectedResult.value.retrieval_config = resultData.retrieval_config
      }

      // Mở hộp phương thức
      resultModalVisible.value = true

      // Tải dữ liệu được phân trang
      await loadResultsWithPagination()
    } else {
      message.error('Không thu được kết quả đánh giá：Lỗi định dạng dữ liệu')
    }
  } catch (error) {
    console.error('Không thu được kết quả đánh giá:', error)
    message.error('Không thu được kết quả đánh giá')
  } finally {
    resultsLoading.value = false
  }
}

// Xóa hồ sơ đánh giá
const deleteEvaluationRecord = async (runId) => {
  try {
    // Tìm bản ghi tương ứng và thiết lập nóloadingTrạng thái
    const record = evaluationHistory.value.find((r) => r.run_id === runId)
    if (record) {
      record.deleting = true
    }

    const response = await evaluationApi.deleteRun(props.kbId, runId)
    if (response.message === 'success') {
      message.success('Xóa thành công')
      // Tải lại lịch sử đánh giá
      await loadEvaluationHistory()
    }
  } catch (error) {
    console.error('Không thể xóa bản ghi đánh giá:', error)
    message.error('Không thể xóa bản ghi đánh giá')
  } finally {
    // XóaloadingTrạng thái
    const record = evaluationHistory.value.find((r) => r.run_id === runId)
    if (record) {
      record.deleting = false
    }
  }
}

const formatTime = (timeStr) => {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN')
}

const isFiniteNumber = (value) => typeof value === 'number' && Number.isFinite(value)

const getDatasetName = (datasetId) => {
  const benchmark = availableDatasets.value.find((b) => b.dataset_id === datasetId)
  return benchmark ? benchmark.name : datasetId?.slice(0, 8) || '-'
}

const getRunName = (record) =>
  record?.name || record?.run_name || record?.run_id?.slice(0, 8) || '-'

const getRecall10 = (record) => record?.metrics?.['recall@10']

const formatPercent = (value, digits = 1) => {
  if (!isFiniteNumber(value)) return '-'
  return `${(value * 100).toFixed(digits)}%`
}

const formatRunItems = (record) => `${record?.completed_items || 0}/${record?.total_items || 0}`

const formatCompletionRate = (record) => {
  const total = Number(record?.total_items || 0)
  if (!total) return '-'
  return formatPercent(Number(record?.completed_items || 0) / total, 0)
}

const formatRunDuration = (record) => {
  if (record?.status === 'running') return 'Đang tiến hành'
  if (!record?.started_at || !record?.completed_at) return '-'
  const duration = (new Date(record.completed_at) - new Date(record.started_at)) / 1000
  return Number.isFinite(duration) && duration >= 0 ? formatDuration(duration) : '-'
}

const getRunProgress = (record) => {
  if (isFiniteNumber(record?.progress))
    return Math.max(0, Math.min(Math.round(record.progress), 100))

  const total = Number(record?.total_items || 0)
  if (!total) return 0
  const completed = Number(record?.completed_items || 0)
  return Math.max(0, Math.min(Math.round((completed / total) * 100), 100))
}

const getRunProgressMessage = (record) => {
  if (record?.message) return record.message
  const total = Number(record?.total_items || 0)
  if (total) return `Đánh giá ${Number(record?.completed_items || 0)}/${total}`
  return 'Đang tiến hành đánh giá'
}

const formatLatestRingValue = (record) =>
  record?.status === 'running'
    ? `${getRunProgress(record)}%`
    : formatPercent(record?.overall_score, 0)

const getLatestRingClass = (record) =>
  record?.status === 'running' ? 'score-running' : getScoreLevelClass(record?.overall_score)

const getMetricColor = (value) => (isFiniteNumber(value) ? getScoreColor(value) : undefined)

const renderMetricTag = (value, status, digits = 3) => {
  if (isFiniteNumber(value)) {
    return h(
      'a-tag',
      { color: getScoreTagColor(value) },
      digits === 0 ? formatPercent(value, 0) : formatMetricValue(value)
    )
  }
  if (status === 'running') return h('a-tag', { color: 'processing' }, 'Tính toán')
  if (status === 'completed') return h('a-tag', { color: 'default' }, 'Không có dữ liệu')
  return h('span', '-')
}

const getScoreLevelClass = (score) => {
  if (!isFiniteNumber(score)) return 'score-empty'
  if (score >= 0.8) return 'score-high'
  if (score >= 0.6) return 'score-medium'
  return 'score-low'
}

const getScoreColor = (score) => {
  if (score >= 0.8) return 'var(--color-success-500)'
  if (score >= 0.6) return 'var(--color-warning-500)'
  return 'var(--color-error-500)'
}

const getScoreTagColor = (score) => {
  if (score >= 0.8) return 'success'
  if (score >= 0.6) return 'warning'
  return 'error'
}

const getStatusColor = (status) => {
  const colors = {
    running: 'blue',
    completed: 'green',
    failed: 'red',
    paused: 'orange'
  }
  return colors[status] || 'default'
}

const getStatusText = (status) => {
  const texts = {
    running: 'Đang chạy',
    completed: 'Đã hoàn thành',
    failed: 'thất bại',
    paused: 'Bị đình chỉ'
  }
  return texts[status] || status
}

const getMetricTitle = (key) => {
  const titles = {
    precision: 'Độ chính xác',
    recall: 'thu hồi',
    map: 'độ chính xác trung bình',
    ndcg: 'NDCG',
    bleu: 'BLEUghi điểm',
    rouge: 'ROUGEghi điểm',
    answer_correctness: 'Trả lời chính xác',
    score: 'Đánh giá',
    reasoning: 'Lý do',
    overall_score: 'Đánh giá chung'
  }
  // Quy trình recall@k
  if (key.startsWith('recall@')) return `thu hồi (${key.split('@')[1]})`
  if (key.startsWith('precision@')) return `Độ chính xác (${key.split('@')[1]})`

  return titles[key] || key
}

// Nhận loại chỉ báo
const getMetricType = (key) => {
  if (key.startsWith('recall')) return 'recall'
  if (key.startsWith('precision')) return 'precision'
  if (key === 'map') return 'map'
  if (key === 'ndcg') return 'ndcg'
  return 'default'
}

// Nhận tên ngắn chỉ báo
const getMetricShortName = (key) => {
  if (key.startsWith('recall@')) return `R@${key.split('@')[1]}`
  if (key.startsWith('precision@')) return `P@${key.split('@')[1]}`
  if (key === 'precision') return 'Precision'
  if (key === 'recall') return 'Recall'
  if (key === 'map') return 'MAP'
  if (key === 'ndcg') return 'NDCG'
  return key
}

// Giá trị chỉ báo định dạng
const formatMetricValue = (val) => {
  if (typeof val !== 'number') return '-'
  return val.toFixed(3)
}

// Định dạng thời lượng
const formatDuration = (seconds) => {
  if (seconds < 60) {
    return `${Math.round(seconds)}giây`
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = Math.round(seconds % 60)
    return `${minutes}điểm${remainingSeconds}giây`
  } else {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}giờ${minutes}điểm`
  }
}

watch(evaluationHistory, syncEvaluationRefresh, { deep: true })

watch(evaluationDropdownOpen, (open) => {
  if (open) {
    configForm.name = buildDefaultEvaluationName()
  }
})

// Tải dữ liệu khi thành phần được gắn kết
onMounted(() => {
  loadDatasets()
  loadEvaluationHistory()
})

onUnmounted(() => {
  stopEvaluationRefresh()
  stopColumnResize?.()
})
</script>

<style lang="less" scoped>
.rag-evaluation-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

:global(.evaluation-start-dropdown) {
  width: 420px;
  padding: 14px;
  border: 1px solid var(--gray-200);
  border-radius: 10px;
  background: var(--color-bg-container);
  box-shadow: 0 10px 30px var(--shadow-3);
}

:global(.evaluation-start-dropdown .dropdown-header) {
  padding-bottom: 10px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--gray-150);
}

:global(.evaluation-start-dropdown .dropdown-title) {
  margin-bottom: 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-1000);
}

:global(.evaluation-start-dropdown .dropdown-subtitle) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--color-text-secondary);
}

:global(.evaluation-start-dropdown .dropdown-model-fields) {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

:global(.evaluation-start-dropdown .dropdown-benchmark-row) {
  display: flex;
  align-items: center;
  gap: 8px;
}

:global(.evaluation-start-dropdown .refresh-benchmarks-btn) {
  flex: 0 0 32px;
  color: var(--gray-600);
}

:global(.evaluation-start-dropdown .ant-form-item) {
  margin-bottom: 0;
}

:global(.evaluation-start-dropdown .ant-form-item-label) {
  padding-bottom: 4px;
  font-weight: 500;
}

:global(.evaluation-start-dropdown .dropdown-hint) {
  margin: 12px 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--color-info-50);
  color: var(--color-info-700);
  font-size: 12px;
  line-height: 1.5;
}

// Đánh giá lĩnh vực nội dung
.evaluation-content {
  flex: 1;
  overflow: hidden;
  min-height: 0;
  padding: 10px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

// Khu vực kết quả đánh giá
.evaluation-results {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: auto;
  margin-top: 0;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 3px;

    &:hover {
      background-color: rgba(0, 0, 0, 0.3);
    }
  }
}

.rag-evaluation-empty {
  flex: 1;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;

  .progress-stats {
    flex: 1;
    margin-right: 24px;
    min-width: 300px;

    .ant-statistic {
      margin-bottom: 12px;

      .ant-statistic-title {
        font-size: 13px;
        color: var(--gray-600);
      }

      .ant-statistic-content {
        font-size: 18px;
        font-weight: 500;
      }
    }
  }

  .progress-actions {
    flex-shrink: 0;
    padding-top: 24px;
  }
}

.query-text {
  font-size: 12px;
  line-height: 1.5;
  word-wrap: break-word;
  white-space: normal;
  overflow: visible;
}

.answer-text {
  font-size: 12px;
  line-height: 1.5;
  word-wrap: break-word;
  white-space: normal;
  overflow: visible;
  color: var(--gray-700);
}

.log-time {
  color: var(--gray-500);
  margin-left: 8px;
  font-size: 12px;
}

// Tối ưu hóa kiểu bảng
:deep(.ant-table) {
  overflow: auto;
  .ant-table-tbody > tr > td {
    padding: 12px 12px;
    vertical-align: top;
  }

  .ant-table-thead > tr > th {
    padding: 8px 12px;
    font-weight: 500;
    background-color: var(--gray-50);
  }
}

// Tối ưu hóa khoảng cách thẻ
:deep(.ant-card) {
  .ant-card-head {
    padding: 8px 16px;
    min-height: 40px;

    .ant-card-head-title {
      font-size: 14px;
      font-weight: 500;
      padding: 4px 0;
    }
  }
}

// Tối ưu hóa phong cách dòng thời gian
:deep(.ant-timeline) {
  .ant-timeline-item-content {
    margin-left: 20px;
    padding-bottom: 12px;
  }
}

// Tối ưu hóa kiểu danh sách mô tả
:deep(.ant-descriptions) {
  .ant-descriptions-item-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--gray-600);
  }

  .ant-descriptions-item-content {
    font-size: 13px;
  }
}

// Tối ưu hóa khoảng cách mục biểu mẫu
:deep(.ant-form) {
  .ant-form-item {
    margin-bottom: 16px;
  }
}

:deep(.ant-form-inline) {
  .ant-form-item {
    margin-right: 24px;
    margin-bottom: 16px;

    &:last-child {
      margin-right: 0;
    }
  }
}

// Tối ưu hóa phong cách thống kê
:deep(.ant-row) {
  .ant-col {
    .ant-statistic {
      padding: 12px;
      border: 1px solid var(--gray-200);
      border-radius: 6px;
      text-align: center;
      transition: all 0.3s;

      &:hover {
        border-color: var(--gray-300);
        box-shadow: 0 2px 4px var(--shadow-1);
      }
    }
  }
}

// Truy xuất kiểu chỉ báo
.retrieval-metrics {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  align-items: center;
  max-width: 100%;
}

.metric-content {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  line-height: 1.45;
  font-weight: 500;
  white-space: nowrap;
  color: var(--gray-650);

  &.metric-recall {
    .metric-value {
      color: var(--color-info-700);
    }
  }

  &.metric-precision {
    .metric-value {
      color: var(--color-success-700);
    }
  }

  &.metric-map,
  &.metric-ndcg {
    .metric-value {
      color: var(--color-accent-700);
    }
  }
}

.metric-name {
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0;
  color: var(--gray-550);
}

.metric-value {
  font-weight: 700;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  color: var(--gray-900);
  font-variant-numeric: tabular-nums;
}

.no-metrics {
  color: var(--gray-400);
  font-style: italic;
}

.answer-judgement {
  display: flex;
  align-items: flex-start;
  gap: 6px;

  :deep(.ant-tag) {
    flex-shrink: 0;
    margin-inline-end: 0;
  }
}

// Trả lời kiểu lập luận
.answer-reasoning {
  font-size: 12px;
  color: var(--gray-600);
  line-height: 1.4;
  cursor: pointer;
  word-wrap: break-word;
  white-space: normal;
  overflow: visible;

  &:hover {
    color: var(--gray-800);
  }
}

// Đang tải và kiểu trạng thái trống
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
}

.empty-results {
  padding: 40px 0;
  text-align: center;
}

:global(.evaluation-detail-overlay) {
  position: fixed;
  inset: 0;
  z-index: 1000;
  width: 100vw;
  height: 100dvh;
  padding: 12px;
  box-sizing: border-box;
  background: var(--dark-25);
  overflow: hidden;
}

:global(.evaluation-detail-panel) {
  width: 100%;
  height: calc(100dvh - 24px);
  max-height: calc(100dvh - 24px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 12px;
  background: var(--color-bg-container);
  box-shadow: 0 12px 32px var(--shadow-4);
}

:global(.evaluation-detail-titlebar) {
  height: 44px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 14px 0 16px;
  border-bottom: 1px solid var(--gray-150);
}

:global(.evaluation-detail-title) {
  min-width: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-1000);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-detail-content {
  flex: 1;
  height: auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 12px 16px;

  :deep(.ant-table-wrapper) {
    flex: 1;
    min-height: 0;
  }

  :deep(.ant-table) {
    .ant-table-thead > tr > th {
      position: relative;
      padding: 6px 10px;
      font-size: 12px;
    }

    .ant-table-tbody > tr > td {
      padding: 6px 10px;
      font-size: 12px;
    }

    .ant-table-pagination {
      margin: 10px 0 0;
    }
  }
}

.result-summary-bar {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--gray-150);
}

.summary-items {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: center;
  font-size: 12px;
}

.summary-item {
  color: var(--gray-700);
  white-space: nowrap;
}

.summary-run-id {
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-metrics-bar {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  gap: 8px 14px;
  align-items: center;
  padding: 8px 0;
  font-size: 12px;
  color: var(--gray-700);
}

.metric-items {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: center;
}

.result-count {
  color: var(--color-text-secondary);
}

.compact-metric {
  white-space: nowrap;
}

:deep(.table-nowrap) {
  .ant-table-cell {
    white-space: nowrap;
    overflow: hidden;
  }

  .answer-judgement {
    width: 100%;
    max-width: 100%;
    align-items: center;
  }

  .query-text,
  .answer-text,
  .answer-reasoning {
    display: block;
    width: 100%;
    max-width: 100%;
    white-space: nowrap;
    word-wrap: normal;
    overflow: hidden;
    text-overflow: clip;
  }
}

:deep(.resizable-table-header) {
  position: relative;

  .ant-table-column-title {
    display: block;
    width: 100%;
  }
}

:deep(.resizable-table-title) {
  position: relative;
  display: flex;
  align-items: center;
  min-height: 20px;
  padding-right: 14px;
}

:deep(.resizable-table-title-text) {
  overflow: hidden;
  text-overflow: ellipsis;
}

:deep(.column-resize-handle) {
  position: absolute;
  top: -6px;
  right: -16px;
  bottom: -6px;
  width: 14px;
  cursor: col-resize;
  z-index: 2;

  &::after {
    content: '';
    position: absolute;
    top: 7px;
    bottom: 7px;
    right: 2px;
    width: 1px;
    background: transparent;
  }

  &:hover::after {
    background: var(--color-primary-400);
  }
}

// Phong cách báo cáo đánh giá
.evaluation-report {
  margin-bottom: 20px;

  .report-metric {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid var(--gray-100);

    &:last-child {
      border-bottom: none;
    }

    .metric-label {
      font-size: 14px;
      padding-right: 18px;
      color: var(--gray-700);
    }

    .metric-value {
      font-size: 14px;
      font-weight: 600;
      font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
    }
  }

  .accuracy-stats {
    .accuracy-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 0;
      border-bottom: 1px solid var(--gray-100);

      &:last-child {
        border-bottom: none;
      }

      .accuracy-label {
        font-size: 14px;
        color: var(--gray-700);
      }

      .accuracy-value {
        font-size: 16px;
        font-weight: 600;
        font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
      }
    }
  }

  :deep(.ant-card) {
    .ant-card-head {
      border-bottom: 1px solid var(--gray-200);

      .ant-card-head-title {
        font-size: 14px;
        font-weight: 500;
      }
    }
  }
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;

  .section-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--gray-800);
  }
}

.last-evaluation-section {
  padding: 14px 16px;
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 10px;
}

.last-evaluation-card {
  display: grid;
  grid-template-columns: minmax(260px, 1.1fr) minmax(360px, 1.8fr);
  gap: 16px;
  align-items: stretch;
}

.last-evaluation-main {
  display: flex;
  gap: 14px;
  align-items: center;
  min-width: 0;
}

.score-ring {
  width: 64px;
  height: 64px;
  flex: 0 0 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  background: var(--gray-50);
  color: var(--gray-700);
  border: 6px solid var(--gray-200);

  &.score-high {
    color: var(--color-success-700);
    border-color: var(--color-success-100);
    background: var(--color-success-50);
  }

  &.score-medium {
    color: var(--color-warning-700);
    border-color: var(--color-warning-100);
    background: var(--color-warning-50);
  }

  &.score-low {
    color: var(--color-error-700);
    border-color: var(--color-error-100);
    background: var(--color-error-50);
  }

  &.score-running {
    color: var(--color-primary-700);
    border-color: var(--color-primary-100);
    background: var(--color-primary-50);
  }
}

.last-evaluation-info {
  min-width: 0;
}

.last-evaluation-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  margin-bottom: 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--gray-1000);
}

.last-evaluation-meta {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.last-evaluation-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;

  :deep(.ant-progress) {
    width: 160px;
    line-height: 1;
  }
}

.run-progress-message {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.run-id-link {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-primary-700);
  cursor: pointer;
  font: inherit;

  &:hover {
    color: var(--color-primary-900);
    text-decoration: underline;
  }
}

.last-evaluation-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.metric-card {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-10);

  .metric-label {
    display: block;
    margin-bottom: 4px;
    font-size: 12px;
    color: var(--color-text-secondary);
  }

  strong {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 16px;
    color: var(--gray-1000);
    font-variant-numeric: tabular-nums;
  }
}

.last-evaluation-empty {
  padding: 18px;
  border: 1px dashed var(--gray-200);
  border-radius: 8px;
  background: var(--gray-10);
  color: var(--color-text-secondary);
  text-align: center;
  font-size: 13px;
}

@media (max-width: 960px) {
  .last-evaluation-card {
    grid-template-columns: 1fr;
  }

  .last-evaluation-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

// Khu vực hồ sơ đánh giá lịch sử
.history-section {
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .section-title {
      margin: 0;
      font-size: 14px;
      font-weight: 500;
      color: var(--gray-700);
    }

    .refresh-btn {
      color: var(--gray-600);
      border: none;
      box-shadow: none;
      padding: 4px 8px;
      height: auto;
      font-size: 13px;

      &:hover {
        color: var(--color-primary-600);
        background-color: var(--color-primary-50);
      }

      &:active {
        color: var(--color-primary-700);
        background-color: var(--color-primary-100);
      }

      .anticon {
        font-size: 14px;
      }
    }
  }

  :deep(.ant-table) {
    border: 1px solid var(--gray-100);
  }

  .history-action-link {
    color: var(--color-primary-500);
    font-size: 13px;
    text-decoration: none;
    cursor: pointer;

    &:hover {
      color: var(--color-primary-700);
    }
  }

  .history-action-link-danger {
    color: var(--color-error-700);

    &:hover {
      color: var(--color-error-900);
    }
  }
}

// JSON Kiểu người xem
.json-viewer-container {
  max-height: 400px;
  overflow: auto;

  .json-viewer {
    margin: 0;
    padding: 0;
    font-family: 'SF Mono', 'Monaco', 'Consolas', 'Menlo', monospace;
    font-size: 13px;
    line-height: 1.5;
    color: var(--gray-800);
    white-space: pre-wrap;
    word-wrap: break-word;
    background: var(--gray-50);
    border: 1px solid var(--gray-200);
    border-radius: 6px;
    padding: 12px;
  }
}

// Chỉ xem kiểu nút lỗi
.error-only-active {
  background-color: var(--color-error-500) !important;
  border-color: var(--color-error-500) !important;
  color: white !important;

  &:hover {
    background-color: var(--color-error-600) !important;
    border-color: var(--color-error-600) !important;
  }

  &:focus {
    background-color: var(--color-error-500) !important;
    border-color: var(--color-error-500) !important;
  }
}
</style>
