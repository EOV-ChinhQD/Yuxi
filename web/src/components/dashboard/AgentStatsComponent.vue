<template>
  <a-card title="AIphân tích tác nhân" :loading="loading" class="dashboard-card">
    <!-- Tổng quan về đại lý -->
    <div class="stats-overview">
      <a-row :gutter="16">
        <a-col :span="8">
          <a-statistic
            title="Tổng số đại lý"
            :value="agentStats?.total_agents || 0"
            :value-style="{ color: 'var(--color-info-500)' }"
            suffix="một"
          />
        </a-col>
        <a-col :span="8">
          <a-statistic
            title="Tổng số cuộc trò chuyện"
            :value="totalConversations"
            :value-style="{ color: 'var(--color-accent-500)' }"
            suffix="lần"
          />
        </a-col>
        <a-col :span="8">
          <a-statistic
            title="Tổng số cuộc gọi công cụ"
            :value="totalToolUsage"
            :value-style="{ color: 'var(--color-warning-500)' }"
            suffix="lần"
          />
        </a-col>
      </a-row>
    </div>

    <a-divider />

    <!-- khu vực biểu đồ -->
    <a-row :gutter="24">
      <!-- Phân phối số lượng cuộc hội thoại và số lượng cuộc gọi công cụ -->
      <a-col :span="24">
        <div class="chart-container">
          <h4>đối thoại/Phân phối cuộc gọi công cụ (TOP 3)</h4>
          <div ref="conversationToolChartRef" class="chart"></div>
        </div>
      </a-col>
    </a-row>

    <!-- Xếp hạng hiệu suất -->
    <a-divider />
    <div class="top-performers">
      <h4>đại lý hoạt động tốt nhất TOP 5</h4>
      <a-table
        :columns="performerColumns"
        :data-source="topPerformers"
        size="small"
        :pagination="false"
      >
        <template #bodyCell="{ column, record, index }">
          <template v-if="column.key === 'rank'">
            <div class="rank-display">
              <span class="rank-number" :class="{ featured: index < 3 }">{{ index + 1 }}</span>
            </div>
          </template>
          <template v-if="column.key === 'agent_id'">
            <span class="agent-name" :title="resolveAgentName(record.agent_id)">
              {{ resolveAgentName(record.agent_id) }}
            </span>
          </template>
          <template v-if="column.key === 'satisfaction_rate'">
            <a-statistic
              :value="record.satisfaction_rate"
              suffix="%"
              :value-style="{
                color:
                  record.satisfaction_rate >= 80
                    ? 'var(--color-success-500)'
                    : record.satisfaction_rate >= 60
                      ? 'var(--color-warning-500)'
                      : 'var(--color-error-500)',
                fontSize: '14px'
              }"
            />
          </template>
          <template v-if="column.key === 'conversation_count'">
            <span class="metric-value">{{ record.conversation_count }}</span>
          </template>
        </template>
      </a-table>
    </div>
  </a-card>
</template>

<script setup>
import { ref, onMounted, watch, nextTick, computed } from 'vue'
import * as echarts from 'echarts'
import { getColorByIndex } from '@/utils/chartColors'
import { useThemeStore } from '@/stores/theme'

// CSS Chức năng công cụ phân tích cú pháp biến
function getCSSVariable(variableName, element = document.documentElement) {
  return getComputedStyle(element).getPropertyValue(variableName).trim()
}

// theme store
const themeStore = useThemeStore()

// Props
const props = defineProps({
  agentStats: {
    type: Object,
    default: () => ({})
  },
  loading: {
    type: Boolean,
    default: false
  }
})

// Chart refs
const conversationToolChartRef = ref(null)
let conversationToolChart = null

