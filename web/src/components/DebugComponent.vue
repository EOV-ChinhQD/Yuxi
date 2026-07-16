<template>
  <a-modal
    v-model:open="showModal"
    title="Bảng gỡ lỗi（Vui lòng sử dụng thận trọng trong môi trường sản xuất）"
    width="90%"
    :footer="null"
    :maskClosable="true"
    :destroyOnClose="true"
    class="debug-modal"
  >
    <div :class="['log-viewer', { fullscreen: state.isFullscreen }]" ref="logViewer">
      <div class="control-panel">
        <div class="button-group">
          <a-button
            @click="fetchLogs"
            :loading="state.fetching"
            :icon="h(ReloadOutlined)"
            class="icon-only"
          >
          </a-button>
          <a-button @click="clearLogs" :icon="h(ClearOutlined)" class="icon-only"> </a-button>
          <a-button @click="printSystemConfig">
            <template #icon><SettingOutlined /></template>
            Cấu hình hệ thống
          </a-button>
          <a-button @click="printUserInfo">
            <template #icon><UserOutlined /></template>
            Thông tin người dùng
          </a-button>
          <a-button @click="printDatabaseInfo">
            <template #icon><DatabaseOutlined /></template>
            Thông tin cơ sở kiến thức
          </a-button>
          <a-button @click="printAgentConfig">
            <template #icon><RobotOutlined /></template>
            Cấu hình đại lý
          </a-button>
          <a-button @click="toggleDebugMode" :type="infoStore.debugMode ? 'primary' : 'default'">
            <template #icon><BugOutlined /></template>
            Debug chế độ: {{ infoStore.debugMode ? 'bật lên' : 'đóng' }}
          </a-button>
          <a-button @click="toggleFullscreen">
            <template #icon>
              <FullscreenOutlined v-if="!state.isFullscreen" />
              <FullscreenExitOutlined v-else />
            </template>
            {{ state.isFullscreen ? 'Thoát toàn màn hình' : 'toàn màn hình' }}
          </a-button>
          <a-tooltip
            :title="
              state.autoRefresh
                ? 'Nhấp để dừng làm mới tự động'
                : 'Nhấp để bật tính năng làm mới tự động'
            "
          >
            <a-button
              :type="state.autoRefresh ? 'primary' : 'default'"
              :class="{ 'auto-refresh-button': state.autoRefresh }"
              @click="toggleAutoRefresh(!state.autoRefresh)"
            >
              <template #icon>
                <SyncOutlined :spin="state.autoRefresh" />
              </template>
              Tự động làm mới
              <span v-if="state.autoRefresh" class="refresh-interval">(5s)</span>
            </a-button>
          </a-tooltip>
          <a-button @click="openUserSwitcher">
            <template #icon><SwapOutlined /></template>
            Chuyển đổi người dùng
          </a-button>
        </div>
        <div class="filter-group">
          <a-input-search
            v-model:value="state.searchText"
            placeholder="Nhật ký tìm kiếm..."
            style="width: 200px; height: 32px"
            @search="onSearch"
          />
          <div class="log-level-selector">
            <div class="multi-select-cards">
              <div
                v-for="level in logLevels"
                :key="level.value"
                class="option-card"
                :class="{
                  selected: isLogLevelSelected(level.value),
                  unselected: !isLogLevelSelected(level.value)
                }"
                @click="toggleLogLevel(level.value)"
              >
                <div class="option-content">
                  <span class="option-text">{{ level.label }}</span>
                  <div class="option-indicator">
                    <CheckCircleOutlined v-if="isLogLevelSelected(level.value)" />
                    <PlusCircleOutlined v-else />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div ref="logContainer" class="log-container">
        <div v-if="processedLogs.length" class="log-lines">
          <div
            v-for="(log, index) in processedLogs"
            :key="index"
            :class="['log-line', `level-${log.level.toLowerCase()}`]"
          >
            <span class="timestamp">{{ formatTimestamp(log.timestamp) }}</span>
            <span class="level">{{ log.level }}</span>
            <span class="module">{{ log.module }}</span>
            <span class="message">{{ log.message }}</span>
          </div>
        </div>
        <div v-else class="empty-logs">Chưa có nhật ký nào</div>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <!-- Chuyển đổi người dùng Modal -->
      <a-modal
        v-model:open="state.showUserSwitcher"
        title="Chuyển đổi người dùng"
        :confirmLoading="state.switchingUser"
        :footer="null"
        :bodyStyle="{ padding: '12px' }"
      >
        <a-list item-layout="horizontal" :data-source="state.users">
          <template #renderItem="{ item }">
            <a-list-item @click="switchToUser(item)" style="cursor: pointer">
              <a-list-item-meta :title="item.username" :description="item.role" />
            </a-list-item>
          </template>
          <template #empty>
            <a-empty description="Chưa có người dùng nào" />
          </template>
        </a-list>
      </a-modal>
    </div>
  </a-modal>
