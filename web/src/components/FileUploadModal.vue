<template>
  <a-modal v-model:open="visible" title="Thêm tập tin" width="800px" @cancel="handleCancel">
    <template #footer>
      <div class="footer-container">
        <a-button type="link" class="help-link-btn" @click="openDocLink">
          <CircleHelp :size="14" /> Hướng dẫn xử lý tài liệu
        </a-button>
        <div class="footer-buttons">
          <a-button key="back" @click="handleCancel">Hủy bỏ</a-button>
          <a-button
            key="submit"
            type="primary"
            @click="chunkData"
            :loading="chunkLoading"
            :disabled="!canSubmit"
          >
            Thêm vào cơ sở kiến thức
          </a-button>
        </div>
      </div>
    </template>

    <div class="add-files-content">
      <!-- 1. thanh hành động hàng đầu -->
      <div class="top-action-bar">
        <div class="mode-switch">
          <a-segmented
            v-model:value="uploadMode"
            :options="uploadModeOptions"
            class="custom-segmented"
          />
        </div>
        <div class="auto-index-toggle">
          <a-checkbox v-model:checked="autoIndex">Tự động đưa vào bộ nhớ sau khi tải lên</a-checkbox>
        </div>
      </div>

      <!-- 2. Bảng cấu hình -->
      <div
        class="settings-panel"
        v-if="folderTreeData.length > 0 || uploadMode !== 'url' || autoIndex"
      >
        <!-- dòng đầu tiên：vị trí lưu trữ + OCR động cơ -->
        <div
          class="setting-row"
          v-if="folderTreeData.length > 0 || uploadMode !== 'url'"
          :class="{ 'two-cols': uploadMode !== 'url' && folderTreeData.length > 0 }"
        >
          <div class="col-item" v-if="folderTreeData.length > 0">
            <div class="setting-label">vị trí lưu trữ</div>
            <div class="setting-content flex-row">
              <a-tree-select
                v-model:value="selectedFolderId"
                show-search
                class="folder-select"
                :dropdown-style="{ maxHeight: '400px', overflow: 'auto' }"
                placeholder="Chọn thư mục đích（Mặc định là thư mục gốc）"
                allow-clear
                tree-default-expand-all
                :tree-data="folderTreeData"
                tree-node-filter-prop="title"
              >
              </a-tree-select>
            </div>
            <p class="param-description">Chọn thư mục đích để lưu file</p>
          </div>
          <div class="col-item" v-if="uploadMode !== 'url'">
            <div class="setting-label">
              OCR động cơ（Chỉ áp dụng cho PDF/Tệp hình ảnh）
              <a-tooltip title="Kiểm tra trạng thái dịch vụ">
                <ReloadOutlined
                  class="action-icon refresh-icon"
                  :class="{ spinning: ocrHealthChecking }"
                  @click="checkOcrHealth"
                />
              </a-tooltip>
            </div>
            <div class="setting-content">
              <a-popover
                v-model:open="ocrPanelOpen"
                placement="bottomLeft"
                trigger="click"
                overlayClassName="ocr-engine-popover"
                @openChange="handleOcrPanelOpenChange"
              >
                <template #content>
                  <div class="ocr-engine-panel">
                    <button
                      v-for="option in availableOcrOptions"
                      :key="option.value"
                      type="button"
                      class="ocr-engine-option"
                      :class="{ selected: processingParams.ocr_engine === option.value }"
                      :disabled="chunkLoading"
                      @click="selectOcrEngine(option.value)"
                    >
                      <span class="ocr-engine-option-header">
                        <span class="ocr-engine-name">{{ option.label }}</span>
                        <span
                          class="ocr-engine-status"
                          :class="`status-${getOcrStatus(option.value)}`"
                        >
                          {{ getOcrStatusLabel(option.value) }}
                        </span>
                      </span>
                      <span class="ocr-engine-desc">{{ getOcrDescription(option.value) }}</span>
                    </button>

                    <div v-if="unavailableOcrOptions.length" class="unavailable-ocr-options">
                      <button
                        type="button"
                        class="unavailable-toggle"
                        @click="toggleUnavailableOcrOptions"
                      >
                        <span>Tùy chọn không khả dụng（{{ unavailableOcrOptions.length }}）</span>
                        <ChevronUp v-if="unavailableOcrExpanded" :size="14" />
                        <ChevronDown v-else :size="14" />
                      </button>

                      <div v-if="unavailableOcrExpanded" class="unavailable-ocr-list">
                        <button
                          v-for="option in unavailableOcrOptions"
                          :key="option.value"
                          type="button"
                          class="ocr-engine-option disabled"
                          disabled
                        >
                          <span class="ocr-engine-option-header">
                            <span class="ocr-engine-name">{{ option.label }}</span>
                            <span
                              class="ocr-engine-status"
                              :class="`status-${getOcrStatus(option.value)}`"
                            >
                              {{ getOcrStatusLabel(option.value) }}
                            </span>
                          </span>
                          <span class="ocr-engine-desc">{{ getOcrDescription(option.value) }}</span>
                        </button>
                      </div>
                    </div>
                  </div>
                </template>

                <a-button class="ocr-engine-trigger" block>
                  <span class="ocr-engine-trigger-main">
                    <ReloadOutlined v-if="ocrHealthChecking" class="ocr-engine-trigger-loading" />
                    <span class="ocr-engine-trigger-label">{{ selectedOcrEngineLabel }}</span>
                  </span>
                  <ChevronDown :size="14" />
                </a-button>
              </a-popover>
            </div>
          </div>
        </div>

        <!-- dòng thứ hai：Cấu hình lưu trữ tự động (Chỉ hiển thị khi bật) -->
        <div class="setting-row" v-if="autoIndex">
          <div class="col-item">
            <div class="setting-label">Cấu hình tham số kho</div>
            <div class="setting-content">
              <ChunkParamsConfig
                :temp-chunk-params="indexParams"
                :show-qa-split="true"
                :show-chunk-size-overlap="true"
                :show-preset="true"
                :allow-preset-follow-default="true"
                :database-preset-id="
                  store.database?.additional_params?.chunk_preset_id || 'general'
                "
              />
            </div>
          </div>
        </div>
      </div>

      <!-- PDF/hình ảnhOCRnhắc nhở (AlertTối ưu hóa phong cách) -->
      <div v-if="hasPdfOrImageFiles && !isOcrEnabled" class="inline-alert warning">
        <Info :size="16" />
        <span>phát hiệnPDFhoặc tập tin hình ảnh，Khuyến nghị kích hoạt OCR để trích xuất nội dung văn bản</span>
      </div>

      <!-- Khu vực tải lên tập tin -->
      <div class="upload-area" v-if="uploadMode === 'file' || uploadMode === 'folder'">
        <a-upload-dragger
          class="custom-dragger"
          v-model:fileList="fileList"
          name="file"
          :multiple="true"
          :directory="isFolderUpload"
          :disabled="chunkLoading"
          :show-upload-list="!showAggregateProgress"
          :accept="acceptedFileTypes"
          :before-upload="beforeUpload"
          :customRequest="customRequest"
          :action="'/api/knowledge/files/upload?kb_id=' + kbId"
          :headers="getAuthHeaders()"
          @change="handleFileUpload"
          @drop="handleDrop"
        >
          <p class="ant-upload-text">Nhấp hoặc kéo tập tin vào đây</p>
          <p class="ant-upload-hint">Loại hỗ trợ: {{ uploadHint }}</p>
          <div class="zip-tip" v-if="hasZipFiles">📦 ZIPGói sẽ được tự động giải nén và giải nén. Markdown với hình ảnh</div>
        </a-upload-dragger>

        <div v-if="showAggregateProgress" class="upload-progress-card">
          <div class="progress-header">
            <div class="progress-header-left">
              <div class="progress-title">Tiến trình tải lên</div>
              <div class="progress-stats inline-in-header">
                <div class="stat-pill">tổng cộng {{ totalUploadCount }}</div>
                <div class="stat-pill uploading" v-if="uploadingUploadCount > 0">
                  Đang tải lên {{ uploadingUploadCount }}
                </div>
                <div class="stat-pill queued" v-if="queuedUploadCount > 0">
                  xếp hàng {{ queuedUploadCount }}
                </div>
                <div class="stat-pill error" v-if="failedUploadCount > 0">
                  thất bại {{ failedUploadCount }}
                </div>
              </div>
            </div>
            <div class="progress-header-right">
              <div class="progress-percent">{{ overallUploadProgress }}%</div>
              <a-button
                type="text"
                size="small"
                class="toggle-progress-btn"
                @click="progressExpanded = !progressExpanded"
              >
                <span>{{ progressExpanded ? 'đóng' : 'Mở rộng' }}</span>
                <ChevronUp v-if="progressExpanded" :size="14" />
                <ChevronDown v-else :size="14" />
              </a-button>
            </div>
          </div>

          <div v-if="progressExpanded" class="progress-details">
            <div class="details-list" v-if="failedDetailItems.length > 0">
              <div v-for="item in failedDetailItems" :key="item.uid" class="detail-row">
                <span class="detail-name" :title="item.name">{{ item.name }}</span>
                <span class="detail-error" :title="item.errorText">{{ item.errorText }}</span>
              </div>
            </div>

            <div class="progress-tip" v-else>Hiện tại không có tập tin bị lỗi。</div>

            <div class="progress-tip" v-if="hasPendingUploads">
              Tải lên thư mục sử dụng chế độ xếp hàng，Tải lên đồng thời tối đa {{ MAX_UPLOAD_CONCURRENCY }} tập tin。
            </div>
            <div class="progress-tip" v-else>Hàng đợi tải lên đã hoàn tất，Có thể nhấp“Thêm vào cơ sở kiến thức”Tiếp tục đến bước tiếp theo。</div>
          </div>
        </div>
      </div>

      <!-- Vùng chọn tệp không gian làm việc -->
      <div class="workspace-area" v-if="uploadMode === 'workspace'">
        <div class="workspace-toolbar">
          <div class="workspace-summary">
            <FolderOpen :size="16" />
            <span class="workspace-current-path" :title="workspaceCurrentPath">
              {{ workspaceCurrentPath }}
            </span>
            <span
              >Đã chọn
              {{ selectedWorkspacePaths.length }}
              tập tin，Lưu ý rằng việc tải lên sẽ được làm phẳng，Không bảo toàn thứ bậc tập tin</span
            >
          </div>
          <div class="workspace-actions">
            <a-button
              size="small"
              class="lucide-icon-btn"
              :disabled="workspaceCurrentPath === '/' || workspaceLoading"
              @click="openWorkspaceParent"
            >
              <ArrowLeft :size="14" />
            </a-button>
            <a-button
              size="small"
              @click="loadWorkspaceFiles()"
              :loading="workspaceLoading"
              class="lucide-icon-btn"
            >
              <RotateCw :size="14" />
            </a-button>
          </div>
        </div>

        <div class="workspace-list" v-if="workspaceItems.length > 0">
          <button
            v-for="item in workspaceDirectoryItems"
            :key="item.path"
            type="button"
            class="workspace-item workspace-directory"
            :disabled="chunkLoading"
            @click="openWorkspaceDirectory(item.path)"
          >
            <a-checkbox disabled />
            <FileTypeIcon is-dir :size="16" class="workspace-file-icon" />
            <span class="workspace-file-name" :title="item.path">{{ item.name }}</span>
          </button>

          <label
            v-for="item in workspaceFileItems"
            :key="item.path"
            class="workspace-item"
            :class="{ disabled: !item.supported }"
          >
            <a-checkbox
              :checked="selectedWorkspacePathSet.has(item.path)"
              :disabled="!item.supported || chunkLoading"
              @change="toggleWorkspacePath(item.path, $event.target.checked)"
            />
            <FileTypeIcon :name="item.path" :size="16" class="workspace-file-icon" />
            <span class="workspace-file-name" :title="item.path">{{ item.path }}</span>
            <span class="workspace-file-size">{{ formatFileSize(item.size) }}</span>
          </label>
        </div>

        <div class="url-empty-tip" v-else>
          <Info :size="16" />
          <span>{{ workspaceLoading ? 'Đang tải tập tin không gian làm việc' : 'Không có tập tin nào trong thư mục hiện tại' }}</span>
        </div>
      </div>

      <!-- URL khu vực đầu vào -->
      <div class="url-area" v-if="uploadMode === 'url'">
        <div class="url-input-wrapper">
          <a-textarea
            v-model:value="newUrl"
            placeholder="đầu vào URL，Một trên mỗi dòng&#10;https://site1.com&#10;https://site2.com"
            :auto-size="{ minRows: 4, maxRows: 8 }"
            class="url-input"
            @keydown.enter.ctrl="handleFetchUrls"
          />
          <div class="url-actions">
            <span class="url-hint">
              Hỗ trợ dán hàng loạt，Tự động lọc dòng trống。
              <span class="warning-text">Cần cấu hình danh sách trắng，Xem tài liệu để biết chi tiết</span>
            </span>
            <a-button
              type="primary"
              @click="handleFetchUrls"
              class="add-url-btn"
              :loading="fetchingUrls"
              :disabled="!newUrl.trim()"
            >
              Tải URLs
            </a-button>
          </div>
        </div>
        <div class="url-list" v-if="urlList.length > 0">
          <div v-for="(item, index) in urlList" :key="index" class="url-item">
            <div class="url-icon-wrapper">
              <Link v-if="item.status === 'success'" :size="14" class="url-icon success" />
              <Info
                v-else-if="item.status === 'error'"
                :size="14"
                class="url-icon error"
                :title="item.error"
              />
              <RotateCw v-else :size="14" class="url-icon spinning" />
            </div>
            <div class="url-content">
              <span class="url-text" :title="item.url">{{ item.url }}</span>
              <span v-if="item.status === 'error'" class="url-error-msg">{{ item.error }}</span>
            </div>
            <a-button type="text" size="small" class="remove-url-btn" @click="removeUrl(index)">
              <X :size="14" />
            </a-button>
          </div>
        </div>
        <div class="url-empty-tip" v-else>
          <Info :size="16" />
          <span>đầu vào URL Sau đó bấm vào để tải，Hệ thống sẽ tự động thu thập nội dung web</span>
        </div>
      </div>

      <!-- Dấu nhắc tệp có cùng tên -->
      <div v-if="sameNameFiles.length > 0" class="conflict-files-panel">
        <div class="panel-header">
          <Info :size="14" class="icon-warning" />
          <span>Một tập tin có cùng tên đã tồn tại ({{ sameNameFiles.length }})</span>
        </div>
        <div class="file-list-scroll">
          <div v-for="file in sameNameFiles" :key="file.file_id" class="conflict-item">
            <div class="file-meta">
              <span class="fname" :title="file.filename">{{ file.filename }}</span>
              <span class="ftime">{{ formatFileTime(file.created_at) }}</span>
            </div>
            <div class="file-actions">
              <a-button
                type="text"
                size="small"
                class="action-btn download"
                @click="downloadSameNameFile(file)"
              >
                <Download :size="14" />
              </a-button>
              <a-button
                type="text"
                size="small"
                danger
                class="action-btn delete"
                @click="deleteSameNameFile(file)"
              >
                <Trash2 :size="14" />
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, computed, onMounted, watch, h } from 'vue'
import { message, Upload, Modal } from 'ant-design-vue'
import { useUserStore } from '@/stores/user'
import { useDatabaseStore } from '@/stores/database'
import { ocrApi } from '@/apis/system_api'
import { fileApi, documentApi } from '@/apis/knowledge_api'
import { getWorkspaceTree } from '@/apis/workspace_api'
import { ReloadOutlined } from '@ant-design/icons-vue'
import {
  FileUp,
  FolderUp,
  FolderOpen,
  ArrowLeft,
  RotateCw,
  CircleHelp,
  Info,
  Download,
  Trash2,
  Link,
  X,
  ChevronDown,
  ChevronUp
} from 'lucide-vue-next'
import { buildChunkParamsPayload } from '@/utils/chunk_presets'
import ChunkParamsConfig from '@/components/ChunkParamsConfig.vue'
import FileTypeIcon from '@/components/common/FileTypeIcon.vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  folderTree: {
    type: Array,
    default: () => []
  },
  currentFolderId: {
    type: String,
    default: null
  },
  isFolderMode: {
    type: Boolean,
    default: false
  },
  mode: {
    type: String,
    default: 'file'
  }
})

