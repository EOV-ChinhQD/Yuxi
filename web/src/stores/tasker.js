import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import { taskerApi } from '@/apis/tasker'
import { useUserStore } from '@/stores/user'
import { parseToShanghai } from '@/utils/time'

const ACTIVE_STATUSES = new Set(['pending', 'running', 'queued'])
const FAILED_STATUSES = new Set(['failed', 'cancelled'])

const createDefaultSummary = () => ({
  total: 0,
  filtered_total: 0,
  status_counts: {},
  type_counts: {}
})

const toTask = (raw = {}) => ({
  id: raw.id,
  name: raw.name || 'Tác vụ nền',
  type: raw.type || 'general',
  status: raw.status || 'pending',
  progress: raw.progress ?? 0,
  message: raw.message || '',
  created_at: raw.created_at,
  updated_at: raw.updated_at,
  started_at: raw.started_at,
  completed_at: raw.completed_at,
  payload: raw.payload || {},
  result: raw.result,
  error: raw.error,
  cancel_requested: raw.cancel_requested || false
})

export const useTaskerStore = defineStore('tasker', () => {
  const userStore = useUserStore()
  const tasks = ref([])
  const loading = ref(false)
  const lastError = ref(null)
  const isDrawerOpen = ref(false)
  const summary = ref(createDefaultSummary())
  let pollingTimer = null

  const sortedTasks = computed(() => {
    return [...tasks.value].sort((a, b) => {
      const timeA = parseToShanghai(a.created_at)
      const timeB = parseToShanghai(b.created_at)
      if (!timeA && !timeB) return 0
      if (!timeA) return 1
      if (!timeB) return -1
      return timeB.valueOf() - timeA.valueOf()
    })
  })

  const statusCounts = computed(() => summary.value?.status_counts || {})

  const activeCount = computed(() =>
    Array.from(ACTIVE_STATUSES).reduce(
      (count, status) => count + (statusCounts.value?.[status] || 0),
      0
    )
  )
  const failedCount = computed(() =>
    Array.from(FAILED_STATUSES).reduce(
      (count, status) => count + (statusCounts.value?.[status] || 0),
      0
    )
  )
  const successCount = computed(() => statusCounts.value?.success || 0)
  const totalCount = computed(() => summary.value?.total || 0)

  // Có nhiệm vụ nào yêu cầu bỏ phiếu liên tục không?：summary Nhiệm vụ tích cực để thống kê hoặc đăng ký lạc quan cục bộ
  const hasActiveTasks = computed(
    () => activeCount.value > 0 || tasks.value.some((task) => ACTIVE_STATUSES.has(task.status))
  )

  function upsertTask(rawTask) {
    if (!rawTask || !rawTask.id) return
    const task = toTask(rawTask)
    const index = tasks.value.findIndex((item) => item.id === task.id)
    if (index >= 0) {
      tasks.value.splice(index, 1, { ...tasks.value[index], ...task })
    } else {
      tasks.value.unshift(task)
    }
  }

  async function loadTasks(params = {}) {
    if (!userStore.isAdmin) {
      tasks.value = []
      summary.value = createDefaultSummary()
      lastError.value = null
      syncPolling()
      return
    }

    loading.value = true
    lastError.value = null
    try {
      const response = await taskerApi.fetchTasks(params)
      const taskList = response?.tasks || []
      summary.value = {
        ...createDefaultSummary(),
        ...(response?.summary || {})
      }
      tasks.value = taskList.map(toTask)
    } catch (error) {
      console.error('Không tải được danh sách nhiệm vụ', error)
      lastError.value = error
      summary.value = createDefaultSummary()
    } finally {
      loading.value = false
      syncPolling()
    }
  }

  async function refreshTask(taskId) {
    if (!taskId) return
    try {
      const response = await taskerApi.fetchTaskDetail(taskId)
      if (response?.task) {
        upsertTask(response.task)
      }
    } catch (error) {
      console.error(`nhiệm vụ làm mới ${taskId} Chi tiết không thành công`, error)
      lastError.value = error
    }
  }

  async function cancelTask(taskId) {
    if (!taskId) return
    try {
      await taskerApi.cancelTask(taskId)
      message.success('Đã hủy tác vụ thành công')
      await refreshTask(taskId)
    } catch (error) {
      console.error(`Hủy tác vụ ${taskId} thất bại`, error)
      message.error(error?.message || 'Không hủy được nhiệm vụ')
    }
  }

  async function deleteTask(taskId) {
    if (!taskId) return
    try {
      await taskerApi.deleteTask(taskId)
      message.success('Đã xóa tác vụ thành công')
      // Xóa khỏi danh sách cục bộ
      const index = tasks.value.findIndex((item) => item.id === taskId)
      if (index >= 0) {
        tasks.value.splice(index, 1)
      }
    } catch (error) {
      console.error(`Xóa tác vụ ${taskId} thất bại`, error)
      message.error(error?.message || 'Xóa tác vụ không thành công')
    }
  }

  function registerQueuedTask({ task_id, name, task_type, message: msg, payload } = {}) {
    if (!task_id) return
    const now = new Date().toISOString()
    upsertTask({
      id: task_id,
      name: name || 'Tác vụ nền',
      type: task_type || 'manual',
      status: 'queued',
      progress: 0,
      message: msg || 'Nhiệm vụ được xếp hàng đợi',
      created_at: now,
      updated_at: now,
      payload: payload || {}
    })
    syncPolling()
  }

  function openDrawer() {
    isDrawerOpen.value = true
    syncPolling()
  }

  function closeDrawer() {
    isDrawerOpen.value = false
    syncPolling()
  }

  function startPolling(interval = 5000) {
    if (pollingTimer) return
    pollingTimer = setInterval(() => {
      loadTasks()
    }, interval)
  }

  function stopPolling() {
    if (pollingTimer) {
      clearInterval(pollingTimer)
      pollingTimer = null
    }
  }

  // Quyền sở hữu cuộc thăm dò hội tụ đến store：Thăm dò liên tục khi ngăn kéo mở hoặc có tác vụ đang hoạt động，Nếu không thì dừng lại，
  // Đã sửa biểu tượng tác vụ sau khi đóng ngăn kéo（activeCount）Vấn đề không còn được cập nhật。
  function syncPolling() {
    if (userStore.isAdmin && (isDrawerOpen.value || hasActiveTasks.value)) {
      startPolling()
    } else {
      stopPolling()
    }
  }

  function reset() {
    stopPolling()
    tasks.value = []
    lastError.value = null
    isDrawerOpen.value = false
    summary.value = createDefaultSummary()
  }

  return {
    isDrawerOpen,
    tasks,
    sortedTasks,
    totalCount,
    successCount,
    failedCount,
    loading,
    lastError,
    activeCount,
    loadTasks,
    refreshTask,
    cancelTask,
    deleteTask,
    registerQueuedTask,
    reset,
    openDrawer,
    closeDrawer
  }
})
