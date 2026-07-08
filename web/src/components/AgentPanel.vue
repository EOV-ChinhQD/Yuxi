<template>
  <div class="agent-panel" :class="{ resizing: isResizing }">
    <div class="resize-handle" @pointerdown="startResize"></div>
    <div class="panel-header side-panel__header">
      <div class="panel-title">
        <div v-if="hasActivePreview && normalizedPreviewTabs.length" class="preview-tabs-bar">
          <div
            v-for="tab in normalizedPreviewTabs"
            :key="tab.path"
            class="preview-tab"
            :class="{ active: tab.path === activePreviewPath }"
          >
            <button
              type="button"
              class="preview-tab-main"
              :title="tab.path"
              @click="activatePreviewTab(tab.path)"
            >
              <FileTypeIcon :name="tab.path" :size="16" class="preview-tab-icon" />
              <span class="preview-tab-name">{{ tab.name }}</span>
            </button>
            <button
              type="button"
              class="preview-tab-close"
              title="Đóng bản xem trước"
              aria-label="Đóng bản xem trước"
              @click.stop="closePreviewTab(tab.path)"
            >
              <X :size="13" />
            </button>
          </div>
        </div>
        <span v-else><strong>tập tin</strong></span>
      </div>
      <div class="window-actions">
        <button
          v-if="hasActivePreview"
          class="header-action-btn"
          :class="{ active: treePaneVisible }"
          :title="treePaneVisible ? 'Danh sách tập tin ẩn' : 'Xem danh sách tập tin'"
          :aria-label="treePaneVisible ? 'Danh sách tập tin ẩn' : 'Xem danh sách tập tin'"
          @click="toggleFileTree"
        >
          <Folders :size="15" />
        </button>
        <button class="header-action-btn" title="Làm mới" aria-label="Làm mới" @click="emitRefresh">
          <RefreshCw :size="15" />
        </button>
        <button
          class="header-action-btn"
          title="Đóng bảng tập tin"
          aria-label="Đóng bảng tập tin"
          @click="emitClose"
        >
          <PanelRightClose :size="15" />
        </button>
      </div>
    </div>

    <div class="tab-content">
      <div
        class="files-display"
        :class="{ 'has-preview': hasActivePreview, 'with-tree': treePaneVisible }"
      >
        <div v-if="hasActivePreview" class="preview-pane">
          <AgentFilePreview
            v-if="currentFile"
            containerClass="side-preview-shell"
            contentClass="side-file-content"
            :file="currentFile"
            :filePath="currentFilePath"
            :fullHeight="true"
            :showFileIcon="false"
            :borderless="true"
            :showClose="false"
            :showDownload="true"
            :showFullscreen="true"
            @download="downloadFile"
          />
          <div v-else class="preview-empty">
            <div class="preview-empty-title">Sau khi chọn sản phẩm bàn giao của mình, bạn có thể xem trước chúng tại đây</div>
            <div class="preview-empty-desc">Bạn cũng có thể mở danh sách tập tin，Duyệt tập tin trong không gian làm việc hiện tại。</div>
          </div>
        </div>

        <div v-if="treePaneVisible" class="tree-pane">
          <div v-if="!threadId" class="empty">Có thể xem không gian làm việc sau khi tạo cuộc trò chuyện</div>
          <div v-else-if="loadingFiles" class="empty">Đang tải hệ thống tập tin...</div>
          <div v-else-if="filesystemError" class="empty error-state">
            <div>{{ filesystemError }}</div>
            <a-button type="link" size="small" @click="refreshFileSystem">Thử lại</a-button>
          </div>
          <div v-else-if="!fileTreeData.length" class="empty">Không gian làm việc hiện tại trống</div>
          <div v-else class="file-tree-container">
            <FileTreeComponent
              v-model:selectedKeys="selectedKeys"
              v-model:expandedKeys="expandedKeys"
              :tree-data="fileTreeData"
              :load-data="loadData"
              @select="onFileSelect"
            >
              <template #title="{ node }">
                <div class="tree-node-name" :title="node.title">
                  <span class="name-start">{{ node.nameStart || node.title }}</span>
                  <span class="name-end" v-if="node.nameEnd">{{ node.nameEnd }}</span>
                </div>
              </template>
              <template #actions="{ node }">
                <div class="node-actions-container">
                  <button
                    v-if="node.isLeaf"
                    class="tree-action-btn tree-download-btn"
                    @click.stop="downloadFile(node.fileData)"
                    title="Tải tập tin xuống"
                    aria-label="Tải tập tin xuống"
                  >
                    <Download :size="14" />
                  </button>
                  <button
                    class="tree-action-btn tree-delete-btn"
                    :disabled="deletingPaths.has(node.key)"
                    @click.stop="confirmDeleteNode(node)"
                    :title="node.isLeaf ? 'Xóa tập tin' : 'xóa thư mục'"
                    :aria-label="node.isLeaf ? 'Xóa tập tin' : 'xóa thư mục'"
                  >
                    <Trash2 :size="14" />
                  </button>
                </div>
              </template>
            </FileTreeComponent>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Download, Folders, PanelRightClose, RefreshCw, Trash2, X } from 'lucide-vue-next'
