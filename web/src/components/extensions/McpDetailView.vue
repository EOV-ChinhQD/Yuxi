<template>
  <div class="mcp-detail extension-detail-page">
    <div v-if="loading" class="loading-bar-wrapper">
      <div class="loading-bar"></div>
    </div>
    <div class="detail-top-bar">
      <button class="detail-back-btn" @click="goBack">
        <ArrowLeft :size="16" />
        <span>Trở lại</span>
      </button>
      <div class="detail-title-area">
        <span class="detail-icon">{{ server?.icon || '🔌' }}</span>
        <div class="detail-title-text">
          <h2>{{ server?.name || name }}</h2>
          <span class="detail-subtitle">{{ server?.transport || '' }}</span>
        </div>
      </div>
      <div class="detail-actions">
        <a-space :size="8">
          <button
            type="button"
            @click="handleTestServer"
            :disabled="testLoading"
            class="lucide-icon-btn extension-panel-action extension-panel-action-secondary"
          >
            <Zap :size="14" v-if="!testLoading" />
            <span>kiểm tra</span>
          </button>
          <button
            type="button"
            @click="startEdit"
            :disabled="isEditing || !server"
            class="lucide-icon-btn extension-panel-action extension-panel-action-secondary"
          >
            <Pencil :size="14" />
            <span>Chỉnh sửa</span>
          </button>
          <button
            type="button"
            @click="handleDangerAction"
            :class="[
              'lucide-icon-btn',
              'extension-panel-action',
              server?.enabled === false
                ? 'extension-panel-action-primary'
                : 'extension-panel-action-danger'
            ]"
          >
            <Plus v-if="server?.enabled === false" :size="14" />
            <Trash2 v-else :size="14" />
            <span>{{ actionLabel }}</span>
          </button>
        </a-space>
      </div>
    </div>

    <div class="detail-content-wrapper">
      <a-spin :spinning="loading">
        <div v-if="server" class="detail-content-inner">
          <a-tabs v-model:activeKey="detailTab" class="detail-tabs">
            <a-tab-pane key="general">
              <template #tab>
                <span class="tab-title"><Settings2 :size="14" />thông tin</span>
              </template>
              <div class="tab-content">
                <div v-if="isEditing" class="edit-panel">
                  <div class="edit-panel-header">
                    <div>
                      <h3>Chỉnh sửa MCP</h3>
                      <p>Sau khi sửa đổi, lưu sẽ ngay lập tức cập nhật hiện tại MCP Cấu hình。</p>
                    </div>
                  </div>

                  <a-form layout="vertical" class="extension-form inline-edit-form">
                    <section class="form-section">
                      <div class="form-section-title">
                        <span>Thông tin cơ bản</span>
                        <small>độ nét MCP tên、Mô tả và trình bày。</small>
                      </div>
                      <div class="form-grid form-grid-three">
                        <a-form-item label="MCP biểu tượng" required class="form-item">
                          <a-input v-model:value="editForm.slug" disabled />
                        </a-form-item>
                        <a-form-item label="MCP Tên" required class="form-item">
                          <a-input
                            v-model:value="editForm.name"
                            placeholder="Vui lòng nhập MCP tên hiển thị"
                          />
                        </a-form-item>
                        <a-form-item label="Kiểu truyền động" required class="form-item">
                          <a-select v-model:value="editForm.transport">
                            <a-select-option value="streamable_http"
                              >streamable_http</a-select-option
                            >
                            <a-select-option value="sse">sse</a-select-option>
                            <a-select-option value="stdio">stdio</a-select-option>
                          </a-select>
                        </a-form-item>
                        <a-form-item label="biểu tượng" class="form-item">
                          <a-input
                            v-model:value="editForm.icon"
                            placeholder="đầu vào emoji，Chẳng hạn như 🧠"
                            :maxlength="2"
                          />
                        </a-form-item>
                      </div>
                      <a-form-item label="Mô tả" class="form-item form-item-full">
                        <a-textarea
                          v-model:value="editForm.description"
                          placeholder="Vui lòng nhập MCP Mô tả"
                          :rows="2"
                        />
                      </a-form-item>
                    </section>

                    <section class="form-section">
                      <div class="form-section-title">
                        <span>Cấu hình kết nối</span>
                        <small
                          >Định cấu hình các tham số kết nối cần thiết cho phương thức truyền hiện
                          tại。</small
                        >
                      </div>
                      <template
                        v-if="
                          editForm.transport === 'streamable_http' || editForm.transport === 'sse'
                        "
                      >
                        <a-form-item label="MCP URL" required class="form-item form-item-full">
                          <a-input
                            v-model:value="editForm.url"
                            placeholder="https://example.com/mcp"
                          />
                        </a-form-item>
                        <div class="form-grid">
                          <a-form-item label="HTTP hết thời gian chờ（giây）" class="form-item">
                            <a-input-number
                              v-model:value="editForm.timeout"
                              :min="1"
                              :max="300"
                              style="width: 100%"
                            />
                          </a-form-item>
                          <a-form-item label="SSE Đọc thời gian chờ（giây）" class="form-item">
                            <a-input-number
                              v-model:value="editForm.sse_read_timeout"
                              :min="1"
                              :max="300"
                              style="width: 100%"
                            />
                          </a-form-item>
                        </div>
                      </template>
                      <template v-if="isStdioTransport">
                        <a-form-item label="lệnh" required class="form-item form-item-full">
                          <a-input
                            v-model:value="editForm.command"
                            placeholder="Ví dụ：npx hoặc /path/to/server"
                          />
                        </a-form-item>
                      </template>
                      <a-form-item label="nhãn" class="form-item form-item-full">
                        <a-select
                          v-model:value="editForm.tags"
                          mode="tags"
                          placeholder="Nhập tag rồi nhấn Enter để thêm"
                          style="width: 100%"
                        />
                      </a-form-item>
                    </section>

                    <section class="form-section">
                      <div class="form-section-title">
                        <span>Cấu hình nâng cao</span>
                        <small
                          >Tiêu đề yêu cầu、Các thông số khởi động và biến môi trường sẽ ảnh hưởng
                          trực tiếp MCP chạy。</small
                        >
                      </div>
                      <template
                        v-if="
                          editForm.transport === 'streamable_http' || editForm.transport === 'sse'
                        "
                      >
                        <a-form-item label="HTTP Tiêu đề yêu cầu" class="form-item form-item-full">
                          <a-textarea
                            v-model:value="editForm.headersText"
                            placeholder='JSON định dạng，Chẳng hạn như：{"Authorization": "Bearer xxx"}'
                            :rows="4"
                            class="config-textarea"
                          />
                          <div class="form-helper">
                            Vui lòng nhập hợp pháp JSON vật thể，Để trống để không gửi tiêu đề yêu
                            cầu bổ sung。
                          </div>
                        </a-form-item>
                      </template>
                      <template v-if="isStdioTransport">
                        <a-form-item label="thông số" class="form-item form-item-full">
                          <a-select
                            v-model:value="editForm.args"
                            mode="tags"
                            placeholder="Nhập các thông số rồi nhấn Enter để thêm，Chẳng hạn như：-m"
                            style="width: 100%"
                          />
                        </a-form-item>
                        <a-form-item label="biến môi trường" class="form-item form-item-full">
                          <div class="env-editor-shell">
                            <McpEnvEditor v-model="editForm.env" />
                          </div>
                        </a-form-item>
                      </template>
                    </section>
                  </a-form>

                  <div class="edit-panel-actions">
                    <a-button @click="cancelEdit" :disabled="editLoading" class="lucide-icon-btn">
                      <template #icon><X :size="14" /></template>
                      Hủy bỏ
                    </a-button>
                    <a-button
                      type="primary"
                      @click="handleSaveEdit"
                      :loading="editLoading"
                      class="lucide-icon-btn"
                    >
                      <template #icon><Save :size="14" /></template>
                      lưu lại
                    </a-button>
                  </div>
                </div>

                <div v-else class="info-grid">
                  <div class="info-item" v-if="server.description">
                    <label>Mô tả</label>
                    <span>{{ server.description }}</span>
                  </div>
                  <div class="info-item">
                    <label>Kiểu truyền động</label>
                    <span>
                      <a-tag :color="getTransportColor(server.transport)">{{
                        server.transport
                      }}</a-tag>
                    </span>
                  </div>
                  <div
                    class="info-item"
                    v-if="Array.isArray(server.tags) && server.tags.length > 0"
                  >
                    <label>nhãn</label>
                    <span>
                      <a-tag v-for="tag in server.tags" :key="tag">{{ tag }}</a-tag>
                    </span>
                  </div>
                  <template
                    v-if="server.transport === 'streamable_http' || server.transport === 'sse'"
                  >
                    <div class="info-item" v-if="server.url">
                      <label>MCP URL</label>
                      <span class="code-inline text-break-all">{{ server.url }}</span>
                    </div>
                    <div
                      class="info-item"
                      v-if="server.headers && Object.keys(server.headers).length > 0"
                    >
                      <label>Tiêu đề yêu cầu</label>
                      <pre class="code-pre">{{ JSON.stringify(server.headers, null, 2) }}</pre>
                    </div>
                    <div class="info-item" v-if="server.timeout">
                      <label>HTTP hết thời gian chờ</label>
                      <span>{{ server.timeout }} giây</span>
                    </div>
                    <div class="info-item" v-if="server.sse_read_timeout">
                      <label>SSE Đọc thời gian chờ</label>
                      <span>{{ server.sse_read_timeout }} giây</span>
                    </div>
                  </template>
                  <template v-if="server.transport === 'stdio'">
                    <div class="info-item" v-if="server.command">
                      <label>lệnh</label>
                      <span class="code-inline">{{ server.command }}</span>
                    </div>
                    <div class="info-item" v-if="server.args && server.args.length > 0">
                      <label>thông số</label>
                      <span>
                        <a-tag v-for="(arg, index) in server.args" :key="index" size="small">{{
                          arg
                        }}</a-tag>
                      </span>
                    </div>
                    <div class="info-item" v-if="server.env && Object.keys(server.env).length > 0">
                      <label>biến môi trường</label>
                      <pre class="code-pre">{{ JSON.stringify(server.env, null, 2) }}</pre>
                    </div>
                  </template>
                  <div class="info-item">
                    <label>thời gian sáng tạo</label>
                    <span>{{ formatTime(server.created_at) }}</span>
                  </div>
                  <div class="info-item">
                    <label>Thời gian cập nhật</label>
                    <span>{{ formatTime(server.updated_at) }}</span>
                  </div>
                  <div class="info-item">
                    <label>Người sáng tạo</label>
                    <span>{{ server.created_by }}</span>
                  </div>
                </div>
              </div>
            </a-tab-pane>

            <a-tab-pane key="tools">
              <template #tab>
                <span class="tab-title"><Wrench :size="14" />Công cụ ({{ tools.length }})</span>
              </template>
              <div class="tab-content tools-tab">
                <div class="tools-toolbar">
                  <a-input-search
                    v-model:value="toolSearchText"
                    placeholder="Công cụ tìm kiếm..."
                    style="width: 200px"
                    allowClear
                  />
                  <a-button @click="fetchTools" :loading="toolsLoading" class="lucide-icon-btn">
                    <RotateCw :size="14" />
                    <span>Làm mới</span>
                  </a-button>
                </div>
                <a-spin :spinning="toolsLoading">
                  <div v-if="filteredTools.length === 0" class="empty-tools">
                    <a-empty :description="toolsError || 'Chưa có công cụ nào'" />
                  </div>
                  <div v-else class="tools-list">
                    <div
                      v-for="tool in filteredTools"
                      :key="tool.name"
                      class="tool-card"
                      :class="{ disabled: !tool.enabled }"
                    >
                      <div class="tool-header">
                        <div class="tool-info">
                          <span class="tool-name">{{ tool.name }}</span>
                          <a-tooltip :title="`ID: ${tool.id}`">
                            <Info :size="14" class="info-icon" />
                          </a-tooltip>
                        </div>
                        <div class="tool-actions">
                          <a-switch
                            :checked="tool.enabled"
                            @change="handleToggleTool(tool)"
                            :loading="toggleToolLoading === tool.name"
                            size="small"
                          />
                          <a-tooltip title="Sao chép tên công cụ">
                            <a-button
                              type="text"
                              size="small"
                              @click="copyToolName(tool.name)"
                              class="lucide-icon-btn"
                            >
                              <Copy :size="14" />
                            </a-button>
                          </a-tooltip>
                        </div>
                      </div>
                      <div class="tool-description" v-if="tool.description">
                        {{ tool.description }}
                      </div>
                      <a-collapse
                        v-if="tool.parameters && Object.keys(tool.parameters).length > 0"
                        ghost
                      >
                        <a-collapse-panel key="params" header="thông số">
                          <div class="params-list">
                            <div
                              v-for="(param, paramName) in tool.parameters"
                              :key="paramName"
                              class="param-item"
                            >
                              <div class="param-header">
                                <span class="param-name">{{ paramName }}</span>
                                <span
                                  class="param-required"
                                  v-if="tool.required?.includes(paramName)"
                                  >Bắt buộc</span
                                >
                                <span class="param-type">{{ param.type || 'any' }}</span>
                              </div>
                              <div class="param-desc" v-if="param.description">
                                {{ param.description }}
                              </div>
                            </div>
                          </div>
                        </a-collapse-panel>
                      </a-collapse>
                    </div>
                  </div>
                </a-spin>
              </div>
            </a-tab-pane>
          </a-tabs>
        </div>
        <div v-else-if="!loading" class="detail-empty">
          <a-empty description="không tìm thấy MCP máy chủ" />
        </div>
      </a-spin>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  ArrowLeft,
  Zap,
  Pencil,
  Trash2,
  Plus,
  RotateCw,
  Info,
  Copy,
  Settings2,
  Wrench,
  Save,
  X
} from 'lucide-vue-next'
import { mcpApi } from '@/apis/mcp_api'
import { formatFullDateTime } from '@/utils/time'
import McpEnvEditor from '@/components/McpEnvEditor.vue'