</template>

<script setup>
import {
  ref,
  reactive,
  computed,
  onMounted,
  onActivated,
  onUnmounted,
  nextTick,
  toRaw,
  h,
  watch
} from 'vue'

const showModal = defineModel('show')

// màn hình showModal thay đổi，Nhận nhật ký khi mở
watch(showModal, (isOpen) => {
  if (isOpen) {
    // Trì hoãn để đảm bảo DOM Kết xuất hoàn tất
    setTimeout(fetchLogs, 100)
  }
})

import { useConfigStore } from '@/stores/config'
import { useUserStore } from '@/stores/user'
import { useDatabaseStore } from '@/stores/database'
import { isBuiltinAgent, useAgentStore } from '@/stores/agent'
import { useInfoStore } from '@/stores/info'
import { useThrottleFn } from '@vueuse/core'
import {
  message,
  Modal,
  List as AList,
  ListItem as AListItem,
  ListItemMeta as AListItemMeta,
  Empty as AEmpty
} from 'ant-design-vue'
import {
  FullscreenOutlined,
  FullscreenExitOutlined,
  ReloadOutlined,
  ClearOutlined,
  SettingOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  PlusCircleOutlined,
  UserOutlined,
  DatabaseOutlined,
  RobotOutlined,
  BugOutlined,
  SwapOutlined
} from '@ant-design/icons-vue'
import dayjs from '@/utils/time'
import { configApi } from '@/apis/system_api'
import { checkSuperAdminPermission } from '@/stores/user'

const configStore = useConfigStore()
const userStore = useUserStore()
const databaseStore = useDatabaseStore()
const agentStore = useAgentStore()
const infoStore = useInfoStore()
const config = configStore.config

// Xác định cấp độ nhật ký
const logLevels = [
  { value: 'INFO', label: 'INFO' },
  { value: 'ERROR', label: 'ERROR' },
  { value: 'DEBUG', label: 'DEBUG' },
  { value: 'WARNING', label: 'WARNING' }
]

const logViewer = ref(null)

// Quản lý trạng thái
const state = reactive({
  fetching: false,
  autoRefresh: false,
  searchText: '',
  selectedLevels: logLevels.map((l) => l.value),
  rawLogs: [],
  isFullscreen: false,
  showUserSwitcher: false,
  users: [],
  switchingUser: false
})

const error = ref('')
const logContainer = ref(null)
let autoRefreshInterval = null

// Phân tích dòng nhật ký
const parseLogLine = (line) => {
  // Hỗ trợ hai định dạng dấu thời gian：Có và không có mili giây
  const match = line.match(
    /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?)\s*-\s*(\w+)\s*-\s*([^-]+?)\s*-\s*(.+)$/
  )
  if (match) {
    return {
      timestamp: match[1],
      level: match[2],
      module: match[3].trim(),
      message: match[4].trim(),
      raw: line
    }
  }
  return null
}