const emit = defineEmits(['update:visible', 'success'])

const store = useDatabaseStore()

// Lựa chọn thư mục liên quan
const selectedFolderId = ref(null)
const folderTreeData = computed(() => {
  // Chuyển đổi folderTree Dữ liệu là TreeSelect định dạng bắt buộc
  const transformData = (nodes) => {
    return nodes
      .map((node) => {
        if (!node.is_folder) return null
        return {
          title: node.filename,
          value: node.file_id,
          key: node.file_id,
          children: node.children ? transformData(node.children).filter(Boolean) : []
        }
      })
      .filter(Boolean)
  }
  return transformData(props.folderTree)
})

watch(
  () => props.visible,
  (newVal) => {
    if (newVal) {
      selectedFolderId.value = props.currentFolderId
      isFolderUpload.value = props.isFolderMode
      uploadMode.value = props.mode || (props.isFolderMode ? 'folder' : 'file')
      if (uploadMode.value === 'workspace') {
        loadWorkspaceFiles()
      }
    }
  }
)

const DEFAULT_SUPPORTED_TYPES = ['.txt', '.pdf', '.jpg', '.jpeg', '.md', '.docx']

const normalizeExtensions = (extensions) => {
  if (!Array.isArray(extensions)) {
    return []
  }
  const normalized = extensions
    .map((ext) => (typeof ext === 'string' ? ext.trim().toLowerCase() : ''))
    .filter((ext) => ext.length > 0)
    .map((ext) => (ext.startsWith('.') ? ext : `.${ext}`))

  return Array.from(new Set(normalized)).sort()
}