// định nghĩa cột trong bảng
const performerColumns = [
  {
    title: 'Xếp hạng',
    key: 'rank',
    width: '80px',
    align: 'center'
  },
  {
    title: 'đại lý',
    key: 'agent_id',
    width: '30%'
  },
  {
    title: 'Sự hài lòng',
    key: 'satisfaction_rate',
    width: '25%',
    align: 'center'
  },
  {
    title: 'Số lượng cuộc trò chuyện',
    key: 'conversation_count',
    width: '20%',
    align: 'center'
  }
]

// Thuộc tính tính toán
const totalConversations = computed(() => {
  const conversationCounts = props.agentStats?.agent_conversation_counts || []
  return conversationCounts.reduce((sum, item) => sum + item.conversation_count, 0)
})

const totalToolUsage = computed(() => {
  const toolUsage = props.agentStats?.agent_tool_usage || []
  return toolUsage.reduce((sum, item) => sum + item.tool_usage_count, 0)
})

const topPerformers = computed(() => {
  return props.agentStats?.top_performing_agents || []
})

const agentNames = computed(() => props.agentStats?.agent_names || {})

const resolveAgentName = (agentId) => agentNames.value[agentId] || agentId

// Biểu đồ đã hợp nhất về số lượng cuộc trò chuyện khởi tạo và số lượng cuộc gọi công cụ
const initConversationToolChart = () => {
  if (
    !conversationToolChartRef.value ||
    (!props.agentStats?.agent_conversation_counts?.length &&
      !props.agentStats?.agent_tool_usage?.length)
  )
    return

  // Nếu một phiên bản biểu đồ đã tồn tại，Tiêu diệt đầu tiên
  if (conversationToolChart) {
    conversationToolChart.dispose()
    conversationToolChart = null
  }

  conversationToolChart = echarts.init(conversationToolChartRef.value)

  const conversationData = props.agentStats.agent_conversation_counts || []
  const toolData = props.agentStats.agent_tool_usage || []

  // Nhận tất cả các đại lýIDvà theo số lượng cuộc trò chuyện+Sắp xếp số lượng cuộc gọi công cụ，Trước khi nhặt3một
  const allAgentStats = {}

  // Đếm tổng lượng dữ liệu cho mỗi tác nhân（Số lượng cuộc trò chuyện + Số lần gọi công cụ）
  conversationData.forEach((item) => {
    if (!allAgentStats[item.agent_id]) {
      allAgentStats[item.agent_id] = { conversation: 0, tool: 0, total: 0 }
    }
    allAgentStats[item.agent_id].conversation = item.conversation_count
    allAgentStats[item.agent_id].total += item.conversation_count
  })

  toolData.forEach((item) => {
    if (!allAgentStats[item.agent_id]) {
      allAgentStats[item.agent_id] = { conversation: 0, tool: 0, total: 0 }
    }
    allAgentStats[item.agent_id].tool = item.tool_usage_count
    allAgentStats[item.agent_id].total += item.tool_usage_count
  })

  // Sắp xếp theo tổng khối lượng dữ liệu theo thứ tự giảm dần，Trước khi nhặt3một
  const topAgentIds = Object.entries(allAgentStats)
    .sort(([, a], [, b]) => b.total - a.total)
    .slice(0, 3)
    .map(([agentId]) => agentId)

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: getCSSVariable('--gray-0'),
      borderColor: getCSSVariable('--gray-200'),
      borderWidth: 1,
      textStyle: {
        color: getCSSVariable('--gray-600')
      }
    },
    legend: {
      data: ['Số lượng cuộc trò chuyện', 'Số lần gọi công cụ'],
      right: '0%',
      top: '0%',
      orient: 'horizontal',
      textStyle: {
        color: getCSSVariable('--gray-500')
      }
    },
    grid: {
      left: '3%',
      right: '15%',
      bottom: '3%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: topAgentIds.map(resolveAgentName),
      axisLine: {
        lineStyle: {
          color: getCSSVariable('--gray-200')
        }
      },
      axisLabel: {
        color: getCSSVariable('--gray-500'),
        interval: 0
        // rotate: 45
      }
    },
    yAxis: {
      type: 'value',
      axisLine: {
        lineStyle: {
          color: getCSSVariable('--gray-200')
        }
      },
      axisLabel: {
        color: getCSSVariable('--gray-500')
      },
      splitLine: {
        lineStyle: {
          color: getCSSVariable('--gray-150')
        }
      }
    },
    series: [
      {
        name: 'Số lượng cuộc trò chuyện',
        type: 'bar',
        data: topAgentIds.map((agentId) => {
          const item = conversationData.find((d) => d.agent_id === agentId)
          return item ? item.conversation_count : 0
        }),
        itemStyle: {
          color: getColorByIndex(0),
          borderRadius: [4, 4, 0, 0]
        },
        emphasis: {
          itemStyle: {
            color: getColorByIndex(0),
            shadowBlur: 10,
            shadowColor: getCSSVariable('--color-info-50')
          }
        }
      },
      {
        name: 'Số lần gọi công cụ',
        type: 'bar',
        data: topAgentIds.map((agentId) => {
          const item = toolData.find((d) => d.agent_id === agentId)
          return item ? item.tool_usage_count : 0
        }),
        itemStyle: {
          color: getColorByIndex(1),
          borderRadius: [4, 4, 0, 0]
        },
        emphasis: {
          itemStyle: {
            color: getColorByIndex(1),
            shadowBlur: 10,
            shadowColor: getCSSVariable('--color-info-50')
          }
        }
      }
    ]
  }

  conversationToolChart.setOption(option)
}

