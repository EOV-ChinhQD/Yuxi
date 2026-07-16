<template>
  <div class="chat-container">
    <div
      class="chat"
      :class="{
        'has-file-panel': isFilePanelOpen,
        'is-resizing-file-panel': isResizing
      }"
      :style="{ '--file-panel-width': filePanelWidthStyle }"
    >
      <div class="chat-header" :class="{ 'has-active-thread': !!currentChatId }">
        <div class="header__left">
          <slot name="header-left"></slot>
          <div
            v-if="currentThread?.title && currentThread.title !== 'New Chat'"
            class="conversation-title"
          >
            {{ currentThread.title }}
          </div>
        </div>
        <div class="header__right">
          <button
            v-if="showStateEntry"
            type="button"
            class="agent-nav-btn agent-state-btn state-entry-btn"
            :class="{ active: statePanelOpen }"
            title="View Status"
            :aria-expanded="statePanelOpen"
            aria-controls="agent-state-panel"
            @click.stop="toggleStatePanel"
          >
            <LayoutList size="16" class="nav-btn-icon" />
            <span class="hide-text">Status</span>
          </button>
          <button
            v-if="showFileEntry && !isFilePanelOpen"
            type="button"
            class="agent-nav-btn agent-state-btn file-entry-btn"
            title="View Files"
            :aria-expanded="isFilePanelOpen"
            aria-controls="agent-file-panel"
            @click.stop="toggleAgentPanel"
          >
            <FolderKanban size="16" class="nav-btn-icon" />
            <span class="hide-text">Files</span>
          </button>
          <slot
            name="header-right"
            :side-active="sideActive"
            :is-file-panel-open="isFilePanelOpen"
            :is-state-panel-open="statePanelOpen"
            :has-active-thread="!!currentChatId"
            :toggle-agent-panel="toggleAgentPanel"
          ></slot>
        </div>
      </div>

      <div
        ref="chatContentContainerRef"
        class="chat-content-container"
        :class="{
          'has-file-panel': isFilePanelOpen,
          'has-state-panel': statePanelDocked,
          'has-floating-state-panel': statePanelFloating
        }"
      >
        <!-- Main Chat Area -->
        <div class="chat-main" ref="chatMainRef">
          <div class="chat-box">
            <template v-for="row in conversationRows" :key="row.key">
              <div v-if="row.type === 'conversation'" class="conv-box">
                <template
                  v-for="(displayItem, itemIndex) in row.displayItems"
                  :key="displayItem.key"
                >
                  <AgentMessageComponent
                    v-if="displayItem.type === 'message'"
                    :message="displayItem.message"
                    :is-processing="isDisplayMessageProcessing(row.conv, displayItem)"
                    :show-refs="showMsgRefs(displayItem.message, row.conv)"
                    :hide-tool-calls="true"
                    :mention="mentionConfig"
                    @retry="retryMessage(displayItem.message)"
                  >
                  </AgentMessageComponent>
                  <ToolCallsGroupComponent
                    v-else
                    :tool-calls="displayItem.toolCalls"
                    :is-active="isToolGroupActive(row.conv, itemIndex, row.displayItems)"
                  />
                </template>
                <AgentArtifactsCard
                  v-if="shouldShowArtifacts(row.conv)"
                  :artifacts="currentArtifacts"
                  :thread-id="currentChatId"
                  @saved="handleArtifactSaved"
                  @open-preview="openPanelPreview"
                />
                <!-- Hiển thị mô hình được sử dụng cho tin nhắn cuối cùng của cuộc trò chuyện -->
                <RefsComponent
                  v-if="shouldShowRefs(row.conv)"
                  :message="getLastMessage(row.conv)"
                  :show-refs="['model', 'copy', 'sources']"
                  :is-latest-message="false"
                  :sources="getConversationSources(row.conv)"
                />
              </div>
              <div v-else class="chat-inline-notice">
                <span>{{ row.notice.message }}</span>
              </div>
            </template>

            <!-- Trạng thái tải trong khi tạo - Hỗ trợ chính thức cho trò chuyện chính vàresumeQuy trình -->
            <div class="generating-status" v-if="isReplyLoading && conversations.length > 0">
              <div class="generating-indicator">
                <div class="loading-dots">
                  <div></div>
                  <div></div>
                  <div></div>
                </div>
                <span class="generating-text">{{ replyLoadingText }}</span>
              </div>
            </div>
          </div>
          <div class="bottom" :class="{ 'start-screen': !conversations.length }">
            <!-- Cửa sổ phê duyệt thủ công - đặt trên trên ô nhập -->
            <HumanApprovalModal
              :visible="currentApprovalModalVisible"
              :questions="currentApprovalQuestions"
              @submit="handleQuestionSubmit"
              @cancel="handleQuestionCancel"
            />

            <div class="message-input-wrapper">
              <!-- Trạng thái tải: đang tải tin -->
              <div v-if="isLoadingMessages" class="chat-loading">
                <div class="loading-spinner"></div>
                <span>Loading messages...</span>
              </div>

              <!-- Khu vực chào hỏi - phía trên hộp nhập -->
              <div v-if="!conversations.length" class="chat-greeting-input">
                <h1>{{ randomGreeting }}</h1>
              </div>

              <AgentInputArea
                v-model="userInput"
                :is-loading="isProcessing"
                :disabled="!currentAgent"
                :send-button-disabled="isSendButtonDisabled"
                :mention="mentionConfig"
                :thread-id="currentChatId"
                :supports-file-upload="supportsFileUpload"
                :attachments="currentPendingThreadAttachments"
                @send="handleSendOrStop"
                @upload-attachment="handleAttachmentUpload"
                @remove-attachment="handleAttachmentRemove"
              >
                <template #actions-left-extra>
                  <slot name="input-actions-left" :has-active-thread="!!currentChatId"></slot>
                </template>
                <template #actions-right-extra>
                  <div class="input-model-selector">
                    <ModelSelectorComponent
                      :model_spec="currentModelSpec"
                      size="nano"
                      display-name="mini"
                      placeholder="Select Model"
                      @select-model="handleModelSelect"
                    />
                  </div>
                  <slot name="input-actions-right" :has-active-thread="!!currentChatId"></slot>
                </template>
              </AgentInputArea>

              <AttachmentTmpUploadModal
                v-model:open="attachmentUploadModalOpen"
                :thread-id="currentChatId"
                :ensure-thread="ensureAttachmentThread"
                :initial-files="attachmentInitialFiles"
                :initial-files-key="attachmentInitialFilesKey"
                @added="handleTmpAttachmentsAdded"
              />

              <div class="bottom-actions" v-if="conversations.length > 0">
                <p class="note">
                  Current Agent: {{ currentThreadAgentName }}; please note to verify the reliability
                  of the content
                </p>
              </div>
            </div>
          </div>
        </div>

        <div
          id="agent-state-panel"
          class="side-panel side-panel--state"
          :class="{
            'is-visible': statePanelOpen,
            'is-docked': statePanelDocked,
            'is-floating': statePanelFloating
          }"
          :style="{
            flexBasis: statePanelDocked ? `${statePanelDockWidth}px` : '0px'
          }"
        >
          <div v-if="statePanelOpen" class="state-panel">
            <div class="side-panel__header state-panel-header">
              <span class="state-panel-title">Status</span>
              <div class="state-panel-header-actions">
                <span class="state-panel-summary">{{ stateSummaryLabel }}</span>
                <button
                  type="button"
                  class="state-refresh-btn"
                  title="Refresh Status"
                  :disabled="isRefreshingState"
                  @click.stop="handleAgentStateRefresh()"
                >
                  <RefreshCw :size="14" :class="{ 'is-spinning': isRefreshingState }" />
                </button>
              </div>
            </div>

            <div class="state-panel-body">
              <section
                v-if="currentTokenUsage"
                class="state-section"
                :class="{ 'is-collapsed': !isStateSectionExpanded('tokenUsage') }"
                aria-label="Context Usage"
              >
                <button
                  type="button"
                  class="state-section-header"
                  :aria-expanded="isStateSectionExpanded('tokenUsage')"
                  aria-controls="state-section-token-usage"
                  @click="toggleStateSection('tokenUsage')"
                >
                  <span class="state-section-label">
                    <span class="state-section-title">Context Usage</span>
                    <ChevronDown
                      :size="15"
                      class="state-section-chevron"
                      :class="{ 'is-collapsed': !isStateSectionExpanded('tokenUsage') }"
                    />
                  </span>
                  <span class="state-section-meta">
                    {{ tokenUsageHeaderPercentLabel }}
                  </span>
                </button>
                <div
                  v-show="isStateSectionExpanded('tokenUsage')"
                  id="state-section-token-usage"
                  class="state-section-content"
                >
                  <div class="token-usage-content">
                    <div class="token-usage-stack">
                      <div class="token-usage-stack-head">
                        <span>Current Context</span>
                        <strong>{{ tokenUsageStackHeadLabel }}</strong>
                      </div>
                      <div class="token-usage-stack-track" aria-label="Token Composition">
                        <div
                          v-for="segment in tokenUsageBarSegments"
                          :key="segment.key"
                          class="token-usage-stack-segment"
                          :class="segment.tone"
                          :style="{ width: segment.percent }"
                          :title="`${segment.label}: ${segment.valueLabel}`"
                        ></div>
                      </div>
                      <div class="token-usage-stack-legend">
                        <span
                          v-for="segment in tokenUsageSegments"
                          :key="segment.key"
                          class="token-usage-stack-legend-item"
                        >
                          <i :class="segment.tone"></i>
                          {{ segment.label }} {{ segment.valueLabel }}
                        </span>
                      </div>
                    </div>

                    <div v-if="tokenUsageMetaRows.length" class="token-usage-breakdown">
                      <div
                        v-for="item in tokenUsageMetaRows"
                        :key="item.key"
                        class="token-usage-breakdown-row"
                      >
                        <span>{{ item.label }}</span>
                        <strong>{{ item.value }}</strong>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              <section
                v-if="currentTodos.length"
                class="state-section"
                :class="{ 'is-collapsed': !isStateSectionExpanded('todos') }"
              >
                <button
                  type="button"
                  class="state-section-header"
                  :aria-expanded="isStateSectionExpanded('todos')"
                  aria-controls="state-section-todos"
                  @click="toggleStateSection('todos')"
                >
                  <span class="state-section-label">
                    <span class="state-section-title">To-do</span>
                    <ChevronDown
                      :size="15"
                      class="state-section-chevron"
                      :class="{ 'is-collapsed': !isStateSectionExpanded('todos') }"
                    />
                  </span>
                  <span v-if="totalTodoCount" class="state-section-meta">
                    {{ completedTodoCount }}/{{ totalTodoCount }} · {{ todoProgress }}%
                  </span>
                </button>
                <div
                  v-show="isStateSectionExpanded('todos')"
                  id="state-section-todos"
                  class="state-section-content"
                >
                  <div class="todo-panel-list">
                    <div
                      v-for="(todo, index) in currentTodos"
                      :key="`${todo.fullContent}-${index}`"
                      class="todo-item"
                    >
                      <div class="todo-item-icon" :class="todo.status || 'unknown'">
                        <CheckCircleOutlined v-if="todo.status === 'completed'" />
                        <SyncOutlined v-else-if="todo.status === 'in_progress'" spin />
                        <ClockCircleOutlined v-else-if="todo.status === 'pending'" />
                        <CloseCircleOutlined v-else-if="todo.status === 'cancelled'" />
                        <QuestionCircleOutlined v-else />
                      </div>
                      <div class="todo-item-body">
                        <span class="todo-item-text" :title="todo.fullContent">
                          {{ todo.displayContent }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              <section
                v-if="currentStateFiles.length"
                class="state-section"
                :class="{ 'is-collapsed': !isStateSectionExpanded('files') }"
              >
                <button
                  type="button"
                  class="state-section-header"
                  :aria-expanded="isStateSectionExpanded('files')"
                  aria-controls="state-section-files"
                  @click="toggleStateSection('files')"
                >
                  <span class="state-section-label">
                    <span class="state-section-title">Attachments/Files</span>
                    <ChevronDown
                      :size="15"
                      class="state-section-chevron"
                      :class="{ 'is-collapsed': !isStateSectionExpanded('files') }"
                    />
                  </span>
                  <span class="state-section-meta">{{ currentStateFiles.length }}</span>
                </button>
                <div
                  v-show="isStateSectionExpanded('files')"
                  id="state-section-files"
                  class="state-section-content"
                >
                  <div class="state-list">
                    <div v-for="file in currentStateFiles" :key="file.key" class="state-list-item">
                      <FileTypeIcon
                        :name="file.name || file.path"
                        :size="18"
                        class="state-list-item-icon"
                      />
                      <div class="state-list-item-body">
                        <div class="state-list-item-title">{{ file.name }}</div>
                        <div class="state-list-item-meta">{{ file.meta || file.path }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              <section
                v-if="currentArtifactFiles.length"
                class="state-section"
                :class="{ 'is-collapsed': !isStateSectionExpanded('artifacts') }"
              >
                <button
                  type="button"
                  class="state-section-header"
                  :aria-expanded="isStateSectionExpanded('artifacts')"
                  aria-controls="state-section-artifacts"
                  @click="toggleStateSection('artifacts')"
                >
                  <span class="state-section-label">
                    <span class="state-section-title">Artifacts</span>
                    <ChevronDown
                      :size="15"
                      class="state-section-chevron"
                      :class="{ 'is-collapsed': !isStateSectionExpanded('artifacts') }"
                    />
                  </span>
                  <span class="state-section-meta">{{ currentArtifactFiles.length }}</span>
                </button>
                <div
                  v-show="isStateSectionExpanded('artifacts')"
                  id="state-section-artifacts"
                  class="state-section-content"
                >
                  <div class="state-list">
                    <button
                      v-for="file in currentArtifactFiles"
                      :key="file.path"
                      type="button"
                      class="state-list-item state-list-item--button"
                      :title="`Open ${file.name}`"
                      @click="openPanelPreview(file)"
                    >
                      <FileTypeIcon
                        :name="file.name || file.path"
                        :size="18"
                        class="state-list-item-icon"
                      />
                      <div class="state-list-item-body">
                        <div class="state-list-item-title">{{ file.name }}</div>
                        <div class="state-list-item-meta">{{ file.meta }}</div>
                      </div>
                    </button>
                  </div>
                </div>
              </section>

              <section
                v-if="displaySubagentRuns.length"
                class="state-section"
                :class="{ 'is-collapsed': !isStateSectionExpanded('subagents') }"
              >
                <button
                  type="button"
                  class="state-section-header"
                  :aria-expanded="isStateSectionExpanded('subagents')"
                  aria-controls="state-section-subagents"
                  @click="toggleStateSection('subagents')"
                >
                  <span class="state-section-label">
                    <span class="state-section-title">Sub-agents</span>
                    <ChevronDown
                      :size="15"
                      class="state-section-chevron"
                      :class="{ 'is-collapsed': !isStateSectionExpanded('subagents') }"
                    />
                  </span>
                  <span class="state-section-meta">{{ displaySubagentRuns.length }}</span>
                </button>
                <div
                  v-show="isStateSectionExpanded('subagents')"
                  id="state-section-subagents"
                  class="state-section-content"
                >
                  <div class="state-list">
                    <div
                      v-for="(run, index) in displaySubagentRuns"
                      :key="run.id || `${run.subagent_slug || 'subagent'}-${index}`"
                      class="state-list-item"
                      :class="{ 'is-clickable': run.child_thread_id }"
                      @click="run.child_thread_id && openSubagentThread(run)"
                    >
                      <FallbackAvatar
                        class="state-subagent-icon"
                        :src="getSubagentIconSrc(run)"
                        :default-src="getSubagentDefaultIconSrc(run)"
                        :name="getSubagentRunName(run)"
                        :seed="run.subagent_slug || getSubagentRunName(run)"
                        kind="agent"
                        :size="28"
                        shape="rounded"
                        :alt="`${getSubagentRunName(run)} Icon`"
                      />
                      <div class="state-list-item-body">
                        <div class="state-list-item-title state-subagent-title">
                          <span>{{ getSubagentRunName(run) }}</span>
                          <CheckCircleOutlined
                            v-if="run.status === 'completed'"
                            class="state-subagent-status-icon state-subagent-completed-icon"
                          />
                          <CloseCircleOutlined
                            v-else-if="run.status === 'failed'"
                            class="state-subagent-status-icon state-subagent-failed-icon"
                          />
                          <SyncOutlined
                            v-else-if="run.status === 'running'"
                            spin
                            class="state-subagent-status-icon state-subagent-running-icon"
                          />
                        </div>
                        <div class="state-list-item-meta">
                          {{ run.description || getSubagentRunMeta(run) }}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              <div v-if="!hasVisibleStateSections" class="state-panel-empty">No status updates</div>
            </div>
          </div>
        </div>
      </div>

      <div
        id="agent-file-panel"
        class="side-panel side-panel--file"
        ref="panelWrapperRef"
        :class="{
          'is-visible': isFilePanelOpen,
          'no-transition': isResizing
        }"
        :style="{
          width: filePanelWidthStyle
        }"
      >
        <AgentPanel
          v-if="isFilePanelOpen"
          :agent-state="currentAgentState"
          :thread-id="currentChatId"
          :panel-ratio="panelRatio"
          :preview-tabs="agentPanelPreviewTabs"
          :active-preview-path="agentPanelActivePreviewPath"
          :view-mode="agentPanelViewMode"
          @close="closeFilePanel"
          @refresh="handleAgentStateRefresh"
          @resize="handlePanelResize"
          @resizing="handleResizingChange"
          @open-preview="openPanelPreview"
          @activate-preview="activatePanelPreview"
          @close-preview-tab="closePanelPreviewTab"
          @close-preview-path="closePanelPreviewPath"
          @view-mode-change="setAgentPanelViewMode"
        />
      </div>
    </div>

    <SubagentThreadModal
      v-model:open="subagentThreadModal.open"
      :child-thread-id="subagentThreadModal.childThreadId"
      :run-id="activeSubagentThreadRunId"
      :run-status="activeSubagentThreadRunStatus"
      :subagent-name="activeSubagentThreadName"
      :subagent-avatar="activeSubagentThreadAvatar"
      :subagent-default-avatar="activeSubagentThreadDefaultAvatar"
      :ongoing-messages="activeSubagentThreadOngoingMessages"
      :is-streaming="activeSubagentThreadIsStreaming"
    />
  </div>