const supportedFileTypes = ref(normalizeExtensions(DEFAULT_SUPPORTED_TYPES))

const applySupportedFileTypes = (extensions) => {
  const normalized = normalizeExtensions(extensions)
  if (normalized.length > 0) {
    supportedFileTypes.value = normalized
  } else {
    supportedFileTypes.value = normalizeExtensions(DEFAULT_SUPPORTED_TYPES)
  }
}

const acceptedFileTypes = computed(() => {
  if (!supportedFileTypes.value.length) {
    return ''
  }
  const exts = new Set(supportedFileTypes.value)
  exts.add('.zip')
  return Array.from(exts).join(',')
})

const uploadHint = computed(() => {
  if (!supportedFileTypes.value.length) {
    return 'Đang tải...'
  }
  const exts = new Set(supportedFileTypes.value)
  exts.add('.zip')
  return Array.from(exts).join(', ')
})

const isSupportedExtension = (fileName) => {
  if (!fileName) {
    return true
  }
  if (!supportedFileTypes.value.length) {
    return true
  }
  const lastDotIndex = fileName.lastIndexOf('.')
  if (lastDotIndex === -1) {
    return false
  }
  const ext = fileName.slice(lastDotIndex).toLowerCase()
  return supportedFileTypes.value.includes(ext) || ext === '.zip'
}

const loadSupportedFileTypes = async () => {
  try {
    const data = await fileApi.getSupportedFileTypes()
    applySupportedFileTypes(data?.file_types)
  } catch (error) {
    console.error('Không thể tải các loại tệp được hỗ trợ:', error)
    message.warning('Không thể tải các loại tệp được hỗ trợ，Cấu hình mặc định được sử dụng')
    applySupportedFileTypes(DEFAULT_SUPPORTED_TYPES)
  }
}

onMounted(() => {
  loadSupportedFileTypes()
})

const visible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

const kbId = computed(() => store.kbId)
const chunkLoading = computed(() => store.state.chunkLoading)

// Chế độ tải lên
const uploadMode = ref('file')
const MAX_UPLOAD_CONCURRENCY = 10

// danh sách tập tin
const fileList = ref([])

const uploadQueue = ref([])
const activeUploadCount = ref(0)
const uploadTaskStatus = ref({})
const uploadTaskProgress = ref({})
const progressExpanded = ref(false)

const totalUploadCount = computed(() => fileList.value.length)
const queuedUploadCount = computed(
  () => Object.values(uploadTaskStatus.value).filter((status) => status === 'queued').length
)
const uploadingUploadCount = computed(
  () => Object.values(uploadTaskStatus.value).filter((status) => status === 'uploading').length
)
const successUploadCount = computed(
  () => Object.values(uploadTaskStatus.value).filter((status) => status === 'done').length
)
const failedUploadCount = computed(
  () => Object.values(uploadTaskStatus.value).filter((status) => status === 'error').length
)
const hasPendingUploads = computed(() => queuedUploadCount.value + uploadingUploadCount.value > 0)

const overallUploadProgress = computed(() => {
  const total = totalUploadCount.value
  if (!total) {
    return 0
  }
  const validUidSet = new Set(fileList.value.map((file) => file.uid).filter(Boolean))
  let sum = 0
  for (const uid of validUidSet) {
    sum += uploadTaskProgress.value[uid] || 0
  }
  return Math.round(sum / total)
})

const showAggregateProgress = computed(() => totalUploadCount.value >= MAX_UPLOAD_CONCURRENCY)

const failedDetailItems = computed(() => {
  return fileList.value
    .map((file) => {
      const uid = file.uid
      const rawStatus = uploadTaskStatus.value[uid] || file.status || 'unknown'
      const detail = file?.response?.detail || file?.error?.message || ''
      return {
        uid,
        name: file.name || 'tập tin không tên',
        status: rawStatus,
        errorText: detail || 'Tải lên không thành công'
      }
    })
    .filter((item) => item.status === 'error')
})

const canSubmit = computed(() => {
  if (uploadMode.value === 'url') {
    return urlList.value.some((item) => item.status === 'success')
  }
  if (uploadMode.value === 'workspace') {
    return selectedWorkspacePaths.value.length > 0 && !workspaceLoading.value
  }
  return successUploadCount.value > 0 && !hasPendingUploads.value
})

const uploadModeOptions = computed(() => [
  {
    value: 'file',
    label: h('div', { class: 'segmented-option' }, [
      h(FileUp, { size: 16, class: 'option-icon' }),
      h('span', { class: 'option-text' }, 'Tải tập tin lên')
    ])
  },
  {
    value: 'folder',
    label: h('div', { class: 'segmented-option' }, [
      h(FolderUp, { size: 16, class: 'option-icon' }),
      h('span', { class: 'option-text' }, 'Tải lên thư mục')
    ])
  },
  {
    value: 'url',
    label: h('div', { class: 'segmented-option' }, [
      h(Link, { size: 16, class: 'option-icon' }),
      h('span', { class: 'option-text' }, 'phân tích cú pháp URL')
    ])
  },
  {
    value: 'workspace',
    label: h('div', { class: 'segmented-option' }, [
      h(FolderOpen, { size: 16, class: 'option-icon' }),
      h('span', { class: 'option-text' }, 'không gian làm việc')
    ])
  }
])

