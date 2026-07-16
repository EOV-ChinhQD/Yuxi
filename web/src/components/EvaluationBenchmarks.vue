<template>
  <div class="evaluation-benchmarks-container">
    <!-- Thanh hành động -->
    <div class="benchmarks-header">
      <div class="header-left">
        <a-button type="primary" class="lucide-icon-btn" @click="showUploadModal">
          <template #icon><Upload :size="16" /></template>
          Tải điểm chuẩn lên
        </a-button>
        <a-button class="lucide-icon-btn" @click="showGenerateModal">
          <template #icon><Bot :size="16" /></template>
          Được tạo tự động
        </a-button>
        <span class="total-count">{{ benchmarks.length }} điểm chuẩn</span>
      </div>
      <div class="header-right">
        <a-button class="lucide-icon-btn" @click="loadBenchmarks">
          <template #icon><RefreshCw :size="16" /></template>
          Làm mới
        </a-button>
      </div>
    </div>

    <!-- Danh sách điểm chuẩn -->
    <div class="benchmarks-list">
      <ResourceEmptyState
        v-if="!loading && benchmarks.length === 0"
        title="Chưa có cơ sở đánh giá"
        description="Tải tập dữ liệu lên，hoặc tự động tạo ra các câu hỏi đánh giá từ cơ sở kiến thức hiện tại。"
        :icon="ClipboardList"
        size="compact"
      >
        <template #actions>
          <a-button type="primary" class="lucide-icon-btn" @click="showUploadModal">
            <template #icon><Upload :size="16" /></template>
            Tải điểm chuẩn lên
          </a-button>
          <a-button class="lucide-icon-btn" @click="showGenerateModal">
            <template #icon><Bot :size="16" /></template>
            Được tạo tự động
          </a-button>
        </template>
      </ResourceEmptyState>

      <div v-else-if="loading" class="loading-state">
        <a-spin size="large" />
      </div>

      <div v-else class="benchmark-list-content">
        <div
          v-for="benchmark in benchmarks"
          :key="benchmark.dataset_id"
          class="benchmark-item"
          :class="{ 'benchmark-item-disabled': !isDatasetCompleted(benchmark) }"
          @click="isDatasetCompleted(benchmark) && previewDataset(benchmark)"
        >
          <!-- Nội dung chính -->
          <div class="benchmark-main">
            <div class="benchmark-header">
              <h4 class="benchmark-name">{{ benchmark.name }}</h4>
              <div class="benchmark-actions" @click.stop>
                <a-dropdown :trigger="['click']">
                  <button
                    type="button"
                    class="benchmark-more-action"
                    aria-label="Thêm hành động"
                    @click.stop
                  >
                    <MoreVertical :size="16" />
                  </button>
                  <template #overlay>
                    <a-menu>
                      <a-menu-item
                        key="download"
                        :disabled="
                          !isDatasetCompleted(benchmark) ||
                          !!downloadingDatasetMap[benchmark.dataset_id]
                        "
                        @click="downloadDataset(benchmark)"
                      >
                        <span class="benchmark-menu-item">
                          <Download :size="14" />
                          <span>Tải xuống</span>
                        </span>
                      </a-menu-item>
                      <a-menu-item
                        key="delete"
                        danger
                        :disabled="shouldShowBuildProgress(benchmark)"
                        @click="deleteDataset(benchmark)"
                      >
                        <span class="benchmark-menu-item">
                          <Trash2 :size="14" />
                          <span>Xóa</span>
                        </span>
                      </a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
              </div>
            </div>

            <p class="benchmark-desc">{{ benchmark.description || 'Chưa có mô tả' }}</p>

            <!-- khu vực nhãn -->
            <div class="benchmark-meta">
              <div class="meta-row">
                <span
                  v-if="benchmark.has_gold_chunks && !benchmark.has_gold_answers"
                  class="card-tag benchmark-tag tag-blue"
                >
                  Đánh giá tìm kiếm
                </span>
                <span
                  v-if="benchmark.has_gold_answers && !benchmark.has_gold_chunks"
                  class="card-tag benchmark-tag tag-gold"
                >
                  Đánh giá hỏi đáp
                </span>
                <span
                  v-if="!benchmark.has_gold_chunks && !benchmark.has_gold_answers"
                  class="card-tag benchmark-tag"
                >
                  Chỉ truy vấn
                </span>

                <span v-if="benchmark.has_gold_chunks" class="card-tag benchmark-tag tag-green">
                  Gold Chunks
                </span>
                <span v-if="benchmark.has_gold_answers" class="card-tag benchmark-tag tag-green">
                  Gold Answer
                </span>
                <span class="card-tag benchmark-tag tag-blue">
                  {{ getDatasetSourceText(benchmark) }}
                </span>
                <span
                  v-if="!isDatasetCompleted(benchmark)"
                  class="card-tag benchmark-tag"
                  :class="getDatasetStatusClass(benchmark)"
                >
                  {{ getDatasetStatusText(benchmark) }}
                </span>
              </div>
            </div>
          </div>

          <!-- Thông tin đáy -->
          <div class="benchmark-footer">
            <span class="benchmark-time">{{ formatDate(benchmark.created_at) }}</span>
            <div v-if="shouldShowBuildProgress(benchmark)" class="footer-build-progress">
              <a-progress
                :percent="getDatasetProgress(benchmark)"
                size="small"
                status="active"
                :show-info="false"
              />
              <span class="build-message">
                {{ getDatasetBuildMessage(benchmark) }}
              </span>
            </div>
            <span v-else class="benchmark-count">{{ benchmark.item_count }} câu hỏi</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Hộp phương thức tải lên -->
    <BenchmarkUploadModal
      v-model:visible="uploadModalVisible"
      :kb-id="kbId"
      @success="onUploadSuccess"
    />

    <!-- Tạo hộp phương thức -->
    <BenchmarkGenerateModal
      v-model:visible="generateModalVisible"
      :kb-id="kbId"
      @success="onGenerateSuccess"
    />

    <Teleport to="body">
      <div v-if="previewModalVisible" class="evaluation-detail-overlay">
        <div class="evaluation-detail-panel">
          <div class="evaluation-detail-titlebar">
            <div class="evaluation-detail-title">Chi tiết điểm chuẩn đánh giá</div>
            <a-button
              type="text"
              size="small"
              class="lucide-icon-btn"
              title="đóng"
              @click="previewModalVisible = false"
            >
              <X :size="16" />
            </a-button>
          </div>

          <div v-if="previewData" class="preview-content">
            <div class="preview-header">
              <h3>{{ previewData.name }}</h3>
              <div class="preview-meta">
                <span class="meta-item">
                  <span class="meta-label">số lượng câu hỏi:</span>
                  {{ previewData.item_count }}
                </span>
                <span class="meta-item">
                  <span class="meta-label">Gold Chunks:</span>
                  <span :class="previewData.has_gold_chunks ? 'status-yes' : 'status-no'">
                    {{ previewData.has_gold_chunks ? 'Có' : 'không có' }}
                  </span>
                </span>
                <span class="meta-item">
                  <span class="meta-label">Gold Answer:</span>
                  <span :class="previewData.has_gold_answers ? 'status-yes' : 'status-no'">
                    {{ previewData.has_gold_answers ? 'Có' : 'không có' }}
                  </span>
                </span>
              </div>
            </div>

            <div class="preview-questions" v-if="previewQuestions && previewQuestions.length > 0">
              <div class="table-section-header">
                <div class="table-title-group">
                  <h4>Danh sách câu hỏi</h4>
                  <span>tổng cộng {{ previewPagination.total }} Bài viết</span>
                </div>
                <a-switch
                  v-model:checked="previewAutoWrap"
                  checked-children="dòng mới"
                  un-checked-children="Không ngắt dòng"
                />
              </div>
              <a-table
                :dataSource="previewQuestions"
                :columns="displayedQuestionColumns"
                :pagination="paginationConfig"
                :scroll="{ x: questionTableScrollX, y: 'calc(100dvh - 294px)' }"
                :class="{ 'table-nowrap': !previewAutoWrap }"
                size="small"
                :rowKey="(_, index) => index"
                :loading="previewPagination.loading"
              >
                <template #bodyCell="{ column, record, index }">
                  <template v-if="column.key === 'index'">
                    <span class="question-num"
                      >Q{{
                        (previewPagination.current - 1) * previewPagination.pageSize + index + 1
                      }}</span
                    >
                  </template>
                  <template v-else-if="column.key === 'query'">
                    <div class="question-text" :title="record?.query || ''">
                      {{ record?.query || '' }}
                    </div>
                  </template>
                  <template v-if="column.key === 'gold_chunk_ids'">
                    <div
                      v-if="record?.gold_chunk_ids && record.gold_chunk_ids.length > 0"
                      :title="record.gold_chunk_ids.join(', ')"
                      class="question-chunk"
                    >
                      {{ record.gold_chunk_ids.join(', ') }}
                    </div>
                    <span v-else class="no-data">-</span>
                  </template>
                  <template v-else-if="column.key === 'gold_answer'">
                    <div
                      v-if="record?.gold_answer"
                      :title="record.gold_answer"
                      class="question-answer"
                    >
                      {{ record.gold_answer }}
                    </div>
                    <span v-else class="no-data">-</span>
                  </template>
                </template>
              </a-table>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch, h } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  Bot,
  ClipboardList,
  Download,
  MoreVertical,
  RefreshCw,
  Trash2,
  Upload,
  X
} from 'lucide-vue-next'
import { evaluationApi } from '@/apis/knowledge_api'
import { useTaskerStore } from '@/stores/tasker'
import ResourceEmptyState from '@/components/shared/ResourceEmptyState.vue'
import BenchmarkUploadModal from './modals/BenchmarkUploadModal.vue'
import BenchmarkGenerateModal from './modals/BenchmarkGenerateModal.vue'

