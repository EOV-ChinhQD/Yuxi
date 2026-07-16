<template>
  <a-modal
    v-model:open="visible"
    width="800px"
    :footer="null"
    :closable="false"
    wrap-class-name="file-detail"
    @after-open-change="afterOpenChange"
    :bodyStyle="{ height: '80vh', padding: '0' }"
  >
    <template #title>
      <div class="modal-title-wrapper">
        <!-- bên trái：Tên tập tin và biểu tượng -->
        <div class="file-title">
          <FileTypeIcon :name="file?.filename" :size="18" />
          <span class="file-name">{{ file?.filename || 'Chi tiết tài liệu' }}</span>
        </div>

        <div class="header-controls">
          <!-- Số ký tự/Số lượng clip được hiển thị trong segment trái -->
          <span v-if="viewInfoText" class="view-info">{{ viewInfoText }}</span>

          <!-- Chuyển đổi chế độ xem -->
          <div class="view-controls" v-if="file && viewModeOptions.length > 1">
            <a-segmented v-model:value="viewMode" :options="viewModeOptions" />
          </div>

          <!-- Menu thả xuống nút tải xuống -->
          <a-dropdown trigger="click" v-if="file">
            <a-button type="default" class="download-btn" title="Tải xuống" aria-label="Tải xuống">
              <Download :size="16" />
              <ChevronDown :size="14" />
            </a-button>
            <template #overlay>
              <a-menu @click="handleDownloadMenuClick">
                <a-menu-item key="original" :disabled="!file.file_id">
                  <template #icon><Download :size="16" /></template>
                  Tải văn bản gốc
                </a-menu-item>
                <a-menu-item key="markdown" :disabled="contentState.loading || !mergedContent">
                  <template #icon><FileText :size="16" /></template>
                  Tải xuống Markdown
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>

          <!-- Nút đóng tùy chỉnh -->
          <button class="custom-close-btn" @click="visible = false">
            <X :size="16" />
          </button>
        </div>
      </div>
    </template>
    <div v-if="basicLoading" class="loading-container">
      <a-spin tip="Đang tải nội dung tài liệu..." />
    </div>
    <div v-else-if="detailError" class="empty-content">
      <p>{{ detailError }}</p>
    </div>
    <div v-else-if="file && hasAvailableView" class="file-detail-content">
      <div v-if="viewMode === 'source'" class="content-panel source-panel">
        <div v-if="sourcePreview.loading" class="loading-container">
          <a-spin tip="Đang tải bản xem trước tệp nguồn..." />
        </div>
        <AgentFilePreview
          v-else
          :file="sourcePreviewFile"
          :file-path="file?.filename || ''"
          :show-header="false"
          :show-download="false"
          :show-inline-html-controls="true"
          :full-height="true"
          :borderless="true"
          container-class="source-preview-container"
          content-class="source-preview-content"
        />
      </div>

      <!-- Markdown chế độ -->
      <div v-else-if="viewMode === 'markdown'" class="content-panel flat-md-preview">
        <div v-if="contentState.loading" class="loading-container">
          <a-spin tip="Đang tải nội dung được phân tích cú pháp..." />
        </div>
        <MarkdownPreview
          v-else-if="mergedContent"
          :content="mergedContent"
          class="markdown-content"
        />
        <div v-else class="empty-content">
          <p>{{ contentState.error || 'Chưa có nội dung tập tin' }}</p>
        </div>
      </div>

      <!-- Chunks chế độ：sử dụng Grid Bố cục -->
      <div v-else-if="viewMode === 'chunks'" class="chunks-panel">
        <div v-if="contentState.loading" class="loading-container">
          <a-spin tip="Đang tải nội dung bị phân đoạn..." />
        </div>
        <div v-else class="chunk-grid">
          <div v-for="chunk in mappedChunks" :key="chunk.id" class="chunk-card">
            <div class="chunk-card-header">
              <span class="chunk-order">#{{ chunk.chunk_order_index }}</span>
            </div>
            <div class="chunk-card-content">
              {{ chunk.content.replace(/\n+/g, ' ') }}
            </div>
          </div>
        </div>
        <div v-if="!contentState.loading && mappedChunks.length === 0" class="empty-content">
          <p>{{ contentState.error || 'Chưa có thông tin phân chia' }}</p>
        </div>
      </div>
    </div>

    <div v-else-if="file" class="empty-content">
      <p>Chưa có nội dung tập tin</p>
    </div>
  </a-modal>