watch(uploadMode, (val) => {
  isFolderUpload.value = val === 'folder'
  // Xóa nội dung đã chọn khi chuyển chế độ，tránh nhầm lẫn
  fileList.value = []
  sameNameFiles.value = []
  urlList.value = []
  newUrl.value = ''
  selectedWorkspacePaths.value = []
  workspaceCurrentPath.value = '/'
  workspaceItems.value = []
  for (const task of uploadQueue.value) {
    task.canceled = true
  }
  uploadQueue.value = []
  uploadTaskStatus.value = {}
  uploadTaskProgress.value = {}
  progressExpanded.value = false
  if (val === 'workspace') {
    loadWorkspaceFiles('/')
  }
})

watch(fileList, (newFileList) => {
  const validUidSet = new Set(newFileList.map((file) => file.uid).filter(Boolean))
  const nextStatus = {}
  const nextProgress = {}

  for (const [uid, status] of Object.entries(uploadTaskStatus.value)) {
    if (validUidSet.has(uid)) {
      nextStatus[uid] = status
    }
  }
  for (const [uid, progress] of Object.entries(uploadTaskProgress.value)) {
    if (validUidSet.has(uid)) {
      nextProgress[uid] = progress
    }
  }

  uploadTaskStatus.value = nextStatus
  uploadTaskProgress.value = nextProgress
})

// URL danh sách
// Item structure: { url: string, status: 'fetching'|'success'|'error', data: object|null, error: string }
const urlList = ref([])
const newUrl = ref('')
const fetchingUrls = ref(false)
const CONTENT_EXISTS_ERROR_TEXT = 'Nội dung đã tồn tại trong cơ sở kiến thức'

// Danh sách các tập tin có cùng tên（Dùng để hiển thị gợi ý）
const sameNameFiles = ref([])