const route = useRoute()
const router = useRouter()
const slug = computed(() => decodeURIComponent(route.params.slug ?? route.params.name))

const loading = ref(false)
const server = ref(null)
const detailTab = ref('general')
const testLoading = ref(null)

const tools = ref([])
const toolsLoading = ref(false)
const toolsError = ref(null)
const toolSearchText = ref('')
const toggleToolLoading = ref(null)

const isEditing = ref(false)
const editLoading = ref(false)

const editForm = reactive({
  slug: '',
  name: '',
  description: '',
  transport: 'streamable_http',
  url: '',
  command: '',
  args: [],
  env: null,
  headersText: '',
  timeout: null,
  sse_read_timeout: null,
  tags: [],
  icon: ''
})

const actionLabel = computed(() => {
  if (server.value?.enabled === false) return 'thêm'
  return server.value?.created_by === 'system' ? 'Xóa' : 'Xóa'
})

const filteredTools = computed(() => {
  if (!toolSearchText.value) return tools.value
  const search = toolSearchText.value.toLowerCase()
  return tools.value.filter(
    (t) =>
      t.name.toLowerCase().includes(search) ||
      (t.description && t.description.toLowerCase().includes(search))
  )
})

const isStdioTransport = computed(
  () =>
    String(editForm.transport || '')
      .trim()
      .toLowerCase() === 'stdio'
)

