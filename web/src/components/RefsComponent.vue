<template>
  <div class="refs" v-if="showRefs">
    <div class="tags">
      <!-- phản hồi -->
      <span
        class="item btn"
        :class="{ disabled: feedbackState.hasSubmitted }"
        @click="likeThisResponse(msg)"
        :title="
          feedbackState.hasSubmitted && feedbackState.rating === 'like' ? 'Đã thích' : 'thích'
        "
      >
        <ThumbsUp size="12" :fill="feedbackState.rating === 'like' ? 'currentColor' : 'none'" />
      </span>
      <span
        class="item btn"
        :class="{ disabled: feedbackState.hasSubmitted }"
        @click="dislikeThisResponse(msg)"
        :title="
          feedbackState.hasSubmitted && feedbackState.rating === 'dislike'
            ? 'Không thích'
            : 'Bấm vào để không thích'
        "
      >
        <ThumbsDown
          size="12"
          :fill="feedbackState.rating === 'dislike' ? 'currentColor' : 'none'"
        />
      </span>
      <!-- Tên mẫu -->
      <span v-if="showKey('model') && getModelName(msg)" class="item" @click="console.log(msg)">
        <Bot size="12" /> {{ getModelName(msg) }}
      </span>
      <!-- Sao chép -->
      <span v-if="showKey('copy')" class="item btn" @click="copyText(msg.content)" title="Sao chép">
        <Check v-if="isCopied" size="12" />
        <Copy v-else size="12" />
      </span>

      <!-- Thử lại -->
      <span
        v-if="showKey('regenerate')"
        class="item btn"
        @click="regenerateMessage()"
        title="tái sinh"
        ><RotateCcw size="12" />
      </span>

      <!-- nút nguồn - sử dụng flex-grow Chiếm không gian còn lại và căn chỉnh sang phải -->
      <div v-if="hasSources && showKey('sources')" class="sources-spacer"></div>
      <span
        v-if="hasSources && showKey('sources')"
        class="item btn sources-btn"
        :class="{ expanded: isSourcesExpanded }"
        @click="toggleSources"
        :title="isSourcesExpanded ? 'Thu gọn chi tiết' : 'Xem chi tiết nguồn'"
      >
        <BookOpen size="12" />
        <span class="sources-label">
          Nguồn
          <template v-if="sourceCount > 0">
            {{ sourceCount }}
          </template>
        </span>
        <ChevronDown :size="12" class="expand-icon" :class="{ rotated: isSourcesExpanded }" />
      </span>
    </div>

    <!-- Bảng chi tiết nguồn -->
    <div v-if="isSourcesExpanded" class="sources-panel-body">
      <KnowledgeSourceSection v-if="knowledgeChunks.length > 0" :chunks="knowledgeChunks" />
      <WebSearchSourceSection v-if="webSources.length > 0" :sources="webSources" />
    </div>
  </div>

  <!-- Dislike reason modal -->
  <a-modal
    v-model:open="dislikeModalVisible"
    title="Hãy cho chúng tôi biết lý do không hài lòng"
    @ok="submitDislikeFeedback"
    @cancel="cancelDislike"
    :confirmLoading="submittingFeedback"
    okText="Gửi"
    cancelText="Hủy bỏ"
  >
    <a-textarea
      v-model:value="dislikeReason"
      :rows="4"
      placeholder="Phản hồi của bạn sẽ giúp chúng tôi cải thiện dịch vụ của mình（Tùy chọn）"
      :maxlength="500"
      show-count
    />
  </a-modal>
</template>

<script setup>
import { ref, computed, reactive, watch } from 'vue'
import { useClipboard } from '@vueuse/core'
import { message as antMessage } from 'ant-design-vue'
import {
  ThumbsUp,
  ThumbsDown,
  Bot,
  Copy,
  Check,
  RotateCcw,
  BookOpen,
  ChevronDown
} from 'lucide-vue-next'
import { agentApi } from '@/apis'
import KnowledgeSourceSection from '@/components/KnowledgeSourceSection.vue'
import WebSearchSourceSection from '@/components/WebSearchSourceSection.vue'

