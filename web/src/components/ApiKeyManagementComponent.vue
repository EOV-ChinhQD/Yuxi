<template>
  <div class="apikey-management">
    <!-- vùng đầu -->
    <div class="header-section">
      <div class="header-content">
        <div class="section-title">API Key quản lý</div>
        <p class="section-description">
          cho các cuộc gọi hệ thống bên ngoài Agent giao diện đàm thoại。Khóa chỉ được hiển thị một
          lần，Hãy giữ nó đúng cách。
        </p>
      </div>
      <div class="header-actions">
        <a-button
          @click="handleRefresh"
          :loading="refreshing"
          title="Làm mới"
          class="refresh-btn lucide-icon-btn"
        >
          <template #icon><RefreshCw :size="16" :class="{ spin: refreshing }" /></template>
        </a-button>
        <a-button type="primary" @click="showCreateModal" class="add-btn lucide-icon-btn">
          <Plus :size="14" />
          tạo ra API Key
        </a-button>
      </div>
    </div>

    <!-- khu vực nội dung chính -->
    <div class="content-section">
      <a-spin :spinning="loading">
        <div v-if="error" class="error-message">
          <a-alert type="error" :message="error" show-icon />
        </div>

        <div class="cards-container">
          <div v-if="apiKeys.length === 0" class="empty-state">
            <a-empty description="Chưa có API Key，Nhấp vào nút ở trên để tạo một cái" />
          </div>
          <div v-else class="apikey-cards-grid">
            <div v-for="key in apiKeys" :key="key.id" class="apikey-card">
              <div class="card-header">
                <div class="key-info">
                  <KeyIcon size="18" class="key-icon" />
                  <div class="key-info-content">
                    <h4 class="key-name">{{ key.name }}</h4>
                  </div>
                </div>
                <code class="key-prefix">{{ key.key_prefix }}****</code>
              </div>

              <div class="card-content">
                <div class="info-item">
                  <span class="info-label">Thời gian hết hạn:</span>
                  <span class="info-value">{{ key.expires_at || 'không bao giờ hết hạn' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">sử dụng lần cuối:</span>
                  <span class="info-value">{{ formatTime(key.last_used_at) }}</span>
                </div>
              </div>

              <div class="card-footer">
                <div class="footer-left">
                  <span class="switch-label">{{ key.is_enabled ? 'Đã bật' : 'Đã tắt' }}</span>
                  <a-switch :checked="key.is_enabled" size="small" @change="toggleEnabled(key)" />
                </div>
                <div class="footer-actions">
                  <a-tooltip title="tái sinh（Nhận chìa khóa đầy đủ）">
                    <a-button
                      type="text"
                      size="small"
                      @click="regenerateKey(key)"
                      class="action-btn lucide-icon-btn"
                    >
                      <RefreshCw :size="14" />
                      <span>tái sinh</span>
                    </a-button>
                  </a-tooltip>
                  <a-popconfirm
                    title="Bạn có chắc chắn muốn xóa cái này không API Key ?？Hoạt động này là không thể đảo ngược。"
                    @confirm="deleteKey(key)"
                    ok-text="được rồi"
                    cancel-text="Hủy bỏ"
                  >
                    <a-tooltip title="Xóa">
                      <a-button type="text" size="small" danger class="action-btn lucide-icon-btn">
                        <Trash2 :size="14" />
                        <span>Xóa</span>
                      </a-button>
                    </a-tooltip>
                  </a-popconfirm>
                </div>
              </div>
            </div>
          </div>
        </div>
      </a-spin>
    </div>

    <!-- tạo ra Modal -->
    <a-modal
      v-model:open="createModalVisible"
      title="tạo ra API Key"
      @ok="handleCreate"
      :confirmLoading="createLoading"
      ok-text="tạo ra"
      cancel-text="Hủy bỏ"
    >
      <a-form layout="vertical" :model="createForm">
        <a-form-item label="Tên" required>
          <a-input
            v-model:value="createForm.name"
            placeholder="Chẳng hạn như：môi trường sản xuấtAPI"
          />
        </a-form-item>
        <a-form-item label="Thời gian hết hạn">
          <a-date-picker
            v-model:value="createForm.expires_at"
            show-time
            placeholder="Để trống để không bao giờ hết hạn"
            style="width: 100%"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Hiển thị phím Modal (Hiển thị một lần sau khi tạo) -->
    <a-modal
      v-model:open="secretModalVisible"
      title="API Key Đã tạo"
      :closable="true"
      @cancel="secretModalVisible = false"
      :footer="null"
      width="520px"
    >
      <div class="secret-display">
        <a-alert
          type="warning"
          message="Hãy sao chép chìa khóa ngay bây giờ，Sau khi đóng, bạn sẽ không thể xem lại toàn bộ key nữa"
          show-icon
          class="secret-alert"
        />
        <div class="secret-value-container">
          <code class="secret-value">{{ createdSecret }}</code>
          <a-button type="primary" @click="copySecret" class="copy-btn lucide-icon-btn">
            <Copy :size="14" />
            Sao chép
          </a-button>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { Plus, RefreshCw, Trash2, Copy } from 'lucide-vue-next'
import { Key as KeyIcon } from 'lucide-vue-next'
import { apikeyApi } from '@/apis/apikey_api'

const loading = ref(false)
const refreshing = ref(false)
const error = ref(null)
const apiKeys = ref([])

const createModalVisible = ref(false)
const secretModalVisible = ref(false)
const createLoading = ref(false)
const createdSecret = ref('')

const createForm = reactive({
  name: '',
  expires_at: null
})

const formatTime = (timeStr) => {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const loadApiKeys = async () => {
  loading.value = true
  error.value = null
  try {
    const res = await apikeyApi.list()
    apiKeys.value = res.api_keys || []
  } catch (e) {
    error.value = e.message || 'Tải không thành công'
  } finally {
    loading.value = false
  }
}

// Làm mới API Key danh sách
const handleRefresh = async () => {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await loadApiKeys()
    message.success('Làm mới thành công')
  } catch (e) {
    console.error('Làm mới không thành công:', e)
    message.error('Làm mới không thành công')
  } finally {
    refreshing.value = false
  }
}

const showCreateModal = () => {
  createForm.name = ''
  createForm.expires_at = null
  createModalVisible.value = true
}

const handleCreate = async () => {
  if (!createForm.name.trim()) {
    message.error('Vui lòng nhập tên')
    return
  }

  createLoading.value = true
  try {
    const data = { name: createForm.name }
    if (createForm.expires_at) {
      data.expires_at = createForm.expires_at.format('YYYY-MM-DDTHH:mm:ss')
    }

    const res = await apikeyApi.create(data)
    createdSecret.value = res.secret
    createModalVisible.value = false
    secretModalVisible.value = true
    await loadApiKeys()
  } catch (e) {
    message.error(e.message || 'Tạo không thành công')
  } finally {
    createLoading.value = false
  }
}

const copySecret = async () => {
  try {
    await navigator.clipboard.writeText(createdSecret.value)
    message.success('Đã sao chép vào bảng nhớ tạm')
  } catch {
    message.error('Sao chép không thành công')
  }
}

const regenerateKey = async (key) => {
  try {
    const res = await apikeyApi.regenerate(key.id)
    createdSecret.value = res.secret
    secretModalVisible.value = true
    await loadApiKeys()
  } catch (e) {
    message.error(e.message || 'Tái tạo không thành công')
  }
}

const toggleEnabled = async (key) => {
  try {
    await apikeyApi.update(key.id, { is_enabled: !key.is_enabled })
    message.success(key.is_enabled ? 'Đã tắt' : 'Đã bật')
    await loadApiKeys()
  } catch (e) {
    message.error(e.message || 'Thao tác không thành công')
  }
}

const deleteKey = async (key) => {
  try {
    await apikeyApi.delete(key.id)
    message.success('Xóa thành công')
    await loadApiKeys()
  } catch (e) {
    message.error(e.message || 'Xóa không thành công')
  }
}

onMounted(() => {
  loadApiKeys()
})
</script>

<style lang="less" scoped>
.apikey-management {
  .header-section {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 16px;
    margin-bottom: 16px;

    .header-content {
      flex: 1;
      min-width: 0;

      .section-title {
        font-size: 16px;
        font-weight: 500;
        color: var(--gray-900);
        line-height: 1.4;
        margin: 12px 0 12px;
      }

      .section-description {
        font-size: 14px;
        color: var(--gray-600);
        line-height: 1.4;
        margin: 0;
      }
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 8px;

      .refresh-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: 6px;
        transition: all 0.2s ease;

        &:hover {
          background: var(--gray-25);
        }

        .spin {
          animation: spin 1s linear infinite;
        }
      }
    }
  }

  .content-section {
    .error-message {
      margin-bottom: 16px;
    }

    .cards-container {
      .empty-state {
        padding: 48px 0;
      }

      .apikey-cards-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 12px;
      }

      .apikey-card {
        background: var(--gray-0);
        border: 1px solid var(--gray-150);
        border-radius: 8px;
        padding: 12px;
        transition:
          border-color 0.2s,
          box-shadow 0.2s;

        &:hover {
          border-color: var(--gray-300);
        }

        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 10px;

          .key-info {
            display: flex;
            align-items: center;
            gap: 10px;

            .key-icon {
              color: var(--main-600);
              flex-shrink: 0;
            }

            .key-info-content {
              .key-name {
                font-size: 14px;
                font-weight: 600;
                color: var(--gray-900);
                margin: 0;
              }
            }
          }

          .key-prefix {
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 12px;
            color: var(--gray-600);
            background: var(--gray-50);
            padding: 2px 8px;
            border-radius: 8px;
          }
        }

        .card-content {
          margin-bottom: 10px;

          .info-item {
            display: flex;
            align-items: flex-start;
            gap: 6px;
            margin-bottom: 6px;
            font-size: 13px;

            &:last-child {
              margin-bottom: 0;
            }

            .info-label {
              color: var(--gray-600);
              flex-shrink: 0;
            }

            .info-value {
              color: var(--gray-900);
              word-break: break-all;
            }

            &.half {
              flex: 1;
            }
          }
        }

        .card-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-top: 8px;
          border-top: 1px solid var(--gray-100);

          .footer-left {
            display: flex;
            align-items: center;
            gap: 8px;

            .switch-label {
              font-size: 12px;
              color: var(--gray-600);
            }
          }

          .footer-actions {
            display: flex;
            gap: 4px;
          }

          .action-btn {
            font-size: 12px;
            color: var(--gray-700);
            display: inline-flex;
            align-items: center;
            gap: 4px;

            &:hover {
              color: var(--main-600);
            }
          }
        }
      }
    }
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

.secret-display {
  .secret-alert {
    margin-bottom: 16px;
  }

  .secret-value-container {
    display: flex;
    gap: 8px;
    align-items: stretch;

    .secret-value {
      flex: 1;
      font-family: 'Monaco', 'Consolas', monospace;
      font-size: 13px;
      background: var(--gray-100);
      border: 1px solid var(--gray-200);
      border-radius: 6px;
      padding: 12px;
      word-break: break-all;
      color: var(--gray-900);
    }

    .copy-btn {
      flex-shrink: 0;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
  }
}
</style>