const goBack = () => {
  router.push({ path: '/extensions', query: { tab: 'mcp' } })
}

const formatTime = (timeStr) => formatFullDateTime(timeStr)

const getTransportColor = (transport) => {
  const colors = { sse: 'orange', stdio: 'green', streamable_http: 'blue' }
  return colors[transport] || 'blue'
}

const resetEditForm = (data) => {
  Object.assign(editForm, {
    slug: data?.slug || '',
    name: data?.name || '',
    description: data?.description || '',
    transport: data?.transport || 'streamable_http',
    url: data?.url || '',
    command: data?.command || '',
    args: data?.args || [],
    env: data?.env || null,
    headersText: data?.headers ? JSON.stringify(data.headers, null, 2) : '',
    timeout: data?.timeout,
    sse_read_timeout: data?.sse_read_timeout,
    tags: data?.tags || [],
    icon: data?.icon || ''
  })
}

const startEdit = () => {
  if (!server.value) return
  detailTab.value = 'general'
  resetEditForm(server.value)
  isEditing.value = true
}

const cancelEdit = () => {
  isEditing.value = false
  resetEditForm(server.value)
}

const buildEditPayload = () => {
  let headers = null
  if (editForm.headersText.trim()) {
    try {
      headers = JSON.parse(editForm.headersText)
    } catch {
      message.error('Tiêu đề yêu cầu JSON Lỗi định dạng')
      return null
    }
  }

  return {
    name: editForm.name,
    description: editForm.description || null,
    transport: editForm.transport,
    url: editForm.url || null,
    command: editForm.command || null,
    args: editForm.args.length > 0 ? editForm.args : null,
    env: editForm.env,
    headers,
    timeout: editForm.timeout || null,
    sse_read_timeout: editForm.sse_read_timeout || null,
    tags: editForm.tags.length > 0 ? editForm.tags : null,
    icon: editForm.icon || null
  }
}

