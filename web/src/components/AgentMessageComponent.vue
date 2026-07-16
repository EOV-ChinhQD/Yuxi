<template>
  <div v-if="message.type === 'human' && message.image_content" class="message-image">
    <img
      :src="`data:${messageImageMimeType};base64,${message.image_content}`"
      alt="Hình ảnh do người dùng tải lên"
      @click="
        openImagePreview(
          `data:${messageImageMimeType};base64,${message.image_content}`,
          'Hình ảnh do người dùng tải lên'
        )
      "
    />
  </div>
  <div
    class="message-box"
    :class="[
      message.type,
      customClasses,
      { 'has-attachments': message.type === 'human' && messageAttachments.length }
    ]"
  >
    <!-- Tin nhắn của người dùng -->
    <div
      v-if="message.type === 'human'"
      class="message-copy-btn human-copy"
      @click="copyToClipboard(message.content)"
      :class="{ 'is-copied': isCopied }"
    >
      <Check v-if="isCopied" size="14" />
      <Copy v-else size="14" />
    </div>
    <p v-if="message.type === 'human'" class="message-text">
      <MentionTextRenderer :content="message.content" :display-labels="mentionDisplayLabels" />
    </p>

    <p v-else-if="message.type === 'system'" class="message-text-system">{{ message.content }}</p>

    <!-- Tin nhắn trợ lý -->
    <div v-else-if="message.type === 'ai'" class="assistant-message">
      <div v-if="parsedData.reasoning_content" class="reasoning-box">
        <a-collapse v-model:activeKey="reasoningActiveKey" :bordered="false">
          <template #expandIcon="{ isActive }">
            <caret-right-outlined :rotate="isActive ? 90 : 0" />
          </template>
          <a-collapse-panel
            key="show"
            :header="message.status == 'reasoning' ? 'suy nghĩ...' : 'quá trình suy luận'"
            class="reasoning-header"
          >
            <p class="reasoning-content">{{ parsedData.reasoning_content }}</p>
          </a-collapse-panel>
        </a-collapse>
      </div>

      <!-- Nội dung tin nhắn -->
      <MarkdownPreview
        v-if="parsedData.content"
        :key="message.id"
        :content="parsedData.content"
        code-copy
        class="message-md"
      />

      <div v-else-if="parsedData.reasoning_content" class="empty-block"></div>

      <!-- khối thông báo lỗi -->
      <div v-if="displayError" class="error-hint">
        <span v-if="getErrorMessage">{{ getErrorMessage }}</span>
        <span v-else-if="message.error_type === 'interrupted'"
          >Việc tạo câu trả lời bị gián đoạn</span
        >
        <span v-else-if="message.error_type === 'unexpect'"
          >Ngoại lệ xảy ra trong quá trình tạo</span
        >
        <span v-else-if="message.error_type === 'content_guard_blocked'"
          >Đã phát hiện nội dung nhạy cảm，Đầu ra bị gián đoạn</span
        >
        <span v-else>{{ message.error_type || 'lỗi không xác định' }}</span>
      </div>

      <ToolCallsGroupComponent
        v-if="!hideToolCalls && validToolCalls.length > 0"
        :tool-calls="validToolCalls"
      />

      <div v-if="message.isStoppedByUser" class="retry-hint">
        Bạn đã ngừng tạo câu trả lời này
        <span class="retry-link" @click="emit('retryStoppedMessage', message.id)"
          >Chỉnh sửa lại câu hỏi</span
        >
      </div>

      <div
        v-if="
          (message.role == 'received' || message.role == 'assistant') &&
          message.status == 'finished' &&
          showRefs
        "
      >
        <RefsComponent
          :message="message"
          :show-refs="showRefs"
          :is-latest-message="isLatestMessage"
          :sources="messageSources"
          @retry="emit('retry')"
          @openRefs="emit('openRefs', $event)"
        />
      </div>
      <!-- thông báo lỗi -->
    </div>

    <div v-if="infoStore.debugMode" class="status-info">{{ message }}</div>

    <!-- Nội dung tùy chỉnh -->
    <slot></slot>
  </div>

  <div
    v-if="message.type === 'human' && messageAttachments.length"
    class="human-message-attachments"
  >
    <div
      v-for="attachment in messageAttachments"
      :key="attachment.fileId"
      class="message-attachment-file"
    >
      <div class="message-attachment-icon">
        <FileTypeIcon :name="attachment.name" :size="18" />
      </div>
      <div class="message-attachment-body">
        <div class="message-attachment-name" :title="attachment.name">
          {{ attachment.name }}
        </div>
        <div class="message-attachment-meta">{{ attachment.meta }}</div>
      </div>
    </div>
  </div>

  <Teleport to="body">
    <div
      v-if="imagePreview.visible"
      class="message-image-preview-overlay"
      @click="closeImagePreview"
    >
      <button class="message-image-preview-close" title="đóng" @click.stop="closeImagePreview">
        <X :size="20" />
      </button>
      <img :src="imagePreview.src" :alt="imagePreview.alt" class="message-image-preview-img" />
    </div>
  </Teleport>