</template>

<script setup>
import { computed, h, onBeforeUnmount, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { documentApi } from '@/apis/knowledge_api'
import { getWorkspaceKnowledgeFileContent } from '@/apis/workspace_api'
import { mergeChunks } from '@/utils/chunkUtils'
import { getPreviewTypeByPath, normalizePreviewResponse } from '@/utils/file_preview'
import {
  canPreviewChunks,
  canPreviewOriginal,
  canPreviewParsed,
  getDefaultDetailView
} from '@/utils/knowledge_file_policy'
import MarkdownPreview from '@/components/common/MarkdownPreview.vue'
import FileTypeIcon from '@/components/common/FileTypeIcon.vue'
import AgentFilePreview from '@/components/AgentFilePreview.vue'
import { Download, ChevronDown, FileSearch, FileText, Rows3, X } from 'lucide-vue-next'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  kbId: {
    type: [String, Number],
    default: ''
  },
  fileId: {
    type: [String, Number],
    default: ''
  }
})

const emit = defineEmits(['update:open', 'closed'])

const visible = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value)
})

const file = ref(null)
const basicLoading = ref(false)
const detailError = ref('')
const downloadingOriginal = ref(false)
const downloadingMarkdown = ref(false)
const contentState = ref({
  loading: false,
  loaded: false,
  lines: [],
  content: '',
  error: ''
})
const sourcePreview = ref({
  loading: false,
  url: '',
  content: '',
  type: '',
  message: '',
  supported: true
})

let basicRequestSeq = 0
let contentRequestSeq = 0
let sourceRequestSeq = 0

const revokeSourcePreviewUrl = () => {
  if (sourcePreview.value.url) {
    window.URL.revokeObjectURL(sourcePreview.value.url)
    sourcePreview.value.url = ''
  }
}

const resetContentState = () => {
  contentState.value = {
    loading: false,
    loaded: false,
    lines: [],
    content: '',
    error: ''
  }
}

const resetSourcePreview = () => {
  sourceRequestSeq += 1
  revokeSourcePreviewUrl()
  sourcePreview.value = {
    loading: false,
    url: '',
    content: '',
    type: '',
    message: '',
    supported: true
  }
}

const resetLocalState = () => {
  basicRequestSeq += 1
  contentRequestSeq += 1
  file.value = null
  basicLoading.value = false
  detailError.value = ''
  downloadingOriginal.value = false
  downloadingMarkdown.value = false
  resetContentState()
  resetSourcePreview()
  viewMode.value = 'markdown'
}

const normalizeFileMeta = (meta = {}) => ({
  ...meta,
  file_id: meta.file_id || String(props.fileId || ''),
  kb_id: meta.kb_id || String(props.kbId || ''),
  filename: meta.filename || meta.original_filename || String(props.fileId || ''),
  file_size: meta.file_size ?? meta.size ?? 0,
  has_original_file:
    'has_original_file' in meta
      ? Boolean(meta.has_original_file)
      : Boolean(meta.minio_url || meta.path),
  has_parsed_markdown:
    'has_parsed_markdown' in meta ? Boolean(meta.has_parsed_markdown) : Boolean(meta.markdown_file)
})

const ensureApiSuccess = (data, fallbackMessage) => {
  if (data?.status === 'failed') {
    throw new Error(data.message || fallbackMessage)
  }
}

// chế độ xem
const viewMode = ref('markdown')
const hasContent = computed(
  () =>
    (contentState.value.lines && contentState.value.lines.length > 0) || contentState.value.content
)
const sourcePreviewCandidateType = computed(() => getPreviewTypeByPath(file.value?.filename || ''))
const sourcePreviewDisplayType = computed(
  () => sourcePreview.value.type || sourcePreviewCandidateType.value
)
const sourceContentLength = computed(() =>
  typeof sourcePreview.value.content === 'string' ? sourcePreview.value.content.length : 0
)
const sourcePreviewFile = computed(() => {
  if (!file.value) return null
  return {
    ...file.value,
    content: sourcePreview.value.content,
    previewType: sourcePreviewDisplayType.value,
    previewUrl: sourcePreview.value.url,
    supported: sourcePreview.value.supported,
    message: sourcePreview.value.message
  }
})
const hasSourcePreview = computed(() => canPreviewOriginal(file.value))
const hasMarkdownPreview = computed(() => canPreviewParsed(file.value) || hasContent.value)
const hasChunkPreview = computed(() => canPreviewChunks(file.value))
const availableViewModes = computed(() => {
  const modes = []
  if (hasSourcePreview.value) modes.push('source')
  if (hasMarkdownPreview.value) modes.push('markdown')
  if (hasChunkPreview.value) modes.push('chunks')
  return modes
})
const hasAvailableView = computed(() => availableViewModes.value.length > 0)