const validateEditPayload = (data) => {
  if (!data.name?.trim()) {
    message.error('MCP Tên không thể trống')
    return false
  }
  if (!data.transport) {
    message.error('Vui lòng chọn loại chuyển khoản')
    return false
  }
  if (['sse', 'streamable_http'].includes(data.transport) && !data.url?.trim()) {
    message.error('HTTP Loại là bắt buộc MCP URL')
    return false
  }
  if (data.transport === 'stdio' && !data.command?.trim()) {
    message.error('StdIO Loại phải được điền vào lệnh')
    return false
  }
  return true
}

const handleSaveEdit = async () => {
  if (!server.value) return
  const data = buildEditPayload()
  if (!data || !validateEditPayload(data)) return

  try {
    editLoading.value = true
    const result = await mcpApi.updateMcpServer(server.value.slug, data)
    if (result.success) {
      message.success('MCP Cập nhật thành công')
      isEditing.value = false
      await fetchServer()
    } else {
      message.error(result.message || 'Cập nhật không thành công')
    }
  } catch (err) {
    message.error(err.message || 'Cập nhật không thành công')
  } finally {
    editLoading.value = false
  }
}

const fetchServer = async () => {
  try {
    loading.value = true
    const result = await mcpApi.getMcpServer(slug.value)
    if (result.success) {
      if (result.data?.enabled === false) {
        server.value = null
        message.info('Vui lòng thêm trước MCP Kiểm tra chi tiết sau')
        router.replace({ path: '/extensions', query: { tab: 'mcp' } })
        return
      }
      server.value = result.data
    } else {
      message.error(result.message || 'Nhận MCP Chi tiết không thành công')
    }
  } catch (err) {
    message.error(err.message || 'Nhận MCP Chi tiết không thành công')
  } finally {
    loading.value = false
  }
}

