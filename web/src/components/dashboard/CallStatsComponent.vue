<template>
  <div class="grid-item call-stats">
    <a-card class="dashboard-card call-stats-section" title="Thống kê cuộc gọi" :loading="loading">
      <template #extra>
        <div class="simple-controls">
          <div class="simple-toggle-group">
            <!-- <span class="simple-toggle-label">thời gian</span> -->
            <span
              v-for="opt in timeRangeOptions"
              :key="opt.value"
              class="simple-toggle"
              :class="{ active: callTimeRange === opt.value }"
              @click="switchTimeRange(opt.value)"
              >{{ opt.label }}
            </span>
          </div>
          <div class="divider"></div>
          <div class="simple-toggle-group">
            <!-- <span class="simple-toggle-label">Loại</span> -->
            <span
              v-for="opt in dataTypeOptions"
              :key="opt.value"
              class="simple-toggle"
              :class="{ active: callDataType === opt.value }"
              @click="switchDataType(opt.value)"
              >{{ opt.label }}
            </span>
          </div>
          <!-- <div class="subtitle">tổng cộng：{{ callStatsData?.total_count || 0 }}</div> -->
        </div>
      </template>

      <div class="call-stats-container">
        <div class="chart-container">
          <div ref="callStatsChartRef" class="chart"></div>
        </div>
      </div>
    </a-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, defineExpose, watch } from 'vue'
import * as echarts from 'echarts'
import { dashboardApi } from '@/apis/dashboard_api'
import { getColorByIndex, truncateLegend } from '@/utils/chartColors'
import { useThemeStore } from '@/stores/theme'

// CSS Chức năng công cụ phân tích cú pháp biến
function getCSSVariable(variableName, element = document.documentElement) {
  return getComputedStyle(element).getPropertyValue(variableName).trim()
}

const props = defineProps({
  loading: { type: Boolean, default: false }
})

// theme store
const themeStore = useThemeStore()

// state
const callStatsData = ref(null)
const callStatsLoading = ref(false)
const callTimeRange = ref('14days')
const callDataType = ref('agents')
const timeRangeOptions = [
  { value: '14hours', label: 'gần14giờ' },
  { value: '14days', label: 'gần14ngày' },
  { value: '14weeks', label: 'gần14tuần' }
]
const dataTypeOptions = [
  { value: 'models', label: 'Cuộc gọi mẫu' },
  { value: 'agents', label: 'Cuộc gọi đại lý' },
  { value: 'tokens', label: 'Tokentiêu thụ' },
  { value: 'tools', label: 'Cuộc gọi công cụ' }
]
const isTokenView = computed(() => callDataType.value === 'tokens')

const formatTokenValue = (value) => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '0M'
  }
  const millionValue = value / 1_000_000
  const absMillion = Math.abs(millionValue)
  const decimalPlaces = absMillion >= 100 ? 0 : absMillion >= 10 ? 1 : 2
  return `${millionValue.toFixed(decimalPlaces)}M`
}

const formatValueForDisplay = (value) => {
  if (isTokenView.value) {
    return formatTokenValue(value)
  }
  if (typeof value === 'number') {
    return value.toLocaleString()
  }
  return (value ?? 0).toString()
}

const switchTimeRange = (val) => {
  if (callTimeRange.value === val) return
  callTimeRange.value = val
  loadCallStats()
}

const switchDataType = (val) => {
  if (callDataType.value === val) return
  callDataType.value = val
  loadCallStats()
}
const callStatsChartRef = ref(null)
let callStatsChart = null
let retryTimer = null
let hoveredSeriesName = null
const retryCount = ref(0)
const maxRetry = 20

const loadCallStats = async () => {
  callStatsLoading.value = true
  try {
    const response = await dashboardApi.getCallTimeseries(callDataType.value, callTimeRange.value)
    callStatsData.value = response
    await nextTick()
    renderCallStatsChart()
  } catch (error) {
    console.error('Không tải được số liệu thống kê cuộc gọi:', error)
  } finally {
    callStatsLoading.value = false
  }
}