const props = defineProps({
  kbId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['refresh'])

const taskerStore = useTaskerStore()

// Trạng thái
const loading = ref(false)
const benchmarks = ref([])
const uploadModalVisible = ref(false)
const generateModalVisible = ref(false)
const previewModalVisible = ref(false)
const previewData = ref(null)
const previewQuestions = ref([])
const previewAutoWrap = ref(false)
const downloadingDatasetMap = reactive({})
const previewPagination = ref({
  current: 1,
  pageSize: 50,
  total: 0,
  loading: false
})
let buildRefreshTimer = null
let stopColumnResize = null

const questionColumnWidths = reactive({
  index: 64,
  query: 380,
  gold_chunk_ids: 260,
  gold_answer: 520
})

const startColumnResize = (event, key, minWidth = 72) => {
  stopColumnResize?.()

  const startX = event.clientX
  const startWidth = questionColumnWidths[key]
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'

  const onMouseMove = (moveEvent) => {
    questionColumnWidths[key] = Math.max(minWidth, startWidth + moveEvent.clientX - startX)
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
  width: questionColumnWidths[column.key],
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
        startColumnResize(event, column.key, column.key === 'index' ? 54 : 120)
      }
    })
  ])
})

// định nghĩa cột trong bảng
const questionColumns = [
  {
    title: '#',
    key: 'index',
    width: 60,
    align: 'center'
  },
  {
    title: 'câu hỏi',
    dataIndex: 'query',
    key: 'query',
    width: 280,
    ellipsis: false
  },
  {
    title: 'Gold Chunks',
    dataIndex: 'gold_chunk_ids',
    key: 'gold_chunk_ids',
    width: 200,
    ellipsis: false
  },
  {
    title: 'Gold Answer',
    dataIndex: 'gold_answer',
    key: 'gold_answer',
    width: 420,
    ellipsis: false
  }
]

