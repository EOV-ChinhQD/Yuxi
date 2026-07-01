<template>
  <a-card title="Cách sử dụng cơ sở kiến thức" :loading="loading" class="dashboard-card">
    <!-- Tổng quan về cơ sở kiến thức -->
    <div class="stats-overview">
      <a-row :gutter="16">
        <a-col :span="8">
          <a-statistic
            title="Tổng số cơ sở kiến thức"
            :value="knowledgeStats?.total_databases || 0"
            :value-style="{ color: 'var(--color-info-500)' }"
            suffix="một"
          />
        </a-col>
        <a-col :span="8">
          <a-statistic
            title="tổng số tập tin"
            :value="knowledgeStats?.total_files || 0"
            :value-style="{ color: 'var(--color-success-500)' }"
            suffix="một"
          />
        </a-col>
        <a-col :span="8">
          <a-statistic
            title="dung lượng lưu trữ"
            :value="formattedStorageSize"
            :value-style="{ color: 'var(--color-warning-500)' }"
          />
        </a-col>
      </a-row>
    </div>

    <a-divider />

    <!-- khu vực biểu đồ -->
    <a-row :gutter="24">
      <!-- Phân phối loại tệp -->
      <a-col :span="24">
        <div class="chart-container">
          <h4>Phân phối loại tệp</h4>
          <div ref="fileTypeChartRef" class="chart donut-chart-container">
            <div class="carousel-info" v-if="fileTypeData.length > 0">
              <div
                class="carousel-item"
                :class="{ active: currentCarouselIndex === index }"
                v-for="(item, index) in fileTypeData"
                :key="item.name"
              >
                <div class="carousel-label">{{ item.name }}</div>
                <div class="carousel-value">{{ item.value }}</div>
                <div class="carousel-percent">
                  {{ ((item.value / totalFiles) * 100).toFixed(1) }}%
                </div>
              </div>
            </div>
          </div>
        </div>
      </a-col>
    </a-row>

    <!-- Thống kê chi tiết -->
    <!-- <a-divider />
    <a-row :gutter="16">
      <a-col :span="8">
        <a-statistic
          title="Số lượng tệp trung bình trên mỗi thư viện"
          :value="averageFilesPerDatabase"
          suffix="một"
          :precision="1"
        />
      </a-col>
      <a-col :span="8">
        <a-statistic
          title="Số nút trung bình trên mỗi tệp"
          :value="averageNodesPerFile"
          suffix="một"
          :precision="1"
        />
      </a-col>
      <a-col :span="8">
        <a-statistic
          title="kích thước nút trung bình"
          :value="averageNodeSize"
          suffix="KB"
          :precision="2"
        />
      </a-col>
    </a-row> -->
  </a-card>
</template>

<script setup>
import { ref, onMounted, watch, nextTick, computed } from 'vue'
import * as echarts from 'echarts'
import { getColorPalette } from '@/utils/chartColors'
import { useThemeStore } from '@/stores/theme'

// CSS Chức năng công cụ phân tích cú pháp biến
function getCSSVariable(variableName, element = document.documentElement) {
  return getComputedStyle(element).getPropertyValue(variableName).trim()
}

// theme store
const themeStore = useThemeStore()

// Props
const props = defineProps({
  knowledgeStats: {
    type: Object,
    default: () => ({})
  },
  loading: {
    type: Boolean,
    default: false
  }
})

// Chart refs
const fileTypeChartRef = ref(null)
let fileTypeChart = null

// File type chart data for carousel
const fileTypeData = ref([])
const totalFiles = ref(0)
const currentCarouselIndex = ref(0)
let carouselTimer = null