const renderCallStatsChart = () => {
  const container = callStatsChartRef.value
  if (!container || !callStatsData.value) return

  // Nếu thẻ gốc vẫn còn đó loading，chờ đã loading kết thúc
  if (props.loading) {
    scheduleRetry()
    return
  }

  const { clientWidth, clientHeight } = container
  if (!clientWidth || !clientHeight) {
    scheduleRetry()
    return
  }

  if (retryTimer) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
  retryCount.value = 0

  if (callStatsChart) {
    callStatsChart.dispose()
  }
  hoveredSeriesName = null

  callStatsChart = echarts.init(container)

  const data = callStatsData.value.data || []
  const categories = callStatsData.value.categories || []

  const xAxisData = data.map((item) => {
    const date = item.date
    if (callTimeRange.value === '14hours') {
      return date.split(' ')[1]
    } else if (callTimeRange.value === '14weeks') {
      return `Không.${date.split('-')[1]}tuần`
    } else {
      return date.split('-').slice(1).join('-')
    }
  })

  const agentNames = callStatsData.value.agent_names || {}

  const resolveCategoryLabel = (cat) => {
    if (cat === 'None') return 'mô hình không xác định'
    return agentNames[cat] || cat
  }

  const series = categories.map((category, index) => ({
    name: resolveCategoryLabel(category),
    type: 'bar',
    stack: 'total',
    emphasis: { focus: 'series' },
    data: data.map((item) => item.data[category] || 0),
    itemStyle: {
      color: getColorByIndex(index),
      borderRadius: 0
    }
  }))

  const option = {
    grid: {
      left: '3%',
      right: '4%',
      top: '5%' /* Giảm khoảng trắng ở trên cùng */,
      bottom: 50 /* Giảm khoảng trắng ở phía dưới，từ60giảm xuống50 */,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      axisLine: { lineStyle: { color: getCSSVariable('--gray-200') } },
      axisTick: { show: false },
      axisLabel: { color: getCSSVariable('--gray-500'), fontSize: 12 }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: getCSSVariable('--gray-500'),
        fontSize: 12,
        formatter: (value) => (isTokenView.value ? formatTokenValue(value) : value)
      },
      splitLine: { lineStyle: { color: getCSSVariable('--gray-100') } }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: getCSSVariable('--gray-0'),
      borderColor: getCSSVariable('--gray-200'),
      borderWidth: 1,
      textStyle: { color: getCSSVariable('--gray-600'), fontSize: 12 },
      formatter: (params) => {
        if (!params?.length) return ''
        const visibleParams = params.filter((param) => Number(param.value) !== 0)
        if (!visibleParams.length) return ''
        let total = 0
        let result = `${visibleParams[0].name}<br/>`
        visibleParams.forEach((param) => {
          total += param.value
          const truncatedName = truncateLegend(param.seriesName)
          const isHovered = param.seriesName === hoveredSeriesName
          const itemStyle = isHovered ? 'font-weight:700;color:var(--gray-900)' : ''
          result += `<span style="display:inline-block;margin-right:5px;border-radius:10px;width:10px;height:10px;background-color:${param.color}"></span>`
          result += `<span style="${itemStyle}">${truncatedName}: ${formatValueForDisplay(param.value)}</span><br/>`
        })
        const labelMap = {
          models: 'Cuộc gọi mẫu',
          agents: 'Cuộc gọi đại lý',
          tokens: 'Tokentiêu thụ',
          tools: 'Cuộc gọi công cụ'
        }
        const formattedTotal = formatValueForDisplay(total)
        return `<div style="font-weight:bold;margin-bottom:5px">${labelMap[callDataType.value]}</div>${result}<strong>tổng cộng: ${formattedTotal}</strong>`
      }
    },
    legend: {
      type: 'scroll',
      data: categories.map(resolveCategoryLabel),
      bottom: 5 /* Điều chỉnh vị trí chú giải，từ0Thay đổi thành5 */,
      textStyle: { color: getCSSVariable('--gray-500'), fontSize: 12 },
      itemWidth: 14,
      itemHeight: 14,
      formatter: (name) => truncateLegend(name),
      pageIconSize: 12,
      pageIconColor: getCSSVariable('--gray-500'),
      pageIconInactiveColor: getCSSVariable('--gray-300'),
      pageTextStyle: { color: getCSSVariable('--gray-500') }
    },
    series
  }

  callStatsChart.setOption(option)
  callStatsChart.on('mouseover', (event) => {
    hoveredSeriesName = event?.seriesName || null
  })
  callStatsChart.on('mouseout', () => {
    hoveredSeriesName = null
  })

  window.addEventListener('resize', handleResize, resizeListenerOptions)
}

