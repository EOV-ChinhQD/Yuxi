<template>
  <!-- Hộp phương thức danh sách phản hồi -->
  <a-modal
    v-model:open="modalVisible"
    title="Chi tiết phản hồi của người dùng"
    width="1200px"
    :footer="null"
  >
    <a-space style="margin-bottom: 16px">
      <a-segmented
        v-model:value="feedbackFilter"
        :options="feedbackOptions"
        @change="loadFeedbacks"
      />
    </a-space>

    <!-- danh sách thẻ -->
    <div v-if="loadingFeedbacks" class="loading-container">
      <a-spin size="large" />
    </div>

    <div v-else class="feedback-cards-container">
      <div v-for="feedback in feedbacks" :key="feedback.id" class="feedback-card">
        <!-- tiêu đề thẻ：Thông tin người dùng và các loại phản hồi -->
        <div class="card-header">
          <div class="user-info">
            <FallbackAvatar
              :src="feedback.avatar"
              :default-src="getFeedbackDefaultAvatarSrc(feedback)"
              :name="feedback.username"
              :seed="feedback.uid || feedback.username"
              kind="user"
              :size="32"
              shape="circle"
              :alt="feedback.username"
              class="user-avatar"
            />
            <div class="user-details">
              <div class="username">{{ feedback.username || 'người dùng không xác định' }}</div>
            </div>
          </div>
          <a-tag
            :color="feedback.rating === 'like' ? 'green' : 'red'"
            class="rating-tag"
            size="small"
          >
            <template #icon>
              <LikeOutlined v-if="feedback.rating === 'like'" />
              <DislikeOutlined v-else />
            </template>
            {{ feedback.rating === 'like' ? 'thích' : 'Bấm vào để không thích' }}
          </a-tag>
        </div>

        <!-- Nội dung thẻ：Thông tin hội thoại、Nội dung tin nhắn và lý do phản hồi -->
        <div class="card-content">
          <!-- Tiêu đề cuộc trò chuyện -->
          <div class="conversation-section" v-if="feedback.conversation_title">
            <div class="conversation-info">
              <div class="info-item">
                <span
                  class="conversation-title"
                  :class="{ collapsed: !expandedStates.get(`${feedback.id}-conversation`) }"
                >
                  Tiêu đề：{{ feedback.conversation_title }}
                </span>
                <a-button
                  v-if="shouldShowConversationExpandButton(feedback.conversation_title)"
                  type="link"
                  size="small"
                  @click="toggleConversationExpand(feedback.id)"
                  class="expand-button-inline"
                >
                  {{ expandedStates.get(`${feedback.id}-conversation`) ? 'đóng' : 'Mở rộng' }}
                </a-button>
              </div>
              <div class="info-item" v-if="!props.agentId">
                <span class="label">đại lý:</span>
                <span class="value">{{ feedback.agent_id }}</span>
              </div>
            </div>
          </div>

          <!-- Nội dung tin nhắn -->
          <div class="message-section">
            <div
              class="message-content"
              :class="{ collapsed: !expandedStates.get(`${feedback.id}-message`) }"
            >
              {{ feedback.message_content }}
            </div>
            <a-button
              v-if="shouldShowExpandButton(feedback.message_content)"
              type="link"
              size="small"
              @click="toggleExpand(feedback.id)"
              class="expand-button"
            >
              {{ expandedStates.get(`${feedback.id}-message`) ? 'đóng' : 'Mở rộng tất cả' }}
            </a-button>
          </div>

          <!-- Lý do phản hồi -->
          <div v-if="feedback.reason" class="reason-section">
            <div class="reason-content">{{ feedback.reason }}</div>
          </div>
        </div>

        <!-- đáy thẻ：thông tin thời gian -->
        <div class="card-footer">
          <div class="time-info">
            <ClockCircleOutlined />
            <span>{{ formatFullDate(feedback.created_at) }}</span>
          </div>
        </div>
      </div>

      <!-- Trạng thái trống -->
      <div v-if="feedbacks.length === 0" class="empty-state">
        <a-empty description="Chưa có dữ liệu phản hồi" />
      </div>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { LikeOutlined, DislikeOutlined, ClockCircleOutlined } from '@ant-design/icons-vue'