const makeViewModeOption = (label, value, icon) => ({
  label: h(
    'span',
    {
      class: 'view-option-icon',
      title: label,
      'aria-label': label
    },
    [h(icon, { size: 15 })]
  ),
  value
})

const viewModeOptions = computed(() => {
  const optionMap = {
    source: makeViewModeOption('tập tin nguồn', 'source', FileSearch),
    markdown: makeViewModeOption('Markdown', 'markdown', FileText),
    chunks: makeViewModeOption('Chunks', 'chunks', Rows3)
  }
  return availableViewModes.value.map((mode) => optionMap[mode])
})

const loadBasicInfo = async () => {
  const kbId = String(props.kbId || '')
  const fileId = String(props.fileId || '')
  if (!kbId || !fileId) return

  const requestId = ++basicRequestSeq
  contentRequestSeq += 1
  file.value = null
  detailError.value = ''
  resetContentState()
  resetSourcePreview()
  viewMode.value = 'markdown'
  basicLoading.value = true

  try {
    const data = await documentApi.getDocumentBasicInfo(kbId, fileId)
    if (requestId !== basicRequestSeq) return
    ensureApiSuccess(data, 'Không thể tải thông tin tập tin')

    const nextFile = normalizeFileMeta(data?.meta || data)
    if (nextFile.is_folder) {
      detailError.value = 'Thư mục không hỗ trợ xem trước chi tiết'
      return
    }

    file.value = nextFile
    viewMode.value = getDefaultDetailView(nextFile)
  } catch (error) {
    if (requestId !== basicRequestSeq) return
    console.error('Không thể tải thông tin tệp cơ bản:', error)
    detailError.value = error.message || 'Không thể tải thông tin tập tin'
    message.error(detailError.value)
  } finally {
    if (requestId === basicRequestSeq) {
      basicLoading.value = false
    }
  }
}

const loadParsedContent = async () => {
  if (!props.kbId || !props.fileId || contentState.value.loading || contentState.value.loaded)
    return

  const requestId = ++contentRequestSeq
  contentState.value = {
    ...contentState.value,
    loading: true,
    error: ''
  }

  try {
    const data = await documentApi.getDocumentContent(props.kbId, props.fileId)
    if (requestId !== contentRequestSeq) return
    ensureApiSuccess(data, 'Không tải được nội dung được phân tích cú pháp')
    contentState.value = {
      loading: false,
      loaded: true,
      lines: data?.lines || [],
      content: data?.content || '',
      error: ''
    }
  } catch (error) {
    if (requestId !== contentRequestSeq) return
    console.error('Không tải được nội dung được phân tích cú pháp:', error)
    const errorMessage = error.message || 'Không tải được nội dung được phân tích cú pháp'
    contentState.value = {
      loading: false,
      loaded: false,
      lines: [],
      content: '',
      error: errorMessage
    }
    message.error(errorMessage)
  }
}

watch(
  () => [props.open, props.kbId, props.fileId],
  ([open]) => {
    if (!open) {
      resetLocalState()
      return
    }
    loadBasicInfo()
  },
  { immediate: true }
)

watch(
  availableViewModes,
  (modes) => {
    if (modes.length > 0 && !modes.includes(viewMode.value)) {
      viewMode.value = modes[0]
    }
  },
  { immediate: true }
)

watch(
  [visible, file, viewMode],
  async ([open, currentFile, currentViewMode]) => {
    if (!open || !currentFile) return
    if (
      (currentViewMode === 'markdown' && canPreviewParsed(currentFile)) ||
      (currentViewMode === 'chunks' && canPreviewChunks(currentFile))
    ) {
      await loadParsedContent()
    }
  },
  { immediate: true }
)

watch(
  [visible, file, viewMode],
  async ([open, currentFile, currentViewMode]) => {
    if (!open || !currentFile || !hasSourcePreview.value || currentViewMode !== 'source') {
      if (!open || !hasSourcePreview.value) {
        resetSourcePreview()
      }
      return
    }

    await loadSourcePreview()
  },
  { immediate: true }
)