// URL Các chức năng liên quan
const isValidUrl = (string) => {
  try {
    const url = new URL(string)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

const mergeSameNameFiles = (sameNameList = []) => {
  if (!Array.isArray(sameNameList) || sameNameList.length === 0) {
    return
  }
  const existingIds = new Set(sameNameFiles.value.map((f) => f.file_id))
  const newConflicts = sameNameList.filter((f) => !existingIds.has(f.file_id))
  sameNameFiles.value.push(...newConflicts)
}

const fetchSingleUrlItem = async (item) => {
  item.status = 'fetching'
  try {
    const res = await fileApi.fetchUrl(item.url, kbId.value)
    item.status = 'success'
    item.data = res
    mergeSameNameFiles(res.same_name_files)
  } catch (error) {
    console.error('Failed to fetch URL:', error)
    item.status = 'error'

    const detailData = error.response?.data?.detail
    const detailMessage =
      (typeof detailData === 'string' ? detailData : detailData?.message) || error.message || ''
    if (detailMessage.includes('same content') || detailMessage.includes('Cùng nội dung')) {
      item.error = CONTENT_EXISTS_ERROR_TEXT
      mergeSameNameFiles(detailData?.same_name_files)
    } else {
      item.error = detailMessage || 'Tải không thành công'
    }
  }
}

const handleFetchUrls = async () => {
  const text = newUrl.value
  if (!text) return

  const lines = text
    .split(/[\r\n]+/)
    .map((l) => l.trim())
    .filter((l) => l)
  if (lines.length === 0) return

  // 1. tiền xử lý：thêm vào danh sách
  const newItems = []
  for (const url of lines) {
    if (!isValidUrl(url)) {
      continue
    }
    if (urlList.value.some((u) => u.url === url)) continue

    const item = { url, status: 'pending', data: null, error: '' }
    urlList.value.push(item)
    newItems.push(item)
  }

  if (newItems.length === 0) {
    if (lines.length > 0) {
      message.warning('Không phát hiện thấy cái mới hợp lệ nào URL')
    }
    return
  }

  newUrl.value = '' // Xóa hộp nhập liệu
  fetchingUrls.value = true

  await Promise.all(newItems.map(fetchSingleUrlItem))
  fetchingUrls.value = false
}

const removeUrl = (index) => {
  urlList.value.splice(index, 1)
}

// Lựa chọn tệp không gian làm việc
const workspaceLoading = ref(false)
const workspaceItems = ref([])
const workspaceCurrentPath = ref('/')
const selectedWorkspacePaths = ref([])
const selectedWorkspacePathSet = computed(() => new Set(selectedWorkspacePaths.value))
const workspaceDirectoryItems = computed(() => workspaceItems.value.filter((entry) => entry.is_dir))
const workspaceFileItems = computed(() =>
  workspaceItems.value
    .filter((entry) => !entry.is_dir)
    .map((entry) => ({
      ...entry,
      supported: isSupportedExtension(entry.name || entry.path)
    }))
)

const formatFileSize = (size) => {
  if (!Number.isFinite(size)) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

const loadWorkspaceFiles = async (path = workspaceCurrentPath.value) => {
  if (workspaceLoading.value) return
  const targetPath = typeof path === 'string' ? path : workspaceCurrentPath.value

  workspaceLoading.value = true
  try {
    const data = await getWorkspaceTree(targetPath, false, false)
    const entries = Array.isArray(data?.entries) ? data.entries : []
    workspaceCurrentPath.value = targetPath
    workspaceItems.value = entries
  } catch (error) {
    console.error('Không tải được tệp không gian làm việc:', error)
    message.error('Không tải được tệp không gian làm việc: ' + (error.message || 'lỗi không xác định'))
  } finally {
    workspaceLoading.value = false
  }
}

const openWorkspaceDirectory = (path) => {
  loadWorkspaceFiles(path)
}

const openWorkspaceParent = () => {
  if (workspaceCurrentPath.value === '/') return
  const normalized = workspaceCurrentPath.value.replace(/\/$/, '')
  const index = normalized.lastIndexOf('/')
  const parentPath = index <= 0 ? '/' : normalized.slice(0, index)
  loadWorkspaceFiles(parentPath)
}

const toggleWorkspacePath = (path, checked) => {
  if (checked) {
    if (!selectedWorkspacePaths.value.includes(path)) {
      selectedWorkspacePaths.value = [...selectedWorkspacePaths.value, path]
    }
    return
  }
  selectedWorkspacePaths.value = selectedWorkspacePaths.value.filter((item) => item !== path)
}

// OCRTình trạng sức khỏe dịch vụ
const ocrHealthStatus = ref({
  rapid_ocr: { status: 'unknown', message: '' },
  mineru_ocr: { status: 'unknown', message: '' },
  mineru_official: { status: 'unknown', message: '' },
  pp_structure_v3_ocr: { status: 'unknown', message: '' },
  deepseek_ocr: { status: 'unknown', message: '' }
})

// OCRtình trạng kiểm tra sức khỏe
const ocrHealthChecking = ref(false)
const ocrPanelOpen = ref(false)
const unavailableOcrExpanded = ref(false)

// Phân tích tham số
const processingParams = ref({
  ocr_engine: 'disable',
  ocr_engine_config: {}
})

// Liên quan đến kho bãi tự động
const autoIndex = ref(false)
const indexParams = ref({
  chunk_preset_id: '',
  chunk_parser_config: {}
})

const buildAutoIndexParams = () => {
  return buildChunkParamsPayload(indexParams.value, {
    includeSizeOverlap: true
  })
}

const isFolderUpload = ref(false)

// Thuộc tính tính toán：Nó đã được kích hoạt chưaOCR
const isOcrEnabled = computed(() => {
  return processingParams.value.ocr_engine !== 'disable'
})

// Logic liên quan đến chuyển đổi chế độ tải lên đã bị loại bỏ

// Thuộc tính tính toán：Có ở đó không?PDFhoặc tập tin hình ảnh
const hasPdfOrImageFiles = computed(() => {
  if (fileList.value.length === 0) {
    return false
  }

  const pdfExtensions = ['.pdf']
  const imageExtensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp']
  const ocrExtensions = [...pdfExtensions, ...imageExtensions]

  return fileList.value.some((file) => {
    if (file.status !== 'done') {
      return false
    }

    const filePath = file.response?.file_path || file.name
    if (!filePath) {
      return false
    }

    const ext = filePath.substring(filePath.lastIndexOf('.')).toLowerCase()
    return ocrExtensions.includes(ext)
  })
})

// Thuộc tính tính toán：Có ở đó không?ZIPtập tin
const hasZipFiles = computed(() => {
  if (fileList.value.length === 0) {
    return false
  }

  return fileList.value.some((file) => {
    if (file.status !== 'done') {
      return false
    }

    const filePath = file.response?.file_path || file.name
    if (!filePath) {
      return false
    }

    const ext = filePath.substring(filePath.lastIndexOf('.')).toLowerCase()
    return ext === '.zip'
  })
})

const ocrEngineOptions = [
  {
    value: 'disable',
    label: 'Chưa bật',
    description: 'Chưa bật OCR，Chỉ xử lý tệp văn bản'
  },
  {
    value: 'rapid_ocr',
    label: 'RapidOCR (ONNX)',
    description: 'ONNX with RapidOCR'
  },
  {
    value: 'mineru_ocr',
    label: 'MinerU OCR',
    description: 'MinerU OCR'
  },
  {
    value: 'mineru_official',
    label: 'MinerU Official API',
    description: 'MinerU Official API'
  },
  {
    value: 'pp_structure_v3_ocr',
    label: 'PP-Structure-V3',
    description: 'PP-Structure-V3'
  },
  {
    value: 'deepseek_ocr',
    label: 'DeepSeek OCR',
    description: 'DeepSeek OCR (SiliconFlow)'
  }
]

const ocrStatusLabels = {
  local: 'Chưa bật',
  healthy: 'Có sẵn',
  unavailable: 'Không có sẵn',
  unhealthy: 'bất thường',
  timeout: 'hết thời gian chờ',
  error: 'bất thường',
  checking: 'Đang được kiểm tra',
  unknown: 'Trạng thái không xác định'
}

const getOcrStatus = (engine) => {
  if (engine === 'disable') return 'local'
  const current = ocrHealthStatus.value?.[engine]
  if (ocrHealthChecking.value && (!current || current.status === 'unknown')) return 'checking'
  return current?.status || 'unknown'
}

const getOcrStatusLabel = (engine) => ocrStatusLabels[getOcrStatus(engine)] || 'Trạng thái không xác định'

const getOcrDescription = (engine) => {
  const option = ocrEngineOptions.find((item) => item.value === engine)
  if (engine === 'disable') return option?.description || 'Chưa bật OCR，Chỉ xử lý tệp văn bản'

  const messageText = ocrHealthStatus.value?.[engine]?.message
  if (messageText) return messageText

  const status = getOcrStatus(engine)
  const fallbackMap = {
    healthy: 'Dịch vụ là bình thường',
    unavailable: 'Dịch vụ không có sẵn',
    unhealthy: 'Ngoại lệ dịch vụ',
    timeout: 'Hết thời gian kiểm tra dịch vụ',
    error: 'Ngoại lệ dịch vụ',
    checking: 'Kiểm tra trạng thái dịch vụ',
    unknown: option?.description || 'Trạng thái dịch vụ không xác định'
  }
  return fallbackMap[status] || option?.description || 'Trạng thái dịch vụ không xác định'
}

const isUnavailableOcrEngine = (engine) => ['unavailable', 'error'].includes(getOcrStatus(engine))

const availableOcrOptions = computed(() =>
  ocrEngineOptions.filter((option) => !isUnavailableOcrEngine(option.value))
)

const unavailableOcrOptions = computed(() =>
  ocrEngineOptions.filter((option) => isUnavailableOcrEngine(option.value))
)

const selectedOcrEngineLabel = computed(() => {
  return (
    ocrEngineOptions.find((option) => option.value === processingParams.value.ocr_engine)?.label ||
    'chọn OCR động cơ'
  )
})

const selectOcrEngine = (engine) => {
  if (isUnavailableOcrEngine(engine)) return
  processingParams.value.ocr_engine = engine
  ocrPanelOpen.value = false
}

const toggleUnavailableOcrOptions = () => {
  unavailableOcrExpanded.value = !unavailableOcrExpanded.value
}

// Xác minhOCRTính khả dụng của dịch vụ
const validateOcrService = () => {
  if (!isOcrEnabled.value) {
    return true
  }

  const engine = processingParams.value.ocr_engine
  if (isUnavailableOcrEngine(engine)) {
    message.error(`OCRDịch vụ không có sẵn: ${getOcrDescription(engine)}`)
    return false
  }

  return true
}

const handleCancel = () => {
  emit('update:visible', false)
}

const beforeUpload = (file) => {
  if (!isSupportedExtension(file?.name)) {
    message.error(`Các loại tệp không được hỗ trợ：${file?.name || 'tập tin không xác định'}`)
    return Upload.LIST_IGNORE
  }
  return true
}

const formatFileTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    const date = new Date(timestamp)
    return date.toLocaleString()
  } catch {
    return timestamp
  }
}

const showSameNameFilesInUploadArea = (files) => {
  sameNameFiles.value = files
  // Logic bổ sung có thể được thêm vào đây，Ví dụ: tự động cuộn đến vùng nhắc
}

const downloadSameNameFile = async (file) => {
  try {
    // Lấy cơ sở dữ liệu hiện tạiID
    const currentDbId = kbId.value
    if (!currentDbId) {
      message.error('cơ sở tri thứcIDkhông tồn tại')
      return
    }

    message.loading('Đang tải xuống tập tin...', 0)
    const response = await documentApi.downloadDocument(currentDbId, file.file_id)
    message.destroy()

    // Tạo liên kết tải xuống
    const blob = await response.blob() // từ Response Trích xuất từ đối tượng Blob dữ liệu
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = file.filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    message.success(`tập tin ${file.filename} Tải xuống thành công`)
  } catch (error) {
    message.destroy()
    console.error('Tải xuống tệp không thành công:', error)
    message.error(`Tải xuống tệp không thành công: ${error.message || 'lỗi không xác định'}`)
  }
}

const deleteSameNameFile = (file) => {
  Modal.confirm({
    title: 'Xác nhận xóa tập tin',
    content: `Xác nhận bạn muốn xóa tập tin "${file.filename}" ?？Hoạt động này là không thể đảo ngược。`,
    okText: 'Xóa',
    okType: 'danger',
    cancelText: 'Hủy bỏ',
    onOk: async () => {
      try {
        // Lấy cơ sở dữ liệu hiện tạiID
        const currentDbId = kbId.value
        if (!currentDbId) {
          message.error('cơ sở tri thứcIDkhông tồn tại')
          return
        }

        message.loading('Xóa tập tin...', 0)
        await documentApi.deleteDocument(currentDbId, file.file_id)
        message.destroy()

        // Xóa khỏi danh sách các tệp có cùng tên
        sameNameFiles.value = sameNameFiles.value.filter((f) => f.file_id !== file.file_id)

        message.success(`tập tin ${file.filename} Xóa thành công`)
      } catch (error) {
        message.destroy()
        console.error('Không thể xóa tập tin:', error)
        message.error(`Không thể xóa tập tin: ${error.message || 'lỗi không xác định'}`)
      }
    }
  })
}

const customRequest = async (options) => {
  const fileUid = options.file?.uid
  if (fileUid) {
    uploadTaskStatus.value[fileUid] = 'queued'
    uploadTaskProgress.value[fileUid] = 0
  }

  const task = {
    options,
    xhr: null,
    canceled: false
  }

  uploadQueue.value.push(task)
  processUploadQueue()

  return {
    abort: () => {
      task.canceled = true
      if (task.xhr) {
        task.xhr.abort()
      }
      const queueIndex = uploadQueue.value.indexOf(task)
      if (queueIndex !== -1) {
        uploadQueue.value.splice(queueIndex, 1)
      }
      if (fileUid) {
        uploadTaskStatus.value[fileUid] = 'error'
      }
    }
  }
}

const processUploadQueue = () => {
  while (activeUploadCount.value < MAX_UPLOAD_CONCURRENCY && uploadQueue.value.length > 0) {
    const task = uploadQueue.value.shift()
    if (!task || task.canceled) {
      continue
    }

    activeUploadCount.value += 1
    runUploadTask(task)
      .catch(() => {
        // Lỗi đã có rồi runUploadTask xử lý nội bộ，Điều này chỉ đảm bảo rằng hàng đợi tiếp tục tiêu thụ
      })
      .finally(() => {
        activeUploadCount.value -= 1
        processUploadQueue()
      })
  }
}

const runUploadTask = (task) => {
  const { file, onProgress, onSuccess, onError } = task.options
  const fileUid = file?.uid

  if (fileUid) {
    uploadTaskStatus.value[fileUid] = 'uploading'
  }

  return new Promise((resolve, reject) => {
    const formData = new FormData()
    const filename =
      isFolderUpload.value && file.webkitRelativePath ? file.webkitRelativePath : file.name
    formData.append('file', file, filename)

    const currentKbId = kbId.value
    if (!currentKbId) {
      const error = new Error('Database ID is missing')
      if (fileUid) {
        uploadTaskStatus.value[fileUid] = 'error'
      }
      onError(error)
      reject(error)
      return
    }

    const xhr = new XMLHttpRequest()
    task.xhr = xhr
    xhr.open('POST', `/api/knowledge/files/upload?kb_id=${currentKbId}`)

    const headers = getAuthHeaders()
    for (const [key, value] of Object.entries(headers)) {
      xhr.setRequestHeader(key, value)
    }

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) {
        return
      }
      const percent = Math.min(100, (event.loaded / event.total) * 100)
      if (fileUid) {
        uploadTaskProgress.value[fileUid] = percent
      }
      onProgress({ percent })
    }

    xhr.onload = () => {
      if (task.canceled) {
        resolve()
        return
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response = JSON.parse(xhr.responseText)
          if (fileUid) {
            uploadTaskStatus.value[fileUid] = 'done'
            uploadTaskProgress.value[fileUid] = 100
          }
          onSuccess(response, xhr)
          resolve()
        } catch (error) {
          if (fileUid) {
            uploadTaskStatus.value[fileUid] = 'error'
          }
          onError(error)
          reject(error)
        }
        return
      }

      let errorResp
      try {
        errorResp = JSON.parse(xhr.responseText || '{}')
      } catch {
        errorResp = {}
      }
      file.response = errorResp
      const error = new Error(errorResp.detail || 'Upload failed')
      if (fileUid) {
        uploadTaskStatus.value[fileUid] = 'error'
      }
      onError(error, file)
      reject(error)
    }

    xhr.onerror = (errorEvent) => {
      if (fileUid) {
        uploadTaskStatus.value[fileUid] = 'error'
      }
      onError(errorEvent)
      reject(errorEvent)
    }

    xhr.onabort = () => {
      if (fileUid) {
        uploadTaskStatus.value[fileUid] = 'error'
      }
      const abortError = new Error('Upload aborted')
      onError(abortError)
      reject(abortError)
    }

    xhr.send(formData)
  })
}

