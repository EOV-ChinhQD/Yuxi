import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { databaseApi, documentApi, queryApi } from '@/apis/knowledge_api'
import { useTaskerStore } from '@/stores/tasker'
import { useUserStore } from '@/stores/user'
import { useRouter } from 'vue-router'
import { parseToShanghai } from '@/utils/time'
import { canSelectFile, isProcessingFile } from '@/utils/knowledge_file_policy'

export const useDatabaseStore = defineStore('database', () => {
  const router = useRouter()
  const taskerStore = useTaskerStore()
  const userStore = useUserStore()

  // State
  const databases = ref([])
  const database = ref({})
  const kbId = ref(null)
  const fileDetailFileId = ref(null)
  const documentFiles = ref([])
  const folderBreadcrumbs = ref([
    { file_id: null, filename: 'Tất cả các tập tin', path_prefix: '' }
  ])

  const queryParams = ref([])
  const meta = reactive({})
  const selectedRowKeys = ref([])
  const fileBrowser = reactive({
    loading: false,
    parentId: null,
    page: 1,
    pageSize: 100,
    total: 0,
    hasMore: false,
    pathPrefix: '',
    status: 'all',
    recursive: false
  })

  const state = reactive({
    listLoading: false,
    creating: false,
    databaseLoading: false,
    lock: false,
    fileDetailModalVisible: false,
    batchDeleting: false,
    chunkLoading: false,
    autoRefresh: false,
    queryParamsLoading: false,
    rightPanelVisible: true
  })

  let refreshInterval = null
  let autoRefreshSource = null // Tracks whether auto-refresh was user-triggered or automatic
  let autoRefreshManualOverride = false // Indicates user explicitly disabled auto-refresh

  function setCurrentFileMap(items = []) {
    database.value = {
      ...database.value,
      files: Object.fromEntries(items.map((item) => [item.file_id, item]))
    }
  }

  function resetFileBrowser() {
    documentFiles.value = []
    folderBreadcrumbs.value = [{ file_id: null, filename: 'Tất cả các tập tin', path_prefix: '' }]
    selectedRowKeys.value = []
    Object.assign(fileBrowser, {
      loading: false,
      parentId: null,
      page: 1,
      pageSize: 100,
      total: 0,
      hasMore: false,
      pathPrefix: '',
      status: 'all',
      recursive: false
    })
    setCurrentFileMap([])
  }

  // Actions
  // Quản trị viên có được tất cả các cơ sở kiến thức，Người dùng thông thường có quyền truy cập vào cơ sở tri thức
  async function loadDatabases() {
    state.listLoading = true
    try {
      const data = userStore.isAdmin
        ? await databaseApi.getDatabases()
        : await databaseApi.getAccessibleDatabases()
      const list = data?.databases || []
      databases.value = list.sort((a, b) => {
        const timeA = parseToShanghai(a.created_at)
        const timeB = parseToShanghai(b.created_at)
        if (!timeA && !timeB) return 0
        if (!timeA) return 1
        if (!timeB) return -1
        return timeB.valueOf() - timeA.valueOf() // Thứ tự giảm dần，mới nhất đầu tiên
      })
    } catch (error) {
      console.error('Không thể tải danh sách cơ sở dữ liệu:', error)
      if (error.message.includes('Quyền')) {
        message.error('Không có quyền truy cập vào cơ sở kiến thức')
      }
      throw error
    } finally {
      state.listLoading = false
    }
  }

  async function createDatabase(formData) {
    // Xác minh
    if (!formData.database_name?.trim()) {
      message.error('Tên cơ sở dữ liệu không được để trống')
      return false
    }

    if (!formData.kb_type) {
      message.error('Vui lòng chọn loại cơ sở kiến thức')
      return false
    }

    state.creating = true
    try {
      const data = await databaseApi.createDatabase(formData)
      message.success('Đã tạo thành công')
      await loadDatabases() // Làm mới danh sách
      return data
    } catch (error) {
      console.error('Không tạo được cơ sở dữ liệu:', error)
      message.error(error.message || 'Tạo không thành công')
      throw error
    } finally {
      state.creating = false
    }
  }

  async function getDatabaseInfo(id, skipQueryParams = false, isBackground = false) {
    const kbIdValue = id || kbId.value
    if (!kbIdValue) return

    if (!isBackground) {
      state.lock = true
      state.databaseLoading = true
    }
    try {
      const data = await databaseApi.getDatabaseInfo(kbIdValue)
      const currentFiles = database.value.files || {}
      database.value = { ...data, files: data?.files || currentFiles }
      ensureAutoRefreshForProcessing(data?.files, data?.stats)

      // Only load query parameters if explicitly requested or if not loaded yet
      if (!skipQueryParams && queryParams.value.length === 0) {
        await loadQueryParams(kbIdValue)
      }
    } catch (error) {
      console.error(error)
      message.error(error.message || 'Không thể lấy được thông tin cơ sở dữ liệu')
    } finally {
      if (!isBackground) {
        state.lock = false
        state.databaseLoading = false
      }
    }
  }

  async function updateDatabaseInfo(formData) {
    try {
      state.lock = true
      await databaseApi.updateDatabase(kbId.value, formData)
      message.success('Thông tin cơ sở kiến thức được cập nhật thành công')
      await getDatabaseInfo() // Load query params after updating database info
    } catch (error) {
      console.error(error)
      message.error(error.message || 'Cập nhật không thành công')
    } finally {
      state.lock = false
    }
  }

  function deleteDatabase() {
    Modal.confirm({
      title: 'Xóa cơ sở dữ liệu',
      content: 'Bạn có chắc chắn muốn xóa cơ sở dữ liệu này?？',
      okText: 'Xác nhận',
      cancelText: 'Hủy bỏ',
      onOk: async () => {
        state.lock = true
        try {
          const data = await databaseApi.deleteDatabase(kbId.value)
          message.success(data.message || 'Xóa thành công')
          router.push({ path: '/extensions', query: { tab: 'knowledge' } })
        } catch (error) {
          console.error(error)
          message.error(error.message || 'Xóa không thành công')
        } finally {
          state.lock = false
        }
      }
    })
  }

  async function deleteFile(fileId) {
    state.lock = true
    try {
      await documentApi.deleteDocument(kbId.value, fileId)
      await getDatabaseInfo(undefined, true) // Skip query params for file deletion
      await loadDocumentFiles({ isBackground: true })
    } catch (error) {
      console.error(error)
      message.error(error.message || 'Xóa không thành công')
      throw error
    } finally {
      state.lock = false
    }
  }

  function handleDeleteFile(fileId) {
    Modal.confirm({
      title: 'Xóa tập tin',
      content: 'Bạn có chắc chắn muốn xóa tập tin này?？',
      okText: 'Xác nhận',
      cancelText: 'Hủy bỏ',
      onOk: () => deleteFile(fileId)
    })
  }

  function handleBatchDelete() {
    const files = database.value.files || {}
    const validFileIds = selectedRowKeys.value.filter((fileId) => {
      const file = files[fileId]
      return canSelectFile(file)
    })

    if (validFileIds.length === 0) {
      message.info('Không có tập tin để xóa')
      return
    }

    Modal.confirm({
      title: 'Xóa tập tin theo đợt',
      content: `Bạn có chắc chắn muốn xóa mục đã chọn ${validFileIds.length} Một tập tin?？`,
      okText: 'Xác nhận',
      cancelText: 'Hủy bỏ',
      onOk: async () => {
        state.batchDeleting = true
        let successCount = 0
        let failureCount = 0
        let processedCount = 0
        const totalCount = validFileIds.length
        const progressKey = `batch-delete-${Date.now()}`
        message.loading({ content: `Xóa tập tin 0/${totalCount}`, key: progressKey, duration: 0 })

        try {
          const CHUNK_SIZE = 50
          for (let i = 0; i < totalCount; i += CHUNK_SIZE) {
            const chunk = validFileIds.slice(i, i + CHUNK_SIZE)

            try {
              const res = await documentApi.batchDeleteDocuments(kbId.value, chunk)
              successCount += res.deleted_count || 0
              if (res.failed_items) {
                failureCount += res.failed_items.length
              }
            } catch (err) {
              console.error(`Xóa hàng loạt ${i / CHUNK_SIZE + 1} thất bại:`, err)
              failureCount += chunk.length
            } finally {
              processedCount += chunk.length
              message.loading({
                content: `Xóa tập tin ${processedCount}/${totalCount}`,
                key: progressKey,
                duration: 0
              })
            }
          }

          message.destroy(progressKey)
          if (successCount > 0 && failureCount === 0) {
            message.success(`đã xóa thành công ${successCount} tập tin`)
          } else if (successCount > 0 && failureCount > 0) {
            message.warning(
              `đã xóa thành công ${successCount} tập tin，${failureCount} Xóa tập tin không thành công`
            )
          } else if (failureCount > 0) {
            message.error(`${failureCount} Xóa tập tin không thành công`)
          }

          selectedRowKeys.value = []
          await getDatabaseInfo(undefined, true) // Skip query params for batch deletion
          await loadDocumentFiles({ isBackground: true })
        } catch (error) {
          message.destroy(progressKey)
          console.error('Lỗi xóa hàng loạt:', error)
          message.error(error.message || 'Đã xảy ra lỗi khi xóa hàng loạt')
        } finally {
          state.batchDeleting = false
        }
      }
    })
  }

  function enableAutoRefresh(source = 'auto') {
    if (autoRefreshManualOverride && source === 'auto') {
      return
    }

    if (!state.autoRefresh) {
      state.autoRefresh = true
      autoRefreshSource = source
      autoRefreshManualOverride = false
      startAutoRefresh()
      return
    }

    if (source === 'auto' && autoRefreshSource !== 'manual') {
      autoRefreshSource = 'auto'
    }
  }

  function ensureAutoRefreshForProcessing(filesMap, stats = null) {
    if (Number(stats?.processing_count || 0) > 0) {
      enableAutoRefresh('auto')
      return true
    }

    const files = Array.isArray(filesMap) ? filesMap : Object.values(filesMap || {})
    const hasPending = files.some((file) => isProcessingFile(file))
    if (hasPending) {
      enableAutoRefresh('auto')
    } else if (autoRefreshSource === 'auto' && state.autoRefresh) {
      state.autoRefresh = false
      autoRefreshSource = null
      autoRefreshManualOverride = false
      stopAutoRefresh()
    }
    return hasPending
  }

  async function loadDocumentFiles(options = {}) {
    const kbIdValue = options.kbId || kbId.value
    if (!kbIdValue) return

    const nextStatus = options.status ?? fileBrowser.status
    const nextRecursive = options.recursive ?? nextStatus !== 'all'
    const nextParentId = nextRecursive ? null : (options.parentId ?? fileBrowser.parentId)
    const nextPathPrefix = nextRecursive ? '' : (options.pathPrefix ?? fileBrowser.pathPrefix)
    const nextPage = Number(options.page ?? fileBrowser.page) || 1
    const nextPageSize = Number(options.pageSize ?? fileBrowser.pageSize) || 100

    if (!options.isBackground) {
      fileBrowser.loading = true
    }

    try {
      const params = {
        page: nextPage,
        page_size: nextPageSize,
        status: nextStatus,
        recursive: nextRecursive
      }
      if (!nextRecursive && nextParentId) {
        params.parent_id = nextParentId
      }
      if (!nextRecursive && nextPathPrefix) {
        params.path_prefix = nextPathPrefix
      }

      const data = await documentApi.listDocuments(kbIdValue, params)
      const items = data?.items || []
      documentFiles.value = items
      setCurrentFileMap(items)
      Object.assign(fileBrowser, {
        parentId: nextParentId,
        page: data?.page || nextPage,
        pageSize: data?.page_size || nextPageSize,
        total: data?.total || 0,
        hasMore: Boolean(data?.has_more),
        pathPrefix: data?.path_prefix || nextPathPrefix,
        status: nextStatus,
        recursive: nextRecursive
      })

      if (data?.stats) {
        database.value = {
          ...database.value,
          stats: data.stats,
          row_count: data.stats.row_count
        }
      }
      ensureAutoRefreshForProcessing(items, data?.stats)
    } catch (error) {
      console.error(error)
      if (!options.isBackground) {
        message.error(error.message || 'Không thể tải danh sách tập tin')
      }
    } finally {
      if (!options.isBackground) {
        fileBrowser.loading = false
      }
    }
  }

  async function enterFolder(folder) {
    if (!folder?.is_folder) return
    const isVirtualFolder = Boolean(folder.is_virtual_folder)
    const currentParentId = fileBrowser.parentId
    folderBreadcrumbs.value = [
      ...folderBreadcrumbs.value,
      {
        file_id: folder.file_id,
        filename: folder.filename,
        is_virtual_folder: isVirtualFolder,
        parent_id: isVirtualFolder ? currentParentId : folder.file_id,
        path_prefix: isVirtualFolder ? folder.path_prefix || '' : ''
      }
    ]
    selectedRowKeys.value = []
    await loadDocumentFiles({
      parentId: isVirtualFolder ? currentParentId : folder.file_id,
      pathPrefix: isVirtualFolder ? folder.path_prefix || '' : '',
      page: 1,
      status: 'all',
      recursive: false
    })
  }

  async function goToFolder(index) {
    const nextBreadcrumbs = folderBreadcrumbs.value.slice(0, index + 1)
    const target = nextBreadcrumbs[nextBreadcrumbs.length - 1]
    folderBreadcrumbs.value = nextBreadcrumbs
    selectedRowKeys.value = []
    const isVirtualFolder = Boolean(target?.is_virtual_folder)
    await loadDocumentFiles({
      parentId: isVirtualFolder ? target?.parent_id || null : target?.file_id || null,
      pathPrefix: isVirtualFolder ? target?.path_prefix || '' : '',
      page: 1,
      status: 'all',
      recursive: false
    })
  }

  async function addFiles({ items, contentType, params, parentId }) {
    if (items.length === 0) {
      message.error(
        contentType === 'file'
          ? 'Vui lòng tải tập tin lên trước'
          : 'Vui lòng nhập một liên kết web hợp lệ'
      )
      return
    }

    state.chunkLoading = true
    try {
      const requestParams = { ...params, content_type: contentType }
      if (parentId) {
        requestParams.parent_id = parentId
      }
      const data = await documentApi.addDocuments(kbId.value, items, requestParams)
      if (data.status === 'success' || data.status === 'queued') {
        const itemType = contentType === 'file' ? 'tập tin' : 'URL'
        enableAutoRefresh('auto')
        message.success(
          data.message ||
            `${itemType}Đã gửi để xử lý，Vui lòng kiểm tra tiến độ trong trung tâm tác vụ`
        )
        if (data.task_id) {
          taskerStore.registerQueuedTask({
            task_id: data.task_id,
            name: `Nhập khẩu cơ sở kiến thức (${kbId.value || ''})`,
            task_type: 'knowledge_ingest',
            message: data.message,
            payload: {
              kb_id: kbId.value,
              count: items.length,
              content_type: contentType
            }
          })
        }
        await delayedRefresh() // sự chậm trễ1Làm mới sau vài giây
        return true // Indicate success
      } else {
        message.error(data.message || 'Xử lý không thành công')
        return false
      }
    } catch (error) {
      console.error(error)
      message.error(error.message || 'Yêu cầu xử lý không thành công')
      return false
    } finally {
      state.chunkLoading = false
    }
  }

  async function parseFiles(fileIds) {
    if (fileIds.length === 0) return
    state.chunkLoading = true
    try {
      const data = await documentApi.parseDocuments(kbId.value, fileIds)
      if (data.status === 'success' || data.status === 'queued') {
        enableAutoRefresh('auto')
        message.success(data.message || 'Nhiệm vụ phân tích cú pháp đã được gửi')
        if (data.task_id) {
          taskerStore.registerQueuedTask({
            task_id: data.task_id,
            name: `Phân tích tài liệu (${kbId.value})`,
            task_type: 'knowledge_parse',
            message: data.message,
            payload: { kb_id: kbId.value, count: fileIds.length }
          })
        }
        await delayedRefresh() // sự chậm trễ1Làm mới sau vài giây
        return true
      } else {
        message.error(data.message || 'Gửi không thành công')
        return false
      }
    } catch (error) {
      console.error(error)
      message.error(error.message || 'Yêu cầu không thành công')
      return false
    } finally {
      state.chunkLoading = false
    }
  }

  async function parsePendingFiles(count = 0) {
    state.chunkLoading = true
    try {
      const data = await documentApi.parsePendingDocuments(kbId.value)
      if (data.status === 'success' || data.status === 'queued') {
        enableAutoRefresh('auto')
        message.success(data.message || 'Nhiệm vụ phân tích cú pháp đã được gửi')
        if (data.task_id) {
          taskerStore.registerQueuedTask({
            task_id: data.task_id,
            name: `Phân tích tài liệu (${kbId.value})`,
            task_type: 'knowledge_parse',
            message: data.message,
            payload: { kb_id: kbId.value, count: data.queued_count || count, scope: 'pending' }
          })
        }
        await delayedRefresh()
        return true
      } else {
        message.error(data.message || 'Gửi không thành công')
        return false
      }
    } catch (error) {
      console.error(error)
      message.error(error.message || 'Yêu cầu không thành công')
      return false
    } finally {
      state.chunkLoading = false
    }
  }

  async function indexFiles(fileIds, params = {}) {
    if (fileIds.length === 0) return
    state.chunkLoading = true
    try {
      const data = await documentApi.indexDocuments(kbId.value, fileIds, params)
      if (data.status === 'success' || data.status === 'queued') {
        enableAutoRefresh('auto')
        message.success(data.message || 'Nhiệm vụ kho bãi đã được gửi')
        if (data.task_id) {
          taskerStore.registerQueuedTask({
            task_id: data.task_id,
            name: `Lưu trữ tài liệu (${kbId.value})`,
            task_type: 'knowledge_index',
            message: data.message,
            payload: { kb_id: kbId.value, count: fileIds.length }
          })
        }
        await delayedRefresh() // sự chậm trễ1Làm mới sau vài giây
        return true
      } else {
        message.error(data.message || 'Gửi không thành công')
        return false
      }
    } catch (error) {
      console.error(error)
      message.error(error.message || 'Yêu cầu không thành công')
      return false
    } finally {
      state.chunkLoading = false
    }
  }

  async function indexPendingFiles(params = {}, count = 0) {
    state.chunkLoading = true
    try {
      const data = await documentApi.indexPendingDocuments(kbId.value, params)
      if (data.status === 'success' || data.status === 'queued') {
        enableAutoRefresh('auto')
        message.success(data.message || 'Nhiệm vụ kho bãi đã được gửi')
        if (data.task_id) {
          taskerStore.registerQueuedTask({
            task_id: data.task_id,
            name: `Lưu trữ tài liệu (${kbId.value})`,
            task_type: 'knowledge_index',
            message: data.message,
            payload: { kb_id: kbId.value, count: data.queued_count || count, scope: 'pending' }
          })
        }
        await delayedRefresh()
        return true
      } else {
        message.error(data.message || 'Gửi không thành công')
        return false
      }
    } catch (error) {
      console.error(error)
      message.error(error.message || 'Yêu cầu không thành công')
      return false
    } finally {
      state.chunkLoading = false
    }
  }

  function openFileDetail(fileId) {
    const nextFileId = typeof fileId === 'object' ? fileId?.file_id : fileId
    if (!nextFileId) {
      message.error('Thông tin tập tin không đầy đủ')
      return
    }
    fileDetailFileId.value = nextFileId
    state.fileDetailModalVisible = true
  }

  function closeFileDetail() {
    state.fileDetailModalVisible = false
    fileDetailFileId.value = null
  }

  async function loadQueryParams(id) {
    const kbIdValue = id || kbId.value
    if (!kbIdValue) return

    state.queryParamsLoading = true
    try {
      const response = await queryApi.getKnowledgeBaseQueryParams(kbIdValue)
      queryParams.value = response.params?.options || []

      // Create a set of currently supported parameter keys
      const supportedParamKeys = new Set(queryParams.value.map((param) => param.key))

      // Remove unsupported parameters from meta
      for (const key in meta) {
        if (key !== 'kb_id' && !supportedParamKeys.has(key)) {
          delete meta[key]
        }
      }

      // Add default values for supported parameters that are not in meta
      queryParams.value.forEach((param) => {
        if (!(param.key in meta)) {
          meta[param.key] = param.default
        }
      })
    } catch (error) {
      console.error('Failed to load query params:', error)
      message.error('Không tải được tham số truy vấn')
    } finally {
      state.queryParamsLoading = false
    }
  }

  function startAutoRefresh() {
    if (state.autoRefresh && !refreshInterval) {
      refreshInterval = setInterval(() => {
        getDatabaseInfo(undefined, true, true) // Skip loading query params during auto-refresh
        loadDocumentFiles({ isBackground: true })
      }, 1000)
    }
  }

  function stopAutoRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  }

  // Hiểu tập tin làm mới bị trì hoãn（sự chậm trễ1Làm mới sau vài giây）
  async function delayedRefresh() {
    await new Promise((resolve) => setTimeout(resolve, 1000))
    await getDatabaseInfo(undefined, true)
    await loadDocumentFiles({ isBackground: true })
  }

  function toggleAutoRefresh() {
    const nextState = !state.autoRefresh
    state.autoRefresh = nextState
    if (nextState) {
      autoRefreshSource = 'manual'
      autoRefreshManualOverride = false
      startAutoRefresh()
    } else {
      autoRefreshManualOverride = true
      autoRefreshSource = null
      stopAutoRefresh()
    }
  }

  function selectAllFailedFiles() {
    const files = Object.values(database.value.files || {})
    const failedFiles = files.filter((file) => file.status === 'failed').map((file) => file.file_id)

    const newSelectedKeys = [...new Set([...selectedRowKeys.value, ...failedFiles])]
    selectedRowKeys.value = newSelectedKeys

    if (failedFiles.length > 0) {
      message.success(`Đã chọn ${failedFiles.length} tập tin bị lỗi`)
    } else {
      message.info('Hiện tại không có tập tin bị lỗi')
    }
  }

  function getDatabaseNameById(id) {
    const normalizedId = String(id || '').trim()
    if (!normalizedId) return ''

    const matchedDatabase = databases.value.find(
      (item) => String(item.kb_id || '').trim() === normalizedId
    )
    if (matchedDatabase?.name) return matchedDatabase.name

    if (String(database.value?.kb_id || '').trim() === normalizedId) {
      return database.value?.name || ''
    }

    return ''
  }

  return {
    databases,
    database,
    kbId,
    fileDetailFileId,
    documentFiles,
    folderBreadcrumbs,
    queryParams,
    meta,
    selectedRowKeys,
    fileBrowser,
    state,
    loadDatabases,
    createDatabase,
    getDatabaseInfo,
    updateDatabaseInfo,
    deleteDatabase,
    deleteFile,
    handleDeleteFile,
    handleBatchDelete,
    addFiles,
    parseFiles,
    parsePendingFiles,
    indexFiles,
    indexPendingFiles,
    openFileDetail,
    closeFileDetail,
    loadQueryParams,
    loadDocumentFiles,
    enterFolder,
    goToFolder,
    resetFileBrowser,

    startAutoRefresh,
    stopAutoRefresh,
    toggleAutoRefresh,
    selectAllFailedFiles,
    getDatabaseNameById
  }
})