</template>

<script setup>
import {
  ref,
  reactive,
  onMounted,
  watch,
  nextTick,
  computed,
  provide,
  onUnmounted,
  onActivated,
  onDeactivated
} from 'vue'
import { message } from 'ant-design-vue'
import { ChevronDown, FolderKanban, LayoutList, RefreshCw } from 'lucide-vue-next'
import { formatFileSize } from '@/utils/file_utils'
import FileTypeIcon from '@/components/common/FileTypeIcon.vue'
import { generatePixelAvatar } from '@/utils/pixelAvatar'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
  SyncOutlined
} from '@ant-design/icons-vue'
import AgentInputArea from '@/components/AgentInputArea.vue'
import ModelSelectorComponent from '@/components/ModelSelectorComponent.vue'
import AgentMessageComponent from '@/components/AgentMessageComponent.vue'
import RefsComponent from '@/components/RefsComponent.vue'
import ToolCallsGroupComponent from '@/components/ToolCallsGroupComponent.vue'
import { handleChatError, handleValidationError } from '@/utils/errorHandler'
import { ScrollController } from '@/utils/scrollController'
import { AgentValidator } from '@/utils/agentValidator'
import { useAgentStore } from '@/stores/agent'
import { useChatThreadsStore } from '@/stores/chatThreads'
import { useChatUIStore } from '@/stores/chatUI'
import { useConfigStore } from '@/stores/config'
import { storeToRefs } from 'pinia'
import { MessageProcessor } from '@/utils/messageProcessor'
import { agentApi, threadApi } from '@/apis'
import HumanApprovalModal from '@/components/HumanApprovalModal.vue'
import { useApproval } from '@/composables/useApproval'
import { useAgentThreadState } from '@/composables/useAgentThreadState'
import { useAgentRunStream } from '@/composables/useAgentRunStream'
import { useAgentStreamHandler } from '@/composables/useAgentStreamHandler'
import { useStreamSmoother } from '@/composables/useStreamSmoother'
import { useAgentMentionConfig } from '@/composables/useAgentMentionConfig'
import AgentArtifactsCard from '@/components/AgentArtifactsCard.vue'
import AgentPanel from '@/components/AgentPanel.vue'
import AttachmentTmpUploadModal from '@/components/AttachmentTmpUploadModal.vue'
import SubagentThreadModal from '@/components/SubagentThreadModal.vue'
import FallbackAvatar from '@/components/common/FallbackAvatar.vue'
import { enrichTaskToolCalls, parseToolCallArgs } from '@/components/ToolCallingResult/toolRegistry'
import { getConversationDisplayItems } from '@/utils/messageGrouping'
import { makeChildThreadId } from '@/utils/subagentThread'

// ==================== PROPS & EMITS ====================
const props = defineProps({
  agentId: { type: String, default: '' },
  singleMode: { type: Boolean, default: true },
  sendDisabled: { type: Boolean, default: false }
})
const emit = defineEmits(['thread-change'])

// ==================== STORE MANAGEMENT ====================
const agentStore = useAgentStore()
const chatThreadsStore = useChatThreadsStore()
const chatUIStore = useChatUIStore()
const configStore = useConfigStore()
const { agents, selectedAgentId, agentConfig, configurableItems, availableKnowledgeBases } =
  storeToRefs(agentStore)
const { threads, currentThreadId, currentThread } = storeToRefs(chatThreadsStore)

// ==================== LOCAL CHAT & UI STATE ====================
const userInput = ref('')
const sendCooldownActive = ref(false)
let sendCooldownTimer = null
// Predefined greeting texts
const greetingMessages = [
  '👋 Hello, how can I help you today?',
  '👋 Hi! What would you like to talk about?',
  '👋 Hey, is there anything I can help you with?',
  '👋 Welcome! What topic shall we discuss today?',
  '👋 Hello, I am at your service!'
]

// Chọn ngẫu nhiên một văn bản chào hỏi
const randomGreeting = greetingMessages[Math.floor(Math.random() * greetingMessages.length)]

// Trạng thái nghiệp vụ (giữ lại trong thành phần)）
const chatState = reactive({
  currentThreadId: null,
  // VớithreadIdTrạng thái chuỗi làm khóa
  threadStates: {},
  // Ghi lại trong thời gian luồng, cha task Gọi công cụ id → Trợ lý thông minh con child_thread_id（Khi chạy lần đầu, giao diện không thể suy luận điều này id）
  subagentThreadByToolCall: {}
})
const recordSubagentThread = (toolCallId, childThreadId) => {
  if (!toolCallId || !childThreadId) return
  if (chatState.subagentThreadByToolCall[toolCallId] === childThreadId) return
  chatState.subagentThreadByToolCall[toolCallId] = childThreadId
}
const getSubagentThreadIdByToolCall = (toolCallId) =>
  (toolCallId && chatState.subagentThreadByToolCall[String(toolCallId)]) || ''
const setCurrentThreadId = (threadId) => {
  chatState.currentThreadId = threadId || null
  chatThreadsStore.setCurrentThreadId(threadId || null)
}
const streamSmoother = useStreamSmoother({
  getThreadState: (threadId) => chatState.threadStates[threadId] || null
})
const { getThreadState, resetOnGoingConv, stopThreadStream } = useAgentThreadState({
  chatState,
  getCurrentThreadId: () => chatState.currentThreadId,
  onStopThread: (threadId) => streamSmoother.flushThread(threadId),
  onBeforeResetThread: (threadId) => streamSmoother.resetThread(threadId),
  onBeforeCleanupThread: (threadId) => streamSmoother.resetThread(threadId)
})

// Trạng thái thông báo, tệp đính kèm và gợi ý ở cấp thành phần
const threadMessages = ref({})
const threadFilesMap = ref({})
const threadAttachmentsMap = ref({})
const attachmentUploadModalOpen = ref(false)
const attachmentInitialFiles = ref([])
const attachmentInitialFilesKey = ref(0)
const isRefreshingState = ref(false)
const collapsedStateSections = reactive({
  tokenUsage: false,
  todos: false,
  files: false,
  artifacts: false,
  subagents: false
})
const threadConfigNoticeMap = ref({})
const threadPendingConfigNoticeMap = ref({})
const threadConfigSnapshotMap = ref({})
const configNoticeSyncDepth = ref(0)
const configNoticeScrollVersion = ref(0)

// Địa phương UI Trạng thái (chỉ sử dụng trong thành phần này)）
const localUIState = reactive({
  chatMainWidth: typeof window !== 'undefined' ? window.innerWidth : 0,
  chatContentWidth: typeof window !== 'undefined' ? window.innerWidth : 0
})

// Agent Panel State
const isFilePanelOpen = ref(false)
const statePanelOpen = ref(false)
const sideActive = computed(() => {
  if (isFilePanelOpen.value) return 'file'
  if (statePanelOpen.value) return 'state'
  return ''
})
const isResizing = ref(false)
const defaultPanelRatio = 0.3
const previewPanelRatio = 0.65
const minPanelRatio = 0.25
const maxPanelRatio = 0.75
const minChatMainWidth = 350
const filePanelGapWidth = 0
const mobilePanelBreakpoint = 768
const statePanelDockWidth = 340
const statePanelDockMinChatWidth = 800
const panelRatio = ref(defaultPanelRatio) // Tỷ lệ chiều rộng bảng điều khiển (0-1)
const filePanelDragWidth = ref(null)
const agentPanelPreviewTabs = ref([])
const agentPanelActivePreviewPath = ref('')
const agentPanelViewMode = ref('tree')
const chatContentContainerRef = ref(null)
const panelWrapperRef = ref(null) // Thao tác trực tiếp DOM
const TODO_NAME_MAX_LENGTH = 20
let resizeStartX = 0
let resizeStartWidth = 0
let panelContainerWidth = 0
let streamingStateRefreshTimer = null

const formatTodoName = (content) => {
  return Array.from(String(content || ''))
    .slice(0, TODO_NAME_MAX_LENGTH)
    .join('')
}

const getPanelContainerWidth = () => {
  const container = chatContentContainerRef.value || panelWrapperRef.value?.parentElement
  return container?.clientWidth || (typeof window !== 'undefined' ? window.innerWidth : 0)
}

const getFilePanelMaxWidth = (containerWidth = getPanelContainerWidth()) => {
  if (!containerWidth) return 0
  if (containerWidth <= mobilePanelBreakpoint) return Math.max(0, containerWidth - 16)
  return Math.max(0, containerWidth - minChatMainWidth - filePanelGapWidth)
}

const getFilePanelMinWidth = (containerWidth, maxWidth = getFilePanelMaxWidth(containerWidth)) => {
  const preferredMinWidth = containerWidth <= mobilePanelBreakpoint ? 280 : 320
  return Math.min(preferredMinWidth, maxWidth)
}

const getMaxPanelRatio = (containerWidth = getPanelContainerWidth()) => {
  if (!containerWidth) return maxPanelRatio
  return Math.max(
    minPanelRatio,
    Math.min(maxPanelRatio, getFilePanelMaxWidth(containerWidth) / containerWidth)
  )
}

const clampPanelRatio = (ratio, containerWidth = getPanelContainerWidth()) => {
  return Math.max(minPanelRatio, Math.min(ratio, getMaxPanelRatio(containerWidth)))
}

const filePanelWidthStyle = computed(() => {
  if (!isFilePanelOpen.value) return '0px'
  if (filePanelDragWidth.value !== null) return `${filePanelDragWidth.value}px`

  const containerWidth = localUIState.chatContentWidth || getPanelContainerWidth()
  if (!containerWidth) return `${panelRatio.value * 100}%`

  const maxWidth = getFilePanelMaxWidth(containerWidth)
  const minWidth = getFilePanelMinWidth(containerWidth, maxWidth)
  const preferredWidth = containerWidth * panelRatio.value
  return `${Math.max(minWidth, Math.min(preferredWidth, maxWidth))}px`
})

const statePanelCanDock = computed(() => {
  if (isFilePanelOpen.value) return false
  const containerWidth = localUIState.chatContentWidth || getPanelContainerWidth()
  return containerWidth - statePanelDockWidth > statePanelDockMinChatWidth
})
const statePanelDocked = computed(() => statePanelOpen.value && statePanelCanDock.value)
const statePanelFloating = computed(() => statePanelOpen.value && !statePanelDocked.value)

const setPanelRatioForViewMode = () => {
  const hasPreview = Boolean(agentPanelActivePreviewPath.value)
  panelRatio.value = clampPanelRatio(hasPreview ? previewPanelRatio : defaultPanelRatio)
}

const showFilePanel = (mode = 'tree') => {
  isFilePanelOpen.value = true
  statePanelOpen.value = false
  agentPanelViewMode.value =
    mode === 'preview' && agentPanelActivePreviewPath.value ? 'preview' : 'tree'
  setPanelRatioForViewMode()
}

const showFileTreePanel = () => {
  isFilePanelOpen.value = true
  statePanelOpen.value = false
  agentPanelActivePreviewPath.value = ''
  agentPanelViewMode.value = 'tree'
  setPanelRatioForViewMode()
}

const getPanelFileName = (file) => {
  if (file?.name) return file.name
  if (file?.path) return String(file.path).split('/').pop() || String(file.path)
  return 'Tệp không xác định'
}

const getArtifactMetaLabel = (path) => {
  const filename = getPanelFileName({ path })
  if (!filename.includes('.')) return 'Tệp giao nhận'
  const extension = filename.split('.').pop()
  return extension ? `Tệp giao nhận · ${extension.toUpperCase()}` : 'Tệp giao nhận'
}

const getSubagentRunName = (run) => {
  const subagentSlug = run?.subagent_slug ? String(run.subagent_slug) : ''
  return (
    run?.subagent_name ||
    currentSubagentOptionBySlug.value.get(subagentSlug)?.name ||
    'Trợ lý thông minh con'
  )
}

const getSubagentAgent = (run) => {
  const subagentSlug = run?.subagent_slug
  if (!subagentSlug) return null
  return agents.value.find((agent) => agent.slug === subagentSlug) || null
}

const getSubagentIconSrc = (run) => {
  const agent = getSubagentAgent(run)
  return agent?.icon || ''
}