import { Modal, message } from 'ant-design-vue'
import FileTreeComponent from '@/components/FileTreeComponent.vue'
import AgentFilePreview from '@/components/AgentFilePreview.vue'
import FileTypeIcon from '@/components/common/FileTypeIcon.vue'
import {
  deleteViewerFile,
  downloadViewerFile,
  getViewerFileContent,
  getViewerFileSystemTree
} from '@/apis/viewer_filesystem'
import { normalizePreviewResponse } from '@/utils/file_preview'

const props = defineProps({
  agentState: {
    type: Object,
    default: () => ({})
  },
  threadId: {
    type: String,
    default: null
  },
  panelRatio: {
    type: Number,
    default: 0.35
  },
  previewTabs: {
    type: Array,
    default: () => []
  },
  activePreviewPath: {
    type: String,
    default: ''
  },
  viewMode: {
    type: String,
    default: 'tree',
    validator: (value) => ['tree', 'preview'].includes(value)
  }
})

const emit = defineEmits([
  'close',
  'refresh',
  'resize',
  'resizing',
  'open-preview',
  'activate-preview',
  'close-preview-tab',
  'close-preview-path',
  'view-mode-change'
])
const DISPLAY_ROOT_DIRECTORY_NAME = 'user-data'

const currentFile = ref(null)
const currentFilePath = ref('')
const loadingFiles = ref(false)
const filesystemError = ref('')

const dynamicTreeData = ref([])
const selectedKeys = ref([])
const expandedKeys = ref([])
const deletingPaths = ref(new Set())
const isResizing = ref(false)

const normalizedPreviewTabs = computed(() =>
  (props.previewTabs || [])
    .filter((file) => file?.path)
    .map((file) => ({
      ...file,
      path: String(file.path),
      name: file.name || getFileName(file)
    }))
)
const hasActivePreview = computed(() => Boolean(props.activePreviewPath))
const treePaneVisible = computed(() => !hasActivePreview.value || props.viewMode === 'tree')
const activePreviewTab = computed(
  () => normalizedPreviewTabs.value.find((file) => file.path === props.activePreviewPath) || null
)
const fileTreeData = computed(() => dynamicTreeData.value)

const buildDisplayName = (fullPath) => {
  const normalized = String(fullPath || '').replace(/\/+$/, '')
  if (!normalized || normalized === '/') return '/'
  const parts = normalized.split('/').filter(Boolean)
  return parts[parts.length - 1] || normalized
}

const sortEntries = (entries) => {
  return [...entries].sort((left, right) => {
    const leftIsDir = Boolean(left?.is_dir)
    const rightIsDir = Boolean(right?.is_dir)
    if (leftIsDir !== rightIsDir) {
      return leftIsDir ? -1 : 1
    }

    const leftName = buildDisplayName(left?.path).toLowerCase()
    const rightName = buildDisplayName(right?.path).toLowerCase()
    return leftName.localeCompare(rightName, 'zh-Hans-CN')
  })
}

const createTreeNode = (entry) => {
  const fullPath = String(entry?.path || '')
  const title = buildDisplayName(fullPath)
  const isLeaf = !entry?.is_dir

  let nameStart = title
  let nameEnd = ''

  if (isLeaf && title.length > 5) {
    nameEnd = title.slice(-5)
    nameStart = title.slice(0, -5)
  }

  return {
    key: fullPath,
    title,
    nameStart,
    nameEnd,
    isLeaf,
    children: isLeaf ? undefined : [],
    fileData: {
      ...entry,
      path: fullPath,
      name: title,
      type: isLeaf ? 'file' : 'directory'
    },
    class: isLeaf ? 'file-node' : 'folder-node'
  }
}

const updateTreeChildren = (nodes, targetKey, children) => {
  return nodes.map((node) => {
    if (node.key === targetKey) {
      return { ...node, children }
    }
    if (!node.children?.length) {
      return node
    }
    return {
      ...node,
      children: updateTreeChildren(node.children, targetKey, children)
    }
  })
}

