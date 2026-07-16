<template>
  <a-modal
    v-model:open="visible"
    :title="editMode ? 'Chỉnh sửa MCP' : 'thêm MCP'"
    @ok="handleFormSubmit"
    :confirmLoading="formLoading"
    @cancel="visible = false"
    :maskClosable="false"
    width="560px"
    class="server-modal"
  >
    <a-form layout="vertical" class="extension-form">
      <a-form-item label="MCP biểu tượng" required class="form-item">
        <a-input
          v-model:value="form.slug"
          placeholder="Vui lòng nhập MCP nhận dạng ổn định，Chẳng hạn như my-mcp"
          :disabled="editMode"
        />
      </a-form-item>
      <a-form-item label="MCP Tên" required class="form-item">
        <a-input v-model:value="form.name" placeholder="Vui lòng nhập MCP tên hiển thị" />
      </a-form-item>
      <a-form-item label="Mô tả" class="form-item">
        <a-input v-model:value="form.description" placeholder="Vui lòng nhập MCP Mô tả" />
      </a-form-item>
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item label="Kiểu truyền động" required class="form-item">
            <a-select v-model:value="form.transport">
              <a-select-option value="streamable_http">streamable_http</a-select-option>
              <a-select-option value="sse">sse</a-select-option>
              <a-select-option value="stdio">stdio</a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item label="biểu tượng" class="form-item">
            <a-input
              v-model:value="form.icon"
              placeholder="đầu vào emoji，Chẳng hạn như 🧠"
              :maxlength="2"
            />
          </a-form-item>
        </a-col>
      </a-row>
      <template v-if="form.transport === 'streamable_http' || form.transport === 'sse'">
        <a-form-item label="MCP URL" required class="form-item">
          <a-input v-model:value="form.url" placeholder="https://example.com/mcp" />
        </a-form-item>
        <a-form-item label="HTTP Tiêu đề yêu cầu" class="form-item">
          <a-textarea
            v-model:value="form.headersText"
            placeholder='JSON định dạng，Chẳng hạn như：{"Authorization": "Bearer xxx"}'
            :rows="3"
          />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="HTTP hết thời gian chờ（giây）" class="form-item">
              <a-input-number
                v-model:value="form.timeout"
                :min="1"
                :max="300"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="SSE Đọc thời gian chờ（giây）" class="form-item">
              <a-input-number
                v-model:value="form.sse_read_timeout"
                :min="1"
                :max="300"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
        </a-row>
      </template>
      <template v-if="isStdioTransport">
        <a-form-item label="lệnh" required class="form-item">
          <a-input v-model:value="form.command" placeholder="Ví dụ：npx hoặc /path/to/server" />
        </a-form-item>
        <a-form-item label="thông số" class="form-item">
          <a-select
            v-model:value="form.args"
            mode="tags"
            placeholder="Nhập các thông số rồi nhấn Enter để thêm，Chẳng hạn như：-m"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="biến môi trường" class="form-item">
          <McpEnvEditor v-model="form.env" />
        </a-form-item>
      </template>
      <a-form-item label="nhãn" class="form-item">
        <a-select
          v-model:value="form.tags"
          mode="tags"
          placeholder="Nhập tag rồi nhấn Enter để thêm"
          style="width: 100%"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import { mcpApi } from '@/apis/mcp_api'
import McpEnvEditor from '@/components/McpEnvEditor.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  editMode: { type: Boolean, default: false },
  editData: { type: Object, default: null }
})

const emit = defineEmits(['update:open', 'submitted'])

const visible = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val)
})

const formLoading = ref(false)

const form = reactive({
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

const isStdioTransport = computed(
  () =>
    String(form.transport || '')
      .trim()
      .toLowerCase() === 'stdio'
)

watch(
  () => props.open,
  (val) => {
    if (val && props.editData) {
      Object.assign(form, {
        slug: props.editData.slug || '',
        name: props.editData.name || '',
        description: props.editData.description || '',
        transport: props.editData.transport || 'streamable_http',
        url: props.editData.url || '',
        command: props.editData.command || '',
        args: props.editData.args || [],
        env: props.editData.env || null,
        headersText: props.editData.headers ? JSON.stringify(props.editData.headers, null, 2) : '',
        timeout: props.editData.timeout,
        sse_read_timeout: props.editData.sse_read_timeout,
        tags: props.editData.tags || [],
        icon: props.editData.icon || ''
      })
    } else if (val && !props.editData) {
      Object.assign(form, {
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
    }
  },
  { immediate: true }
)

const handleFormSubmit = async () => {
  try {
    formLoading.value = true
    let headers = null
    if (form.headersText.trim()) {
      try {
        headers = JSON.parse(form.headersText)
      } catch {
        message.error('Tiêu đề yêu cầu JSON Lỗi định dạng')
        return
      }
    }
    const data = {
      slug: form.slug,
      name: form.name,
      description: form.description || null,
      transport: form.transport,
      url: form.url || null,
      command: form.command || null,
      args: form.args.length > 0 ? form.args : null,
      env: form.env,
      headers,
      timeout: form.timeout || null,
      sse_read_timeout: form.sse_read_timeout || null,
      tags: form.tags.length > 0 ? form.tags : null,
      icon: form.icon || null
    }
    if (!data.slug?.trim()) {
      message.error('MCP ID không thể trống')
      return
    }
    if (!data.name?.trim()) {
      message.error('MCP Tên không thể trống')
      return
    }
    if (!data.transport) {
      message.error('Vui lòng chọn loại chuyển khoản')
      return
    }
    if (['sse', 'streamable_http'].includes(data.transport)) {
      if (!data.url?.trim()) {
        message.error('HTTP Loại là bắt buộc MCP URL')
        return
      }
    }
    if (data.transport === 'stdio') {
      if (!data.command?.trim()) {
        message.error('StdIO Loại phải được điền vào lệnh')
        return
      }
    }

    if (props.editMode) {
      const { slug, ...updateData } = data
      const result = await mcpApi.updateMcpServer(props.editData?.slug || slug, updateData)
      if (result.success) {
        message.success('MCP Cập nhật thành công')
      } else {
        message.error(result.message || 'Cập nhật không thành công')
        return
      }
    } else {
      const result = await mcpApi.createMcpServer(data)
      if (result.success) {
        message.success('MCP Đã tạo thành công')
      } else {
        message.error(result.message || 'Tạo không thành công')
        return
      }
    }
    visible.value = false
    emit('submitted')
  } catch (err) {
    message.error(err.message || 'Thao tác không thành công')
  } finally {
    formLoading.value = false
  }
}
</script>

<style lang="less" scoped>
@import '@/assets/css/extensions.less';
</style>