const getSubagentDefaultIconSrc = (run) =>
  run?.subagent_slug ? generatePixelAvatar(run.subagent_slug) : ''

const getSubagentRunMeta = (run) => {
  const artifacts = Array.isArray(run?.artifacts) ? run.artifacts.length : 0
  return artifacts ? `${artifacts} Sản phẩm` : run?.id || ''
}

const normalizePanelPath = (path) => String(path || '').replace(/\/+$/, '')

const isSameOrChildPanelPath = (path, targetPath) => {
  const normalizedPath = normalizePanelPath(path)
  const normalizedTargetPath = normalizePanelPath(targetPath)
  if (!normalizedPath || !normalizedTargetPath) return false
  return (
    normalizedPath === normalizedTargetPath || normalizedPath.startsWith(`${normalizedTargetPath}/`)
  )
}

const resetAgentPanelState = () => {
  isFilePanelOpen.value = false
  statePanelOpen.value = false
  panelRatio.value = defaultPanelRatio
  agentPanelPreviewTabs.value = []
  agentPanelActivePreviewPath.value = ''
  agentPanelViewMode.value = 'tree'
}

const setAgentPanelViewMode = (mode) => {
  agentPanelViewMode.value =
    mode === 'preview' && agentPanelActivePreviewPath.value ? 'preview' : 'tree'
  setPanelRatioForViewMode()
}

const activatePanelPreview = (path) => {
  if (!path) return
  agentPanelActivePreviewPath.value = path
  showFilePanel('preview')
}

const openPanelPreview = (file, keepTreeOpen = false) => {
  if (!file?.path) return

  const tab = {
    ...file,
    path: String(file.path),
    name: getPanelFileName(file)
  }
  const existingIndex = agentPanelPreviewTabs.value.findIndex((item) => item.path === tab.path)

  if (existingIndex >= 0) {
    agentPanelPreviewTabs.value = agentPanelPreviewTabs.value.map((item, index) =>
      index === existingIndex ? { ...item, ...tab } : item
    )
  } else {
    agentPanelPreviewTabs.value = [...agentPanelPreviewTabs.value, tab]
  }

  agentPanelActivePreviewPath.value = tab.path
  showFilePanel(keepTreeOpen ? 'tree' : 'preview')
}

const closePanelPreviewTab = (path) => {
  if (!path) return

  const closingIndex = agentPanelPreviewTabs.value.findIndex((item) => item.path === path)
  const nextTabs = agentPanelPreviewTabs.value.filter((item) => item.path !== path)
  agentPanelPreviewTabs.value = nextTabs

  if (agentPanelActivePreviewPath.value !== path) return

  const nextActiveTab = nextTabs[Math.min(closingIndex, nextTabs.length - 1)]
  agentPanelActivePreviewPath.value = nextActiveTab?.path || ''
  agentPanelViewMode.value = nextActiveTab ? 'preview' : 'tree'
  setPanelRatioForViewMode()
}

const closePanelPreviewPath = (targetPath) => {
  if (!targetPath) return

  const nextTabs = agentPanelPreviewTabs.value.filter(
    (item) => !isSameOrChildPanelPath(item.path, targetPath)
  )
  const shouldCloseActive = isSameOrChildPanelPath(agentPanelActivePreviewPath.value, targetPath)
  agentPanelPreviewTabs.value = nextTabs

  if (!shouldCloseActive) return

  const nextActiveTab = nextTabs[0]
  agentPanelActivePreviewPath.value = nextActiveTab?.path || ''
  agentPanelViewMode.value = nextActiveTab ? 'preview' : 'tree'
  setPanelRatioForViewMode()
}

// ==================== COMPUTED PROPERTIES ====================
const currentAgentId = computed(() => {
  if (props.singleMode) {
    return props.agentId || selectedAgentId.value || agents.value[0]?.id || ''
  }
  return selectedAgentId.value
})

const currentAgentName = computed(() => {
  const agent = currentAgent.value
  return agent ? agent.name : 'đại lý thông minh'
})

const currentAgent = computed(() => {
  if (!currentAgentId.value || !agents.value || !agents.value.length) return null
  return agents.value.find((a) => a.id === currentAgentId.value) || null
})
const currentChatId = computed(() => currentThreadId.value)

// ==================== Ghi đè mô hình ở cấp độ hội thoại ====================
// Lưu lựa chọn mô hình của người dùng theo thread. Nếu chưa chọn thì quay về mô hình cấu hình của tác nhân.
const DRAFT_MODEL_KEY = '__draft__'
const selectedModelByThread = reactive({})
const agentDefaultModel = computed(
  () =>
    agentConfig.value?.model ||
    currentAgent.value?.config_json?.context?.model ||
    configStore.config?.default_model ||
    ''
)
const currentModelSpec = computed(
  () => selectedModelByThread[currentChatId.value || DRAFT_MODEL_KEY] || agentDefaultModel.value
)
const handleModelSelect = (spec) => {
  if (typeof spec === 'string') {
    if (spec) {
      selectedModelByThread[currentChatId.value || DRAFT_MODEL_KEY] = spec
    } else {
      delete selectedModelByThread[currentChatId.value || DRAFT_MODEL_KEY]
    }
  }
}

const currentThreadAgentName = computed(() => {
  const threadAgentId = currentThread.value?.agent_id
  if (threadAgentId && agents.value?.length) {
    const threadAgent = agents.value.find((agent) => agent.id === threadAgentId)
    if (threadAgent?.name) {
      return threadAgent.name
    }
  }
  return currentAgentName.value
})
// Kiểm tra xem tác nhân hiện tại có hỗ trợ tải lên tệp không
const supportsFileUpload = computed(() => {
  if (!currentAgent.value) return false
  const capabilities = currentAgent.value.capabilities || []
  return capabilities.includes('file_upload')
})

const supportsFiles = computed(() => {
  if (!currentAgent.value) return false
  const capabilities = currentAgent.value.capabilities || []
  return capabilities.includes('files')
})

// AgentState Các thuộc tính tính toán liên quan
const currentAgentState = computed(() => {
  return currentChatId.value ? getThreadState(currentChatId.value)?.agentState || null : null
})
const toFiniteNumber = (value) => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}
const TOKEN_COUNT_K_UNIT = 1024
const formatTokenCount = (value) => {
  const numeric = toFiniteNumber(value)
  if (numeric === null) return '-'
  if (numeric >= TOKEN_COUNT_K_UNIT) {
    const digits = numeric >= TOKEN_COUNT_K_UNIT * 10 ? 1 : 2
    return `${(numeric / TOKEN_COUNT_K_UNIT).toFixed(digits).replace(/\.0+$/, '')}k`
  }
  return String(Math.round(numeric))
}
const currentTokenUsage = computed(() => {
  const usage = currentAgentState.value?.token_usage
  return usage && typeof usage === 'object' && !Array.isArray(usage) ? usage : null
})
const tokenUsageSegments = computed(() => {
  const usage = currentTokenUsage.value
  if (!usage) return []

  const summaryTokens = usage.summary_active
    ? Math.max(toFiniteNumber(usage.summary_message_tokens) || 0, 0)
    : 0
  const llmMessageTokens = Math.max(toFiniteNumber(usage.llm_messages_tokens) || 0, 0)
  const hasSplitMessageTokens =
    toFiniteNumber(usage.llm_content_message_tokens) !== null ||
    toFiniteNumber(usage.llm_tool_message_tokens) !== null
  const contentMessageTokens = hasSplitMessageTokens
    ? Math.max(toFiniteNumber(usage.llm_content_message_tokens) || 0, 0)
    : Math.max(llmMessageTokens - summaryTokens, 0)
  const toolMessageTokens = Math.max(toFiniteNumber(usage.llm_tool_message_tokens) || 0, 0)
  const stateMessageTokensBeforeCall = Math.max(
    toFiniteNumber(usage.state_messages_tokens_before_call ?? usage.state_messages_tokens) || 0,
    0
  )
  const cutMessageTokens = Math.max(stateMessageTokensBeforeCall - llmMessageTokens, 0)
  const llmMessageCount = Math.max(toFiniteNumber(usage.llm_message_count) || 0, 0)
  const contentMessageCount = hasSplitMessageTokens
    ? Math.max(toFiniteNumber(usage.llm_content_message_count) || 0, 0)
    : Math.max(llmMessageCount - (usage.summary_active ? 1 : 0), 0)
  const toolMessageCount = Math.max(toFiniteNumber(usage.llm_tool_message_count) || 0, 0)
  const stateMessageCountBeforeCall = Math.max(
    toFiniteNumber(usage.state_message_count_before_call ?? usage.state_message_count) || 0,
    0
  )
  const cutMessageCount = Math.max(stateMessageCountBeforeCall - llmMessageCount, 0)
  const systemTokens = Math.max(toFiniteNumber(usage.system_tokens) || 0, 0)
  const toolsTokens = Math.max(toFiniteNumber(usage.tools_tokens) || 0, 0)
  const inputTokens = Math.max(toFiniteNumber(usage.llm_input_tokens) || 0, 0)
  const rawSegments = [
    {
      key: 'cut',
      label: 'Đã nén',
      value: cutMessageTokens,
      messageCount: cutMessageCount,
      tone: 'is-cut'
    },
    {
      key: 'messages',
      label: 'Tin nội dung',
      value: contentMessageTokens,
      messageCount: contentMessageCount,
      tone: 'is-messages'
    },
    {
      key: 'toolMessages',
      label: 'Tin nhắn công cụ',
      value: toolMessageTokens,
      messageCount: toolMessageCount,
      tone: 'is-tool-messages'
    },
    {
      key: 'summary',
      label: 'Tóm tắt',
      value: summaryTokens,
      messageCount: usage.summary_active ? 1 : 0,
      tone: 'is-summary'
    },
    {
      key: 'system',
      label: 'Tin nhắn hệ thống',
      value: systemTokens,
      tone: 'is-system'
    },
    {
      key: 'tools',
      label: `Định nghĩa công cụ (${usage.tool_count || 0})`,
      value: toolsTokens,
      tone: 'is-tools'
    }
  ].filter((segment) => segment.value > 0)

  const accountedInputTokens = llmMessageTokens + systemTokens + toolsTokens
  if (inputTokens > accountedInputTokens) {
    rawSegments.push({
      key: 'overhead',
      label: 'Các khác',
      value: inputTokens - accountedInputTokens,
      tone: 'is-overhead'
    })
  }

  const segmentTotal = rawSegments.reduce((sum, segment) => sum + segment.value, 0)
  const total = Math.max(cutMessageTokens + inputTokens, segmentTotal, 1)
  return rawSegments.map((segment) => {
    const ratio = segment.value / total
    return {
      ...segment,
      percent: `${Math.max(0, Math.min(ratio * 100, 100)).toFixed(2)}%`,
      valueLabel: segment.messageCount
        ? `${formatTokenCount(segment.value)} (${segment.messageCount}Mục)`
        : formatTokenCount(segment.value)
    }
  })
})
const tokenUsageStackTotal = computed(() => {
  const inputTokens = toFiniteNumber(currentTokenUsage.value?.llm_input_tokens)
  if (inputTokens !== null) return Math.max(inputTokens, 0)
  return tokenUsageSegments.value
    .filter((segment) => segment.key !== 'cut')
    .reduce((sum, segment) => sum + segment.value, 0)
})
const tokenUsageStackLimit = computed(() => {
  const summaryTriggerTokens = toFiniteNumber(currentTokenUsage.value?.summary_trigger_tokens)
  if (summaryTriggerTokens && summaryTriggerTokens > 0) return summaryTriggerTokens

  const contextWindow = toFiniteNumber(currentTokenUsage.value?.context_window)
  if (contextWindow && contextWindow > 0) return contextWindow

  return Math.max(tokenUsageStackTotal.value, 1)
})
const tokenUsageHeaderPercentLabel = computed(() => {
  const limit = Math.max(tokenUsageStackLimit.value, 1)
  const percent = Math.max(0, Math.min((tokenUsageStackTotal.value / limit) * 100, 100))
  if (percent > 0 && percent < 1) return '<1%'
  return `${Math.round(percent)}%`
})
const tokenUsageStackHeadLabel = computed(() => {
  const summaryTriggerTokens = toFiniteNumber(currentTokenUsage.value?.summary_trigger_tokens)
  if (summaryTriggerTokens && summaryTriggerTokens > 0) {
    return `${formatTokenCount(tokenUsageStackTotal.value)} / ${formatTokenCount(summaryTriggerTokens)} Token`
  }
  return `${formatTokenCount(tokenUsageStackTotal.value)} Token`
})
const tokenUsageBarSegments = computed(() => {
  const limit = Math.max(tokenUsageStackLimit.value, 1)
  let remaining = limit
  return tokenUsageSegments.value
    .filter((segment) => segment.key !== 'cut')
    .map((segment) => {
      const value = Math.min(segment.value, Math.max(remaining, 0))
      remaining -= value
      return {
        ...segment,
        percent: `${Math.max(0, Math.min((value / limit) * 100, 100)).toFixed(2)}%`
      }
    })
    .filter((segment) => segment.value > 0 && segment.percent !== '0.00%')
})
const tokenUsageMetaRows = computed(() => {
  const usage = currentTokenUsage.value
  if (!usage) return []
  const rows = []
  if (toFiniteNumber(usage.context_window)) {
    rows.push({
      key: 'context',
      label: 'Cửa sổ/còn lại',
      value: `${formatTokenCount(usage.context_window)} / ${formatTokenCount(usage.remaining_context_tokens)}`
    })
  }
  return rows
})
const currentThreadAttachments = computed(() => {
  if (!currentChatId.value) return []
  return threadAttachmentsMap.value[currentChatId.value] || []
})
const currentPendingThreadAttachments = computed(() =>
  currentThreadAttachments.value.filter((attachment) => !attachment?.request_id)
)
const currentArtifacts = computed(() => {
  const artifacts = currentAgentState.value?.artifacts
  return Array.isArray(artifacts) ? artifacts : []
})
const currentArtifactFiles = computed(() =>
  currentArtifacts.value
    .map((path) => String(path || '').trim())
    .filter(Boolean)
    .map((path) => ({
      path,
      name: getPanelFileName({ path }),
      meta: getArtifactMetaLabel(path)
    }))
)
const currentTodos = computed(() => {
  const todos = currentAgentState.value?.todos
  if (!Array.isArray(todos)) return []
  return todos.map((todo) => {
    const fullContent = String(todo?.content || '')
    return {
      ...todo,
      fullContent,
      displayContent: formatTodoName(fullContent)
    }
  })
})
const currentSubagentRuns = computed(() => {
  const runs = currentAgentState.value?.subagent_runs
  return Array.isArray(runs) ? runs : []
})
const currentSubagentRunById = computed(() => {
  const runById = new Map()
  currentSubagentRuns.value.forEach((run) => {
    if (run?.id) runById.set(String(run.id), run)
    if (run?.run_id) runById.set(String(run.run_id), run)
  })
  return runById
})
const currentSubagentRunByThreadId = computed(() => {
  const runByThreadId = new Map()
  currentSubagentRuns.value.forEach((run) => {
    if (run?.child_thread_id) runByThreadId.set(String(run.child_thread_id), run)
  })
  return runByThreadId
})
const currentSubagentOptionBySlug = computed(() => {
  const optionBySlug = new Map()
  mentionConfig.value.subagents.forEach((subagent) => {
    if (subagent?.slug) optionBySlug.set(String(subagent.slug), subagent)
  })
  return optionBySlug
})