const emit = defineEmits(['retry', 'openRefs'])
const props = defineProps({
  message: Object,
  showRefs: {
    type: [Array, Boolean],
    default: () => false
  },
  isLatestMessage: {
    type: Boolean,
    default: false
  },
  sources: {
    type: Object,
    default: () => ({})
  }
})

const msg = ref(props.message)

// Sources state
const isSourcesExpanded = ref(false)

const knowledgeChunks = computed(() =>
  Array.isArray(props.sources?.knowledgeChunks) ? props.sources.knowledgeChunks : []
)
const webSources = computed(() =>
  Array.isArray(props.sources?.webSources) ? props.sources.webSources : []
)

const hasSources = computed(() => knowledgeChunks.value.length > 0 || webSources.value.length > 0)

const sourceCount = computed(() => knowledgeChunks.value.length + webSources.value.length)

const toggleSources = () => {
  isSourcesExpanded.value = !isSourcesExpanded.value
}

// Feedback state
const feedbackState = reactive({
  hasSubmitted: false,
  rating: null, // 'like' or 'dislike'
  reason: null
})

// Khởi tạo trạng thái phản hồi - từ antMessage.feedback Đọc phản hồi lịch sử
const initFeedbackState = () => {
  if (msg.value?.feedback) {
    feedbackState.hasSubmitted = true
    feedbackState.rating = msg.value.feedback.rating
    feedbackState.reason = msg.value.feedback.reason
  } else {
    feedbackState.hasSubmitted = false
    feedbackState.rating = null
    feedbackState.reason = null
  }
}

// màn hình message prop thay đổi (Dùng để cập nhật trạng thái khi chuyển đổi cuộc trò chuyện)
watch(
  () => props.message,
  () => {
    msg.value = props.message
    initFeedbackState()
  },
  { immediate: true }
)

// Modal state for dislike
const dislikeModalVisible = ref(false)
const dislikeReason = ref('')
const submittingFeedback = ref(false)

// sử dụng useClipboard Thực hiện chức năng sao chép
const { copy, isSupported } = useClipboard()

const showKey = (key) => {
  if (props.showRefs === true) {
    return true
  }
  return props.showRefs.includes(key)
}

// trạng thái sao chép
const isCopied = ref(false)

// độ nét copy phương pháp
const copyText = async (text) => {
  if (isSupported) {
    try {
      await copy(text)
      antMessage.success('Đã sao chép văn bản vào bảng nhớ tạm')
      isCopied.value = true
      setTimeout(() => {
        isCopied.value = false
      }, 2000)
    } catch (error) {
      console.error('Sao chép không thành công:', error)
      antMessage.error('Sao chép không thành công，Vui lòng sao chép thủ công')
    }
  } else {
    console.warn('Trình duyệt không hỗ trợ sao chép tự động')
    antMessage.warning('Trình duyệt không hỗ trợ sao chép tự động，Vui lòng sao chép thủ công')
  }
}

const showRefs = computed(() => {
  // Nếu nó chỉ để hiển thị thông tin mô hình，Không cần kiểm tra trạng thái
  if (props.showRefs && Array.isArray(props.showRefs) && props.showRefs.includes('model')) {
    return true
  }
  // logic gốc
  return (
    (msg.value.role == 'received' || msg.value.role == 'assistant') &&
    msg.value.status == 'finished'
  )
})

// Thêm phương pháp tái sinh
const regenerateMessage = () => {
  emit('retry')
}