const removeTreeNode = (nodes, targetKey) => {
  return nodes.reduce((result, node) => {
    if (node.key === targetKey) {
      return result
    }

    const nextNode = node.children?.length
      ? {
          ...node,
          children: removeTreeNode(node.children, targetKey)
        }
      : node

    result.push(nextNode)
    return result
  }, [])
}

const normalizePathKey = (path) => String(path || '').replace(/\/+$/, '')

const isSameOrChildPath = (path, targetPath) => {
  const normalizedPath = normalizePathKey(path)
  const normalizedTargetPath = normalizePathKey(targetPath)
  if (!normalizedPath || !normalizedTargetPath) return false
  return (
    normalizedPath === normalizedTargetPath || normalizedPath.startsWith(`${normalizedTargetPath}/`)
  )
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

const getFileName = (fileItem) => {
  if (fileItem?.name) return fileItem.name
  if (fileItem?.path) {
    return String(fileItem.path).split('/').pop() || String(fileItem.path)
  }
  return 'tập tin không xác định'
}

const loadDirectoryChildren = async (directoryPath) => {
  const res = await getViewerFileSystemTree(props.threadId, directoryPath)
  return sortEntries(res?.entries || []).map((entry) => createTreeNode(entry))
}

const refreshFileSystem = async () => {
  if (!props.threadId) {
    dynamicTreeData.value = []
    filesystemError.value = ''
    return
  }

  loadingFiles.value = true
  filesystemError.value = ''

  try {
    const res = await getViewerFileSystemTree(props.threadId, '/')
    if (res?.entries) {
      const displayRootEntry = res.entries.find(
        (entry) => entry?.is_dir && entry.name === DISPLAY_ROOT_DIRECTORY_NAME
      )

      dynamicTreeData.value = displayRootEntry
        ? await loadDirectoryChildren(displayRootEntry.path)
        : []
      expandedKeys.value = []
      selectedKeys.value = props.activePreviewPath ? [props.activePreviewPath] : []
    } else {
      dynamicTreeData.value = []
    }
  } catch (error) {
    dynamicTreeData.value = []
    filesystemError.value = error?.message || 'Không thể tải hệ thống tập tin'
    console.error('Failed to load root files', error)
  } finally {
    loadingFiles.value = false
  }
}

const loadData = async (treeNode) => {
  if (treeNode.isLeaf || treeNode.children?.length || !props.threadId) return

  try {
    const children = await loadDirectoryChildren(treeNode.key)
    dynamicTreeData.value = updateTreeChildren(dynamicTreeData.value, treeNode.key, children)
  } catch (error) {
    console.error('Failed to load children for', treeNode.key, error)
  }
}

let previewRequestSeq = 0

const revokeCurrentPreviewUrl = () => {
  const previewUrl = currentFile.value?.previewUrl
  if (previewUrl) {
    window.URL.revokeObjectURL(previewUrl)
  }
}

const loadActivePreview = async () => {
  const filePath = props.activePreviewPath
  const requestSeq = ++previewRequestSeq

  revokeCurrentPreviewUrl()

  if (!filePath || !props.threadId) {
    currentFile.value = null
    currentFilePath.value = ''
    return
  }

  const baseFile = {
    ...(activePreviewTab.value || {}),
    path: filePath,
    name: activePreviewTab.value?.name || getFileName({ path: filePath }),
    type: 'file'
  }

  currentFilePath.value = filePath
  currentFile.value = {
    ...baseFile,
    content: 'Loading...',
    supported: true,
    previewType: 'text',
    message: '',
    previewUrl: ''
  }

  try {
    const res = await getViewerFileContent(props.threadId, filePath)
    if (requestSeq !== previewRequestSeq) return

    const nextFile = await normalizePreviewResponse(res, baseFile)

    if (requestSeq !== previewRequestSeq) {
      if (nextFile.previewUrl) window.URL.revokeObjectURL(nextFile.previewUrl)
      return
    }

    currentFile.value = nextFile
  } catch (error) {
    if (requestSeq !== previewRequestSeq) return

    currentFile.value = {
      ...baseFile,
      content: `Error loading file: ${error?.message || 'unknown error'}`,
      supported: false,
      previewType: 'unsupported',
      message: error?.message || 'Xem trước tệp không thành công',
      previewUrl: ''
    }
  }
}

const onFileSelect = (nextSelectedKeys, { node }) => {
  selectedKeys.value = nextSelectedKeys
  if (!node?.isLeaf || !props.threadId) return
  emit('open-preview', node.fileData, true)
}

const activatePreviewTab = (filePath) => {
  emit('activate-preview', filePath)
}

const closePreviewTab = (filePath) => {
  emit('close-preview-tab', filePath)
}

const toggleFileTree = () => {
  emit('view-mode-change', treePaneVisible.value ? 'preview' : 'tree')
}

const pruneTreeStateAfterDelete = (targetPath) => {
  selectedKeys.value = selectedKeys.value.filter((key) => !isSameOrChildPath(key, targetPath))
  expandedKeys.value = expandedKeys.value.filter((key) => !isSameOrChildPath(key, targetPath))
  emit('close-preview-path', targetPath)
}

const confirmDeleteNode = (node) => {
  const fileName = node?.title || getFileName(node?.fileData)
  const isDirectory = !node?.isLeaf
  Modal.confirm({
    title: isDirectory ? `Xác nhận xóa thư mục「${fileName}」？` : `Xác nhận xóa tập tin「${fileName}」？`,
    content: isDirectory ? 'Thư mục và tất cả nội dung của nó sẽ bị xóa，Không thể phục hồi sau khi xóa。' : 'Không thể phục hồi sau khi xóa。',
    okText: 'Xóa',
    okType: 'danger',
    cancelText: 'Hủy bỏ',
    onOk: async () => {
      const nextDeletingPaths = new Set(deletingPaths.value)
      nextDeletingPaths.add(node.key)
      deletingPaths.value = nextDeletingPaths

      try {
        await deleteViewerFile(props.threadId, node.key)
        dynamicTreeData.value = removeTreeNode(dynamicTreeData.value, node.key)
        pruneTreeStateAfterDelete(node.key)
        message.success(isDirectory ? 'Đã xóa thư mục thành công' : 'Đã xóa tệp thành công')
      } catch (error) {
        console.error(isDirectory ? 'Không xóa được thư mục:' : 'Không thể xóa tập tin:', error)
        message.error(error?.message || (isDirectory ? 'Không xóa được thư mục' : 'Không thể xóa tập tin'))
      } finally {
        const latestDeletingPaths = new Set(deletingPaths.value)
        latestDeletingPaths.delete(node.key)
        deletingPaths.value = latestDeletingPaths
      }
    }
  })
}

const downloadFile = async (fileItem) => {
  if (!props.threadId || !fileItem?.path) return

  try {
    const response = await downloadViewerFile(props.threadId, fileItem.path)
    const blob = await response.blob()
    const contentDisposition =
      response.headers.get('Content-Disposition') || response.headers.get('content-disposition')
    const filename = parseDownloadFilename(contentDisposition) || getFileName(fileItem)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Tải xuống tệp không thành công:', error)
  }
}

const emitRefresh = () => {
  refreshFileSystem()
  emit('refresh', props.threadId)
}

const emitClose = () => {
  emit('close')
}

let resizePointerId = null
let pendingClientX = 0
let resizeFrameId = 0

const flushResize = () => {
  resizeFrameId = 0
  if (!isResizing.value) return
  emit('resize', pendingClientX)
}

const queueResize = (clientX) => {
  pendingClientX = clientX
  if (resizeFrameId) return
  resizeFrameId = window.requestAnimationFrame(flushResize)
}

const startResize = (e) => {
  if (e.button !== 0) return

  isResizing.value = true
  resizePointerId = e.pointerId
  pendingClientX = e.clientX
  emit('resizing', true, e.clientX)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'

  e.currentTarget?.setPointerCapture?.(e.pointerId)
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', stopResize)
  window.addEventListener('pointercancel', stopResize)
}

const onPointerMove = (e) => {
  if (!isResizing.value || e.pointerId !== resizePointerId) return
  queueResize(e.clientX)
}

const stopResize = (e) => {
  if (!isResizing.value || (e && e.pointerId !== resizePointerId)) return

  if (resizeFrameId) {
    window.cancelAnimationFrame(resizeFrameId)
    resizeFrameId = 0
  }

  if (e) {
    pendingClientX = e.clientX
    emit('resize', pendingClientX)
  }

  isResizing.value = false
  resizePointerId = null
  emit('resizing', false)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', stopResize)
  window.removeEventListener('pointercancel', stopResize)
}

onMounted(() => {
  refreshFileSystem()
})

onUnmounted(() => {
  if (resizeFrameId) {
    window.cancelAnimationFrame(resizeFrameId)
    resizeFrameId = 0
  }
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', stopResize)
  window.removeEventListener('pointercancel', stopResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  revokeCurrentPreviewUrl()
})

watch(
  () => props.threadId,
  (threadId) => {
    if (threadId) {
      refreshFileSystem()
    } else {
      dynamicTreeData.value = []
      expandedKeys.value = []
      selectedKeys.value = []
      filesystemError.value = ''
    }
  }
)

watch([() => props.threadId, () => props.activePreviewPath], loadActivePreview, { immediate: true })

watch(
  () => props.activePreviewPath,
  (filePath) => {
    selectedKeys.value = filePath ? [filePath] : []
  }
)
</script>

<style scoped lang="less">
.resize-handle {
  position: absolute;
  left: -2px;
  top: 50%;
  transform: translateY(-50%);
  height: 32px;
  width: 4px;
  cursor: col-resize;
  background: var(--gray-300);
  border-radius: 2px;
  z-index: 10;
  transition: background 0.2s;
  touch-action: none;

  &:hover {
    background: var(--main-400);
  }
}

.agent-panel {
  width: 100%;
  height: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  position: relative;
  background: var(--gray-0);
  transition: none;

  &.resizing {
    transition: none;
  }

  .panel-header {
    border-bottom: 1px solid var(--gray-100);
  }

  :deep(.side-preview-shell) {
    border: none;
  }

  :deep(.preview-header) {
    min-height: 32px;
    padding-top: 0;
  }
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 12px;
  min-height: var(--header-height);
  background: var(--gray-25);
  border-bottom: 1px solid var(--gray-100);
  flex-shrink: 0;
}

.header-action-btn {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--gray-600);
  cursor: pointer;
  padding: 0;
  transition: all 0.15s ease;

  &:hover,
  &.active {
    background: var(--gray-100);
    color: var(--gray-900);
  }

  &:disabled {
    color: var(--gray-300);
    cursor: not-allowed;
    background: transparent;
  }
}

.panel-title {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  font-weight: 600;
  font-size: 14px;
  color: var(--gray-900);

  > span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.window-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.tab-content {
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.files-display {
  height: 100%;
  min-height: 0;
  display: flex;
}

.preview-pane {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
}

.tree-pane {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 6px;
}

.files-display.has-preview.with-tree .tree-pane {
  flex: 0 0 34%;
  min-width: 260px;
  max-width: 380px;
  border-left: 1px solid var(--gray-100);
}

.preview-tabs-bar {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  padding-bottom: 1px;
  scrollbar-width: none;

  &::-webkit-scrollbar {
    display: none;
  }
}

.preview-tab {
  min-width: 0;
  max-width: 220px;
  display: flex;
  align-items: center;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-25);
  color: var(--gray-700);
  overflow: hidden;
  flex-shrink: 0;

  &.active {
    border-color: var(--gray-150);
    background: var(--gray-0);
    color: var(--main-800);
  }
}

.preview-tab-main {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 5px 6px 5px 8px;
}

.preview-tab-icon {
  flex-shrink: 0;
  font-size: 14px;
}

.preview-tab-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
}

.preview-tab-close {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--gray-500);
  cursor: pointer;
  padding: 0;

  &:hover {
    color: var(--gray-900);
    background: var(--gray-100);
  }
}