const subagentThreadModal = reactive({
  open: false,
  childThreadId: '',
  runId: '',
  runStatus: '',
  subagentName: '',
  subagentAvatar: '',
  subagentDefaultAvatar: ''
})
const openSubagentThread = (run) => {
  if (!run?.child_thread_id) return
  subagentThreadModal.childThreadId = String(run.child_thread_id)
  subagentThreadModal.runId = run.run_id ? String(run.run_id) : ''
  subagentThreadModal.runStatus = run.status ? String(run.status) : ''
  subagentThreadModal.subagentName = getSubagentRunName(run)
  subagentThreadModal.subagentAvatar = getSubagentIconSrc(run)
  subagentThreadModal.subagentDefaultAvatar = getSubagentDefaultIconSrc(run)
  subagentThreadModal.open = true
}
const isStateSectionExpanded = (key) => !collapsedStateSections[key]
const toggleStateSection = (key) => {
  collapsedStateSections[key] = !collapsedStateSections[key]
}
const currentStateFiles = computed(() => {
  const files = []
  const seenPaths = new Set()
  const pushFile = (entry, fallbackName = 'Tệp') => {
    const path = String(entry?.path || entry?.file_path || entry?.file_name || entry?.name || '')
    if (!path || seenPaths.has(path)) return
    seenPaths.add(path)
    const name = entry?.file_name || entry?.name || getPanelFileName({ path }) || fallbackName
    const sizeLabel = formatFileSize(entry?.file_size ?? entry?.size)
    const status = entry?.status || ''
    files.push({
      key: path,
      path,
      name,
      meta: [status, sizeLabel === '-' ? '' : sizeLabel, path].filter(Boolean).join(' · ')
    })
  }

  const rawFiles = currentAgentState.value?.files || {}
  if (typeof rawFiles === 'object' && !Array.isArray(rawFiles)) {
    Object.entries(rawFiles).forEach(([path, fileData]) => pushFile({ path, ...fileData }))
  }
  currentThreadAttachments.value.forEach((attachment) => pushFile(attachment, 'Tệp đính kèm'))

  return files
})
const totalTodoCount = computed(() => currentTodos.value.length)
const completedTodoCount = computed(
  () => currentTodos.value.filter((todo) => todo?.status === 'completed').length
)
const showStateEntry = computed(() => Boolean(currentChatId.value))
const showFileEntry = computed(() => Boolean(currentChatId.value))
const todoProgress = computed(() => {
  if (!totalTodoCount.value) return 0
  return Math.round((completedTodoCount.value / totalTodoCount.value) * 100)
})
const stateSummaryLabel = computed(() => {
  const total =
    (currentTokenUsage.value ? 1 : 0) +
    totalTodoCount.value +
    currentStateFiles.value.length +
    currentArtifactFiles.value.length +
    displaySubagentRuns.value.length
  return total ? `${total} Mục` : 'Chưa có nội dung'
})
const hasVisibleStateSections = computed(
  () =>
    Boolean(currentTokenUsage.value) ||
    currentTodos.value.length > 0 ||
    currentStateFiles.value.length > 0 ||
    currentArtifactFiles.value.length > 0 ||
    displaySubagentRuns.value.length > 0
)

const { mentionConfig } = useAgentMentionConfig({
  currentAgentState,
  currentThreadAttachments,
  configurableItems,
  agentConfig
})

const currentThreadMessages = computed(() => threadMessages.value[currentChatId.value] || [])
const currentThreadHasHistory = computed(() => currentThreadMessages.value.length > 0)
const currentThreadConfigNotice = computed(() => {
  if (!currentChatId.value) return null
  return threadConfigNoticeMap.value[currentChatId.value] || null
})

const currentApprovalModalVisible = computed(
  () =>
    approvalState.showModal &&
    Boolean(approvalState.threadId) &&
    approvalState.threadId === currentChatId.value
)
const currentApprovalQuestions = computed(() =>
  currentApprovalModalVisible.value ? approvalState.questions : []
)

const shouldSuppressRefsForApproval = () =>
  currentApprovalModalVisible.value ||
  Boolean(
    approvalState.threadId && currentChatId.value === approvalState.threadId && isProcessing.value
  )

// Xác định xem một lượt hội thoại đã 'kết thúc' chưa, tức là có thể hiển thị refs (Nguồn/Thanh hành động):
// - Phía sau có ngay lượt hội thoại tiếp theo bắt đầu bằng tin nhắn của người dùng (human message) -> Đã kết thúc.
// - Đây là lượt hội thoại cuối cùng và hiện tại không có phản hồi nào đang được tạo -> Đã kết thúc.
// Ngược lại (phía sau không có human message mà là AI tiếp tục viết, hoặc vẫn đang trong quá trình tạo) -> Chưa hoàn thành, không hiển thị.
const isConversationSettled = (conv) => {
  const convs = conversations.value
  const idx = convs.indexOf(conv)
  if (idx === -1) return false
  const next = convs[idx + 1]
  if (next) {
    return next.messages?.[0]?.type === 'human'
  }
  return !(isProcessing.value || isReplyLoading.value)
}

// Tính toán xem có hiển thị khôngRefsĐiều kiện của thành phần
const shouldShowRefs = computed(() => {
  return (conv) => {
    if (!getLastMessage(conv) || conv.status === 'streaming' || shouldSuppressRefsForApproval()) {
      return false
    }
    return isConversationSettled(conv)
  }
})

const shouldShowArtifacts = computed(() => {
  return (conv) => {
    if (!currentArtifacts.value.length || conv.status === 'streaming') return false
    const latestConv = conversations.value[conversations.value.length - 1]
    return latestConv === conv
  }
})

// Trạng thái luồng hiện tạicomputedthuộc tính
const currentThreadState = computed(() => {
  return getThreadState(currentChatId.value)
})

const getThreadOngoingMessages = (threadId) => {
  const threadState = getThreadState(threadId)
  if (!threadState || !threadState.onGoingConv) return []

  const msgs = Object.values(threadState.onGoingConv.msgChunks)
    .map(MessageProcessor.mergeMessageChunk)
    .filter(Boolean)
  return msgs.length > 0
    ? MessageProcessor.convertToolResultToMessages(msgs).filter((msg) => msg.type !== 'tool')
    : []
}

const onGoingConvMessages = computed(() => getThreadOngoingMessages(currentChatId.value))

// Đọc quỹ đạo thời gian thực của luồng con / định vị khi chạy lần đầu child_thread_id
provide('getThreadOngoingMessages', getThreadOngoingMessages)
provide('getSubagentThreadIdByToolCall', getSubagentThreadIdByToolCall)

// hasResult Trong giai đoạn phát trực tiếp luôn là false，Không thể dựa vào nó để xác định trạng thái。
const ongoingTaskCalls = computed(() => {
  const calls = []
  onGoingConvMessages.value.forEach((message, messageIndex) => {
    if (message?.type !== 'ai' || !Array.isArray(message.tool_calls)) return
    message.tool_calls.forEach((toolCall) => {
      const name = toolCall?.name || toolCall?.function?.name
      if (name !== 'task') return
      const id = toolCall?.id ? String(toolCall.id) : ''
      if (!id) return
      const args = parseToolCallArgs(toolCall)
      calls.push({
        id,
        messageIndex,
        hasResult: Boolean(toolCall.tool_call_result || toolCall.result),
        subagentSlug: args.subagent_slug || '',
        description: args.description || '',
        childThreadId: args.thread_id ? String(args.thread_id) : getSubagentThreadIdByToolCall(id)
      })
    })
  })
  return calls
})

// Đang hoạt động ( thực sự đang thực hiện ) task Gọi = Mục cuối cùng 'chứa chưa hoàn thành task Gọi đến AI Những lệnh gọi trong tin nhắn。
// steer Thực hiện tuần tự → chỉ cuộc gọi của tin nhắn cuối cùng được thực thi; song song → tất cả các cuộc gọi của cùng một tin nhắn đều được thực thi. // Xác định dựa trên thứ tự tin nhắn, không phụ thuộc vào suy luận không đồng bộ child_thread_id，Tránh nhầm lẫn trạng thái do hash chưa sẵn sàng khi chạy lần đầu。
const activeSubagentToolCallIds = computed(() => {
  const pending = ongoingTaskCalls.value.filter((call) => !call.hasResult)
  if (!pending.length) return new Set()
  const lastMessageIndex = pending[pending.length - 1].messageIndex
  return new Set(
    pending.filter((call) => call.messageIndex === lastMessageIndex).map((call) => call.id)
  )
})
provide('activeSubagentToolCallIds', activeSubagentToolCallIds)

// agent_state.subagent_runs Chỉ trong task Ghi khi trả về (trạng thái hoàn thành); các mục đang chạy của bảng điều khiển chỉ lấy các cuộc gọi "hoạt động",
// tránh các mục đã hoàn thành steer Các cuộc gọi lịch sử được lặp lại thành các mục bổ sung trong bảng điều khiển。
const runningSubagentRunsFromStream = computed(() => {
  const activeIds = activeSubagentToolCallIds.value
  return ongoingTaskCalls.value
    .filter((call) => activeIds.has(call.id))
    .map((call) => {
      const option = call.subagentSlug
        ? currentSubagentOptionBySlug.value.get(call.subagentSlug)
        : null
      return {
        id: call.id,
        subagent_slug: call.subagentSlug,
        subagent_name: option?.name || call.subagentSlug || 'Trợ lý thông minh con',
        description: call.description,
        child_thread_id: call.childThreadId || '',
        status: 'running'
      }
    })
})

// task Mô tả nhiệm vụ được đưa vào tham số gọi công cụ（tool_call_id -> description），Ghi đè lịch sử và tin nhắn đang xử lý. // Backend subagent_runs Không còn lưu trữ thừa description，Panel được xác định là đã hoàn thành run Nội dung hiển thị được điền lại。
const taskDescriptionByToolCallId = computed(() => {
  const map = new Map()
  const collect = (messages) => {
    if (!Array.isArray(messages)) return
    messages.forEach((message) => {
      if (message?.type !== 'ai' || !Array.isArray(message.tool_calls)) return
      message.tool_calls.forEach((toolCall) => {
        const name = toolCall?.name || toolCall?.function?.name
        if (name !== 'task') return
        const id = toolCall?.id ? String(toolCall.id) : ''
        if (!id || map.has(id)) return
        const desc = String(parseToolCallArgs(toolCall).description || '').trim()
        if (desc) map.set(id, desc)
      })
    })
  }
  collect(historyConversations.value)
  collect(onGoingConvMessages.value)
  return map
})

// Backend gộp trạng thái bền vững theo run_id; các mục task tạm thời trong giai đoạn stream chưa có run_id, chỉ dùng ID cuộc gọi công cụ để điền vào vị trí trống.
const displaySubagentRuns = computed(() => {
  const descByToolCall = taskDescriptionByToolCallId.value
  const merged = currentSubagentRuns.value.map((run) => {
    const copy = { ...run }
    // Các mục được lưu trữ vĩnh viễn không có description，Nhấn tool_call_id（ngay lập tức run.id）Từ task Điền tham số khi gọi。
    if (!copy.description && copy.id) {
      const desc = descByToolCall.get(String(copy.id))
      if (desc) copy.description = desc
    }
    return copy
  })
  const runIdIndex = new Map()
  const transientIdIndex = new Map()
  merged.forEach((run, index) => {
    if (run.run_id) runIdIndex.set(String(run.run_id), index)
    // Các mục bền vững (chứa cả run_id và id) cũng được tạo chỉ mục theo ID cuộc gọi công cụ, nếu không, mục giữ chỗ của stream sẽ không tìm thấy và sẽ bị lặp thành một dòng thừa trên bảng điều khiển.
    if (run.id) transientIdIndex.set(String(run.id), index)
  })
  runningSubagentRunsFromStream.value.forEach((run) => {
    let position
    if (run.run_id && runIdIndex.has(String(run.run_id))) {
      position = runIdIndex.get(String(run.run_id))
    } else if (!run.run_id && run.id && transientIdIndex.has(String(run.id))) {
      position = transientIdIndex.get(String(run.id))
    }
    if (position === undefined) {
      position = merged.length
      merged.push(run)
    } else if (!merged[position].run_id) {
      // đã được lưu vào kho (có run_id）Các mục sau này dựa trên backend, không bị ghi đè bởi trạng thái chạy stream; chỉ ghi đè các mục placeholder trống
      merged[position] = { ...merged[position], ...run }
    }
    if (run.run_id) runIdIndex.set(String(run.run_id), position)
    else if (run.id) transientIdIndex.set(String(run.id), position)
  })
  return merged
})

const activeSubagentThreadRun = computed(() => {
  if (!subagentThreadModal.childThreadId) return null
  return (
    displaySubagentRuns.value.find(
      (run) => String(run?.child_thread_id || '') === subagentThreadModal.childThreadId
    ) || null
  )
})
const activeSubagentThreadName = computed(() =>
  activeSubagentThreadRun.value
    ? getSubagentRunName(activeSubagentThreadRun.value)
    : subagentThreadModal.subagentName
)
const activeSubagentThreadRunId = computed(() =>
  activeSubagentThreadRun.value?.run_id
    ? String(activeSubagentThreadRun.value.run_id)
    : subagentThreadModal.runId
)
const activeSubagentThreadRunStatus = computed(() =>
  activeSubagentThreadRun.value?.status
    ? String(activeSubagentThreadRun.value.status)
    : subagentThreadModal.runStatus
)
const activeSubagentThreadAvatar = computed(() =>
  activeSubagentThreadRun.value
    ? getSubagentIconSrc(activeSubagentThreadRun.value) || subagentThreadModal.subagentAvatar
    : subagentThreadModal.subagentAvatar
)
const activeSubagentThreadDefaultAvatar = computed(() =>
  activeSubagentThreadRun.value
    ? getSubagentDefaultIconSrc(activeSubagentThreadRun.value) ||
      subagentThreadModal.subagentDefaultAvatar
    : subagentThreadModal.subagentDefaultAvatar
)
const activeSubagentThreadOngoingMessages = computed(() => {
  if (!subagentThreadModal.childThreadId) return []
  return getThreadOngoingMessages(subagentThreadModal.childThreadId)
})
const activeSubagentThreadIsStreaming = computed(
  () =>
    activeSubagentThreadOngoingMessages.value.length > 0 ||
    activeSubagentThreadRun.value?.status === 'running'
)

// Agent con chạy lần đầu: frontend tính toán theo cùng hash như backend child_thread_id，Bảo quản trong bản đồ để panel/định vị đường đi。
watch(
  onGoingConvMessages,
  (messages) => {
    const parentThreadId = currentChatId.value
    if (!parentThreadId) return
    messages.forEach((message) => {
      if (message?.type !== 'ai' || !Array.isArray(message.tool_calls)) return
      message.tool_calls.forEach((toolCall) => {
        const name = toolCall?.name || toolCall?.function?.name
        if (name !== 'task') return
        if (toolCall.tool_call_result || toolCall.result) return
        const id = toolCall?.id ? String(toolCall.id) : ''
        if (!id || chatState.subagentThreadByToolCall[id]) return
        const args = parseToolCallArgs(toolCall)
        if (args.thread_id || !args.subagent_slug) return
        makeChildThreadId(parentThreadId, String(args.subagent_slug), id).then((childThreadId) => {
          recordSubagentThread(id, childThreadId)
        })
      })
    })
  },
  { deep: true }
)

