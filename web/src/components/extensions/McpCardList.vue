<template>
  <div class="mcp-cards-page extension-page-root">
    <PageShoulder search-placeholder="Tìm kiếm MCP..." v-model:search="searchQuery">
      <template #actions>
        <a-button type="primary" @click="handleMcpAdd" class="lucide-icon-btn">
          <Plus :size="14" />
          <span>thêm MCP</span>
        </a-button>
        <a-tooltip title="Làm mới MCP" placement="bottom">
          <a-button class="lucide-icon-btn" :disabled="loading" @click="fetchServers">
            <RefreshCw :size="14" />
          </a-button>
        </a-tooltip>
      </template>
    </PageShoulder>

    <div
      v-if="filteredEnabledServers.length === 0 && filteredDisabledServers.length === 0"
      class="extension-card-grid-empty-state"
    >
      <a-empty
        :image="false"
        :description="
          searchQuery ? 'Không có trận đấu MCP' : 'Chưa có MCP，Bấm vào nút bên trên để thêm'
        "
      />
    </div>

    <template v-else>
      <div v-if="filteredEnabledServers.length" class="extension-section-header">Đã thêm</div>
      <ExtensionCardGrid v-if="filteredEnabledServers.length" :min-width="360">
        <InfoCard
          v-for="server in filteredEnabledServers"
          :key="server.slug"
          variant="mini"
          :title="formatExtensionCardTitle(server.name)"
          :description="server.description || 'Chưa có mô tả'"
          @click="handleCardClick(server)"
        >
          <template #icon>
            <span class="info-card-emoji-icon">{{ server.icon || '🔌' }}</span>
          </template>
          <template #action>
            <button
              type="button"
              class="mcp-card-action mcp-card-action-danger"
              :disabled="isActionLoading(server)"
              :aria-label="server.created_by === 'system' ? 'Xóa MCP' : 'Xóa MCP'"
              @click.stop="handleRemoveServer(server)"
            >
              <Check :size="15" class="action-icon action-icon-check" />
              <Trash2 :size="15" class="action-icon action-icon-trash" />
            </button>
          </template>
        </InfoCard>
      </ExtensionCardGrid>

      <div v-if="filteredDisabledServers.length" class="extension-section-header">
        Có thể được thêm vào
      </div>
      <ExtensionCardGrid v-if="filteredDisabledServers.length" :min-width="360">
        <InfoCard
          v-for="server in filteredDisabledServers"
          :key="server.slug"
          variant="mini"
          :title="formatExtensionCardTitle(server.name)"
          :description="server.description || 'Chưa có mô tả'"
          @click="openBasicInfo(server)"
        >
          <template #icon>
            <span class="info-card-emoji-icon">{{ server.icon || '🔌' }}</span>
          </template>
          <template #action>
            <button
              type="button"
              class="mcp-card-action"
              :disabled="isActionLoading(server)"
              aria-label="thêm MCP"
              @click.stop="handleSetServerEnabled(server, true)"
            >
              <Plus :size="15" class="action-icon" />
            </button>
          </template>
        </InfoCard>
      </ExtensionCardGrid>
    </template>

    <a-modal
      v-model:open="basicInfoVisible"
      class="mcp-basic-info-modal"
      :footer="null"
      width="560px"
      :destroy-on-close="true"
      @cancel="closeBasicInfo"
    >
      <div v-if="previewServer" class="mcp-basic-info-panel">
        <div class="mcp-basic-info-header">
          <div class="mcp-basic-info-icon">
            <span>{{ previewServer.icon || '🔌' }}</span>
          </div>
          <div class="mcp-basic-info-title-area">
            <div class="mcp-basic-info-title">
              {{ formatExtensionCardTitle(previewServer.name) }}
            </div>
            <div class="mcp-basic-info-meta">
              <span>{{ previewServer.transport || 'Loại chuyển không xác định' }}</span>
              <span v-if="previewServer.created_by === 'system'" class="mcp-basic-info-tag">
                Tích hợp sẵn
              </span>
            </div>
          </div>
        </div>

        <div class="mcp-basic-info-body">
          <div class="mcp-basic-info-row">
            <label>Mô tả</label>
            <span>{{ previewServer.description || 'Chưa có mô tả' }}</span>
          </div>
          <div class="mcp-basic-info-row">
            <label>Kiểu truyền động</label>
            <span>{{ previewServer.transport || '-' }}</span>
          </div>
          <div
            v-if="Array.isArray(previewServer.tags) && previewServer.tags.length > 0"
            class="mcp-basic-info-row"
          >
            <label>nhãn</label>
            <span class="mcp-basic-info-tags">
              <a-tag v-for="tag in previewServer.tags" :key="tag">{{ tag }}</a-tag>
            </span>
          </div>
          <div class="mcp-basic-info-row">
            <label>Người sáng tạo</label>
            <span>{{ previewServer.created_by || '-' }}</span>
          </div>
        </div>

        <div class="mcp-basic-info-footer">
          <a-button @click="closeBasicInfo">đóng</a-button>
          <a-button
            type="primary"
            class="lucide-icon-btn"
            :loading="isActionLoading(previewServer)"
            @click="handleSetServerEnabled(previewServer, true)"
          >
            <template #icon><Plus :size="14" /></template>
            thêm
          </a-button>
        </div>
      </div>
    </a-modal>

    <McpFormModal
      v-model:open="formModalVisible"
      :edit-mode="false"
      @submitted="handleFormSubmitted"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { Check, Plus, RefreshCw, Trash2 } from 'lucide-vue-next'