// Thống kê
const mergeResult = computed(() => mergeChunks(contentState.value.lines || []))
const mappedChunks = computed(() => mergeResult.value.chunks)
const mergedContent = computed(() => contentState.value.content || mergeResult.value.content || '')
const charCount = computed(() => mergedContent.value.length)
const chunkCount = computed(
  () => mappedChunks.value.length || contentState.value.lines?.length || 0
)
const viewInfoText = computed(() => {
  if (viewMode.value === 'chunks') {
    if (contentState.value.loading) return ''
    return `${chunkCount.value} mảnh vỡ`
  }
  if (viewMode.value === 'source') {
    if (sourcePreview.value.loading) return ''
    if (sourceContentLength.value > 0)
      return `${formatTextLength(sourceContentLength.value)} nhân vật`
    if (sourcePreview.value.url) return 'Xem trước tập tin nguồn'
    return ''
  }
  if (contentState.value.loading) return ''
  return `${formatTextLength(charCount.value)} nhân vật`
})

// Định dạng độ dài văn bản
function formatTextLength(length) {
  if (!length && length !== 0) return '0 nhân vật'

  if (length < 1000) {
    return `${length}`
  } else {
    return `${(length / 1000).toFixed(1)}k`
  }
}

const afterOpenChange = (open) => {
  if (!open) {
    resetLocalState()
    emit('closed')
  }
}

const loadSourcePreview = async () => {
  if (!file.value?.file_id || !props.kbId || !props.fileId || !hasSourcePreview.value) return
  if (sourcePreview.value.url || sourcePreview.value.content || sourcePreview.value.message) return

  const requestId = ++sourceRequestSeq
  sourcePreview.value.loading = true
  try {
    const response = await getWorkspaceKnowledgeFileContent(props.kbId, props.fileId)
    const preview = await normalizePreviewResponse(response)
    if (requestId !== sourceRequestSeq) {
      if (preview.previewUrl) {
        window.URL.revokeObjectURL(preview.previewUrl)
      }
      return
    }
    revokeSourcePreviewUrl()
    sourcePreview.value.type = preview.previewType || sourcePreviewCandidateType.value
    sourcePreview.value.message = preview.message || ''
    sourcePreview.value.supported = preview.supported !== false
    sourcePreview.value.url = preview.previewUrl || ''
    sourcePreview.value.content = preview.content || ''
  } catch (error) {
    if (requestId !== sourceRequestSeq) return
    console.error('Không thể tải bản xem trước tệp nguồn:', error)
    sourcePreview.value.message = error.message || 'Không thể tải bản xem trước tệp nguồn'
    sourcePreview.value.supported = false
    message.error(sourcePreview.value.message)
  } finally {
    if (requestId === sourceRequestSeq) {
      sourcePreview.value.loading = false
    }
  }
}

// Xử lý nhấp chuột vào menu tải xuống
const handleDownloadMenuClick = ({ key }) => {
  if (key === 'original') {
    handleDownloadOriginal()
  } else if (key === 'markdown') {
    handleDownloadMarkdown()
  }
}

// Tải văn bản gốc
const handleDownloadOriginal = async () => {
  if (!file.value || !props.kbId || !props.fileId) {
    message.error('Thông tin tập tin không đầy đủ')
    return
  }

  downloadingOriginal.value = true
  try {
    const response = await documentApi.downloadDocument(props.kbId, props.fileId)

    // Lấy tên tập tin
    const contentDisposition = response.headers.get('content-disposition')
    let filename = file.value.filename
    if (contentDisposition) {
      // Đầu tiên hãy thử để phù hợpRFC 2231định dạng filename*=UTF-8''...
      const rfc2231Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
      if (rfc2231Match) {
        try {
          filename = decodeURIComponent(rfc2231Match[1])
        } catch (error) {
          console.warn('Failed to decode RFC2231 filename:', rfc2231Match[1], error)
        }
      } else {
        // dự phòng về định dạng chuẩn filename="..."
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '')
          // Giải mãURLtên tệp được mã hóa
          try {
            filename = decodeURIComponent(filename)
          } catch (error) {
            console.warn('Failed to decode filename:', filename, error)
          }
        }
      }
    }

    // tạo rablobvà tải về
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success('Tải xuống thành công')
  } catch (error) {
    console.error('Lỗi tải tập tin xuống:', error)
    message.error(error.message || 'Tải xuống tệp không thành công')
  } finally {
    downloadingOriginal.value = false
  }
}