const fetchTools = async () => {
  if (!server.value) return
  try {
    toolsLoading.value = true
    toolsError.value = null
    const result = await mcpApi.getMcpServerTools(server.value.slug)
    if (result.success) {
      tools.value = result.data || []
    } else {
      toolsError.value = result.message || 'Không lấy được danh sách công cụ'
      tools.value = []
    }
  } catch (err) {
    toolsError.value = err.message || 'Không lấy được danh sách công cụ'
    tools.value = []
  } finally {
    toolsLoading.value = false
  }
}

const handleToggleTool = async (tool) => {
  if (!server.value) return
  try {
    toggleToolLoading.value = tool.name
    const result = await mcpApi.toggleMcpServerTool(server.value.slug, tool.name)
    if (result.success) {
      message.success(result.message)
      const targetTool = tools.value.find((t) => t.name === tool.name)
      if (targetTool) targetTool.enabled = result.enabled
    } else {
      message.error(result.message || 'Thao tác không thành công')
    }
  } catch (err) {
    message.error(err.message || 'Thao tác không thành công')
  } finally {
    toggleToolLoading.value = null
  }
}

const copyToolName = async (toolName) => {
  try {
    await navigator.clipboard.writeText(toolName)
    message.success('Đã sao chép vào bảng nhớ tạm')
  } catch {
    message.error('Sao chép không thành công')
  }
}

