<template>
  <div class="dashboard-container">
    <!-- thanh trạng thái trên cùng -->

    <!-- Thanh thống kê hàng đầu hiện đại -->
    <div class="modern-stats-header">
      <StatusBar />
      <StatsOverviewComponent :basic-stats="basicStats" @open-feedback="handleOpenFeedback" />
    </div>

    <!-- GridKhu vực nội dung chính của bố cục -->
    <div class="dashboard-grid">
      <!-- Mô-đun thống kê cuộc gọi - chiếm giữ2x1lưới -->
      <CallStatsComponent :loading="loading" ref="callStatsRef" />

      <!-- Phân tích hoạt động của người dùng - chiếm giữ1x1lưới -->
      <div class="grid-item user-stats">
        <UserStatsComponent
          :user-stats="allStatsData?.users"
          :loading="loading"
          ref="userStatsRef"
        />
      </div>

      <!-- AIphân tích tác nhân - chiếm giữ1x1lưới -->
      <div class="grid-item agent-stats">
        <AgentStatsComponent
          :agent-stats="allStatsData?.agents"
          :loading="loading"
          ref="agentStatsRef"
        />
      </div>

      <!-- Giám sát cuộc gọi công cụ - chiếm giữ1x1lưới -->
      <div class="grid-item tool-stats">
        <ToolStatsComponent
          :tool-stats="allStatsData?.tools"
          :loading="loading"
          ref="toolStatsRef"
        />
      </div>

      <!-- Cách sử dụng cơ sở kiến thức - chiếm giữ1x1lưới -->
      <div class="grid-item knowledge-stats">
        <KnowledgeStatsComponent
          :knowledge-stats="allStatsData?.knowledge"
          :loading="loading"
          ref="knowledgeStatsRef"
        />
      </div>
    </div>

    <!-- Hộp phương thức phản hồi -->
    <FeedbackModalComponent ref="feedbackModal" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { dashboardApi } from '@/apis/dashboard_api'

// Nhập thành phần phụ
import StatusBar from '@/components/StatusBar.vue'
import UserStatsComponent from '@/components/dashboard/UserStatsComponent.vue'
import ToolStatsComponent from '@/components/dashboard/ToolStatsComponent.vue'
import KnowledgeStatsComponent from '@/components/dashboard/KnowledgeStatsComponent.vue'
import AgentStatsComponent from '@/components/dashboard/AgentStatsComponent.vue'
import CallStatsComponent from '@/components/dashboard/CallStatsComponent.vue'
import StatsOverviewComponent from '@/components/dashboard/StatsOverviewComponent.vue'
import FeedbackModalComponent from '@/components/dashboard/FeedbackModalComponent.vue'

// tham chiếu thành phần
const feedbackModal = ref(null)

// Thống kê - Sử dụng các cấu trúc đáp ứng mới
const basicStats = ref({})
const allStatsData = ref({
  users: null,
  tools: null,
  knowledge: null,
  agents: null
})

// Danh sách cuộc trò chuyện
const loading = ref(false)

// Tham chiếu thành phần phụ thống kê cuộc gọi
const callStatsRef = ref(null)

// tham chiếu thành phần phụ
const userStatsRef = ref(null)
const toolStatsRef = ref(null)
const knowledgeStatsRef = ref(null)
const agentStatsRef = ref(null)

// Tải số liệu thống kê - Sử dụng song songAPIgọi
const loadAllStats = async () => {
  loading.value = true
  try {
    // Sử dụng song songAPIGọi để nhận tất cả số liệu thống kê
    const response = await dashboardApi.getAllStats()

    // Cập nhật số liệu thống kê cơ bản
    basicStats.value = response.basic

    // Cập nhật số liệu thống kê chi tiết
    allStatsData.value = {
      users: response.users,
      tools: response.tools,
      knowledge: response.knowledge,
      agents: response.agents
    }

    console.log('Dashboard Tải dữ liệu hoàn tất:', response)
    message.success('Dữ liệu được tải thành công')
  } catch (error) {
    console.error('Không tải được số liệu thống kê:', error)
    message.error('Không tải được số liệu thống kê')

    // Nếu yêu cầu song song không thành công，Hãy thử tải riêng dữ liệu cơ bản
    try {
      const basicResponse = await dashboardApi.getStats()
      basicStats.value = basicResponse
      message.warning('Tải dữ liệu chi tiết không thành công，Chỉ hiển thị số liệu thống kê cơ bản')
    } catch (basicError) {
      console.error('Tải số liệu thống kê cơ bản cũng không thành công:', basicError)
      message.error('Không thể tải bất kỳ số liệu thống kê nào')
    }
  } finally {
    loading.value = false
  }
}

// Mở cửa sổ bật lên chi tiết phản hồi
const handleOpenFeedback = () => {
  feedbackModal.value?.show()
}

// Chức năng dọn dẹp - Dọn dẹp các phiên bản biểu đồ của tất cả các thành phần con
const cleanupCharts = () => {
  if (userStatsRef.value?.cleanup) userStatsRef.value.cleanup()
  if (toolStatsRef.value?.cleanup) userStatsRef.value.cleanup()
  if (knowledgeStatsRef.value?.cleanup) knowledgeStatsRef.value.cleanup()
  if (agentStatsRef.value?.cleanup) agentStatsRef.value.cleanup()
  if (callStatsRef.value?.cleanup) callStatsRef.value.cleanup()
}

// khởi tạo
onMounted(() => {
  loadAllStats()
})

// Làm sạch biểu đồ khi thành phần được dỡ xuống
onUnmounted(() => {
  cleanupCharts()
})
</script>