</template>

<script setup>
import { computed, ref, onUnmounted } from 'vue'
import { CaretRightOutlined } from '@ant-design/icons-vue'
import RefsComponent from '@/components/RefsComponent.vue'
import { Copy, Check, X } from 'lucide-vue-next'
import ToolCallsGroupComponent from '@/components/ToolCallsGroupComponent.vue'
import MarkdownPreview from '@/components/common/MarkdownPreview.vue'
import MentionTextRenderer from '@/components/common/MentionTextRenderer.vue'
import { useAgentStore } from '@/stores/agent'
import { useInfoStore } from '@/stores/info'
import { storeToRefs } from 'pinia'
import { MessageProcessor } from '@/utils/messageProcessor'
import { inferImageMimeTypeFromBase64, normalizeAttachmentPreviews } from '@/utils/file_utils'
import { buildMentionDisplayLabels } from '@/utils/mention_utils'
import FileTypeIcon from '@/components/common/FileTypeIcon.vue'
import { enrichTaskToolCalls } from '@/components/ToolCallingResult/toolRegistry'

const props = defineProps({
  // vai trò tin nhắn：'user'|'assistant'|'sent'|'received'
  message: {
    type: Object,
    required: true
  },
  // Nó có đang được xử lý không?
  isProcessing: {
    type: Boolean,
    default: false
  },
  // Lớp tùy chỉnh
  customClasses: {
    type: Object,
    default: () => ({})
  },
  // Có thể hiện quá trình lập luận hay không
  showRefs: {
    type: [Array, Boolean],
    default: () => false
  },
  // Đây có phải là tin tức mới nhất?
  isLatestMessage: {
    type: Boolean,
    default: false
  },
  hideToolCalls: {
    type: Boolean,
    default: false
  },
  mention: {
    type: Object,
    default: () => null
  },
  // Có hiển thị thông tin gỡ lỗi hay không (Không được dùng nữa，sử dụng infoStore.debugMode)
  debugMode: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['retry', 'retryStoppedMessage', 'openRefs'])

// Hình ảnh xem trước toàn màn hình
const imagePreview = ref({ visible: false, src: '', alt: '' })

const handleImagePreviewKeydown = (e) => {
  if (e.key === 'Escape') {
    closeImagePreview()
  }
}

const openImagePreview = (src, alt = '') => {
  if (!src) return
  imagePreview.value = { visible: true, src, alt }
  window.addEventListener('keydown', handleImagePreviewKeydown)
}

const closeImagePreview = () => {
  imagePreview.value = { visible: false, src: '', alt: '' }
  window.removeEventListener('keydown', handleImagePreviewKeydown)
}

onUnmounted(() => {
  window.removeEventListener('keydown', handleImagePreviewKeydown)
})

// trạng thái sao chép
const isCopied = ref(false)

const copyToClipboard = async (text) => {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      // Xử lý hạ cấp：Sử dụng truyền thống execCommand phương pháp
      const textArea = document.createElement('textarea')
      textArea.value = text
      textArea.style.position = 'fixed'
      textArea.style.left = '-999999px'
      textArea.style.top = '-999999px'
      document.body.appendChild(textArea)
      textArea.focus()
      textArea.select()
      const successful = document.execCommand('copy')
      document.body.removeChild(textArea)
      if (!successful) throw new Error('execCommand failed')
    }
    isCopied.value = true
    setTimeout(() => {
      isCopied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy: ', err)
  }
}

// Trạng thái mở rộng bảng lý luận
const reasoningActiveKey = ref(['hide'])

// Xử lý thông báo lỗi
const displayError = computed(() => {
  // Đơn giản hóa việc phán đoán lỗi：Chỉ kiểm tra các mã định danh loại lỗi rõ ràng
  return !!(props.message.error_type || props.message.extra_metadata?.error_type)
})

const getErrorMessage = computed(() => {
  // Ưu tiên trực tiếp error_message trường
  if (props.message.error_message) {
    return props.message.error_message
  }

  // Thứ hai từ extra_metadata Nhận thông tin lỗi cụ thể từ
  if (props.message.extra_metadata?.error_message) {
    return props.message.extra_metadata.error_message
  }

  // Đối với các loại lỗi đã biết，Quay lại lời nhắc mặc định
  switch (props.message.error_type) {
    case 'interrupted':
      return 'Việc tạo câu trả lời bị gián đoạn'
    case 'content_guard_blocked':
      return 'Đã phát hiện nội dung nhạy cảm，Đầu ra bị gián đoạn'
    case 'unexpect':
      return 'Ngoại lệ xảy ra trong quá trình tạo'
    case 'agent_error':
      return 'Việc mua lại đại lý không thành công'
    default:
      return null
  }
})

// Giới thiệu tác nhân thông minh store
const agentStore = useAgentStore()
const { availableKnowledgeBases } = storeToRefs(agentStore)
const infoStore = useInfoStore()
const messageAttachments = computed(() =>
  normalizeAttachmentPreviews(props.message.extra_metadata?.attachments)
)
const messageImageMimeType = computed(
  () => inferImageMimeTypeFromBase64(props.message.image_content) || 'image/jpeg'
)

const mentionDisplayLabels = computed(() => buildMentionDisplayLabels(props.mention || {}))

const messageSources = computed(() => {
  if (props.message.type === 'ai') {
    return MessageProcessor.extractSourcesFromMessage(props.message, availableKnowledgeBases.value)
  }
  return { knowledgeChunks: [], webSources: [] }
})

const validToolCalls = computed(() => enrichTaskToolCalls(props.message.tool_calls))

const parsedData = computed(() => {
  const { content, reasoningContent } = MessageProcessor.parseAssistantMessageBody(props.message)
  return {
    content,
    reasoning_content: reasoningContent
  }
})
</script>

<style lang="less" scoped>
.message-box {
  display: inline-block;
  border-radius: 1.5rem;
  margin: 0.8rem 0;
  padding: 0.625rem 1.25rem;
  user-select: text;
  word-break: break-word;
  word-wrap: break-word;
  font-size: 15px;
  line-height: 24px;
  box-sizing: border-box;
  color: var(--gray-10000);
  max-width: 100%;
  position: relative;
  letter-spacing: 0.25px;

  &.human,
  &.sent {
    max-width: 95%;
    color: var(--gray-1000);
    background-color: var(--main-50);
    align-self: flex-end;
    border-radius: 0.5rem;
    padding: 0.5rem 1rem;
  }

  &.assistant,
  &.received,
  &.ai {
    color: initial;
    width: 100%;
    text-align: left;
    margin: 0;
    padding: 0px;
    background-color: transparent;
    border-radius: 0;
  }

  .message-text {
    max-width: 100%;
    margin-bottom: 0;
    white-space: pre-line;
  }

  &.human.has-attachments,
  &.sent.has-attachments {
    margin-bottom: 0.375rem;
  }

  .message-copy-btn {
    cursor: pointer;
    color: var(--gray-400);
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    flex-shrink: 0;

    &:hover {
      color: var(--main-color);
    }

    &.is-copied {
      color: var(--color-success-500);
      opacity: 1;
    }

    &.human-copy {
      position: absolute;
      left: -28px;
      bottom: 8px;
    }
  }

  &:hover {
    .message-copy-btn {
      opacity: 1;
    }
  }

  .message-text-system {
    max-width: 100%;
    margin-bottom: 0;
    white-space: pre-line;
    color: var(--gray-600);
    font-style: italic;
    font-size: 14px;
    padding: 8px 12px;
    background-color: var(--gray-50);
    border-left: 3px solid var(--gray-300);
    border-radius: 4px;
  }

  .err-msg {
    color: var(--color-error-500);
    border: 1px solid currentColor;
    padding: 0.5rem 1rem;
    border-radius: 8px;
    text-align: left;
    background: var(--color-error-50);
    margin-bottom: 10px;
    cursor: pointer;
  }

  .searching-msg {
    color: var(--gray-700);
    animation: colorPulse 1s infinite ease-in-out;
  }

  .reasoning-box {
    margin-top: 10px;
    margin-bottom: 15px;
    border-radius: 8px;
    border: 1px solid var(--gray-150);
    background-color: var(--gray-25);
    overflow: hidden;
    transition: all 0.2s ease;

    :deep(.ant-collapse) {
      background-color: transparent;
      border: none;

      .ant-collapse-item {
        border: none;

        .ant-collapse-header {
          padding: 8px 12px;
          font-size: 14px;
          font-weight: 500;
          color: var(--gray-700);
          transition: all 0.2s ease;

          .ant-collapse-expand-icon {
            color: var(--gray-400);
          }
        }

        .ant-collapse-content {
          border: none;
          background-color: transparent;

          .ant-collapse-content-box {
            padding: 16px;
            background-color: var(--gray-25);
          }
        }
      }
    }

    .reasoning-content {
      font-size: 13px;
      color: var(--gray-800);
      white-space: pre-wrap;
      margin: 0;
      line-height: 1.6;
    }
  }

  .assistant-message {
    width: 100%;
  }

  .error-hint {
    margin: 10px 0;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
    background-color: var(--color-error-50);
    color: var(--color-error-500);
    span {
      line-height: 1.5;
    }
  }

  .status-info {
    display: block;
    background-color: var(--gray-50);
    color: var(--gray-700);
    padding: 10px;
    border-radius: 8px;
    margin-bottom: 10px;
    font-size: 12px;
    font-family: monospace;
    max-height: 200px;
    overflow-y: auto;
  }
}

.human-message-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: flex-end;
  align-self: flex-end;
  max-width: 95%;
  margin-bottom: 0.8rem;
}