const handleTestServer = async () => {
  if (!server.value) return
  try {
    testLoading.value = server.value.name
    const result = await mcpApi.testMcpServer(server.value.slug)
    if (result.success) {
      message.success(result.message)
    } else {
      message.warning(result.message || 'Kết nối không thành công')
    }
  } catch (err) {
    message.error(err.message || 'thử nghiệm thất bại')
  } finally {
    testLoading.value = null
  }
}

const handleDangerAction = async () => {
  if (!server.value) return
  if (server.value.enabled === false) {
    await handleSetServerEnabled(server.value, true)
    return
  }
  if (server.value.created_by === 'system') {
    await handleSetServerEnabled(server.value, false)
    return
  }
  confirmDeleteServer(server.value)
}

const handleSetServerEnabled = async (srv, enabled) => {
  try {
    const result = await mcpApi.updateMcpServerStatus(srv.slug, enabled)
    if (result.success) {
      message.success(result.message || `MCP Đã rồi${enabled ? 'thêm' : 'Xóa'}`)
      await fetchServer()
    } else {
      message.error(result.message || 'Thao tác không thành công')
    }
  } catch (err) {
    message.error(err.message || 'Thao tác không thành công')
  }
}

const confirmDeleteServer = (srv) => {
  Modal.confirm({
    title: 'Xác nhận xóa MCP',
    content: `Xác nhận xóa MCP "${srv.name}" ?？Hành động này không thể thay đổi được。`,
    okText: 'Xóa',
    okType: 'danger',
    cancelText: 'Hủy bỏ',
    async onOk() {
      try {
        const result = await mcpApi.deleteMcpServer(srv.slug)
        if (result.success) {
          message.success('MCP Xóa thành công')
          router.push({ path: '/extensions', query: { tab: 'mcp' } })
        } else {
          message.error(result.message || 'Xóa không thành công')
        }
      } catch (err) {
        message.error(err.message || 'Xóa không thành công')
      }
    }
  })
}

watch(detailTab, (tab) => {
  if (tab === 'tools' && server.value) {
    fetchTools()
  }
})

onMounted(() => {
  fetchServer()
})
</script>

<style lang="less" scoped>
@import '@/assets/css/extensions.less';
@import '@/assets/css/extension-detail.less';