// Định dạng dấu thời gian
const formatTimestamp = (timestamp) => {
  try {
    // Xử lý định dạng bằng mili giây：sẽ "2025-03-10 08:26:37,269" Chuyển đổi thành "2025-03-10 08:26:37.269"
    let normalizedTimestamp = timestamp.replace(',', '.')

    // nếu không có mili giây，thêm .000
    if (!/\.\d{3}$/.test(normalizedTimestamp)) {
      normalizedTimestamp += '.000'
    }

    const date = dayjs(normalizedTimestamp)
    return date.isValid() ? date.format('HH:mm:ss.SSS') : timestamp
  } catch (err) {
    console.error('Lỗi định dạng dấu thời gian:', err)
    return timestamp
  }
}

// Hiển thị nhật ký xử lý
const processedLogs = computed(() => {
  return state.rawLogs
    .map(parseLogLine)
    .filter((log) => log !== null)
    .filter((log) => {
      if (!state.searchText) return true
      return log.raw.toLowerCase().includes(state.searchText.toLowerCase())
    })
})

// Nhận dữ liệu nhật ký
const fetchLogs = async () => {
  if (!checkSuperAdminPermission()) return

  state.fetching = true
  try {
    error.value = ''
    // Chuyển đổi các cấp độ nhật ký đã chọn thành chuỗi được phân tách bằng dấu phẩy và chuyển nó vào phần phụ trợ
    const levelsParam = state.selectedLevels.join(',')
    const logData = await configApi.getLogs(levelsParam)
    state.rawLogs = logData.log.split('\n').filter((line) => line.trim())

    await nextTick()
    const scrollToBottom = useThrottleFn(() => {
      if (logContainer.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight
      }
    }, 100)
    scrollToBottom()
  } catch (err) {
    error.value = `Lỗi: ${err.message}`
  } finally {
    state.fetching = false
  }
}

// Xóa nhật ký
const clearLogs = () => {
  if (!checkSuperAdminPermission()) return
  state.rawLogs = []
}

// Chức năng tìm kiếm
const onSearch = () => {
  // Việc tìm kiếm sẽ vượt quacomputedKích hoạt tự động
}

// Các phương pháp liên quan đến lựa chọn cấp độ nhật ký
const isLogLevelSelected = (level) => {
  return state.selectedLevels.includes(level)
}

const toggleLogLevel = (level) => {
  const currentLevels = [...state.selectedLevels]
  const index = currentLevels.indexOf(level)

  if (index > -1) {
    // Nếu không có cấp độ nào được chọn sau khi bỏ chọn，Chọn tất cả theo mặc định
    if (currentLevels.length === 1) {
      return
    }
    currentLevels.splice(index, 1)
  } else {
    currentLevels.push(level)
  }

  state.selectedLevels = currentLevels
  // Lấy lại dữ liệu sau khi chuyển đổi cấp độ nhật ký
  fetchLogs()
}

// Tự động làm mới
const toggleAutoRefresh = (value) => {
  if (!checkSuperAdminPermission()) return

  if (value) {
    autoRefreshInterval = setInterval(fetchLogs, 5000)
    state.autoRefresh = true
  } else {
    if (autoRefreshInterval) {
      clearInterval(autoRefreshInterval)
      autoRefreshInterval = null
    }
    state.autoRefresh = false
  }
}

// Chuyển đổi toàn màn hình
const toggleFullscreen = async () => {
  if (!checkSuperAdminPermission()) return

  try {
    if (!state.isFullscreen) {
      if (logViewer.value.requestFullscreen) {
        await logViewer.value.requestFullscreen()
      } else if (logViewer.value.webkitRequestFullscreen) {
        await logViewer.value.webkitRequestFullscreen()
      } else if (logViewer.value.msRequestFullscreen) {
        await logViewer.value.msRequestFullscreen()
      }
    } else {
      if (document.exitFullscreen) {
        await document.exitFullscreen()
      } else if (document.webkitExitFullscreen) {
        await document.webkitExitFullscreen()
      } else if (document.msExitFullscreen) {
        await document.msExitFullscreen()
      }
    }
  } catch (err) {
    console.error('Chuyển đổi toàn màn hình không thành công:', err)
  }
}