<style scoped lang="less">
.dashboard-container {
  background-color: var(--gray-25);
  min-height: calc(100vh - 64px);
  overflow-x: hidden;
}

// Dashboard Bố cục lưới độc đáo
.dashboard-grid {
  display: grid;
  padding: var(--page-padding);
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: auto auto;
  gap: 16px;
  margin-bottom: 24px;
  min-height: 600px;

  .grid-item {
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    min-height: 300px;
    background-color: transparent;
    border: none;
    transition: all 0.2s ease;

    &:hover {
      .conversations-section,
      .call-stats-section {
        border-color: var(--gray-200);
        box-shadow: 0 1px 3px 0 var(--shadow-100);
      }
    }

    // Bố cục trang lớn：dòng đầu tiên 2x1 + 1x1，dòng thứ hai 3x1x1
    &.call-stats {
      grid-column: 1 / 3;
      grid-row: 1 / 2;
      min-height: 400px;
    }

    &.user-stats {
      grid-column: 3 / 4;
      grid-row: 1 / 2;
      min-height: 400px;
    }

    &.agent-stats {
      grid-column: 1 / 2;
      grid-row: 2 / 3;
      min-height: 350px;
    }

    &.tool-stats {
      grid-column: 2 / 3;
      grid-row: 2 / 3;
      min-height: 350px;
    }

    &.knowledge-stats {
      grid-column: 3 / 4;
      grid-row: 2 / 3;
      min-height: 350px;
    }
  }
}

// Dashboard Những kiểu thiệp độc đáo
.call-stats-section {
  background-color: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  transition: all 0.2s ease;
  box-shadow: none;

  &:hover {
    background-color: var(--gray-25);
    border-color: var(--gray-200);
    box-shadow: 0 1px 3px 0 var(--shadow-100);
  }

  :deep(.ant-card-head) {
    border-bottom: 1px solid var(--gray-200);
    min-height: 56px;
    padding: 0 20px;
    background-color: var(--gray-0);

    .ant-card-head-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--gray-1000);
    }
  }

  :deep(.ant-card-body) {
    padding: 16px 20px;
    background-color: var(--gray-0);
  }

  :deep(.ant-card-extra) {
    .ant-space {
      gap: 8px;
    }
  }
}

// Dashboard Các kiểu giữ chỗ độc đáo
.placeholder-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--gray-600);

  .placeholder-icon {
    width: 64px;
    height: 64px;
    background-color: var(--gray-100);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 16px;

    .icon {
      width: 32px;
      height: 32px;
      color: var(--gray-500);
    }
  }

  .placeholder-text {
    font-size: 18px;
    font-weight: 600;
    color: var(--gray-800);
    margin-bottom: 8px;
  }

  .placeholder-subtitle {
    font-size: 14px;
    color: var(--gray-600);
  }
}

// Kiểu mô-đun thống kê cuộc gọi
.call-stats-section {
  .call-stats-container {
    .call-summary {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 24px;

      .summary-card {
        background: linear-gradient(135deg, var(--gray-50) 0%, var(--gray-100) 100%);
        border: 1px solid var(--gray-200);
        border-radius: 8px;
        padding: 12px;
        text-align: center;

        .summary-value {
          font-size: 16px;
          font-weight: 600;
          color: var(--gray-800);
          margin-bottom: 4px;
        }

        .summary-label {
          font-size: 11px;
          color: var(--gray-500);
          font-weight: 500;
        }
      }
    }

    .chart-container {
      .chart {
        width: 100%;
        height: 280px;
        border-radius: 8px;
        overflow: hidden;
      }
    }
  }

  :deep(.ant-card-extra) {
    .ant-space {
      gap: 8px;
    }
  }
}

// Dashboard Thiết kế đáp ứng độc đáo
@media (max-width: 1200px) {
  .dashboard-grid {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto auto;
    gap: 16px;

    .grid-item {
      // Bố cục trang nhỏ：dòng đầu tiên 2x1，Dòng thứ hai và thứ ba là mỗi dòng 2x1x1
      &.call-stats {
        grid-column: 1 / 3;
        grid-row: 1 / 2;
        min-height: 350px;
      }

      &.user-stats {
        grid-column: 1 / 2;
        grid-row: 2 / 3;
        min-height: 300px;
      }

      &.agent-stats {
        grid-column: 2 / 3;
        grid-row: 2 / 3;
        min-height: 300px;
      }

      &.tool-stats {
        grid-column: 1 / 2;
        grid-row: 3 / 4;
        min-height: 300px;
      }

      &.knowledge-stats {
        grid-column: 2 / 3;
        grid-row: 3 / 4;
        min-height: 300px;
      }
    }
  }
}

@media (max-width: 768px) {
  .dashboard-container {
    padding: 16px;
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
    gap: 12px;

    .grid-item {
      &.call-stats,
      &.agent-stats,
      &.user-stats,
      &.tool-stats,
      &.knowledge-stats {
        grid-column: 1 / 2;
        grid-row: auto;
        min-height: 300px;
      }
    }
  }

  .call-stats-section {
    .call-stats-container {
      .call-summary {
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;

        .summary-card {
          padding: 12px;

          .summary-value {
            font-size: 18px;
          }

          .summary-label {
            font-size: 11px;
          }
        }
      }

      .chart-container {
        .chart {
          height: 200px;
        }
      }
    }
  }

  .placeholder-content {
    height: 150px;

    .placeholder-icon {
      width: 48px;
      height: 48px;
      margin-bottom: 12px;

      .icon {
        width: 24px;
        height: 24px;
      }
    }

    .placeholder-text {
      font-size: 16px;
    }

    .placeholder-subtitle {
      font-size: 12px;
    }
  }
}
</style>