// Cập nhật biểu đồ
const updateCharts = () => {
  nextTick(() => {
    initConversationToolChart()
  })
}

// Theo dõi sự thay đổi dữ liệu
watch(
  () => props.agentStats,
  () => {
    updateCharts()
  },
  { deep: true }
)

// Thay đổi kích thước biểu đồ khi kích thước cửa sổ thay đổi
const handleResize = () => {
  if (conversationToolChart) conversationToolChart.resize()
}

onMounted(() => {
  updateCharts()
  window.addEventListener('resize', handleResize)
})

// Theo dõi thay đổi chủ đề，Hiển thị lại biểu đồ
watch(
  () => themeStore.isDark,
  () => {
    if (props.agentStats && conversationToolChart) {
      nextTick(() => {
        updateCharts()
      })
    }
  }
)

// Dọn dẹp khi các thành phần được gỡ cài đặt
const cleanup = () => {
  window.removeEventListener('resize', handleResize)
  if (conversationToolChart) {
    conversationToolChart.dispose()
    conversationToolChart = null
  }
}

// Xuất hàm dọn dẹp cho thành phần cha để gọi
defineExpose({
  cleanup
})
</script>

<style scoped lang="less">
/* Kiểu giá trị chỉ báo */
.metric-value {
  font-weight: 500;
  color: var(--gray-1000);
  font-size: 14px;
}

/* Phong cách hiển thị xếp hạng */
.rank-display {
  display: flex;
  align-items: center;
  justify-content: center;

  .rank-number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    background-color: var(--gray-50);
    border-radius: 50%;
    font-size: 12px;
    font-weight: 600;
    color: var(--gray-600);
    border: 1px solid var(--gray-150);
  }

  .rank-number.featured {
    background-color: var(--main-20);
    border-color: var(--main-100);
    color: var(--main-color);
  }
}

.agent-name {
  display: inline-block;
  max-width: 100%;
  color: var(--gray-900);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
  white-space: nowrap;
}

// AgentStatsComponent phong cách độc đáo
.top-performers,
.metrics-comparison {
  h4 {
    margin-bottom: 16px;
    font-weight: 600;
    color: var(--gray-1000);
    font-size: 16px;
  }

  h5 {
    margin-bottom: 12px;
    color: var(--gray-600);
    font-weight: 500;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
}

:deep(.ant-progress-bg) {
  transition: all 0.3s ease;
}

:deep(.ant-statistic-content-value) {
  font-weight: bold !important;
}
</style>