const handleFileUpload = (info) => {
  if (info?.file?.status === 'error') {
    const file = info.file
    // Hãy thử nhiều cách để nhận được thông báo lỗi
    const detail = file?.response?.detail || file?.error?.message || ''
    if (detail.includes('same content') || detail.includes('Cùng nội dung')) {
      message.error(`${file.name} Đã có file nội dung tương tự，Không cần phải tải lên lại`)
    } else {
      message.error(detail || `Tải tệp lên không thành công：${file.name}`)
    }
  }

  // Kiểm tra xem có dấu nhắc tệp có cùng tên không
  if (info?.file?.status === 'done' && info.file.response) {
    const response = info.file.response
    if (response.has_same_name && response.same_name_files && response.same_name_files.length > 0) {
      showSameNameFilesInUploadArea(response.same_name_files)
    }
  }

  fileList.value = info?.fileList ?? []
}

const handleDrop = () => {}

// Logic tải lên thư mục đã bị xóa

const checkOcrHealth = async () => {
  if (ocrHealthChecking.value) return

  ocrHealthChecking.value = true
  try {
    const healthData = await ocrApi.getHealth()
    ocrHealthStatus.value = healthData.services
  } catch (error) {
    console.error('OCRKiểm tra sức khỏe không thành công:', error)
    message.error('OCRKiểm tra tình trạng dịch vụ không thành công')
  } finally {
    ocrHealthChecking.value = false
  }
}

const handleOcrPanelOpenChange = (open) => {
  ocrPanelOpen.value = open
  if (open) {
    checkOcrHealth()
  }
}

const getAuthHeaders = () => {
  const userStore = useUserStore()
  return userStore.getAuthHeaders()
}

const openDocLink = () => {
  window.open(
    'https://xerrors.github.io/Yuxi/advanced/document-processing.html',
    '_blank',
    'noopener'
  )
}