.side-preview-shell {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--gray-150);
  border-radius: 12px;
  background: var(--gray-0);
  overflow: hidden;
}

.side-preview-shell :deep(.file-content),
.side-preview-shell :deep(.side-file-content) {
  flex: 1;
  min-height: 0;
  max-height: none;
}

.preview-empty,
.empty {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--gray-500);
  padding: 24px;
  font-size: 14px;
}

.preview-empty {
  border: 1px dashed var(--gray-200);
  border-radius: 12px;
  background: linear-gradient(180deg, var(--gray-25) 0%, var(--gray-0) 100%);
}

.preview-empty-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-800);
}

.preview-empty-desc {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
}

.error-state {
  gap: 8px;
}

.file-tree-container {
  flex: 1;
  min-height: 0;
  overflow-y: auto;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: var(--gray-50);
  }

  &::-webkit-scrollbar-thumb {
    background: var(--gray-300);
    border-radius: 3px;

    &:hover {
      background: var(--gray-400);
    }
  }
}

.tree-node-name {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  font-size: 14px;
  color: var(--gray-800);
}

.name-start {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.name-end {
  flex-shrink: 0;
  white-space: nowrap;
}

.node-actions-container {
  display: flex;
  align-items: center;
  gap: 4px;
}

.tree-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--gray-500);
  cursor: pointer;
  padding: 0;

  &:disabled {
    cursor: not-allowed;
    opacity: 0.45;
  }
}

.tree-download-btn:hover {
  color: var(--main-600);
}

.tree-delete-btn:hover:not(:disabled) {
  color: var(--error-600, #dc2626);
}
</style>