import { dashboardApi } from '@/apis/dashboard_api'
import { formatFullDateTime } from '@/utils/time'
import { generatePixelAvatar } from '@/utils/pixelAvatar'
import FallbackAvatar from '@/components/common/FallbackAvatar.vue'

// cấu hình không đổi
const CONFIG = {
  MESSAGE_MAX_LINES: 8, // Số dòng tin nhắn tối đa được hiển thị
  CONVERSATION_MAX_LINES: 2, // Số dòng tối đa được hiển thị cho tiêu đề cuộc hội thoại
  CONVERSATION_MAX_CHARS: 60, // Ngưỡng ký tự tiêu đề cuộc hội thoại
  AVG_CHARS_PER_LINE: 30 // Số ký tự trung bình trên mỗi dòng（Hỗn hợp tiếng Trung và tiếng Anh）
}

// Props
const props = defineProps({
  agentId: {
    type: String,
    default: null
  }
})

// Trạng thái phương thức
const modalVisible = ref(false)

// Dữ liệu liên quan đến phản hồi
const feedbacks = ref([])
const loadingFeedbacks = ref(false)
const feedbackFilter = ref('all')
const feedbackOptions = [
  { label: 'Tất cả', value: 'all' },
  { label: 'thích', value: 'like' },
  { label: 'Bấm vào để không thích', value: 'dislike' }
]

// Mở rộng bản đồ tiểu bang（sử dụng Map Tránh sửa đổi trực tiếp các đối tượng）
const expandedStates = ref(new Map())

// Hiển thị hộp phương thức
const show = () => {
  modalVisible.value = true
  loadFeedbacks()
}

// Hiển thị các phương thức cho thành phần cha mẹ
defineExpose({ show })

// Hàm trợ giúp đếm dòng văn bản（Ước tính）
const estimateLines = (text) => {
  if (!text) return 0
  return Math.ceil(text.length / CONFIG.AVG_CHARS_PER_LINE)
}

// Xác định xem có hiển thị nút mở rộng hay không
const shouldShowExpandButton = (content) => {
  return estimateLines(content) > CONFIG.MESSAGE_MAX_LINES
}

// Xác định xem tiêu đề cuộc trò chuyện có cần nút mở rộng hay không
const shouldShowConversationExpandButton = (title) => {
  if (!title) return false
  return title.length > CONFIG.CONVERSATION_MAX_CHARS
}

// Chuyển đổi để mở rộng/Trạng thái thu gọn
const toggleExpand = (feedbackId) => {
  const key = `${feedbackId}-message`
  const currentState = expandedStates.value.get(key) ?? false
  expandedStates.value.set(key, !currentState)
}

// Chuyển đổi tiêu đề cuộc trò chuyện để mở rộng/Trạng thái thu gọn
const toggleConversationExpand = (feedbackId) => {
  const key = `${feedbackId}-conversation`
  const currentState = expandedStates.value.get(key) ?? false
  expandedStates.value.set(key, !currentState)
}

// Tải danh sách phản hồi
const loadFeedbacks = async () => {
  loadingFeedbacks.value = true
  try {
    const params = {
      rating: feedbackFilter.value === 'all' ? undefined : feedbackFilter.value,
      agent_id: props.agentId || undefined
    }

    const response = await dashboardApi.getFeedbacks(params)
    feedbacks.value = response
    // Đặt lại trạng thái mở rộng
    expandedStates.value.clear()
  } catch (error) {
    console.error('Không tải được danh sách phản hồi:', error)
    message.error('Không tải được danh sách phản hồi，Vui lòng thử lại sau')
    feedbacks.value = []
  } finally {
    loadingFeedbacks.value = false
  }
}

const getFeedbackDefaultAvatarSrc = (feedback) =>
  feedback.uid ? generatePixelAvatar(feedback.uid) : ''

// Định dạng ngày hoàn thành
const formatFullDate = (dateString) => formatFullDateTime(dateString)

// màn hình agentId thay đổi，Tải lại dữ liệu
watch(
  () => props.agentId,
  () => {
    if (modalVisible.value) {
      loadFeedbacks()
    }
  }
)
</script>

<style scoped lang="less">
// Trạng thái tải
.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40px 0;
}