const displayedQuestionColumns = computed(() => {
  const columns =
    previewData.value && previewData.value.has_gold_chunks === false
      ? questionColumns.filter((c) => c.key !== 'gold_chunk_ids')
      : questionColumns

  return columns.map(withResizableTitle)
})

const questionTableScrollX = computed(() => {
  return displayedQuestionColumns.value.reduce(
    (total, column) => total + Number(column.width || 0),
    0
  )
})

// Cấu hình phân trang
const paginationConfig = computed(() => ({
  current: previewPagination.value.current,
  pageSize: previewPagination.value.pageSize,
  total: previewPagination.value.total,
  showTotal: (total, range) =>
    `Không. ${range[0]}-${range[1]} Bài viết，tổng cộng ${total} Bài viết`,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50', '100'],
  showQuickJumper: true,
  size: 'small',
  onChange: handlePageChange,
  onShowSizeChange: handlePageSizeChange
}))

const getBuildMetadata = (benchmark) => benchmark?.build_metadata || {}

const getDatasetBuildStatus = (benchmark) => getBuildMetadata(benchmark).status || 'completed'

const isDatasetCompleted = (benchmark) => getDatasetBuildStatus(benchmark) === 'completed'

const isDatasetBuilding = (benchmark) =>
  ['pending', 'running'].includes(getDatasetBuildStatus(benchmark))

const hasValidDatasetProgress = (benchmark) => {
  const progress = Number(getBuildMetadata(benchmark).progress)
  return Number.isFinite(progress)
}

const shouldShowBuildProgress = (benchmark) =>
  isDatasetBuilding(benchmark) && hasValidDatasetProgress(benchmark)