const historyConversations = computed(() => {
  return MessageProcessor.convertServerHistoryToMessages(currentThreadMessages.value)
})

function getMessageRequestId(message) {
  const metadataRequestId = message?.extra_metadata?.request_id
  if (typeof metadataRequestId === 'string' && metadataRequestId.trim())
    return metadataRequestId.trim()
  if (typeof message?.request_id === 'string' && message.request_id.trim())
    return message.request_id.trim()
  if (message?.type === 'human' && typeof message.id === 'string' && message.id.trim()) {
    return message.id.trim()
  }
  return null
}

function getMessageRunId(message) {
  const metadataRunId = message?.extra_metadata?.run_id
  if (typeof metadataRunId === 'string' && metadataRunId.trim()) return metadataRunId.trim()
  if (typeof message?.run_id === 'string' && message.run_id.trim()) return message.run_id.trim()
  return null
}

function mergeLocalImageFields(message, localMessage) {
  if (!localMessage?.image_content || message?.image_content) return message
  return {
    ...message,
    message_type: localMessage.message_type || message.message_type,
    image_content: localMessage.image_content,
    extra_metadata: message.extra_metadata || {}
  }
}

function mergeOngoingUserMessageIntoHistory(historyConvs, ongoingMessages) {
  if (!Array.isArray(historyConvs) || !historyConvs.length || !Array.isArray(ongoingMessages)) {
    return { historyConvs, ongoingMessages }
  }

  const firstOngoingMessage = ongoingMessages[0]
  if (!firstOngoingMessage || firstOngoingMessage.type !== 'human') {
    return { historyConvs, ongoingMessages }
  }

  const lastHistoryConv = historyConvs[historyConvs.length - 1]
  const historyMessages = Array.isArray(lastHistoryConv?.messages) ? lastHistoryConv.messages : []
  const historyHumanIndex = historyMessages.findIndex((message) => message?.type === 'human')
  if (historyHumanIndex === -1) return { historyConvs, ongoingMessages }

  const historyHuman = historyMessages[historyHumanIndex]
  const historyRequestId = getMessageRequestId(historyHuman)
  const ongoingRequestId = getMessageRequestId(firstOngoingMessage)
  if (!historyRequestId || !ongoingRequestId || historyRequestId !== ongoingRequestId) {
    return { historyConvs, ongoingMessages }
  }

  const patchedHistoryHuman = mergeLocalImageFields(historyHuman, firstOngoingMessage)
  if (patchedHistoryHuman === historyHuman) {
    return { historyConvs, ongoingMessages: ongoingMessages.slice(1) }
  }

  const patchedHistoryMessages = [...historyMessages]
  patchedHistoryMessages[historyHumanIndex] = patchedHistoryHuman
  const patchedHistoryConvs = [...historyConvs]
  patchedHistoryConvs[historyConvs.length - 1] = {
    ...lastHistoryConv,
    messages: patchedHistoryMessages
  }
  return { historyConvs: patchedHistoryConvs, ongoingMessages: ongoingMessages.slice(1) }
}

function mergeActiveRunOngoingIntoHistory(historyConvs, ongoingMessages, activeRunId) {
  if (!activeRunId || !Array.isArray(historyConvs) || !Array.isArray(ongoingMessages)) {
    return { historyConvs, ongoingMessages }
  }
  if (!ongoingMessages.length) return { historyConvs, ongoingMessages }

  const filteredHistoryConvs = historyConvs
    .map((conv) => ({
      ...conv,
      messages: (conv.messages || []).filter(
        (message) => !(message?.type === 'ai' && getMessageRunId(message) === activeRunId)
      )
    }))
    .filter((conv) => conv.messages.length > 0)

  const firstOngoingMessage = ongoingMessages[0]
  if (firstOngoingMessage?.type === 'human' || filteredHistoryConvs.length === 0) {
    return { historyConvs: filteredHistoryConvs, ongoingMessages }
  }

  const lastHistoryConv = filteredHistoryConvs[filteredHistoryConvs.length - 1]
  const lastMessages = Array.isArray(lastHistoryConv.messages) ? lastHistoryConv.messages : []
  const lastHuman = lastMessages.find((message) => message?.type === 'human')
  if (!lastHuman) return { historyConvs: filteredHistoryConvs, ongoingMessages }

  const historyRequestId = getMessageRequestId(lastHuman)
  const ongoingRequestId = getMessageRequestId(firstOngoingMessage)
  const sameActiveRun =
    getMessageRunId(lastHuman) === activeRunId ||
    (Boolean(historyRequestId) &&
      Boolean(ongoingRequestId) &&
      ongoingRequestId === historyRequestId)
  if (!sameActiveRun) return { historyConvs: filteredHistoryConvs, ongoingMessages }

  const patchedHistoryConvs = [...filteredHistoryConvs]
  patchedHistoryConvs[patchedHistoryConvs.length - 1] = {
    ...lastHistoryConv,
    messages: [...lastMessages, ...ongoingMessages],
    status: 'streaming'
  }
  return { historyConvs: patchedHistoryConvs, ongoingMessages: [] }
}

const conversations = computed(() => {
  const historyConvs = historyConversations.value
  const { historyConvs: mergedHistoryConvs, ongoingMessages: mergedOngoingMessages } =
    mergeOngoingUserMessageIntoHistory(historyConvs, onGoingConvMessages.value)
  const { historyConvs: activeRunHistoryConvs, ongoingMessages: activeRunOngoingMessages } =
    mergeActiveRunOngoingIntoHistory(
      mergedHistoryConvs,
      mergedOngoingMessages,
      currentThreadState.value?.activeRunId || null
    )

  // Nếu có tin nhắn đang tiến hành và trạng thái luồng cho thấy đang xử lý luồng, thêm cuộc trò chuyện đang tiến hành
  if (activeRunOngoingMessages.length > 0) {
    const onGoingConv = {
      messages: activeRunOngoingMessages,
      status: 'streaming'
    }
    return [...activeRunHistoryConvs, onGoingConv]
  }
  return activeRunHistoryConvs
})

const conversationRows = computed(() => {
  const rows = conversations.value.map((conv, index) => ({
    type: 'conversation',
    key: conv.status === 'streaming' ? 'ongoing-conversation' : `history-${index}`,
    conv,
    displayItems: getDisplayItems(conv)
  }))

  if (currentThreadConfigNotice.value) {
    const insertAfterCount = Math.max(
      0,
      Math.min(
        Number(currentThreadConfigNotice.value.insertAfterConversationCount) || 0,
        rows.length
      )
    )
    rows.splice(insertAfterCount, 0, {
      type: 'notice',
      key: currentThreadConfigNotice.value.id,
      notice: currentThreadConfigNotice.value
    })
  }

  return rows
})

const isLoadingMessages = computed(() => chatUIStore.isLoadingMessages)
const isStreaming = computed(() => {
  const threadState = currentThreadState.value
  return threadState ? threadState.isStreaming : false
})
const shouldRefreshStateWhileStreaming = computed(
  () => Boolean(currentChatId.value) && isStreaming.value && statePanelOpen.value
)
const isProcessing = computed(() => isStreaming.value)
const isReplyLoading = computed(() => {
  const threadState = currentThreadState.value
  return Boolean(threadState?.replyLoadingVisible)
})
const replyLoadingText = computed(() =>
  currentThreadState.value?.contextCompressing ? 'Đang nén ngữ cảnh...' : 'Đang tạo phản hồi...'
)
const isSendButtonDisabled = computed(() => {
  return (
    sendCooldownActive.value ||
    (props.sendDisabled && !isProcessing.value) ||
    ((!userInput.value || !currentAgent.value) && !isProcessing.value)
  )
})

const startSendCooldown = () => {
  sendCooldownActive.value = true
  if (sendCooldownTimer) {
    clearTimeout(sendCooldownTimer)
  }
  sendCooldownTimer = setTimeout(() => {
    sendCooldownActive.value = false
    sendCooldownTimer = null
  }, 2000)
}

const createClientRequestId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

const buildOptimisticHumanMessage = ({
  requestId,
  text,
  imageContent = null,
  attachments = []
}) => {
  const message = {
    id: requestId,
    role: 'user',
    type: 'human',
    content: text,
    message_type: imageContent ? 'multimodal_image' : 'text',
    extra_metadata: {
      request_id: requestId,
      attachments
    }
  }

  if (imageContent) {
    message.image_content = imageContent
  }

  return message
}

// Gửi runs Đầu tiên chèn một tin nhắn người dùng ở phía trước để tránh chờ đợi worker Tin nhắn chỉ xuất hiện sau khi polling。
const insertOptimisticHumanMessage = (
  threadState,
  { requestId, text, imageContent = null, attachments = [] }
) => {
  if (!threadState || !requestId) return
  threadState.pendingRequestId = requestId
  threadState.replyLoadingVisible = false
  threadState.onGoingConv.msgChunks[requestId] = [
    buildOptimisticHumanMessage({ requestId, text, imageContent, attachments })
  ]
}

const markAttachmentsRequestId = (threadId, attachments, requestId) => {
  if (!threadId || !attachments.length) return null
  const previousAttachments = threadAttachmentsMap.value[threadId] || []
  const fileIds = new Set(attachments.map((attachment) => attachment.file_id).filter(Boolean))
  threadAttachmentsMap.value[threadId] = previousAttachments.map((attachment) =>
    fileIds.has(attachment.file_id) ? { ...attachment, request_id: requestId } : attachment
  )
  return previousAttachments
}

const rollbackAttachments = (threadId, previousAttachments) => {
  if (!threadId || !Array.isArray(previousAttachments)) return
  threadAttachmentsMap.value[threadId] = previousAttachments
}

const CONFIG_CHANGE_NOTICE_MESSAGE =
  'Trong quá trình chạy, chuyển đổi hoặc sửa đổi cấu hình có thể ảnh hưởng đến kết quả cuối cùng; nên tạo một cuộc trò chuyện mới。'

const withConfigNoticeSync = async (task) => {
  configNoticeSyncDepth.value += 1
  try {
    return await task()
  } finally {
    configNoticeSyncDepth.value = Math.max(0, configNoticeSyncDepth.value - 1)
  }
}

const buildThreadConfigSnapshot = () => {
  return {
    agentId: currentAgentId.value || '',
    configJson: JSON.stringify(agentConfig.value || {})
  }
}

const syncThreadConfigSnapshot = (threadId, options = {}) => {
  if (!threadId) return

  const { overwrite = true } = options
  if (!overwrite && threadConfigSnapshotMap.value[threadId]) return
  if (threadPendingConfigNoticeMap.value[threadId]) return

  // Khi chuyển đổi luồng, ghi lại trạng thái hiện tại trước UI Chụp nhanh cấu hình, tránh đồng bộ thread Báo động sai khi liên kết cấu hình。
  threadConfigSnapshotMap.value = {
    ...threadConfigSnapshotMap.value,
    [threadId]: buildThreadConfigSnapshot()
  }
}

const upsertThreadConfigNotice = (threadId, insertAfterConversationCount) => {
  if (!threadId) return

  const existingNotice = threadConfigNoticeMap.value[threadId]
  const nextNotice = {
    id: existingNotice?.id || `config-change-notice-${threadId}`,
    message: existingNotice?.message || CONFIG_CHANGE_NOTICE_MESSAGE,
    insertAfterConversationCount
  }
  const shouldScroll =
    !existingNotice || existingNotice.insertAfterConversationCount !== insertAfterConversationCount

  threadConfigNoticeMap.value = {
    ...threadConfigNoticeMap.value,
    [threadId]: nextNotice
  }

  if (threadPendingConfigNoticeMap.value[threadId]) {
    const nextPendingNotices = { ...threadPendingConfigNoticeMap.value }
    delete nextPendingNotices[threadId]
    threadPendingConfigNoticeMap.value = nextPendingNotices
  }

  if (shouldScroll) {
    configNoticeScrollVersion.value += 1
  }
}

const queuePendingThreadConfigNotice = (threadId) => {
  if (!threadId) return
  threadPendingConfigNoticeMap.value = {
    ...threadPendingConfigNoticeMap.value,
    [threadId]: {
      id: `config-change-notice-${threadId}`,
      message: CONFIG_CHANGE_NOTICE_MESSAGE
    }
  }
}

const flushPendingThreadConfigNotice = (threadId) => {
  if (
    !threadId ||
    !currentThreadHasHistory.value ||
    !threadPendingConfigNoticeMap.value[threadId]
  ) {
    return
  }

  upsertThreadConfigNotice(threadId, conversations.value.length)
}

const maybeInsertThreadConfigNotice = () => {
  const threadId = currentChatId.value
  if (!threadId || configNoticeSyncDepth.value > 0) {
    return
  }

  const previousSnapshot = threadConfigSnapshotMap.value[threadId]
  const currentSnapshot = buildThreadConfigSnapshot()

  if (!previousSnapshot) {
    threadConfigSnapshotMap.value = {
      ...threadConfigSnapshotMap.value,
      [threadId]: currentSnapshot
    }
    return
  }

  if (
    previousSnapshot.agentId === currentSnapshot.agentId &&
    previousSnapshot.configJson === currentSnapshot.configJson
  ) {
    return
  }

  if (currentThreadHasHistory.value) {
    upsertThreadConfigNotice(threadId, conversations.value.length)
  } else if (chatUIStore.isLoadingMessages) {
    // Khi luồng lịch sử vẫn đang tải, tạm hoãn gợi ý trước, tránh việc sau khi tin nhắn trả về lại coi thay đổi là đường cơ sở mới。
    queuePendingThreadConfigNotice(threadId)
  } else {
    return
  }

  threadConfigSnapshotMap.value = {
    ...threadConfigSnapshotMap.value,
    [threadId]: currentSnapshot
  }
}

// ==================== SCROLL & RESIZE HANDLING ====================
const scrollController = new ScrollController('.chat-main')
const chatMainRef = ref(null)
let chatMainResizeObserver = null
// Khởi tạo cờ delay để tránh khi lần đầu mount ResizeObserver Kích hoạt ngay lập tức dẫn đến việc thanh bên đóng lại một cách bất ngờ
let isResizeObserverReady = false
let resizeObserverReadyTimer = null

const armResizeObserver = () => {
  if (resizeObserverReadyTimer) {
    clearTimeout(resizeObserverReadyTimer)
  }

  isResizeObserverReady = false
  // keep-alive Khi quay lại một trang, chờ layout ổn định trước khi tiếp tục tính chiều rộng, để tránh chiều rộng ẩn gây nhiễu trạng thái thanh bên。
  resizeObserverReadyTimer = setTimeout(() => {
    isResizeObserverReady = true
  }, 50)
}

const stopChatMainResizeObserver = () => {
  if (resizeObserverReadyTimer) {
    clearTimeout(resizeObserverReadyTimer)
    resizeObserverReadyTimer = null
  }

  isResizeObserverReady = false

  if (chatMainResizeObserver) {
    chatMainResizeObserver.disconnect()
    chatMainResizeObserver = null
  }
}

const stopStreamingStateRefresh = () => {
  if (streamingStateRefreshTimer) {
    clearInterval(streamingStateRefreshTimer)
    streamingStateRefreshTimer = null
  }
}