// Theo dõi các thay đổi toàn màn hình
const handleFullscreenChange = () => {
  state.isFullscreen = Boolean(
    document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement
  )
}

onMounted(() => {
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  document.addEventListener('webkitfullscreenchange', handleFullscreenChange)
  document.addEventListener('msfullscreenchange', handleFullscreenChange)
})

onActivated(() => {
  if (state.autoRefresh) {
    toggleAutoRefresh(true)
  } else if (showModal.value) {
    fetchLogs()
  }
})

onUnmounted(() => {
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval)
    autoRefreshInterval = null
  }
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  document.removeEventListener('webkitfullscreenchange', handleFullscreenChange)
  document.removeEventListener('msfullscreenchange', handleFullscreenChange)
})

// Cấu hình hệ thống in
const printSystemConfig = () => {
  if (!checkSuperAdminPermission()) return
  console.log('=== Cấu hình hệ thống ===')
  console.log(config)
}

// In thông tin người dùng
const printUserInfo = () => {
  if (!checkSuperAdminPermission()) return
  console.log('=== Thông tin người dùng ===')
  const userInfo = {
    token: userStore.token ? '*** (Ẩn)' : null,
    userId: userStore.userId,
    username: userStore.username,
    uid: userStore.uid,
    phoneNumber: userStore.phoneNumber,
    avatar: userStore.avatar,
    userRole: userStore.userRole,
    isLoggedIn: userStore.isLoggedIn,
    isAdmin: userStore.isAdmin,
    isSuperAdmin: userStore.isSuperAdmin
  }
  console.log(JSON.stringify(userInfo, null, 2))
}

// In thông tin cơ sở kiến thức
const printDatabaseInfo = async () => {
  if (!checkSuperAdminPermission()) return

  try {
    console.log('=== Thông tin cơ sở kiến thức ===')
    console.log('Thông tin cơ bản:', {
      kbId: databaseStore.kbId,
      databaseName: databaseStore.database.name,
      databaseDesc: databaseStore.database.description,
      fileCount: Object.keys(databaseStore.database.files || {}).length
    })

    console.log('thông tin trạng thái:', {
      databaseLoading: databaseStore.state.databaseLoading,
      searchLoading: databaseStore.state.searchLoading,
      lock: databaseStore.state.lock,
      autoRefresh: databaseStore.state.autoRefresh,
      queryParamsLoading: databaseStore.state.queryParamsLoading
    })

    console.log('tham số truy vấn:', {
      queryParams: databaseStore.queryParams,
      meta: databaseStore.meta,
      selectedFileCount: databaseStore.selectedRowKeys.length
    })
  } catch (error) {
    console.error('Không thể lấy được thông tin cơ sở kiến thức:', error)
    message.error('Không thể lấy được thông tin cơ sở kiến thức: ' + error.message)
  }
}

// chuyển đổiDebugchế độ
const toggleDebugMode = () => {
  if (!checkSuperAdminPermission()) return
  infoStore.toggleDebugMode()
}

