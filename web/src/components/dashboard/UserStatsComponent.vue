<template>
  <a-card title="Phân tích hoạt động của người dùng" :loading="loading" class="dashboard-card">
    <!-- Tổng quan về thống kê người dùng nhỏ gọn -->
    <div class="compact-stats-grid">
      <div class="mini-stat-card">
        <div class="mini-stat-value">{{ userStats?.total_users || 0 }}</div>
        <div class="mini-stat-label">tổng số người dùng</div>
      </div>
      <div class="mini-stat-card">
        <div class="mini-stat-value">{{ userStats?.active_users_24h || 0 }}</div>
        <div class="mini-stat-label">24hhoạt động</div>
      </div>
      <div class="mini-stat-card">
        <div class="mini-stat-value">{{ userStats?.active_users_30d || 0 }}</div>
        <div class="mini-stat-label">30ngày năng động</div>
      </div>
    </div>

    <!-- khu vực biểu đồ - nhỏ gọn hơn -->
    <div class="compact-chart-container">
      <div class="chart-header">
        <span class="chart-title">xu hướng hoạt động</span>
        <span class="chart-subtitle">Gần đây7ngày</span>
      </div>
      <div ref="activityChartRef" class="compact-chart"></div>
    </div>
  </a-card>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useThemeStore } from '@/stores/theme'

// CSS Chức năng công cụ phân tích cú pháp biến
function getCSSVariable(variableName, element = document.documentElement) {
  return getComputedStyle(element).getPropertyValue(variableName).trim()
}

// theme store
const themeStore = useThemeStore()

// Props
const props = defineProps({
  userStats: {
    type: Object,
    default: () => ({})
  },
  loading: {
    type: Boolean,
    default: false
  }
})

// Chart refs
const activityChartRef = ref(null)
let activityChart = null

// Khởi tạo biểu đồ xu hướng hoạt động
const initActivityChart = () => {
  if (!activityChartRef.value || !props.userStats?.daily_active_users) return

  // Nếu một phiên bản biểu đồ đã tồn tại，Tiêu diệt đầu tiên
  if (activityChart) {
    activityChart.dispose()
    activityChart = null
  }

  activityChart = echarts.init(activityChartRef.value)

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
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: props.userStats.daily_active_users.map((item) => item.date),
      axisLine: {
        lineStyle: {
          color: getCSSVariable('--gray-200')
        }
      },
      axisLabel: {
        color: getCSSVariable('--gray-500')
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
          color: getCSSVariable('--gray-100')
        }
      }
    },
    series: [
      {
        name: 'Số lượng người dùng đang hoạt động',
        type: 'line',
        data: props.userStats.daily_active_users.map((item) => item.active_users),
        smooth: true,
        lineStyle: {
          color: getCSSVariable('--main-color'),
          width: 3
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              {
                offset: 0,
                color: getCSSVariable('--main-500')
              },
              {
                offset: 1,
                color: getCSSVariable('--main-0')
              }
            ]
          }
        },
        itemStyle: {
          color: getCSSVariable('--main-color'),
          borderWidth: 2,
          borderColor: getCSSVariable('--gray-0')
        },
        emphasis: {
          itemStyle: {
            color: getCSSVariable('--main-color'),
            borderWidth: 3,
            borderColor: getCSSVariable('--gray-0'),
            shadowBlur: 10,
            shadowColor: getCSSVariable('--shadow-1')
          }
        }
      }
    ]
  }

  activityChart.setOption(option)
}

// Cập nhật biểu đồ
const updateCharts = () => {
  nextTick(() => {
    initActivityChart()
  })
}

// Theo dõi sự thay đổi dữ liệu
watch(
  () => props.userStats,
  () => {
    updateCharts()
  },
  { deep: true }
)

// Thay đổi kích thước biểu đồ khi kích thước cửa sổ thay đổi
const handleResize = () => {
  if (activityChart) activityChart.resize()
}

onMounted(() => {
  updateCharts()
  window.addEventListener('resize', handleResize)
})

// Theo dõi thay đổi chủ đề，Hiển thị lại biểu đồ
watch(
  () => themeStore.isDark,
  () => {
    if (props.userStats?.daily_active_users && activityChart) {
      nextTick(() => {
        initActivityChart()
      })
    }
  }
)

// Dọn dẹp khi các thành phần được gỡ cài đặt
const cleanup = () => {
  window.removeEventListener('resize', handleResize)
  if (activityChart) {
    activityChart.dispose()
    activityChart = null
  }
}

// Xuất hàm dọn dẹp cho thành phần cha để gọi
defineExpose({
  cleanup
})
</script>

<style scoped lang="less">
/* lưới thống kê nhỏ gọn */
.compact-stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 16px;

  .mini-stat-card {
    background-color: var(--gray-0);
    border: 1px solid var(--gray-100);
    border-radius: 6px;
    padding: 16px;
    text-align: center;
    transition: all 0.2s ease;

    &:hover {
      border-color: var(--gray-200);
    }

    .mini-stat-value {
      font-size: 20px;
      font-weight: 600;
      color: var(--gray-1000);
      line-height: 1.2;
      margin-bottom: 4px;
    }

    .mini-stat-label {
      font-size: 12px;
      color: var(--gray-600);
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.025em;
    }
  }
}

/* Hộp đựng biểu đồ nhỏ gọn */
.compact-chart-container {
  background-color: var(--gray-0);
  border: 1px solid var(--gray-100);
  border-radius: 6px;
  padding: 16px;
  height: 240px;
  transition: all 0.2s ease;

  &:hover {
    border-color: var(--gray-200);
  }

  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .chart-title {
      font-size: 14px;
      font-weight: 600;
      color: var(--gray-1000);
    }

    .chart-subtitle {
      font-size: 11px;
      color: var(--gray-600);
      background-color: var(--gray-100);
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.025em;
    }
  }

  .compact-chart {
    height: 180px;
    width: 100%;
  }
}

/* Thiết kế đáp ứng */
@media (max-width: 1200px) {
  .compact-stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .compact-stats-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 6px;

    .mini-stat-card {
      padding: 8px;

      .mini-stat-value {
        font-size: 16px;
      }

      .mini-stat-label {
        font-size: 10px;
      }
    }
  }

  .compact-chart-container {
    height: 180px;
    padding: 8px;

    .compact-chart {
      height: 130px;
    }

    .chart-header {
      margin-bottom: 4px;

      .chart-title {
        font-size: 11px;
      }

      .chart-subtitle {
        font-size: 9px;
      }
    }
  }
}
</style>