const startStreamingStateRefresh = () => {
  stopStreamingStateRefresh()
  streamingStateRefreshTimer = setInterval(() => {
    if (!shouldRefreshStateWhileStreaming.value) return
    void handleAgentStateRefresh()
  }, 5000)
}

const startChatMainResizeObserver = () => {
  if (!window.ResizeObserver || !chatMainRef.value || chatMainResizeObserver) {
    return
  }

  const syncLayoutWidths = () => {
    localUIState.chatMainWidth = chatMainRef.value?.clientWidth || window.innerWidth
    localUIState.chatContentWidth =
      chatContentContainerRef.value?.clientWidth || localUIState.chatMainWidth
  }

  syncLayoutWidths()
  chatMainResizeObserver = new ResizeObserver((entries) => {
    // Bỏ qua kiểm tra trong quá trình khởi tạo, chờ layout Ổn định
    if (!isResizeObserverReady) return

    if (!entries.length) return
    syncLayoutWidths()
  })
  chatMainResizeObserver.observe(chatMainRef.value)
  if (chatContentContainerRef.value) {
    chatMainResizeObserver.observe(chatContentContainerRef.value)
  }
  armResizeObserver()
}

onMounted(() => {
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', handlePageVisibilityChange)
  }

  nextTick(() => {
    const chatMainContainer = document.querySelector('.chat-main')
    if (chatMainContainer) {
      chatMainContainer.addEventListener('scroll', scrollController.handleScroll, { passive: true })
    }

    startChatMainResizeObserver()
  })
})

onActivated(() => {
  nextTick(() => {
    startChatMainResizeObserver()
  })
})

onDeactivated(() => {
  stopChatMainResizeObserver()
  stopStreamingStateRefresh()
})

onUnmounted(() => {
  if (typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', handlePageVisibilityChange)
  }
  scrollController.cleanup()
  stopChatMainResizeObserver()
  stopStreamingStateRefresh()
  if (sendCooldownTimer) {
    clearTimeout(sendCooldownTimer)
    sendCooldownTimer = null
  }
  // Dọn dẹp tất cả trạng thái luồng
  resetOnGoingConv()
})

// ==================== Phương pháp quản lý luồng ====================
// Lấy danh sách luồng của trợ lý thông minh hiện tại
const fetchThreads = async (agentId = null) => {
  const targetAgentId = props.singleMode ? agentId || currentAgentId.value : agentId
  if (props.singleMode && !targetAgentId) return

  await chatThreadsStore.loadThreads(targetAgentId)
}

// Tạo luồng mới
const createThread = async (agentId, title = 'Cuộc trò chuyện mới') => {
  if (!agentId) return null

  try {
    const thread = await chatThreadsStore.createThread(agentId, title)
    if (thread) {
      threadMessages.value[thread.id] = []
      threadFilesMap.value[thread.id] = []
      threadAttachmentsMap.value[thread.id] = []
    }
    return thread
  } catch (error) {
    console.error('Failed to create thread:', error)
    handleChatError(error, 'create')
    throw error
  }
}

// Lấy tin nhắn từ luồng
const fetchThreadMessages = async ({ agentId, threadId, delay = 0 }) => {
  if (!threadId || !agentId) return

  // Nếu đã chỉ định độ trễ, chờ thời gian chỉ định (để đảm bảo giao dịch cơ sở dữ liệu backend được commit)）
  if (delay > 0) {
    await new Promise((resolve) => setTimeout(resolve, delay))
  }

  try {
    const response = await agentApi.getAgentHistory(threadId)
    const history = response.history || []
    threadMessages.value[threadId] = history
    restoreThreadModelSelection(threadId, history)
  } catch (error) {
    handleChatError(error, 'load')
    throw error
  }
}

// Phục hồi qua phiên: Sử dụng bản ghi tin nhắn gần nhất của người dùng (model_spec) để khôi phục lựa chọn mô hình
const restoreThreadModelSelection = (threadId, history) => {
  if (selectedModelByThread[threadId]) return
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const msg = history[i]
    if (msg?.type !== 'human') continue
    const modelSpec = msg?.extra_metadata?.model_spec
    if (modelSpec) {
      selectedModelByThread[threadId] = modelSpec
      return
    }
  }
}

const fetchThreadFiles = async (threadId) => {
  if (!threadId) return
  try {
    const response = await threadApi.listThreadFiles(threadId, '/home/gem/user-data', false)
    const entries = Array.isArray(response?.files) ? response.files : []
    threadFilesMap.value[threadId] = entries
  } catch (error) {
    console.warn('Failed to fetch thread files:', error)
    threadFilesMap.value[threadId] = []
  }
}

const fetchThreadAttachments = async (threadId) => {
  if (!threadId) return
  try {
    const response = await threadApi.getThreadAttachments(threadId)
    threadAttachmentsMap.value[threadId] = Array.isArray(response?.attachments)
      ? response.attachments
      : []
  } catch (error) {
    console.warn('Failed to fetch thread attachments:', error)
    threadAttachmentsMap.value[threadId] = []
  }
}

const refreshThreadFilesAndAttachments = async (threadId) => {
  if (!threadId) return
  await Promise.all([fetchThreadFiles(threadId), fetchThreadAttachments(threadId)])
}

const handleArtifactSaved = async () => {
  if (!currentChatId.value) return
  await refreshThreadFilesAndAttachments(currentChatId.value)
  showFileTreePanel()
}

const fetchAgentState = async (agentId, threadId) => {
  if (!threadId) return
  try {
    const res = await agentApi.getAgentState(threadId)
    const targetState = getThreadState(threadId)
    if (!targetState) return
    targetState.agentState = res.agent_state || null
  } catch {
    // agent state is optional UI state
  }
}

const ensureActiveThread = async (title = 'Cuộc trò chuyện mới') => {
  if (currentChatId.value) return currentChatId.value
  try {
    const newThread = await createThread(currentAgentId.value, title || 'Cuộc trò chuyện mới')
    if (newThread) {
      setCurrentThreadId(newThread.id)
      return newThread.id
    }
  } catch {
    // createThread Thông báo lỗi đã được xử lý
  }
  return null
}

const handleAttachmentUpload = async (files = []) => {
  if (
    !AgentValidator.validateAgentIdWithError(
      currentAgentId.value,
      'Tải lênTệp đính kèm',
      handleValidationError
    )
  )
    return

  const droppedFiles = Array.from(files || []).filter((file) => file instanceof File)
  if (droppedFiles.length) {
    attachmentInitialFiles.value = droppedFiles
    attachmentInitialFilesKey.value += 1
  }

  attachmentUploadModalOpen.value = true
}

const ensureAttachmentThread = async () => {
  if (currentChatId.value) return currentChatId.value
  return await ensureActiveThread('Cuộc trò chuyện mới')
}

const handleTmpAttachmentsAdded = async () => {
  const threadId = currentChatId.value
  if (!threadId) return

  await Promise.all([
    fetchAgentState(currentAgentId.value, threadId),
    refreshThreadFilesAndAttachments(threadId)
  ])
  showFileTreePanel()
}

const handleAttachmentRemove = async (attachment) => {
  const threadId = currentChatId.value
  const fileId = attachment?.file_id
  if (!threadId || !fileId) return

  const previousAttachments = threadAttachmentsMap.value[threadId] || []
  threadAttachmentsMap.value[threadId] = previousAttachments.filter(
    (item) => item.file_id !== fileId
  )

  try {
    await threadApi.deleteThreadAttachment(threadId, fileId)
    await Promise.all([
      fetchAgentState(currentAgentId.value, threadId),
      refreshThreadFilesAndAttachments(threadId)
    ])
  } catch (error) {
    threadAttachmentsMap.value[threadId] = previousAttachments
    handleChatError(error, 'delete')
  }
}

// ==================== Quản lý chức năng phê duyệt ====================
const {
  approvalState,
  processApprovalInStream,
  restoreInterruptFromThreadState,
  hideApprovalState
} = useApproval({
  getThreadState,
  fetchThreadMessages
})

const restorePendingInterruptForThread = (threadId) => {
  if (!threadId) return false
  return restoreInterruptFromThreadState(threadId)
}

const { handleStreamChunk } = useAgentStreamHandler({
  getThreadState,
  processApprovalInStream,
  currentAgentId,
  supportsFiles,
  streamSmoother
})
const { startRunStream, resumeActiveRunForThread, stopRunStreamSubscription } = useAgentRunStream({
  getThreadState,
  currentAgentId,
  handleStreamChunk,
  fetchThreadMessages,
  fetchAgentState,
  resetOnGoingConv,
  onScrollToBottom: () => scrollController.scrollToBottom(),
  streamSmoother,
  onInterruptDetected: ({ threadId }) => {
    restorePendingInterruptForThread(threadId)
  },
  onTerminalDetected: ({ threadId, touchedThreadIds = [] }) => {
    if (approvalState.threadId === threadId || touchedThreadIds.includes(approvalState.threadId)) {
      hideApprovalState()
    }
  }
})

const resumeCurrentRunForVisiblePage = async () => {
  if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return
  const threadId = currentChatId.value
  if (!threadId) return

  try {
    await resumeActiveRunForThread(threadId)
    restorePendingInterruptForThread(threadId)
  } catch (error) {
    console.warn('Failed to resume current run after page became visible:', error)
  }
}

const handlePageVisibilityChange = () => {
  if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return
  void resumeCurrentRunForVisiblePage()
}

// ==================== CHAT ACTIONS ====================
// Lấy cuộc trò chuyện đầu tiên không được ưu tiên
const getFirstNonPinnedChat = (chatList) => {
  if (!chatList || chatList.length === 0) return null
  return chatList.find((chat) => !chat.is_pinned) || chatList[0]
}

const selectChat = async (chatId) => {
  const targetChat = threads.value.find((chat) => chat.id === chatId) || null
  const targetAgentId = targetChat?.agent_id || currentAgentId.value
  const previousThreadId = chatState.currentThreadId

  if (!targetAgentId) {
    handleValidationError('Thất bại khi chọn cuộc trò chuyện: thiếu thông tin về trí tuệ nhân tạo')
    return
  }

  if (
    !AgentValidator.validateAgentIdWithError(
      targetAgentId,
      'Chọn cuộc hội thoại',
      handleValidationError
    )
  )
    return

  // Ngắt luồng đầu ra của chủ đề trước (nếu có)）
  if (previousThreadId && previousThreadId !== chatId) {
    stopThreadStream(previousThreadId)
    // Chỉ ngắt kết nối đăng ký SSE của run, không hủy tác vụ đang chạy nền
    stopRunStreamSubscription(previousThreadId)
  }

  if (previousThreadId !== chatId) {
    resetAgentPanelState()
  }

  try {
    await withConfigNoticeSync(async () => {
      // Trước tiên cập nhật luồng hiện tại để đảm bảo tên trí tuệ nhân tạo ở phía dưới đồng bộ với mục đã chọn ngay lập tức。
      setCurrentThreadId(chatId)

      if (
        !props.singleMode &&
        targetChat?.agent_id &&
        targetChat.agent_id !== currentAgentId.value
      ) {
        await agentStore.selectAgent(targetChat.agent_id)
      }

      syncThreadConfigSnapshot(chatId)
    })
  } catch (error) {
    setCurrentThreadId(previousThreadId)
    handleChatError(error, 'load')
    return
  }

  chatUIStore.isLoadingMessages = true
  try {
    await fetchThreadMessages({ agentId: targetAgentId, threadId: chatId })
  } catch (error) {
    handleChatError(error, 'load')
  } finally {
    chatUIStore.isLoadingMessages = false
  }

  await nextTick()
  await scrollController.scrollToBottomStaticForce()
  // await fetchAgentState(targetAgentId, chatId)
  await handleAgentStateRefresh(chatId)
  syncThreadConfigSnapshot(chatId, { overwrite: false })
  await resumeActiveRunForThread(chatId)
  restorePendingInterruptForThread(chatId)
  await scrollController.scrollToBottomStaticForce()
}

const selectThreadFromRoute = async (threadId) => {
  if (!agentStore.isInitialized) {
    await initAll()
  }

  if (!threadId) {
    const previousThreadId = chatState.currentThreadId
    if (previousThreadId) {
      stopThreadStream(previousThreadId)
      stopRunStreamSubscription(previousThreadId)
    }
    resetAgentPanelState()
    setCurrentThreadId(null)
    return true
  }

  if (chatState.currentThreadId === threadId) {
    return true
  }

  if (!threads.value.length || !threads.value.find((thread) => thread.id === threadId)) {
    await loadChatsList()
  }

  const targetThread = threads.value.find((thread) => thread.id === threadId)
  if (!targetThread) {
    return false
  }

  await selectChat(threadId)
  return true
}

const handleSendMessage = async ({ image } = {}) => {
  const text = userInput.value.trim()
  const imageContent = image?.imageContent || null
  if (
    (!text && !image) ||
    !currentAgent.value ||
    isProcessing.value ||
    sendCooldownActive.value ||
    props.sendDisabled
  )
    return

  // Sau khi gửi, vào chế độ làm mát ngắn để ngăn chặn việc kích hoạt liên tục dừng lại
  startSendCooldown()

  let threadId = currentChatId.value
  if (!threadId) {
    threadId = await ensureActiveThread(text)
    if (!threadId) {
      message.error('Tạo cuộc trò chuyện thất bại, vui lòng thử lại')
      return
    }
    // Tạo chủ đề mới: Di chuyển lựa chọn mô hình ở trạng thái bản nháp vào chủ đề thực, tránh mất lựa chọn
    const draftModelSpec = selectedModelByThread[DRAFT_MODEL_KEY]
    if (draftModelSpec) {
      if (!selectedModelByThread[threadId]) {
        selectedModelByThread[threadId] = draftModelSpec
      }
      delete selectedModelByThread[DRAFT_MODEL_KEY]
    }
  }
  // Chỉ gửi bản ghi đè khi người dùng đã chọn mô hình rõ ràng; nếu không, gửi... null，Mô hình được cấu hình bởi tác nhân sử dụng bởi backend
  const modelSpec = selectedModelByThread[threadId] || null

  userInput.value = ''

  await nextTick()
  scrollController.scrollToBottom(true)

  const threadState = getThreadState(threadId)
  if (!threadState) return
  threadState.pendingInterrupt = null
  if (approvalState.threadId === threadId) {
    hideApprovalState()
  }

  const pendingAttachments = [...currentPendingThreadAttachments.value]
  const pendingAttachmentFileIds = pendingAttachments
    .map((attachment) => attachment.file_id)
    .filter(Boolean)

  if ((threadMessages.value[threadId] || []).length === 0) {
    const autoTitle = text.replace(/\s+/g, ' ').trim().slice(0, 2000)
    if (autoTitle) {
      void (async () => {
        try {
          const generatedTitle = await agentApi.generateTitle(
            autoTitle,
            configStore.config?.fast_model
          )
          if (generatedTitle) {
            const finalTitle = generatedTitle.slice(0, 30).replace(/\s+/g, ' ').trim()
            if (finalTitle) {
              void chatThreadsStore.updateThread(threadId, finalTitle).catch(() => {})
            }
          }
        } catch (e) {
          console.error('Title generation failed:', e)
          void chatThreadsStore.updateThread(threadId, autoTitle.slice(0, 30)).catch(() => {})
        }
      })()
    }
  }

  resetOnGoingConv(threadId)
  const requestId = createClientRequestId()
  const previousAttachments = markAttachmentsRequestId(threadId, pendingAttachments, requestId)
  insertOptimisticHumanMessage(threadState, {
    requestId,
    text,
    imageContent,
    attachments: pendingAttachments.map((attachment) => ({
      ...attachment,
      request_id: requestId
    }))
  })
  threadState.isStreaming = true

  try {
    const runResp = await agentApi.createAgentRun({
      query: text,
      agent_slug: currentAgentId.value,
      thread_id: threadId,
      meta: {
        request_id: requestId,
        attachment_file_ids: pendingAttachmentFileIds
      },
      image_content: imageContent,
      model_spec: modelSpec
    })
    const runId = runResp?.run_id
    if (!runId) {
      throw new Error('Tạo run Thất bại: Thiếu run_id')
    }
    await startRunStream(threadId, runId, 0)
  } catch (error) {
    threadState.isStreaming = false
    threadState.replyLoadingVisible = false
    threadState.pendingRequestId = null
    rollbackAttachments(threadId, previousAttachments)
    resetOnGoingConv(threadId)
    handleChatError(error, 'send')
  }
}