.edit-panel {
  background: var(--gray-0);
  border: 1px solid var(--gray-150);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.025);

  .edit-panel-header {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-start;
    margin-bottom: 18px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--gray-100);

    h3 {
      margin: 0 0 4px;
      font-size: 16px;
      font-weight: 600;
      color: var(--gray-900);
    }

    p {
      margin: 0;
      font-size: 13px;
      color: var(--gray-500);
    }
  }

  .inline-edit-form {
    display: flex;
    flex-direction: column;

    :deep(.ant-form-item) {
      margin-bottom: 0;
    }

    :deep(.ant-form-item-label > label) {
      color: var(--gray-700);
      font-size: 13px;
      font-weight: 500;
    }
  }

  .form-section {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 18px 0 0;

    & + .form-section {
      margin-top: 18px;
      border-top: 1px solid var(--gray-100);
    }

    &:first-child {
      padding-top: 0;
    }
  }

  .form-section-title {
    display: flex;
    flex-direction: column;
    gap: 3px;

    span {
      font-size: 14px;
      font-weight: 600;
      color: var(--gray-900);
    }

    small {
      font-size: 12px;
      color: var(--gray-500);
    }
  }

  .form-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
  }

  .form-grid-three {
    grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(120px, 0.45fr);
  }

  .form-item-full {
    width: 100%;
  }

  .form-helper {
    margin-top: 6px;
    font-size: 12px;
    line-height: 1.5;
    color: var(--gray-500);
  }

  .config-textarea {
    font-family: @mono-font;
    font-size: 13px;
    line-height: 1.6;
  }

  .env-editor-shell {
    padding: 0;
  }

  .edit-panel-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 18px;
    padding-top: 16px;
    border-top: 1px solid var(--gray-100);
  }
}

/* Kiểu danh sách công cụ */
.tools-tab {
  .tools-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  .empty-tools {
    padding: 40px 0;
  }

  .tools-list {
    display: flex;
    flex-direction: column;
    gap: 12px;

    .tool-card {
      background: var(--gray-0);
      border: 1px solid var(--gray-150);
      border-radius: 8px;
      padding: 12px 16px;
      transition: all 0.2s ease;

      &:hover {
        border-color: var(--gray-200);
      }

      &.disabled {
        opacity: 0.6;
      }

      .tool-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;

        .tool-info {
          display: flex;
          align-items: center;
          gap: 8px;

          .tool-name {
            font-weight: 600;
            font-size: 14px;
            color: var(--gray-900);
          }

          .info-icon {
            color: var(--gray-400);
            cursor: pointer;
            &:hover {
              color: var(--gray-600);
            }
          }
        }

        .tool-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }
      }

      .tool-description {
        font-size: 13px;
        color: var(--gray-600);
        line-height: 1.4;
        margin-bottom: 8px;
      }

      :deep(.ant-collapse) {
        background: transparent;
        border: none;

        .ant-collapse-header {
          padding: 8px 0;
          font-size: 13px;
          color: var(--gray-600);
        }
        .ant-collapse-content-box {
          padding: 0;
        }
      }

      .params-list {
        display: flex;
        flex-direction: column;
        gap: 8px;

        .param-item {
          background: var(--gray-50);
          padding: 8px 12px;
          border-radius: 4px;

          .param-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;

            .param-name {
              font-weight: 500;
              font-size: 13px;
              color: var(--gray-900);
              font-family: @mono-font;
            }
            .param-required {
              font-size: 11px;
              color: var(--color-error-500);
              background: var(--color-error-50);
              padding: 1px 6px;
              border-radius: 3px;
            }
            .param-type {
              font-size: 11px;
              color: var(--gray-500);
              background: var(--gray-100);
              padding: 1px 6px;
              border-radius: 3px;
              font-family: @mono-font;
            }
          }

          .param-desc {
            font-size: 12px;
            color: var(--gray-600);
            line-height: 1.4;
          }
        }
      }
    }
  }
}

.mcp-detail {
  .detail-content-wrapper {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    background-color: var(--gray-10);
  }

  .detail-content-inner {
    max-width: 900px;
    margin: 0 auto;
    padding: 16px var(--page-padding);
  }
}
</style>