import { mcpApi } from '@/apis/mcp_api'
import ExtensionCardGrid from './ExtensionCardGrid.vue'
import InfoCard from '@/components/shared/InfoCard.vue'
import PageShoulder from '@/components/shared/PageShoulder.vue'
import McpFormModal from './McpFormModal.vue'
import { formatExtensionCardTitle } from '@/utils/extensionDisplayName'

const router = useRouter()

const loading = ref(false)
const servers = ref([])
const searchQuery = ref('')
const formModalVisible = ref(false)
const basicInfoVisible = ref(false)
const previewServer = ref(null)
const actionLoadingSlug = ref('')

const filteredServers = computed(() => {
  const sorted = [...servers.value].sort((a, b) =>
    String(a.name || '').localeCompare(String(b.name || ''), 'zh-Hans-CN', {
      sensitivity: 'base',
      numeric: true
    })
  )
  if (!searchQuery.value) return sorted
  const q = searchQuery.value.toLowerCase()
  return sorted.filter(
    (s) => s.name.toLowerCase().includes(q) || (s.description || '').toLowerCase().includes(q)
  )
})

const filteredEnabledServers = computed(() =>
  filteredServers.value.filter((item) => !!item.enabled)
)
const filteredDisabledServers = computed(() =>
  filteredServers.value.filter((item) => !item.enabled)
)

const navigateToDetail = (server) => {
  router.push({ path: `/extensions/mcp/${encodeURIComponent(server.slug)}` })
}

const handleCardClick = (server) => {
  if (server.enabled) {
    navigateToDetail(server)
    return
  }
  openBasicInfo(server)
}

const openBasicInfo = (server) => {
  previewServer.value = server
  basicInfoVisible.value = true
}

const closeBasicInfo = () => {
  basicInfoVisible.value = false
  previewServer.value = null
}

const isActionLoading = (server) => actionLoadingSlug.value === server?.slug

const handleMcpAdd = () => {
  formModalVisible.value = true
}

const handleFormSubmitted = async () => {
  formModalVisible.value = false
  await fetchServers()
}

const handleSetServerEnabled = async (server, enabled) => {
  try {
    actionLoadingSlug.value = server.slug
    const result = await mcpApi.updateMcpServerStatus(server.slug, enabled)
    if (result.success) {
      message.success(result.message || `MCP Đã rồi${enabled ? 'thêm' : 'Xóa'}`)
      if (enabled) closeBasicInfo()
      await fetchServers()
    } else {
      message.error(result.message || 'Thao tác không thành công')
    }
  } catch (err) {
    message.error(err.message || 'Thao tác không thành công')
  } finally {
    actionLoadingSlug.value = ''
  }
}

const handleRemoveServer = (server) => {
  if (server.created_by === 'system') {
    handleSetServerEnabled(server, false)
    return
  }
  confirmDeleteServer(server)
}

const confirmDeleteServer = (server) => {
  Modal.confirm({
    title: 'Xác nhận xóa MCP',
    content: `Xác nhận xóa MCP "${server.name}" ?？Hành động này không thể thay đổi được。`,
    okText: 'Xóa',
    okType: 'danger',
    cancelText: 'Hủy bỏ',
    async onOk() {
      try {
        actionLoadingSlug.value = server.slug
        const result = await mcpApi.deleteMcpServer(server.slug)
        if (result.success) {
          message.success('MCP Xóa thành công')
          await fetchServers()
        } else {
          message.error(result.message || 'Xóa không thành công')
        }
      } catch (err) {
        message.error(err.message || 'Xóa không thành công')
      } finally {
        actionLoadingSlug.value = ''
      }
    }
  })
}

const fetchServers = async () => {
  try {
    loading.value = true
    const result = await mcpApi.getMcpServers()
    if (result.success) {
      servers.value = result.data || []
    }
  } catch (err) {
    message.error(err.message || 'Nhận MCP Danh sách không thành công')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchServers()
})

defineExpose({ fetchServers, loading })
</script>

<style lang="less" scoped>
@import '@/assets/css/extensions.less';

.info-card-emoji-icon {
  font-size: 18px;
  line-height: 1;
}

.mcp-card-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-0);
  color: var(--main-color);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    color 0.18s ease;

  &:hover,
  &:focus {
    outline: none;
    border-color: var(--main-200);
    background: var(--main-50);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.45;
  }

  &.mcp-card-action-danger {
    color: var(--color-success-700);

    .action-icon-trash {
      display: none;
    }

    &:hover,
    &:focus {
      border-color: var(--color-error-100);
      background: var(--color-error-50);
      color: var(--color-error-700);

      .action-icon-check {
        display: none;
      }

      .action-icon-trash {
        display: block;
      }
    }
  }
}

.action-icon {
  flex-shrink: 0;
}

.mcp-basic-info-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.mcp-basic-info-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mcp-basic-info-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  border: 1px solid var(--gray-150);
  background: var(--main-50);
  color: var(--main-color);
  font-size: 18px;
}

.mcp-basic-info-title-area {
  min-width: 0;
}

.mcp-basic-info-title {
  overflow: hidden;
  color: var(--gray-900);
  font-size: 16px;
  font-weight: 700;
  line-height: 22px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcp-basic-info-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 2px;
  color: var(--gray-500);
  font-size: 12px;
  line-height: 18px;
}

.mcp-basic-info-tag {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--gray-100);
  color: var(--gray-600);
  font-size: 11px;
  font-weight: 600;
}

.mcp-basic-info-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--gray-150);
  border-radius: 12px;
  background: var(--gray-25);
}

.mcp-basic-info-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 12px;
  color: var(--gray-700);
  font-size: 13px;
  line-height: 20px;

  label {
    color: var(--gray-500);
    font-weight: 600;
  }

  span {
    min-width: 0;
    overflow-wrap: anywhere;
  }
}

.mcp-basic-info-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mcp-basic-info-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