const getDatasetProgress = (benchmark) => {
  const progress = Number(getBuildMetadata(benchmark).progress)
  if (!Number.isFinite(progress)) return 0
  return Math.max(0, Math.min(Math.round(progress), 100))
}

const getDatasetSourceText = (benchmark) => {
  const source = getBuildMetadata(benchmark).source
  return source === 'generated' ? 'Được tạo tự động' : 'tải lên'
}

const getDatasetStatusText = (benchmark) => {
  const statusTextMap = {
    pending: 'Chờ đợi thế hệ',
    running: 'Đang tạo',
    completed: 'Đã hoàn thành',
    failed: 'Xây dựng không thành công'
  }
  return statusTextMap[getDatasetBuildStatus(benchmark)] || getDatasetBuildStatus(benchmark)
}

const getDatasetStatusClass = (benchmark) => {
  const statusClassMap = {
    pending: 'tag-gold',
    running: 'tag-blue',
    completed: 'tag-green',
    failed: 'tag-red'
  }
  return statusClassMap[getDatasetBuildStatus(benchmark)] || ''
}

const getDatasetBuildMessage = (benchmark) => {
  const metadata = getBuildMetadata(benchmark)
  return metadata.error_message || metadata.message || getDatasetStatusText(benchmark)
}

const hasActiveBuild = () => benchmarks.value.some(shouldShowBuildProgress)

const stopBuildRefresh = () => {
  if (buildRefreshTimer) {
    window.clearInterval(buildRefreshTimer)
    buildRefreshTimer = null
  }
}

const syncBuildRefresh = () => {
  if (!hasActiveBuild()) {
    stopBuildRefresh()
    return
  }
  if (!buildRefreshTimer) {
    buildRefreshTimer = window.setInterval(() => loadBenchmarks(true), 3000)
  }
}

// Tải danh sách điểm chuẩn
const loadBenchmarks = async (silent = false) => {
  if (!props.kbId) return

  if (!silent) loading.value = true
  try {
    const response = await evaluationApi.listDatasets(props.kbId)

    if (response && response.message === 'success' && Array.isArray(response.data)) {
      benchmarks.value = response.data
    } else {
      console.error('Định dạng phản hồi không như mong đợi:', response)
      message.error('Lỗi định dạng dữ liệu điểm chuẩn')
    }
  } catch (error) {
    console.error('Không tải được điểm chuẩn đánh giá:', error)
    if (!silent) message.error('Không tải được điểm chuẩn đánh giá')
  } finally {
    if (!silent) loading.value = false
    syncBuildRefresh()
  }
}

// Hiển thị hộp phương thức tải lên
const showUploadModal = () => {
  uploadModalVisible.value = true
}

// Hiển thị hộp phương thức được tạo
const showGenerateModal = () => {
  generateModalVisible.value = true
}

// Tải lên gọi lại thành công
const onUploadSuccess = () => {
  loadBenchmarks()
  message.success('Tải lên điểm chuẩn thành công')
  taskerStore.loadTasks() // Làm mới danh sách nhiệm vụ
  // Thông báo cho thành phần cha mẹ để làm mới danh sách cơ sở
  emit('refresh')
}

// Tạo cuộc gọi lại thành công
const onGenerateSuccess = () => {
  loadBenchmarks()
  // message.success('Tạo điểm chuẩn thành công'); // Xóa，Gửi bởi tác vụ nhắc hộp phương thức
  taskerStore.loadTasks() // Làm mới danh sách nhiệm vụ
  // Thông báo cho thành phần cha mẹ để làm mới danh sách cơ sở
  emit('refresh')
}

// Chức năng xử lý phân trang
const handlePageChange = (page, pageSize) => {
  previewPagination.value.current = page
  previewPagination.value.pageSize = pageSize
  loadPreviewQuestions()
}

const handlePageSizeChange = (current, size) => {
  previewPagination.value.current = 1
  previewPagination.value.pageSize = size
  loadPreviewQuestions()
}

// Đang tải sự cố xem trước（Phân trang）
const loadPreviewQuestions = async () => {
  if (!previewData.value?.dataset_id) return

  try {
    previewPagination.value.loading = true
    const response = await evaluationApi.getDataset(
      props.kbId,
      previewData.value.dataset_id,
      previewPagination.value.current,
      previewPagination.value.pageSize
    )

    if (response.message === 'success') {
      previewQuestions.value = response.data.items || []
      previewPagination.value.total = response.data.pagination?.total_items || 0
    }
  } catch (error) {
    console.error('Vấn đề tải bản xem trước không thành công:', error)
    message.error('Vấn đề tải bản xem trước không thành công')
  } finally {
    previewPagination.value.loading = false
  }
}