// hộp đựng thẻ - Bố cục nhiều cột thích ứng
.feedback-cards-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
  max-height: 600px;
  overflow-y: auto;
  padding-right: 8px;

  // Kiểu thanh cuộn
  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: var(--gray-100);
    border-radius: 3px;
  }

  &::-webkit-scrollbar-thumb {
    background: var(--gray-300);
    border-radius: 3px;

    &:hover {
      background: var(--gray-400);
    }
  }
}

// thẻ phản hồi - Thiết kế nhỏ gọn
.feedback-card {
  background: var(--gray-0);
  border: 1px solid var(--gray-100);
  border-radius: 8px;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;

  &:hover {
    border-color: var(--main-color);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
}

// tiêu đề thẻ - Nhỏ gọn
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--gray-100);
  background: var(--gray-25);
  border-radius: 8px 8px 0 0;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-avatar {
  flex-shrink: 0;
}

.user-details {
  .username {
    font-weight: 500;
    color: var(--gray-900);
    font-size: 13px;
    line-height: 1.2;
  }
}

.rating-tag {
  font-weight: 500;
  font-size: 11px;
}

// Nội dung thẻ - Nhỏ gọn
.card-content {
  padding: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-section {
  flex: 1;
}

.message-content {
  background: var(--gray-50);
  padding: 10px;
  border-radius: 6px;
  // border-left: 3px solid var(--main-color);
  font-size: 13px;
  line-height: 1.4;
  color: var(--gray-800);
  word-break: break-word;
  overflow: hidden;
  transition: max-height 0.3s ease;
}

.message-content.collapsed {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 8;
  line-clamp: 8;
  overflow: hidden;
  text-overflow: ellipsis;
}

.expand-button {
  padding: 0;
  height: auto;
  font-size: 12px;
  margin-top: 8px;
  color: var(--main-color);
}

.conversation-section {
  margin: 0;
}

.conversation-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item {
  display: flex;
  align-items: center;
  font-size: 12px;

  .label {
    color: var(--gray-600);
    margin-right: 6px;
    min-width: 50px;
    font-weight: 500;
  }

  .value {
    color: var(--gray-800);
    font-weight: 400;
    word-break: break-all;
  }

  // Kiểu tiêu đề cuộc trò chuyện（hiển thị độc lập）
  .conversation-title {
    display: block;
    color: var(--gray-700);
    font-size: 13px;
    font-weight: 500;
    line-height: 1.4;
    word-break: break-word;
    transition: all 0.3s ease;

    &.collapsed {
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
      line-clamp: 2;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }

  // Chứa tiêu đề cuộc trò chuyện info-item Thay đổi bố cục dọc
  &:has(.conversation-title) {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
}

.expand-button-inline {
  padding: 0;
  height: auto;
  font-size: 11px;
  color: var(--main-color);
  align-self: flex-start;
}

.reason-section {
  margin: 0;
}

.reason-content {
  background: var(--color-warning-50);
  padding: 10px;
  border-radius: 6px;
  border-left: 3px solid var(--color-warning-500);
  font-size: 13px;
  line-height: 1.4;
  color: var(--gray-800);
  word-break: break-word;
}

// đáy thẻ - Nhỏ gọn
.card-footer {
  padding: 8px 16px;
  border-top: 1px solid var(--gray-100);
  background: var(--gray-25);
  border-radius: 0 0 8px 8px;
}

.time-info {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--gray-500);
}

// Trạng thái trống
.empty-state {
  grid-column: 1 / -1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 60px 0;
}

// Thiết kế đáp ứng
@media (max-width: 768px) {
  .feedback-cards-container {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .card-header {
    padding: 10px 12px;
    gap: 8px;
  }

  .card-content {
    padding: 12px;
    gap: 10px;
  }

  .card-footer {
    padding: 6px 12px;
  }
}

@media (max-width: 480px) {
  .feedback-cards-container {
    gap: 8px;
  }

  .card-header {
    padding: 8px 10px;
  }

  .card-content {
    padding: 10px;
    gap: 8px;
  }

  .message-content,
  .reason-content {
    padding: 8px;
    font-size: 12px;
  }

  .info-item {
    font-size: 11px;
  }
}
</style>