// Cấu hình tác nhân in
const printAgentConfig = async () => {
  if (!checkSuperAdminPermission()) return

  try {
    console.log('=== Thông tin cấu hình đại lý ===')

    // Storethông tin trạng thái
    console.log('Store Trạng thái:', {
      isInitialized: agentStore.isInitialized,
      selectedAgentId: agentStore.selectedAgentId,
      agentCount: agentStore.agentsList.length,
      loadingStates: {
        isLoadingAgents: agentStore.isLoadingAgents,
        isLoadingConfig: agentStore.isLoadingConfig,
        isLoadingTools: agentStore.isLoadingTools
      },
      error: agentStore.error,
      hasConfigChanges: agentStore.hasConfigChanges
    })

    // Thông tin danh sách đại lý
    console.log('Danh sách đại lý:', {
      count: agentStore.agentsList.length,
      agents: toRaw(agentStore.agentsList)
    })

    // Thông tin đại lý hiện đang được chọn
    if (agentStore.selectedAgent) {
      console.log('Đại lý hiện được chọn:', {
        agent: toRaw(agentStore.selectedAgent),
        isBuiltin: isBuiltinAgent(agentStore.selectedAgent),
        configurableItemsCount: Object.keys(agentStore.configurableItems).length
      })

      // Cấu hình đại lý hiện tại（Chỉ hiển thị với quản trị viên）
      if (userStore.isAdmin) {
        console.log('Cấu hình đại lý hiện tại:', {
          current: toRaw(agentStore.agentConfig),
          original: toRaw(agentStore.originalAgentConfig),
          hasChanges: agentStore.hasConfigChanges
        })
      } else {
        console.log('Cấu hình đại lý: Cần có quyền quản trị viên để xem cấu hình chi tiết')
      }
    }

    // Thông tin công cụ
    const toolsList = agentStore.availableTools ? Object.values(agentStore.availableTools) : []
    console.log('Công cụ có sẵn:', {
      count: toolsList.length,
      tools: toolsList
    })

    // Thông tin mục cấu hình（Hiển thị với quản trị viên）
    if (userStore.isAdmin && agentStore.selectedAgent) {
      console.log('Các mục có thể cấu hình:', toRaw(agentStore.configurableItems))
    }
  } catch (error) {
    console.error('Không lấy được cấu hình tác nhân:', error)
    message.error('Không lấy được cấu hình tác nhân: ' + error.message)
  }
}

// Lấy danh sách người dùng
const fetchUsers = async () => {
  try {
    const response = await fetch('/api/auth/users', {
      headers: userStore.getAuthHeaders()
    })
    if (!response.ok) {
      throw new Error('Không lấy được danh sách người dùng')
    }
    state.users = await response.json()
  } catch (err) {
    message.error(`Không lấy được danh sách người dùng: ${err.message}`)
  }
}

// Mở bộ chọn người dùng
const openUserSwitcher = () => {
  if (!checkSuperAdminPermission()) return
  state.showUserSwitcher = true
  fetchUsers()
}

// Chuyển đổi người dùng
const switchToUser = async (user) => {
  if (!checkSuperAdminPermission()) return

  // Xác nhận các hoạt động nguy hiểm
  Modal.confirm({
    title: '⚠️ Xác nhận các hoạt động nguy hiểm',
    content: `Xác nhận bạn muốn chuyển sang người dùng "${user.username}" ?？Thao tác này sẽ được ghi lại。`,
    okText: 'Xác nhận chuyển đổi',
    cancelText: 'Hủy bỏ',
    okType: 'danger',
    onOk: async () => {
      state.switchingUser = true
      try {
        const response = await fetch(`/api/auth/impersonate/${user.id}`, {
          method: 'POST',
          headers: userStore.getAuthHeaders()
        })
        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.detail || 'Không thể chuyển đổi người dùng')
        }
        const data = await response.json()
        // thiết lập mới token
        localStorage.setItem('user_token', data.access_token)
        message.success(`Người dùng đã chuyển đổi: ${user.username}`)
        state.showUserSwitcher = false
        // Làm mới trang để khởi động lại ứng dụng
        window.location.reload()
      } catch (err) {
        message.error(`Chuyển đổi không thành công: ${err.message}`)
      } finally {
        state.switchingUser = false
      }
    }
  })
}
</script>