// Xem trước điểm chuẩn
const previewDataset = async (benchmark) => {
  if (!isDatasetCompleted(benchmark)) {
    message.warning(
      'Việc xem trước chỉ có thể được thực hiện sau khi đường cơ sở đánh giá được tạo.'
    )
    return
  }

  try {
    // Đặt lại trạng thái phân trang
    previewPagination.value = {
      current: 1,
      pageSize: 50,
      total: 0,
      loading: false
    }

    const response = await evaluationApi.getDataset(
      props.kbId,
      benchmark.dataset_id,
      previewPagination.value.current,
      previewPagination.value.pageSize
    )

    if (response.message === 'success') {
      // lưu đường cơ sởIDcho các yêu cầu phân trang tiếp theo
      previewData.value = {
        ...response.data,
        dataset_id: benchmark.dataset_id // Thêm thủ côngdataset_id
      }
      previewQuestions.value = response.data.items || []
      previewPagination.value.total = response.data.pagination?.total_items || 0
      previewModalVisible.value = true
    }
  } catch (error) {
    console.error('Không lấy được chi tiết điểm chuẩn:', error)
    message.error('Không lấy được chi tiết điểm chuẩn')
  }
}

const parseDownloadFilename = (contentDisposition) => {
  if (!contentDisposition) return ''

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match && utf8Match[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch (error) {
      console.warn('phân tích cú pháp UTF-8 Tên tệp không thành công:', error)
    }
  }

  const asciiMatch = contentDisposition.match(/filename="?([^";]+)"?/i)
  if (asciiMatch && asciiMatch[1]) {
    return asciiMatch[1]
  }

  return ''
}

// Tải xuống điểm chuẩn
const downloadDataset = async (benchmark) => {
  const benchmarkId = benchmark?.dataset_id
  if (!benchmarkId) return
  if (!isDatasetCompleted(benchmark)) {
    message.warning('Điểm chuẩn đánh giá chỉ có thể được tải xuống sau khi quá trình tạo hoàn tất.')
    return
  }
  if (downloadingDatasetMap[benchmarkId]) return

  downloadingDatasetMap[benchmarkId] = true
  try {
    const response = await evaluationApi.downloadDataset(benchmarkId)
    const blob = await response.blob()
    const contentDisposition =
      response.headers.get('Content-Disposition') || response.headers.get('content-disposition')
    const headerFilename = parseDownloadFilename(contentDisposition)
    const fallbackFilename = `${benchmark.name || benchmarkId}.jsonl`
    const filename = headerFilename || fallbackFilename

    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    message.success('Tải xuống thành công')
  } catch (error) {
    console.error('Tải xuống điểm chuẩn không thành công:', error)
    message.error(`Tải xuống không thành công: ${error.message || 'lỗi không xác định'}`)
  } finally {
    delete downloadingDatasetMap[benchmarkId]
  }
}

// Xóa đường cơ sở
const deleteDataset = (benchmark) => {
  if (shouldShowBuildProgress(benchmark)) {
    message.warning('Điểm chuẩn đánh giá đang được tạo，Chưa thể xóa được')
    return
  }

  Modal.confirm({
    title: 'Xác nhận xóa',
    content: `Bạn có chắc chắn muốn xóa đường cơ sở đánh giá không?"${benchmark.name}"?？Hoạt động này là không thể đảo ngược。`,
    okText: 'được rồi',
    cancelText: 'Hủy bỏ',
    onOk: async () => {
      try {
        const response = await evaluationApi.deleteDataset(benchmark.dataset_id)
        if (response.message === 'success') {
          message.success('Xóa thành công')
          loadBenchmarks()
        }
      } catch (error) {
        console.error('Xóa đường cơ sở không thành công:', error)
        message.error('Xóa đường cơ sở không thành công')
      }
    }
  })
}

// Định dạng ngày
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

watch(benchmarks, syncBuildRefresh, { deep: true })

// Tải dữ liệu khi thành phần được gắn kết
onMounted(() => {
  loadBenchmarks()
})

onUnmounted(() => {
  stopBuildRefresh()
  stopColumnResize?.()
})
</script>

<style lang="less" scoped>
.evaluation-benchmarks-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.benchmarks-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  margin-bottom: 12px;

  .total-count {
    font-size: 13px;
    color: var(--color-text-secondary);
  }

  .header-right,
  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.benchmarks-list {
  flex: 1;
  overflow-y: auto;
}