// Lấy tên mẫu
const getModelName = (msg) => {
  if (msg.response_metadata?.model_name) {
    return msg.response_metadata.model_name
  }
  return null
}
// Handle like action
const likeThisResponse = async (msg) => {
  if (feedbackState.hasSubmitted) {
    antMessage.info('Bạn đã gửi phản hồi')
    return
  }

  if (!msg?.id) {
    antMessage.error('Không thể gửi phản hồi：tin tứcIDkhông tồn tại')
    console.error('Message object:', msg)
    return
  }

  try {
    submittingFeedback.value = true
    await agentApi.submitMessageFeedback(msg.id, 'like', null)

    feedbackState.hasSubmitted = true
    feedbackState.rating = 'like'

    antMessage.success('Cảm ơn bạn đã phản hồi！')
  } catch (error) {
    console.error('Failed to submit like feedback:', error)
    if (error.message?.includes('already submitted')) {
      antMessage.info('Bạn đã gửi phản hồi')
      feedbackState.hasSubmitted = true
    } else {
      antMessage.error('Không thể gửi phản hồi，Vui lòng thử lại sau')
    }
  } finally {
    submittingFeedback.value = false
  }
}

// Handle dislike action
const dislikeThisResponse = async (msg) => {
  if (feedbackState.hasSubmitted) {
    antMessage.info('Bạn đã gửi phản hồi')
    return
  }

  if (!msg?.id) {
    antMessage.error('Không thể gửi phản hồi：tin tứcIDkhông tồn tại')
    console.error('Message object:', msg)
    return
  }

  // Open modal to get reason
  dislikeModalVisible.value = true
}

// Submit dislike feedback with reason
const submitDislikeFeedback = async () => {
  try {
    submittingFeedback.value = true
    await agentApi.submitMessageFeedback(msg.value.id, 'dislike', dislikeReason.value || null)

    feedbackState.hasSubmitted = true
    feedbackState.rating = 'dislike'
    feedbackState.reason = dislikeReason.value

    dislikeModalVisible.value = false
    dislikeReason.value = ''

    antMessage.success('Cảm ơn bạn đã phản hồi！')
  } catch (error) {
    console.error('Failed to submit dislike feedback:', error)
    if (error.message?.includes('already submitted')) {
      antMessage.info('Bạn đã gửi phản hồi')
      feedbackState.hasSubmitted = true
      dislikeModalVisible.value = false
    } else {
      antMessage.error('Không thể gửi phản hồi，Vui lòng thử lại sau')
    }
  } finally {
    submittingFeedback.value = false
  }
}

// Cancel dislike modal
const cancelDislike = () => {
  dislikeModalVisible.value = false
  dislikeReason.value = ''
}
</script>

<style lang="less" scoped>
.refs {
  display: flex;
  flex-direction: column;
  margin-bottom: 20px;
  margin-top: 10px;
  color: var(--gray-500);
  font-size: 13px;
  gap: 12px;

  .item {
    background: var(--gray-50);
    color: var(--gray-700);
    padding: 6px 8px;
    border-radius: 8px;
    font-size: 13px;
    user-select: none;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    line-height: 1;

    &.btn {
      cursor: pointer;
      &:hover {
        background: var(--gray-100);
      }
      &:active {
        background: var(--gray-200);
      }

      // Disabled state - when feedback has been submitted
      &.disabled {
        &:hover {
          background: var(--gray-50);
        }
      }
    }
  }

  .tags {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    width: 100%;

    .sources-spacer {
      flex-grow: 1;
    }

    .sources-btn {
      margin-left: auto;
      background: var(--gray-50);
      border: 1px solid transparent;
      padding: 6px 10px;

      &:hover {
        background: var(--gray-100);
      }

      &.expanded {
        background: var(--main-50);
        color: var(--main-700);
        border-color: var(--main-100);
      }

      .sources-label {
        font-weight: 500;
        margin-left: 2px;
      }

      .expand-icon {
        margin-left: 4px;
        transition: transform 0.2s ease;

        &.rotated {
          transform: rotate(180deg);
        }
      }
    }
  }

  .sources-panel-body {
    background: var(--gray-25);
    border: 1px solid var(--gray-150);
    border-radius: 8px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    animation: slideDown 0.2s ease-out;
  }
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