// Tải xuống Markdown
const handleDownloadMarkdown = () => {
  const content = mergedContent.value

  if (!content) {
    message.error('Không có sẵn để tải xuống Markdown nội dung')
    return
  }

  downloadingMarkdown.value = true
  try {
    // Tạo tên tập tin（Nếu file gốc không có .md phần mở rộng，sau đó thêm）
    let filename = file.value.filename || 'document.md'
    if (!filename.toLowerCase().endsWith('.md')) {
      // Xóa tiện ích mở rộng ban đầu，thêm .md
      const lastDotIndex = filename.lastIndexOf('.')
      if (lastDotIndex > 0) {
        filename = filename.substring(0, lastDotIndex) + '.md'
      } else {
        filename = filename + '.md'
      }
    }

    // tạo ra blob và tải về
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success('Tải xuống thành công')
  } catch (error) {
    console.error('Tải xuống Markdown lỗi:', error)
    message.error(error.message || 'Tải xuống Markdown thất bại')
  } finally {
    downloadingMarkdown.value = false
  }
}

onBeforeUnmount(resetLocalState)
</script>

<style scoped>
.file-detail-content {
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.content-panel,
.chunks-panel {
  flex: 1;
  overflow-y: auto;
  padding: 0;
  min-height: 0;
}

.source-panel {
  overflow: hidden;
}

:deep(.source-preview-container) {
  height: 100%;
  max-height: none;
}

:deep(.source-preview-content) {
  flex: 1 1 auto;
  max-height: none;
  min-height: 0;
}

:deep(.source-preview-content .html-preview),
:deep(.source-preview-content .pdf-preview) {
  display: block;
  height: 100%;
  min-height: 100%;
}

.markdown-content {
  min-height: 100%;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}

.empty-content {
  text-align: center;
  padding: 40px 0;
  color: var(--gray-400);
  width: 100%;
}

/* Chunks Kiểu bảng điều khiển */
.chunk-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.chunk-card {
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 12px;
  transition: all 0.2s ease;
}

.chunk-card:hover {
  border-color: var(--main-color);
  box-shadow: 0 2px 8px rgba(1, 97, 121, 0.1);
}

.chunk-card-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.chunk-order {
  font-weight: 600;
  color: var(--main-color);
  font-size: 12px;
}

.chunk-card-content {
  font-size: 12px;
  color: var(--gray-600);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
}
</style>

<style lang="less">
.file-detail {
  .ant-modal {
    top: 20px;
  }

  .ant-modal-header {
    .ant-modal-title {
      width: 100%;
    }
  }
}

.modal-title-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-width: 0;
}

/* Kiểu tiêu đề tập tin */
.file-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1 1 auto;
  min-width: 0;

  svg {
    flex: 0 0 auto;
  }
}

.file-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
  font-size: 15px;
  color: var(--gray-900);
}

.title-info {
  font-size: 13px;
  color: var(--gray-600);
  font-weight: 500;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
  margin-left: auto;
  min-width: 0;
}

/* Kiểu nút tải xuống */
.download-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: auto;
  min-width: 48px;
  padding: 0 10px;
  height: 28px;
  line-height: 1;
  border-radius: 6px;
  gap: 4px;

  svg {
    flex: 0 0 auto;
    vertical-align: middle;
  }
}

/* Nút đóng tùy chỉnh */
.custom-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 28px;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--gray-500);
  transition: all 0.2s;

  &:hover {
    background: var(--gray-100);
    color: var(--gray-700);
  }
}

/* Xem điều khiển chuyển mạch */
.view-controls {
  display: flex;
  align-items: center;
  flex: 0 0 auto;

  .ant-segmented {
    padding: 2px;
  }

  .ant-segmented-item {
    min-width: 30px;
  }

  .ant-segmented-item-label {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 24px;
    min-height: 24px;
    padding: 0 7px;
    line-height: 24px;
  }
}

.view-option-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
}

.view-info {
  flex: 0 0 auto;
  font-size: 12px;
  color: var(--gray-500);
  white-space: nowrap;
}

/* Kiểu menu thả xuống */
.ant-dropdown-menu {
  border-radius: 8px;
  padding: 4px;
}

.ant-dropdown-menu-item {
  border-radius: 6px;
  display: flex;
  align-items: center;
  padding: 8px 12px;

  svg {
    margin-right: 8px;
  }
}
</style>