.benchmark-list-content {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr));
  gap: 12px;
}

.benchmark-item {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  background: var(--color-bg-container);
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: var(--color-primary-100);
    box-shadow: 0 1px 2px var(--shadow-2);
    background: var(--gray-10);
  }
}

.benchmark-item-disabled {
  cursor: default;
}

.benchmark-main {
  margin-bottom: 8px;
}

.benchmark-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 6px;

  .benchmark-name {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: var(--gray-1000);
    flex: 1;
  }

  .benchmark-actions {
    display: flex;
    gap: 4px;
  }
}

.benchmark-more-action {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;

  &:hover {
    color: var(--gray-1000);
    background: var(--gray-100);
  }
}

.benchmark-menu-item {
  display: inline-flex;
  align-items: center;
  gap: 0;
}

.benchmark-desc {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.benchmark-meta {
  margin-bottom: 8px;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.benchmark-tag {
  min-height: 22px;
  padding: 0 8px;
  border-radius: 4px;
}

.tag-red {
  color: var(--color-error-700);
  background: var(--color-error-50);
  border-color: var(--color-error-100);
}

.footer-build-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  margin-left: 16px;

  :deep(.ant-progress) {
    flex: 1;
    min-width: 80px;
  }
}

.build-message {
  max-width: 180px;
  color: var(--color-text-secondary);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.benchmark-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px solid var(--gray-150);
  font-size: 13px;
  color: var(--color-text-tertiary);

  .benchmark-id {
    font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  }

  .benchmark-count {
    color: var(--color-primary-700);
    font-size: 13px;
    font-weight: 500;
  }
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
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

.preview-content {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 12px 16px;

  .preview-header {
    flex-shrink: 0;
    margin-bottom: 10px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--gray-200);

    h3 {
      margin: 0 0 8px;
      font-size: 16px;
      font-weight: 600;
      color: var(--gray-1000);
    }

    .preview-meta {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;

      .meta-item {
        font-size: 12px;

        .meta-label {
          color: var(--color-text-tertiary);
          margin-right: 4px;
        }

        .status-yes {
          color: var(--color-success-700);
          font-weight: 500;
        }

        .status-no {
          color: var(--color-text-tertiary);
        }
      }
    }
  }

  .preview-questions {
    flex: 1;
    min-height: 0;

    .table-section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;

      span {
        color: var(--color-text-secondary);
        font-size: 12px;
      }
    }

    .table-title-group {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }

    h4 {
      margin: 0;
      font-size: 14px;
      font-weight: 600;
      color: var(--gray-900);
    }

    .question-num {
      font-size: 14px;
      font-weight: 600;
      color: var(--gray-700);
    }

    .question-text {
      font-size: 14px;
      line-height: 1.5;
      color: var(--gray-800);
      word-break: break-all;
      white-space: normal;
      overflow: visible;
      cursor: pointer;
    }

    .question-chunk,
    .question-answer {
      font-size: 13px;
      color: var(--gray-600);
      word-break: break-all;
      white-space: normal;
      overflow: visible;
      cursor: pointer;
    }

    .no-data {
      color: var(--gray-400);
      font-style: italic;
    }

    :deep(.ant-table) {
      .ant-table-thead > tr > th {
        background-color: var(--gray-50);
        border-bottom: 1px solid var(--gray-200);
        font-weight: 600;
        font-size: 12px;
        padding: 6px 10px;
        white-space: nowrap;
        position: relative;
      }

      .ant-table-tbody > tr > td {
        padding: 6px 10px;
        border-bottom: 1px solid var(--gray-150);
        font-size: 12px;
        vertical-align: top;
        line-height: 1.4;
      }

      .ant-table-tbody > tr:hover > td {
        background-color: var(--gray-50);
      }

      .ant-table-cell {
        white-space: normal !important;
        word-wrap: break-word !important;
        word-break: break-all !important;
      }

      .ant-table-pagination {
        margin: 10px 0 0;
      }
    }

    :deep(.table-nowrap) {
      .ant-table-cell {
        white-space: nowrap !important;
        word-break: normal !important;
        overflow: hidden;
      }

      .question-text,
      .question-chunk,
      .question-answer {
        display: block;
        width: 100%;
        max-width: 100%;
        max-height: none;
        white-space: nowrap;
        word-break: normal;
        overflow: hidden;
        text-overflow: clip;
      }
    }
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
</style>