const chunkData = async () => {
  if (!kbId.value) {
    message.error('Vui lòng chọn cơ sở kiến thức trước')
    return
  }

  // Xác minhOCRTính khả dụng của dịch vụ（Không URL chế độ）
  if (uploadMode.value !== 'url' && !validateOcrService()) {
    return
  }

  if (uploadMode.value === 'workspace') {
    if (selectedWorkspacePaths.value.length === 0) {
      message.error('Vui lòng chọn tệp không gian làm việc trước')
      return
    }

    try {
      store.state.chunkLoading = true
      const res = await fileApi.importWorkspaceFiles(kbId.value, selectedWorkspacePaths.value)
      const importedItems = Array.isArray(res?.items) ? res.items : []
      if (importedItems.length === 0) {
        message.error('Nhập tệp không gian làm việc không thành công')
        return
      }

      const imageExtensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']
      const items = []
      const content_hashes = {}
      const file_sizes = {}
      for (const item of importedItems) {
        const filePath = item.file_path
        if (!filePath) continue
        items.push(filePath)
        if (item.content_hash) content_hashes[filePath] = item.content_hash
        if (Number.isFinite(item.size)) file_sizes[filePath] = item.size
        mergeSameNameFiles(item.same_name_files)

        const ext = filePath.substring(filePath.lastIndexOf('.')).toLowerCase()
        if (imageExtensions.includes(ext) && !isOcrEnabled.value) {
          message.error({
            content: 'Đã phát hiện thấy tệp hình ảnh，Phải được kích hoạt OCR Để trích xuất nội dung văn bản。',
            duration: 5
          })
          return
        }
      }

      const params = { ...processingParams.value, content_hashes, file_sizes }
      if (autoIndex.value) {
        params.auto_index = true
        Object.assign(params, buildAutoIndexParams())
      }

      await store.addFiles({
        items,
        contentType: 'file',
        params,
        parentId: selectedFolderId.value
      })

      emit('success')
      handleCancel()
      selectedWorkspacePaths.value = []
    } catch (error) {
      console.error('Nhập tệp không gian làm việc không thành công:', error)
      message.error('Nhập tệp không gian làm việc không thành công: ' + (error.message || 'lỗi không xác định'))
    } finally {
      store.state.chunkLoading = false
    }
    return
  }

  // URL Xử lý mẫu
  if (uploadMode.value === 'url') {
    // Lọc ra các mục thành công
    const successfulItems = urlList.value.filter((item) => item.status === 'success' && item.data)
    if (successfulItems.length === 0) {
      message.error('Vui lòng thêm và đợi ít nhất một URL Đã phân tích cú pháp thành công')
      return
    }

    // Loại bỏ trùng lặp hàng loạt bằng cách băm nội dung，Tránh lưu trữ trùng lặp của cùng một lô
    const deduplicatedItems = []
    const seenKeys = new Set()
    let skippedDuplicates = 0
    for (const item of successfulItems) {
      const dedupKey = item.data?.content_hash || item.data?.file_path || item.url
      if (seenKeys.has(dedupKey)) {
        skippedDuplicates += 1
        continue
      }
      seenKeys.add(dedupKey)
      deduplicatedItems.push(item)
    }

    if (deduplicatedItems.length === 0) {
      message.error('URL Tất cả nội dung đều trùng lặp，Vui lòng thay đổi và thử lại')
      return
    }

    if (skippedDuplicates > 0) {
      message.warning(`phát hiện ${skippedDuplicates} lặp lại URL nội dung，Cái đầu tiên đã được giữ lại và cái còn lại đã bị bỏ qua`)
    }

    try {
      store.state.chunkLoading = true
      const params = { ...processingParams.value }
      if (autoIndex.value) {
        params.auto_index = true
        Object.assign(params, buildAutoIndexParams())
      }

      // cấu trúc _preprocessed_map và items (minio urls)
      const items = []
      const preprocessedMap = {}
      for (const item of deduplicatedItems) {
        // item.data = { file_path: "http://minio...", content_hash: "...", filename: "...", ... }
        // Lưu ý：fetch-url trả lại file_path Thực ra là vậy MinIO URL
        // chúng ta cần phải vượt qua MinIO URL cho addDocuments
        const minioUrl = item.data.file_path
        items.push(minioUrl)
        preprocessedMap[minioUrl] = {
          path: minioUrl,
          content_hash: item.data.content_hash,
          filename: item.data.filename,
          file_size: item.data.size
        }
      }
      params._preprocessed_map = preprocessedMap

      // gọi addFiles (file mode)
      await store.addFiles({
        items: items,
        contentType: 'file', // quan trọng：Thay đổi ở đây thành file，Bởi vì chúng ta đã quay minio tập tin trên
        params,
        parentId: selectedFolderId.value
      })

      emit('success')
      handleCancel()
      urlList.value = []
      newUrl.value = ''
    } catch (error) {
      console.error('URL Gửi không thành công:', error)
      message.error('URL Gửi không thành công: ' + (error.message || 'lỗi không xác định'))
    } finally {
      store.state.chunkLoading = false
    }
    return
  }

  // Xử lý chế độ tập tin
  const imageExtensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']

  // Trích xuất thông tin tập tin đã tải lên
  const items = []
  const content_hashes = {}
  const file_sizes = {}
  for (const file of fileList.value) {
    if (file.status !== 'done') continue
    const file_path = file.response?.file_path
    const content_hash = file.response?.content_hash
    if (!file_path) continue

    items.push(file_path)
    if (content_hash) content_hashes[file_path] = content_hash
    if (Number.isFinite(file.response?.size)) file_sizes[file_path] = file.response.size

    // Kiểm tra nếu cầnOCR
    const ext = file_path.substring(file_path.lastIndexOf('.')).toLowerCase()
    if (imageExtensions.includes(ext) && !isOcrEnabled.value) {
      message.error({
        content: 'Đã phát hiện thấy tệp hình ảnh，Phải được kích hoạt OCR Để trích xuất nội dung văn bản。',
        duration: 5
      })
      return
    }
  }

  if (items.length === 0) {
    message.error('Vui lòng tải tập tin lên trước')
    return
  }

  try {
    store.state.chunkLoading = true
    const params = { ...processingParams.value, content_hashes, file_sizes }
    if (autoIndex.value) {
      params.auto_index = true
      Object.assign(params, buildAutoIndexParams())
    }

    await store.addFiles({
      items,
      contentType: 'file',
      params,
      parentId: selectedFolderId.value
    })

    emit('success')
    handleCancel()
    fileList.value = []
    sameNameFiles.value = []
  } catch (error) {
    console.error('Tải tệp lên không thành công:', error)
    message.error('Tải tệp lên không thành công: ' + (error.message || 'lỗi không xác định'))
  } finally {
    store.state.chunkLoading = false
  }
}
</script>

<style lang="less" scoped>
.footer-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.footer-buttons {
  display: flex;
  gap: 8px;
}

.add-files-content {
  padding: 8px 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Top Bar */
.top-action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.auto-index-toggle {
  display: flex;
  align-items: center;
  padding-right: 4px;

  :deep(.ant-checkbox-wrapper) {
    font-size: 13px;
    color: var(--gray-600);
    font-weight: 500;
  }
}

.help-link-btn {
  color: var(--gray-600);
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0;

  &:hover {
    color: var(--main-color);
  }
}

.custom-segmented {
  background-color: var(--gray-100);
  padding: 3px;

  .segmented-option {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 32px;
    .option-text {
      margin-left: 6px;
    }
  }
}

/* Settings Panel */
.settings-panel {
  background-color: var(--gray-50);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.setting-row {
  display: flex;
  flex-direction: column;
  gap: 8px;

  &.two-cols {
    flex-direction: row;
    gap: 20px;
  }

  .col-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0; // Fix flex overflow
  }
}

.setting-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--gray-700);
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-icon {
  color: var(--gray-400);
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    color: var(--main-color);
  }

  &.spinning {
    animation: spin 1s linear infinite;
    color: var(--main-color);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.flex-row {
  display: flex;
  align-items: center;
  width: 100%;
}

.folder-select {
  flex: 1;
}

.folder-checkbox {
  margin-left: 12px;
  white-space: nowrap;
}

.ocr-engine-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-width: 0;
}

.ocr-engine-trigger-main {
  display: inline-flex;
  align-items: center;
  flex: 1 1 auto;
  min-width: 0;
  gap: 8px;
}

.ocr-engine-trigger-loading {
  flex: 0 0 auto;
  color: var(--main-color);
  animation: spin 1s linear infinite;
}

.ocr-engine-trigger-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ocr-engine-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 280px;
}

.ocr-engine-option {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--gray-100);
  border-radius: 8px;
  background: var(--gray-0);
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.ocr-engine-option:hover:not(:disabled) {
  border-color: var(--main-color);
  background: color-mix(in srgb, var(--main-color) 6%, var(--gray-0));
}

.ocr-engine-option.selected {
  border-color: var(--main-color);
  background: color-mix(in srgb, var(--main-color) 8%, var(--gray-0));
}

.ocr-engine-option.disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.unavailable-ocr-options,
.unavailable-ocr-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.unavailable-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 4px 2px;
  border: none;
  background: transparent;
  color: var(--gray-500);
  cursor: pointer;
  font-size: 12px;
}

.unavailable-toggle:hover {
  color: var(--gray-800);
}

.ocr-engine-option-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.ocr-engine-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--gray-900);
  font-size: 13px;
  font-weight: 500;
}

.ocr-engine-status {
  display: inline-flex;
  align-items: center;
  min-height: 18px;
  flex: none;
  font-size: 12px;
  line-height: 1;
}

.ocr-engine-status.status-local,
.ocr-engine-status.status-healthy {
  color: var(--color-success-700);
}

.ocr-engine-status.status-unavailable,
.ocr-engine-status.status-error {
  color: var(--color-error-700);
}

.ocr-engine-status.status-unhealthy,
.ocr-engine-status.status-timeout,
.ocr-engine-status.status-unknown,
.ocr-engine-status.status-checking {
  color: var(--color-warning-700);
}

.ocr-engine-desc {
  color: var(--gray-500);
  font-size: 12px;
  line-height: 1.4;
}