const scheduleRetry = () => {
  if (retryCount.value >= maxRetry) return
  if (retryTimer) clearTimeout(retryTimer)
  retryTimer = setTimeout(() => {
    retryCount.value += 1
    renderCallStatsChart()
  }, 100)
}

const handleResize = () => {
  if (callStatsChart) callStatsChart.resize()
}

const resizeListenerOptions = { passive: true }

const cleanup = () => {
  window.removeEventListener('resize', handleResize, resizeListenerOptions)
  if (retryTimer) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
  retryCount.value = 0
  if (callStatsChart) {
    callStatsChart.dispose()
    callStatsChart = null
  }
}

defineExpose({ cleanup })

onMounted(() => {
  loadCallStats()
})

watch(
  () => props.loading,
  (now) => {
    if (!now) {
      if (callStatsData.value) {
        nextTick().then(() => renderCallStatsChart())
      }
    }
  }
)

// Theo dõi thay đổi chủ đề，Hiển thị lại biểu đồ
watch(
  () => themeStore.isDark,
  () => {
    if (callStatsData.value && callStatsChart) {
      nextTick(() => {
        renderCallStatsChart()
      })
    }
  }
)

onUnmounted(() => {
  cleanup()
})
</script>

<style scoped lang="less">
/* Tái sử dụng dashboard.css phong cách：Chỉ có phạm vi bảo hiểm tối thiểu được thực hiện ở đây để tránh trùng lặp */
.call-stats-section {
  background-color: var(--gray-0);
  height: 100%;
  display: flex;
  flex-direction: column;
}

:deep(.ant-card-body) {
  flex: 1;
  display: flex;
  padding: 16px; /* giảm bớtpaddingtừ20pxĐến16px */
  overflow-x: hidden; /* Ngăn chặn thanh cuộn ngang */
}

.call-stats-container {
  height: 100%;
  display: flex;
  flex: 1;
}

.call-stats .chart-container {
  height: 100%;
  flex: 1;
  padding: 0; /* Xóa mặc địnhpadding */
}

.call-stats .chart {
  height: 100% !important;
  width: 100%;
  padding: 0; /* Xóachartcủapadding */
  border: none; /* Xóachartcủaborder */
  background-color: transparent; /* Xóa màu nền */
}

.simple-controls {
  display: flex;
  align-items: center;
  gap: 16px;
}

.simple-toggle-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.simple-toggle-label {
  font-size: 12px;
  color: var(--gray-500);
  margin-right: 4px;
}

.simple-toggle {
  padding: 4px 8px;
  font-size: 12px;
  color: var(--gray-500);
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
  user-select: none;
}

.simple-toggle:hover {
  background-color: var(--gray-100);
  color: var(--gray-700);
}

.simple-toggle.active {
  background-color: var(--main-600);
  color: var(--gray-0);
}

.divider {
  width: 1px;
  height: 16px;
  background-color: var(--gray-200);
}
</style>