.message-attachment-file {
  width: 220px;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.625rem 0.75rem;
  border: 1px solid var(--gray-200);
  border-radius: 0.625rem;
  background: var(--gray-0);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.message-attachment-icon {
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 0.5rem;
  color: var(--main-color);
  background: var(--main-50);
}

.message-attachment-body {
  min-width: 0;
  flex: 1;
}

.message-attachment-name {
  overflow: hidden;
  color: var(--gray-900);
  font-size: 0.875rem;
  line-height: 1.25rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-attachment-meta {
  margin-top: 0.125rem;
  color: var(--gray-500);
  font-size: 0.75rem;
  line-height: 1rem;
}

.retry-hint {
  margin-top: 8px;
  padding: 8px 16px;
  color: var(--gray-600);
  font-size: 14px;
  text-align: left;
}

.retry-link {
  color: var(--color-info-500);
  cursor: pointer;
  margin-left: 4px;

  &:hover {
    text-decoration: underline;
  }
}

.ant-btn-icon-only {
  &:has(.anticon-stop) {
    background-color: var(--color-error-500) !important;

    &:hover {
      background-color: var(--color-error-100) !important;
    }
  }
}

@keyframes colorPulse {
  0% {
    color: var(--gray-700);
  }
  50% {
    color: var(--gray-300);
  }
  100% {
    color: var(--gray-700);
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

// Kiểu tin nhắn đa phương thức
.message-image {
  border-radius: 12px;
  overflow: hidden;
  margin-left: auto;
  /* max-height: 200px; */
  border: 1px solid rgba(255, 255, 255, 0.2);

  img {
    max-width: 100%;
    max-height: 200px;
    object-fit: contain;
    cursor: pointer;
  }
}

.message-md {
  margin: 8px 0;
}

.message-image-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  background: rgba(0, 0, 0, 0.75);
  cursor: zoom-out;
}

.message-image-preview-img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: 4px;
  cursor: zoom-out;
}

.message-image-preview-close {
  position: fixed;
  top: 1.5rem;
  right: 1.5rem;
  width: 2.5rem;
  height: 2.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  color: var(--gray-0);
  background: rgba(255, 255, 255, 0.15);
  cursor: pointer;
  transition: background-color 0.15s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.28);
  }
}
</style>