:global(.ocr-engine-popover .ant-popover-inner-content) {
  padding: 10px;
}

.param-description {
  font-size: 12px;
  color: var(--gray-400);
  margin: 4px 0 0 0;
  line-height: 1.4;
  display: flex;
  align-items: center;
  gap: 4px;

  .text-success {
    color: var(--color-success-500);
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .text-warning {
    color: var(--color-warning-500);
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

/* Chunk Display Card */
.chunk-display-card {
  background: var(--gray-0);
  border: 1px solid var(--gray-300);
  border-radius: 6px;
  padding: 0 12px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: var(--main-color);
    box-shadow: 0 0 0 2px var(--main-100);

    .edit-icon {
      color: var(--main-color);
    }
  }

  &.disabled {
    background: var(--gray-100);
    cursor: not-allowed;
    color: var(--gray-400);
    &:hover {
      border-color: var(--gray-300);
      box-shadow: none;
    }
  }
}

.chunk-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--gray-700);

  .divider {
    color: var(--gray-300);
    font-size: 10px;
  }

  b {
    font-weight: 600;
    color: var(--gray-900);
  }
}

.edit-icon {
  color: var(--gray-400);
  font-size: 14px;
}

/* Alerts */
.inline-alert {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;

  &.warning {
    background: var(--color-warning-50);
    border: 1px solid var(--color-warning-200);
    color: var(--color-warning-700);
  }
}

/* Upload Area */
.upload-area {
  flex: 1;
}

.custom-dragger {
  :deep(.ant-upload-drag) {
    background: var(--gray-0);
    border-radius: 8px;
    border: 1px dashed var(--gray-300);
    transition: all 0.3s;

    &:hover {
      border-color: var(--main-color);
      background: var(--main-50);
    }
  }

  .ant-upload-drag-icon {
    font-size: 32px;
    color: var(--main-300);
    margin-bottom: 8px;
  }

  .ant-upload-text {
    font-size: 15px;
    color: var(--gray-800);
    margin-bottom: 4px;
  }

  .ant-upload-hint {
    font-size: 12px;
    color: var(--gray-500);
  }
}

.zip-tip {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-warning-600);
  background: var(--color-warning-50);
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
}

.upload-progress-card {
  margin-top: 8px;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  background: var(--gray-50);
  padding: 8px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-header-left {
  display: flex;
  flex-direction: row;
  gap: 6px;
  align-items: center;
  min-width: 0;
}

.progress-header-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.progress-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--gray-700);
  white-space: nowrap;
}

.progress-percent {
  font-size: 14px;
  font-weight: 700;
  color: var(--main-600);
}

.progress-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;

  &.inline-in-header {
    gap: 6px;
  }
}

.stat-pill {
  border-radius: 999px;
  padding: 1px 8px;
  font-size: 11px;
  line-height: 1.4;
  border: 1px solid var(--gray-300);
  background: var(--gray-100);
  color: var(--gray-600);

  &.uploading {
    background: var(--main-50);
    border-color: var(--main-200);
    color: var(--main-600);
  }

  &.queued {
    background: var(--gray-100);
    border-color: var(--gray-300);
    color: var(--gray-600);
  }

  &.success {
    background: var(--color-success-50);
    border-color: var(--color-success-200);
    color: var(--color-success-600);
  }

  &.error {
    background: var(--color-error-50);
    border-color: var(--color-error-200);
    color: var(--color-error-600);
  }
}

.progress-tip {
  margin-top: 6px;
  font-size: 11px;
  color: var(--gray-500);
}

.progress-details {
  border-top: 1px dashed var(--gray-200);
  padding-top: 6px;
}

.details-list {
  max-height: 160px;
  overflow-y: auto;
  border: 1px solid var(--gray-200);
  border-radius: 6px;
  background: var(--gray-0);
}

.detail-row {
  padding: 6px 8px;
  border-bottom: 1px solid var(--gray-100);

  &:last-child {
    border-bottom: none;
  }
}

.detail-name {
  font-size: 11px;
  color: var(--gray-700);
  font-weight: 500;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.detail-error {
  margin-top: 2px;
  font-size: 11px;
  color: var(--color-error-600);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.toggle-progress-btn {
  color: var(--gray-500);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding-inline: 4px;

  &:hover {
    color: var(--main-600);
    background: var(--gray-100);
  }
}

/* Workspace Area */
.workspace-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.workspace-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.workspace-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--gray-700);
  min-width: 0;
}

.workspace-current-path {
  max-width: 360px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.workspace-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.workspace-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 8px;
  background: var(--gray-0);
}

.workspace-item {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 8px;
  min-height: 34px;
  padding: 6px 8px;
  border-radius: 6px;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: var(--gray-50);
  }

  &.disabled {
    cursor: not-allowed;
    color: var(--gray-400);
  }
}

.workspace-directory {
  color: var(--gray-800);
}

.workspace-file-icon {
  flex-shrink: 0;
  color: var(--main-500);
}

.workspace-file-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--gray-700);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-file-size {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--gray-500);
}

/* URL Area */
.url-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.url-input-wrapper {
  width: 100%;
}

.url-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

.url-hint {
  font-size: 12px;
  color: var(--gray-500);

  .warning-text {
    color: var(--color-warning-500);
    margin-left: 4px;
  }
}

.url-input {
  width: 100%;
  padding: 10px;
}

.add-url-btn {
  margin-left: 8px;
}

.url-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.url-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--gray-50);
  border: 1px solid var(--gray-200);
  border-radius: 6px;
  transition: all 0.2s;

  &:hover {
    background: var(--gray-100);
    border-color: var(--main-300);
  }
}

.url-icon-wrapper {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.url-icon {
  color: var(--main-500);

  &.success {
    color: var(--color-success-500);
  }

  &.error {
    color: var(--color-error-500);
    cursor: help;
  }

  &.spinning {
    animation: spin 1s linear infinite;
    color: var(--main-500);
  }
}

.url-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.url-text {
  font-size: 13px;
  color: var(--gray-700);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.url-error-msg {
  font-size: 11px;
  color: var(--color-error-500);
  margin-top: 2px;
}

.remove-url-btn {
  color: var(--gray-400);
  flex-shrink: 0;

  &:hover {
    color: var(--color-error-500);
  }
}

.url-empty-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: var(--gray-50);
  border: 1px dashed var(--gray-300);
  border-radius: 8px;
  color: var(--gray-500);
  font-size: 13px;
}

/* Conflict Files Panel */
.conflict-files-panel {
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  overflow: hidden;
  background: var(--gray-0);
  margin-top: 4px;
}

.panel-header {
  background: var(--gray-50);
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--gray-700);
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--gray-200);

  .icon-warning {
    color: var(--color-warning-500);
  }
}

.file-list-scroll {
  max-height: 120px;
  overflow-y: auto;
}

.conflict-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--gray-100);
  transition: background 0.2s;

  &:last-child {
    border-bottom: none;
  }

  &:hover {
    background: var(--gray-50);
  }
}

.file-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
  font-size: 13px;

  .fname {
    font-weight: 500;
    color: var(--gray-800);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .ftime {
    color: var(--gray-400);
    font-size: 12px;
    flex-shrink: 0;
  }
}

.file-actions {
  display: flex;
  gap: 4px;

  .action-btn {
    color: var(--gray-500);

    &:hover {
      color: var(--main-600);
      background: var(--main-50);
    }

    &.delete:hover {
      color: var(--color-error-500);
      background: var(--color-error-50);
    }
  }
}

.auto-index-params {
  margin-top: 8px;
  padding: 12px;
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 6px;
}

.setting-label .ant-checkbox {
  margin-right: 8px;
}

@media (max-width: 768px) {
  .top-action-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .auto-index-toggle {
    padding-right: 0;
  }

  .progress-header {
    flex-direction: column;
    gap: 8px;
  }

  .progress-header-right {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