<style scoped>
.log-viewer.fullscreen {
  padding: 16px;
}

.control-panel {
  margin-bottom: 16px;
}

.button-group {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;

  .ant-btn {
    min-width: 80px;
    height: 32px;
    padding: 4px 12px;
    font-size: 13px;
    border-color: var(--gray-300);
    color: var(--gray-700);

    &.icon-only {
      min-width: 32px;
      padding: 0;
    }

    &:hover {
      border-color: var(--main-color);
      color: var(--main-color);
    }

    &.ant-btn-primary {
      background-color: var(--main-color);
      border-color: var(--main-color);
      color: var(--gray-0);

      &:hover,
      &:focus {
        background-color: var(--main-color);
        border-color: var(--main-color);
        color: var(--gray-0);
      }
    }

    .anticon {
      font-size: 14px;
    }
  }

  .refresh-interval {
    font-size: 12px;
    opacity: 0.8;
    margin-left: 2px;
  }

  .auto-refresh-button {
    color: var(--gray-0);
  }
}

.filter-group {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  flex-wrap: wrap;
  height: 32px;

  @media (max-width: 768px) {
    flex-direction: column;
    gap: 12px;
  }
}

.error {
  color: var(--color-error-500);
}

.log-container {
  height: calc(80vh - 200px);
  overflow-y: auto;
  background: #1e1f1f;
  color: #ffffff;
  border-radius: 5px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}

.log-lines {
  padding: 8px;
}

.log-line {
  padding: 2px 4px;
  display: flex;
  gap: 8px;
  line-height: 1.4;
}

.log-line:hover {
  background: rgba(255, 255, 255, 0.05);
}

.timestamp {
  color: var(--color-success-500);
  min-width: 80px;
}

.level {
  min-width: 40px;
  font-weight: bold;
}

.module {
  color: var(--color-info-500);
  min-width: 30px;
}

.message {
  flex: 1;
  white-space: pre-wrap;
  word-break: break-all;
}

.level-info {
  .level {
    color: var(--color-success-500);
  }
}

.level-error {
  .level {
    color: var(--color-error-500);
  }
}

.level-debug {
  .level {
    color: var(--color-info-500);
  }
}

.level-warning {
  .level {
    color: var(--color-warning-500);
  }
}

.empty-logs {
  padding: 16px;
  text-align: center;
  color: var(--gray-500);
}

:fullscreen .log-container {
  height: calc(100vh - 160px);
}

:-webkit-full-screen .log-container {
  height: calc(100vh - 160px);
}

:-ms-fullscreen .log-container {
  height: calc(100vh - 160px);
}

.multi-select-cards {
  display: flex;
  flex-direction: row;
  gap: 10px;

  .option-card {
    border: 1px solid var(--gray-300);
    border-radius: 6px;
    padding: 0px 10px;
    cursor: pointer;
    transition: all 0.2s ease;
    background: var(--gray-0);
    user-select: none;
    height: 32px;
    display: flex;
    align-items: center;

    &:hover {
      border-color: var(--main-color);
      background: var(--main-5);
    }

    &.selected {
      border-color: var(--main-color);
      background: var(--main-10);

      .option-indicator {
        color: var(--main-color);
      }

      .option-text {
        color: var(--main-color);
        font-weight: 500;
      }
    }

    &.unselected {
      .option-indicator {
        color: var(--gray-400);
      }

      .option-text {
        color: var(--gray-700);
      }
    }

    .option-content {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 6px;
      width: 100%;
    }

    .option-text {
      flex: 1;
      font-size: 12px;
      text-align: center;
    }

    .option-indicator {
      flex-shrink: 0;
      font-size: 14px;
      transition: color 0.2s ease;
    }
  }
}

/* Thích ứng đáp ứng */
@media (max-width: 768px) {
  .log-level-selector {
    min-width: 280px;
  }

  .multi-select-cards .options-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