// Thuộc tính tính toán
const formattedStorageSize = computed(() => {
  const size = props.knowledgeStats?.total_storage_size || 0
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(2)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`
})

// const averageFilesPerDatabase = computed(() => {
//   const databases = props.knowledgeStats?.total_databases || 0
//   const files = props.knowledgeStats?.total_files || 0
//   return databases > 0 ? files / databases : 0
// })

// const averageNodeSize = computed(() => {
//   const nodes = props.knowledgeStats?.total_nodes || 0
//   const size = props.knowledgeStats?.total_storage_size || 0
//   return nodes > 0 ? size / (nodes * 1024) : 0 // Chuyển đổi thànhKB
// })

// Bản đồ phân phối loại tệp khởi tạo
const initFileTypeChart = () => {
  if (!fileTypeChartRef.value) return

  // Nếu một phiên bản biểu đồ đã tồn tại，Tiêu diệt đầu tiên
  if (fileTypeChart) {
    fileTypeChart.dispose()
    fileTypeChart = null
  }

  fileTypeChart = echarts.init(fileTypeChartRef.value)

  const fileTypesData = props.knowledgeStats?.file_type_distribution || {}
  if (Object.keys(fileTypesData).length > 0) {
    const data = Object.entries(fileTypesData)
      .map(([type, count]) => ({
        name: type || 'không rõ',
        value: count
      }))
      .sort((a, b) => b.value - a.value) // Sắp xếp theo số lượng

    // Đặt dữ liệu băng chuyền
    fileTypeData.value = data
    totalFiles.value = data.reduce((sum, item) => sum + item.value, 0)

    // Bắt đầu băng chuyền
    startCarousel()

    const option = {
      tooltip: {
        trigger: 'item',
        backgroundColor: getCSSVariable('--gray-0'),
        borderColor: getCSSVariable('--gray-200'),
        borderWidth: 1,
        textStyle: {
          color: getCSSVariable('--gray-600')
        },
        formatter: '{a} <br/>{b}: {c} ({d}%)'
      },
      legend: {
        orient: 'horizontal',
        bottom: '5%',
        left: 'center',
        itemGap: 16,
        itemWidth: 10,
        itemHeight: 10,
        textStyle: {
          fontSize: 11,
          color: getCSSVariable('--gray-600')
        }
      },
      series: [
        {
          name: 'Loại tệp',
          type: 'pie',
          radius: ['45%', '75%'], // Điều chỉnh các vòng lớn hơn，Tạo thêm không gian cho thông tin trung tâm
          center: ['50%', '45%'], // di chuyển lên，Để lại khoảng trống cho các chú giải ở giữa và dưới cùng
          avoidLabelOverlap: true, // Tránh dán nhãn chồng chéo
          itemStyle: {
            borderRadius: 8,
            borderColor: getCSSVariable('--gray-0'),
            borderWidth: 2
          },
          label: {
            show: false // Ẩn nhãn trên biểu đồ hình tròn，Thay vào đó hãy sử dụng chú giải
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: getCSSVariable('--shadow-3')
            }
          },
          labelLine: {
            show: false // Ẩn dòng nhãn
          },
          data: data,
          color: getColorPalette()
        }
      ]
    }

    fileTypeChart.setOption(option)
  } else {
    // Xóa dữ liệu băng chuyền
    fileTypeData.value = []
    totalFiles.value = 0
    stopCarousel()

    // Nếu không có dữ liệu loại tệp，Hiển thị biểu đồ giữ chỗ
    const option = {
      tooltip: {
        trigger: 'item',
        backgroundColor: getCSSVariable('--gray-0'),
        borderColor: getCSSVariable('--gray-200'),
        borderWidth: 1,
        textStyle: {
          color: getCSSVariable('--gray-600')
        },
        formatter: '{a} <br/>{b}: {c} ({d}%)'
      },
      series: [
        {
          name: 'Loại tệp',
          type: 'pie',
          radius: ['45%', '75%'],
          center: ['50%', '45%'],
          avoidLabelOverlap: true,
          itemStyle: {
            borderRadius: 8,
            borderColor: getCSSVariable('--gray-0'),
            borderWidth: 2
          },
          label: {
            show: false
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: getCSSVariable('--shadow-3')
            }
          },
          labelLine: {
            show: false
          },
          data: [{ name: 'Chưa có dữ liệu', value: 1 }],
          color: [getCSSVariable('--color-info-500')]
        }
      ]
    }

    fileTypeChart.setOption(option)
  }
}

// Chức năng băng chuyền
const startCarousel = () => {
  stopCarousel() // Dừng băng chuyền trước đó trước
  if (fileTypeData.value.length <= 1) return

  // Đặt lại chỉ mục
  currentCarouselIndex.value = 0

  // Bắt đầu một băng chuyền mới，mỗi3Chuyển đổi một lần mỗi giây
  carouselTimer = setInterval(() => {
    currentCarouselIndex.value = (currentCarouselIndex.value + 1) % fileTypeData.value.length
  }, 3000)
}

const stopCarousel = () => {
  if (carouselTimer) {
    clearInterval(carouselTimer)
    carouselTimer = null
  }
}

// Cập nhật biểu đồ
const updateCharts = () => {
  nextTick(() => {
    initFileTypeChart()
  })
}

// Theo dõi sự thay đổi dữ liệu
watch(
  () => props.knowledgeStats,
  () => {
    updateCharts()
  },
  { deep: true }
)

// Thay đổi kích thước biểu đồ khi kích thước cửa sổ thay đổi
const handleResize = () => {
  if (fileTypeChart) fileTypeChart.resize()
}

onMounted(() => {
  updateCharts()
  window.addEventListener('resize', handleResize)
})

// Theo dõi thay đổi chủ đề，Hiển thị lại biểu đồ
watch(
  () => themeStore.isDark,
  () => {
    if (props.knowledgeStats && fileTypeChart) {
      nextTick(() => {
        updateCharts()
      })
    }
  }
)

// Dọn dẹp khi các thành phần được gỡ cài đặt
const cleanup = () => {
  window.removeEventListener('resize', handleResize)
  stopCarousel() // Dừng băng chuyền
  if (fileTypeChart) {
    fileTypeChart.dispose()
    fileTypeChart = null
  }
}

// Xuất hàm dọn dẹp cho thành phần cha để gọi
defineExpose({
  cleanup
})
</script>

<style scoped lang="less">
// KnowledgeStatsComponent phong cách độc đáo
.chart-container {
  .chart {
    height: 300px;
    width: 100%;
  }

  // Kiểu hộp đựng biểu đồ bánh rán
  .donut-chart-container {
    position: relative;

    .carousel-info {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      text-align: center;
      pointer-events: none;
      z-index: 10;

      .carousel-item {
        opacity: 0;
        transition: opacity 0.5s ease-in-out;
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        white-space: nowrap;

        &.active {
          opacity: 1;
        }

        .carousel-label {
          font-size: 14px;
          font-weight: 600;
          color: var(--gray-500);
          margin-bottom: 4px;
        }

        .carousel-value {
          font-size: 24px;
          font-weight: 700;
          color: var(--gray-800);
          margin-bottom: 2px;
          line-height: 1;
        }

        .carousel-percent {
          font-size: 12px;
          color: var(--gray-400);
          font-weight: 500;
        }
      }
    }
  }
}
</style>