// Gửi hoặc ngắt
const handleSendOrStop = async (payload) => {
  if (sendCooldownActive.value) {
    return
  }

  const threadId = currentChatId.value
  const threadState = getThreadState(threadId)
  if (isProcessing.value && threadState?.activeRunId) {
    try {
      await agentApi.cancelAgentRun(threadState.activeRunId)
      threadState.pendingInterrupt = null
      if (approvalState.threadId === threadId) {
        hideApprovalState()
      }
      message.info('Đã gửi yêu cầu hủy')
    } catch (error) {
      handleChatError(error, 'stop')
    }
    return
  }
  if (props.sendDisabled) return
  await handleSendMessage(payload)
}

// ==================== Xử lý phê duyệt thủ công ====================
const handleApprovalWithStream = async (answer) => {
  const threadId = approvalState.threadId
  const interruptedRunId = approvalState.interruptedRunId
  if (!threadId) {
    message.error('Yêu cầu đặt câu hỏi không hợp lệ')
    approvalState.showModal = false
    return
  }

  const threadState = getThreadState(threadId)
  if (!threadState) {
    message.error('Không thể tìm thấy chuỗi hội thoại tương ứng')
    approvalState.showModal = false
    return
  }

  if (!interruptedRunId) {
    message.error('Không thể tìm thấy tác vụ đang chạy cần khôi phục')
    approvalState.showModal = false
    return
  }

  const pendingInterrupt = threadState.pendingInterrupt

  try {
    hideApprovalState()
    threadState.pendingInterrupt = null
    threadState.isStreaming = true
    resetOnGoingConv(threadId)
    const requestId = createClientRequestId()
    const runResp = await agentApi.createAgentRun({
      query: null,
      agent_slug: currentAgentId.value,
      thread_id: threadId,
      meta: { request_id: requestId },
      resume: answer,
      created_by_run_id: interruptedRunId
    })
    const runId = runResp?.run_id
    if (!runId) {
      throw new Error('Tạo resume run Thất bại: Thiếu run_id')
    }
    await startRunStream(threadId, runId, '0-0')
  } catch (error) {
    if (pendingInterrupt) {
      threadState.pendingInterrupt = pendingInterrupt
      restorePendingInterruptForThread(threadId)
    }
    threadState.isStreaming = false
    threadState.replyLoadingVisible = false
    handleChatError(error, 'resume')
  }
}

const handleQuestionSubmit = (answer) => {
  handleApprovalWithStream(answer)
}

const handleQuestionCancel = () => {
  handleApprovalWithStream('reject')
}

const buildExportPayload = () => {
  const agentId = currentAgentId.value
  let agentDescription = ''
  if (agentId && agents.value && agents.value.length > 0) {
    const agent = agents.value.find((a) => a.id === agentId)
    agentDescription = agent ? agent.description || '' : ''
  }

  const payload = {
    chatTitle: currentThread.value?.title || 'Cuộc trò chuyện mới',
    agentName: currentAgentName.value || currentAgent.value?.name || 'Trợ lý thông minh',
    agentDescription: agentDescription || currentAgent.value?.description || '',
    messages: conversations.value ? JSON.parse(JSON.stringify(conversations.value)) : [],
    onGoingMessages: onGoingConvMessages.value
      ? JSON.parse(JSON.stringify(onGoingConvMessages.value))
      : []
  }

  return payload
}

defineExpose({
  getExportPayload: buildExportPayload,
  selectThreadFromRoute
})

const handleAgentStateRefresh = async (threadId = null) => {
  if (!currentAgentId.value) return
  const chatId = threadId || currentChatId.value
  if (!chatId) return
  isRefreshingState.value = true
  try {
    await Promise.all([
      fetchAgentState(currentAgentId.value, chatId),
      refreshThreadFilesAndAttachments(chatId)
    ])
  } finally {
    isRefreshingState.value = false
  }
}

const toggleStatePanel = async () => {
  const nextOpen = !statePanelOpen.value
  statePanelOpen.value = nextOpen
  if (nextOpen && currentChatId.value && !currentAgentState.value) {
    await handleAgentStateRefresh()
  }
}

const closeFilePanel = () => {
  isFilePanelOpen.value = false
  filePanelDragWidth.value = null
}

const toggleAgentPanel = async () => {
  const nextOpen = !isFilePanelOpen.value

  if (!nextOpen) {
    closeFilePanel()
    return
  }

  showFileTreePanel()
  await handleAgentStateRefresh()
}

// Điều chỉnh chiều rộng bảng xử lý (sử dụng tỷ lệ)
// Kéo sang phải(deltaX > 0)Làm cho bảng điều khiển hẹp lại, kéo sang trái(deltaX < 0)Làm rộng bảng điều khiển
const handlePanelResize = (clientX) => {
  if (!panelWrapperRef.value) return

  if (!panelContainerWidth) {
    panelContainerWidth = getPanelContainerWidth()
  }

  const deltaX = clientX - resizeStartX
  const rawWidth = resizeStartWidth - deltaX
  const maxWidth = getFilePanelMaxWidth(panelContainerWidth)
  const minWidth = getFilePanelMinWidth(panelContainerWidth, maxWidth)
  const nextWidth = Math.max(minWidth, Math.min(rawWidth, maxWidth))

  filePanelDragWidth.value = nextWidth

  if (nextWidth !== rawWidth) {
    resizeStartX = clientX
    resizeStartWidth = nextWidth
  }
}

// Khi trạng thái kéo thả thay đổi, đồng bộ trạng thái cuối cùng đến Vue Dữ liệu phản hồi
const handleResizingChange = (isResizingState, clientX = 0) => {
  isResizing.value = isResizingState

  if (isResizingState && panelWrapperRef.value) {
    resizeStartX = clientX
    resizeStartWidth = panelWrapperRef.value.offsetWidth
    filePanelDragWidth.value = resizeStartWidth
    if (!panelContainerWidth) {
      panelContainerWidth = getPanelContainerWidth()
    }
    return
  }

  if (!isResizingState && panelWrapperRef.value && panelContainerWidth) {
    const finalWidth = filePanelDragWidth.value ?? panelWrapperRef.value.offsetWidth
    panelRatio.value = clampPanelRatio(finalWidth / panelContainerWidth, panelContainerWidth)
  }

  if (!isResizingState) {
    filePanelDragWidth.value = null
    resizeStartX = 0
    resizeStartWidth = 0
    panelContainerWidth = 0 // Đặt lại để sử dụng lần sau
  }
}

// ==================== HELPER FUNCTIONS ====================
const getMessageToolCalls = (message) => {
  return enrichTaskToolCalls(message?.tool_calls, {
    subagentRunById: currentSubagentRunById.value,
    subagentRunByThreadId: currentSubagentRunByThreadId.value,
    subagentOptionBySlug: currentSubagentOptionBySlug.value
  })
}

const getDisplayItems = (conv) =>
  getConversationDisplayItems(conv, { enrichToolCalls: getMessageToolCalls })

const isDisplayMessageProcessing = (conv, displayItem) => {
  return (
    displayItem?.type === 'message' &&
    isReplyLoading.value &&
    conv?.status === 'streaming' &&
    displayItem.sourceIndex === conv.messages.length - 1
  )
}

const isToolGroupActive = (conv, itemIndex, displayItems) => {
  return (
    isReplyLoading.value && conv?.status === 'streaming' && itemIndex === displayItems.length - 1
  )
}

const getLastMessage = (conv) => {
  if (!conv?.messages?.length) return null
  for (let i = conv.messages.length - 1; i >= 0; i--) {
    if (conv.messages[i].type === 'ai') return conv.messages[i]
  }
  return null
}

const showMsgRefs = (msg, conv) => {
  if (shouldSuppressRefsForApproval()) {
    return false
  }

  // Cuộc hội thoại chứa tin nhắn này chưa kết thúc (phía sau không có human message mà là AI tiếp tục viết hoặc vẫn đang tạo), không hiển thị
  if (!isConversationSettled(conv)) {
    return false
  }

  // Chỉ những tin nhắn thực sự hoàn thành mới hiển thị refs
  if (msg.isLast && msg.status === 'finished') {
    return ['copy', 'sources']
  }
  return false
}

const getConversationSources = (conv) => {
  return MessageProcessor.extractSourcesFromConversation(conv, availableKnowledgeBases.value)
}

// ==================== LIFECYCLE & WATCHERS ====================
const loadChatsList = async () => {
  const agentId = props.singleMode ? currentAgentId.value : null
  if (props.singleMode && !agentId) {
    console.warn('No agent selected, cannot load chats list')
    threads.value = []
    resetAgentPanelState()
    setCurrentThreadId(null)
    threadFilesMap.value = {}
    threadAttachmentsMap.value = {}
    return
  }

  try {
    await fetchThreads(agentId)
    if (props.singleMode && currentAgentId.value !== agentId) return

    // Nếu luồng hiện tại không có trong danh sách luồng, xóa luồng hiện tại
    if (
      chatState.currentThreadId &&
      !threads.value.find((t) => t.id === chatState.currentThreadId)
    ) {
      setCurrentThreadId(null)
    }

    // singleMode Giữ lại hành vi cũ: Tự động chọn cuộc trò chuyện có sẵn đầu tiên
    if (props.singleMode && threads.value.length > 0 && !chatState.currentThreadId) {
      await selectChat(getFirstNonPinnedChat(threads.value).id)
    }
  } catch (error) {
    handleChatError(error, 'load')
  }
}

const initAll = async () => {
  try {
    if (!agentStore.isInitialized) {
      await agentStore.initialize()
    }
  } catch (error) {
    handleChatError(error, 'load')
  }
}

onMounted(async () => {
  await initAll()
  scrollController.enableAutoScroll()
})

watch(showStateEntry, (visible) => {
  if (!visible && statePanelOpen.value) {
    statePanelOpen.value = false
  }
})

watch(showFileEntry, (visible) => {
  if (!visible && isFilePanelOpen.value) {
    closeFilePanel()
  }
})

watch(
  shouldRefreshStateWhileStreaming,
  (shouldRefresh) => {
    if (shouldRefresh) {
      void handleAgentStateRefresh()
      startStreamingStateRefresh()
    } else {
      stopStreamingStateRefresh()
    }
  },
  { immediate: true }
)

watch(
  currentAgentId,
  async (newAgentId, oldAgentId) => {
    if (!props.singleMode) {
      if (oldAgentId === undefined) {
        await loadChatsList()
      }
      return
    }

    if (newAgentId !== oldAgentId) {
      // Xóa trạng thái hiện tại của luồng
      setCurrentThreadId(null)
      threadMessages.value = {}
      threadFilesMap.value = {}
      threadAttachmentsMap.value = {}
      resetAgentPanelState()
      // Dọn dẹp tất cả trạng thái luồng
      resetOnGoingConv()

      if (newAgentId) {
        await loadChatsList()
      } else {
        threads.value = []
      }
    }
  },
  { immediate: true }
)

watch(
  currentThreadMessages,
  () => {
    if (currentThreadHasHistory.value) {
      flushPendingThreadConfigNotice(currentChatId.value)
      syncThreadConfigSnapshot(currentChatId.value, { overwrite: false })
    }
  },
  { deep: false }
)

watch(currentAgentId, (newAgentId, oldAgentId) => {
  if (oldAgentId === undefined || newAgentId === oldAgentId) return
  maybeInsertThreadConfigNotice()
})

watch(
  () => JSON.stringify(agentConfig.value || {}),
  (newConfigJson, oldConfigJson) => {
    if (oldConfigJson === undefined || newConfigJson === oldConfigJson) return
    maybeInsertThreadConfigNotice()
  }
)

watch(
  conversations,
  () => {
    if (isProcessing.value) {
      scrollController.scrollToBottom()
    }
  },
  { deep: true, flush: 'post' }
)

watch(
  configNoticeScrollVersion,
  () => {
    if (!currentChatId.value) return
    scrollController.scrollToBottom(true)
  },
  { flush: 'post' }
)

watch(currentChatId, (threadId, oldThreadId) => {
  if (threadId === oldThreadId) return
  if (!threadId || approvalState.threadId !== threadId) {
    hideApprovalState()
  }
  if (threadId) {
    restorePendingInterruptForThread(threadId)
  }
  emit('thread-change', threadId || '')
})
</script>

<style lang="less" scoped>
@import '@/assets/css/main.css';
@import '@/assets/css/animations.less';

.chat-container {
  display: flex;
  width: 100%;
  height: 100%;
  position: relative;
}

.chat {
  --header-height: 40px;

  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden; /* Changed from overflow-x: hidden to overflow: hidden */
  position: relative;
  box-sizing: border-box;
  transition: all 0.3s ease;

  .chat-header {
    user-select: none;
    z-index: 10;
    height: var(--header-height);
    min-height: var(--header-height);
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 8px;
    flex-shrink: 0; /* Prevent header from shrinking */
    transition: padding-right 0.3s cubic-bezier(0.4, 0, 0.2, 1);

    &.has-active-thread {
      border-bottom: 1px solid var(--gray-150);
    }

    .header__left,
    .header__right {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .switch-icon {
      color: var(--gray-500);
      transition: all 0.2s ease;
    }

    .agent-nav-btn:hover .switch-icon {
      color: var(--main-500);
    }

    .conversation-title {
      font-size: 14px;
      line-height: 20px;
      font-weight: 400;
      color: var(--text-primary);
      max-width: 200px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      margin-left: 8px;
    }
  }

  &.has-file-panel .chat-header {
    padding-right: calc(var(--file-panel-width) + 8px);
  }

  &.is-resizing-file-panel {
    .chat-header,
    .chat-main {
      transition: none;
    }
  }
}

.chat-content-container {
  flex: 1;
  display: flex;
  flex-direction: row;
  overflow: hidden;
  position: relative;
  width: 100%;
  contain: layout;
}

.chat-main {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto; /* Scroll is here now */
  position: relative;
  transition:
    flex-basis 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    margin-right 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  min-width: 0; /* Prevent flex item from overflowing */

  scrollbar-width: none;
}

.chat-content-container.has-file-panel .chat-main {
  margin-right: var(--file-panel-width);
}

.side-panel {
  flex: 0 0 auto;
  overflow: hidden;
  background: var(--gray-0);
  border: 1px solid var(--gray-150);
  border-radius: 10px;
  box-shadow:
    0 16px 40px var(--shadow-1),
    0 2px 10px var(--shadow-0);
  z-index: 20;
  min-width: 0;
  opacity: 0;
  pointer-events: none;
  transform: translateX(10px);
  will-change: width, flex-basis, opacity, transform;
  transition:
    width 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    flex-basis 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.side-panel.is-visible {
  opacity: 1;
  pointer-events: auto;
  transform: translateX(0);
}

.side-panel.no-transition {
  transition: none !important;
}

.side-panel--file {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 30;
  display: flex;
  height: auto;
  max-width: 100%;
  border: none;
  border-left: 1px solid var(--gray-150);
  border-radius: 0;
  box-shadow: none;
}

.side-panel--file.is-visible {
  min-width: 0;
}

.side-panel--state {
  height: auto;
  max-height: calc(100% - 8px);
  max-width: min(340px, calc(100vw - 24px));
  box-shadow: 0 4px 16px var(--shadow-0);
  overflow: auto;
}

.side-panel--state.is-visible {
  min-width: 300px;
}

.side-panel--state.is-docked {
  align-self: flex-start;
  margin: 8px 8px 8px 0;
  max-height: calc(100% - 16px);
}

.side-panel--state.is-floating {
  position: absolute;
  top: 8px;
  right: calc(var(--file-panel-width) + 8px);
  width: min(340px, calc(100% - var(--file-panel-width) - 24px));
  min-width: 0;
  max-height: calc(100% - 16px);
  margin: 0;
  z-index: 26;
  box-shadow:
    0 12px 28px var(--shadow-1),
    0 2px 8px var(--shadow-0);
}

.state-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--gray-0);
}

.chat-greeting-input {
  padding: 24px 0;
  text-align: center;

  h1 {
    font-size: 1.4rem;
    color: var(--gray-1000);
    margin: 0;
  }
}

.agent-segment-wrapper {
  width: fit-content;
  max-width: 100%;
  margin: 0 auto 18px;
  overflow-x: auto;
  scrollbar-width: none;

  &::-webkit-scrollbar {
    display: none;
  }

  :deep(.ant-segmented) {
    width: auto;
    max-width: 100%;
    white-space: nowrap;
    background: var(--gray-50);
    border: 1px solid var(--gray-150);
    border-radius: 10px;
  }

  :deep(.ant-segmented-group) {
    width: auto;
    display: inline-flex;
  }

  :deep(.ant-segmented-item) {
    flex: 0 0 auto;
    min-width: 0;
  }

  :deep(.ant-segmented-item-label) {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.agent-switcher-wrapper {
  display: flex;
  justify-content: center;
  margin: 0 auto 18px;
}

.agent-switcher-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
  padding: 4px 12px;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-0);
  color: var(--gray-900);
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease;

  &:hover {
    background: var(--gray-0);
    border-color: var(--gray-200);
  }
}

.agent-switcher-icon,
.agent-switcher-chevron {
  flex-shrink: 0;
  color: var(--gray-600);
}

.agent-switcher-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.agent-switcher-menu) {
  min-width: 220px;
}

:deep(.agent-switcher-menu-item) {
  display: flex;
  align-items: center;
  gap: 8px;
}

:deep(.agent-switcher-menu-icon) {
  flex-shrink: 0;
  color: var(--gray-600);
}

:deep(.agent-switcher-menu-text) {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.agent-switcher-menu-badge) {
  flex-shrink: 0;
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--main-30);
  color: var(--main-700);
  font-size: 12px;
}

.chat-loading {
  padding: 0 50px;
  text-align: center;
  position: absolute;
  top: 20%;
  width: 100%;
  z-index: 9;
  animation: slideInUp 0.5s ease-out;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;

  span {
    color: var(--gray-700);
    font-size: 14px;
  }

  .loading-spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--gray-200);
    border-top-color: var(--main-color);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
}

.chat-box {
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
  flex-grow: 1;
  padding: 1rem var(--page-padding);
  display: flex;
  flex-direction: column;
}

.conv-box {
  display: flex;
  flex-direction: column;
}

.chat-inline-notice {
  display: flex;
  justify-content: center;
  padding: 6px 16px 12px;
  color: var(--gray-500);
  font-size: 12px;
  line-height: 1.6;
  text-align: center;
}

.bottom {
  position: sticky;
  bottom: 0;
  width: 100%;
  margin: 0 auto;
  padding: 4px 1rem 0 1rem;
  z-index: 1000;

  .message-input-wrapper {
    width: 100%;
    max-width: 800px;
    margin: 0 auto;

    .bottom-actions {
      display: flex;
      justify-content: center;
      align-items: center;
      width: 100%;
      background: var(--gray-0);
    }

    .note {
      font-size: small;
      color: var(--gray-300);
      margin: 4px 0;
      user-select: none;
    }
  }

  .input-model-selector {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 0;
    max-width: min(168px, calc(100vw - 160px));
  }

  &.start-screen {
    position: absolute;
    top: 45%;
    left: 50%;
    transform: translate(-50%, -50%);
    bottom: auto;
    max-width: 800px;
    width: 90%;
    background: transparent;
    padding: 0;
    border-top: none;
    z-index: 100; /* Ensure it's above other elements */
  }
}

.loading-dots {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
}

.loading-dots div {
  width: 6px;
  height: 6px;
  background: linear-gradient(135deg, var(--main-color), var(--main-700));
  border-radius: 50%;
  animation: dotPulse 1.4s infinite ease-in-out both;
}

.loading-dots div:nth-child(1) {
  animation-delay: -0.32s;
}

.loading-dots div:nth-child(2) {
  animation-delay: -0.16s;
}

.loading-dots div:nth-child(3) {
  animation-delay: 0s;
}

.generating-status {
  display: flex;
  justify-content: flex-start;
  padding: 1rem 0;
  animation: fadeInUp 0.4s ease-out;
  transition: all 0.2s;
}

.generating-indicator {
  display: flex;
  align-items: center;
  padding: 0.75rem 0rem;

  .generating-text {
    margin-left: 12px;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.025em;
    /* Khôi phục tông màu xám: Xám đậm -> Xám sáng (highlight)) -> Xám đậm */
    background: linear-gradient(
      90deg,
      var(--gray-700) 0%,
      var(--gray-700) 40%,
      var(--gray-300) 45%,
      var(--gray-200) 50%,
      var(--gray-300) 55%,
      var(--gray-700) 60%,
      var(--gray-700) 100%
    );
    background-size: 200% auto;
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    animation: waveFlash 2s linear infinite;
  }
}

@keyframes waveFlash {
  0% {
    background-position: 200% center;
  }
  100% {
    background-position: -200% center;
  }
}

@media (max-width: 1024px) {
  .chat-content-container.has-file-panel .chat-main,
  .chat-content-container.has-state-panel .chat-main {
    min-width: 350px;
  }

  .side-panel--file.is-visible,
  .side-panel--state.is-docked.is-visible {
    max-width: 100%;
  }
}

@media (max-width: 768px) {
  .chat.has-file-panel .chat-header {
    padding-right: 8px;
  }

  .chat-content-container.has-file-panel .chat-main,
  .chat-content-container.has-state-panel .chat-main {
    margin-right: 0;
    min-width: 0;
  }

  .side-panel--file {
    top: calc(var(--header-height) + 4px);
  }

  .side-panel--file.is-visible {
    min-width: 0;
    max-width: calc(100% - 16px);
  }

  .side-panel--state.is-visible {
    min-width: 0;
    max-width: calc(100% - 24px);
  }

  .side-panel--state.is-floating {
    right: 12px;
    width: min(320px, calc(100% - 24px));
  }

  .agent-segment-wrapper {
    margin-bottom: 8px;

    :deep(.ant-segmented-item-label) {
      font-size: 12px;
    }
  }

  .agent-switcher-wrapper {
    margin-bottom: 8px;
  }

  .agent-switcher-btn {
    width: 100%;
    justify-content: center;
  }

  .chat-header {
    .header__left {
      .text {
        display: none;
      }
    }
  }
}

// Định vị biểu tượng trong chọn trí tuệ nhân tạo
.agent-segment-wrapper {
  :deep(.ant-segmented-item-label) {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  :deep(.agent-option-label) {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  :deep(.agent-option-icon) {
    flex-shrink: 0;
    color: var(--gray-600);
  }
}
</style>

<style lang="less">
.agent-nav-btn {
  display: flex;
  gap: 5px;
  padding: 4px 7px;
  height: 28px;
  justify-content: center;
  align-items: center;
  border-radius: 6px;
  color: var(--gray-900);
  cursor: pointer;
  width: auto;
  font-size: 14px;
  line-height: 20px;
  transition: background-color 0.3s;
  border: none;
  background: transparent;

  &:hover:not(.is-disabled) {
    background-color: var(--gray-100);
  }

  &.is-disabled {
    cursor: not-allowed;
    opacity: 0.7;
    pointer-events: none;
  }

  .nav-btn-icon {
    width: 16px;
    height: 16px;
  }

  .loading-icon {
    animation: spin 1s linear infinite;
  }
}

.side-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: var(--header-height);
  padding: 4px 12px;
  background: var(--gray-25);
  border-bottom: 1px solid var(--gray-100);
  flex-shrink: 0;
}

.state-entry-btn.active {
  color: var(--main-700);
  background-color: var(--main-20);
}

.state-panel-header {
  padding: 10px 14px;
  padding-bottom: 0px;
  background: transparent;
  border-bottom: none;
}

.state-panel-header-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.state-refresh-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: 6px;
  color: var(--gray-500);
  background: transparent;
  cursor: pointer;

  &:hover:not(:disabled) {
    color: var(--main-700);
    background: var(--gray-100);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .is-spinning {
    animation: spin 1s linear infinite;
  }
}

.state-panel-title {
  min-width: 0;
  font-size: 14px;
  font-weight: 400;
  color: var(--gray-500);
}

.state-panel-summary,
.state-section-meta {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--gray-500);
}

.state-panel-body {
  flex: 1;
  min-height: 0;
  padding: 8px 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: auto;
}

.state-section {
  display: flex;
  flex-direction: column;
  gap: 8px;

  &.is-collapsed {
    gap: 0;
  }
}

.state-section-header {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 2px 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;

  &:hover {
    .state-section-title,
    .state-section-chevron {
      color: var(--gray-900);
    }
  }

  &:focus-visible {
    outline: 2px solid var(--main-200);
    outline-offset: 2px;
  }
}

.state-section-label {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.state-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-800);
}

.state-section-chevron {
  flex-shrink: 0;
  color: var(--gray-500);
  transition:
    transform 0.18s ease,
    color 0.18s ease;

  &.is-collapsed {
    transform: rotate(-90deg);
  }
}

.state-section-content {
  min-width: 0;
}

.state-panel-empty {
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--gray-25);
  color: var(--gray-500);
  font-size: 13px;
  text-align: center;
}

.token-usage-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 2px;
}

.token-usage-stack {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.token-usage-stack-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: var(--gray-500);
}

.token-usage-stack-head strong {
  color: var(--gray-900);
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.token-usage-stack-track {
  display: flex;
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--gray-100);
}

.token-usage-stack-segment {
  height: 100%;
  min-width: 2px;
  transition: width 0.2s ease;
}

.token-usage-stack-legend {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 10px;
  font-size: 11px;
  color: var(--gray-500);
}

.token-usage-stack-legend-item {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  line-height: 1.35;
  white-space: normal;
}

.token-usage-stack-legend-item i {
  width: 7px;
  height: 7px;
  flex-shrink: 0;
  border-radius: 2px;
  background: var(--gray-300);
}

.token-usage-stack-segment,
.token-usage-stack-legend-item i {
  &.is-cut {
    background-color: var(--main-500);
    background-image: repeating-linear-gradient(
      135deg,
      var(--main-30) 0,
      var(--main-30) 1px,
      transparent 1px,
      transparent 4px
    );
  }

  &.is-messages {
    background: var(--main-500);
  }

  &.is-tool-messages {
    background: var(--color-primary-500);
  }

  &.is-summary {
    background: var(--color-info-500);
  }

  &.is-system {
    background: var(--color-success-500);
  }

  &.is-tools {
    background: var(--color-warning-500);
  }

  &.is-overhead {
    background: var(--gray-300);
  }
}

.token-usage-breakdown {
  display: flex;
  flex-direction: column;
  gap: 6px 10px;
  padding-top: 2px;
}

.token-usage-breakdown-row {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 6px;
  font-size: 12px;
  color: var(--gray-500);
  flex-wrap: wrap;
}

.token-usage-breakdown-row span,
.token-usage-breakdown-row strong {
  min-width: 0;
  white-space: normal;
}

.token-usage-breakdown-row strong {
  flex: 1 1 100%;
  color: var(--gray-800);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1.35;
  word-break: break-word;
}

.todo-panel-list {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.todo-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
}

.todo-item:last-child {
  border-bottom: none;
}

.todo-item-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--gray-50);
  color: var(--gray-500);

  &.completed {
    background: var(--color-success-10);
    color: var(--color-success-700);
  }

  &.in_progress {
    background: var(--color-info-10);
    color: var(--color-info-700);
  }

  &.pending {
    background: var(--color-warning-10);
    color: var(--color-warning-700);
  }

  &.cancelled {
    background: var(--color-error-10);
    color: var(--color-error-700);
  }
}

.todo-item-body {
  min-width: 0;
}

.todo-item-text {
  font-size: 13px;
  line-height: 1.5;
  color: var(--gray-700);
  word-break: break-word;
}

.state-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.state-list-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 9px;
  border: 1px solid var(--gray-100);
  border-radius: 10px;
  background: var(--gray-25);
  color: inherit;
  text-align: left;
}

.state-list-item--button {
  cursor: pointer;
}

.state-list-item--button:hover,
.state-list-item.is-clickable:hover {
  border-color: var(--main-200);
  background: var(--gray-0);
}

.state-list-item.is-clickable {
  cursor: pointer;
}

.state-list-item-icon {
  flex-shrink: 0;
  font-size: 17px;
}

.state-list-item-body {
  min-width: 0;
  flex: 1;
}

.state-list-item-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--gray-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.state-list-item-meta {
  margin-top: 1px;
  font-size: 12px;
  line-height: 1.25;
  color: var(--gray-500);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.state-subagent-icon {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border: 1px solid var(--gray-150);
  border-radius: 6px;
  background: var(--gray-0);
  object-fit: cover;
}

.state-subagent-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.state-subagent-title span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.state-subagent-status-icon {
  flex-shrink: 0;
  font-size: 13px;
}

.state-subagent-completed-icon {
  color: var(--color-success-700);
}

.state-subagent-failed-icon {
  color: var(--color-error-700);
}

.state-subagent-running-icon {
  color: var(--color-info-700);
}

.hide-text {
  display: none;
}

@media (min-width: 769px) {
  .hide-text {
    display: inline;
  }
}

/* AgentState Kiểu dáng nút khi có nội dung */
.agent-nav-btn.agent-state-btn.has-content:hover:not(.is-disabled) {
  color: var(--gray-900);
  background-color: var(--gray-100);
}

.agent-nav-btn.agent-state-btn.active {
  color: var(--gray-900);
  background-color: var(--gray-100);
}
</style>
