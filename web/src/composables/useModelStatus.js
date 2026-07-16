import { reactive } from 'vue'
import { modelProviderApi } from '@/apis/system_api'

/**
 * Kiểm tra trạng thái mô hình composable，cung cấp Chat/Embedding/Rerank Bộ chọn mô hình chung。
 */
export function useModelStatus() {
  const statusMap = reactive({})

  const getStatusIcon = (key) => {
    const status = statusMap[key]
    if (!status) return '○'
    if (status.status === 'available') return '✓'
    if (status.status === 'unavailable') return '✗'
    if (status.status === 'error') return '⚠'
    return '○'
  }

  const getStatusClass = (key) => {
    return statusMap[key]?.status || ''
  }

  const getStatusTooltip = (key) => {
    const status = statusMap[key]
    if (!status) return 'Trạng thái không xác định'
    const text =
      { available: 'Có sẵn', unavailable: 'Không có sẵn', error: 'Lỗi' }[status.status] ||
      'không rõ'
    return `${text}: ${status.message || 'Không có chi tiết'}`
  }

  const checkV2Status = async (spec) => {
    try {
      const response = await modelProviderApi.getModelStatusBySpec(spec)
      if (response.data) {
        statusMap[spec] = response.data
      }
    } catch {
      statusMap[spec] = { spec, status: 'error', message: 'Kiểm tra không thành công' }
    }
  }

  const checkV2Statuses = async (models) => {
    for (const model of models || []) {
      await checkV2Status(model.spec)
    }
  }

  return {
    statusMap,
    getStatusIcon,
    getStatusClass,
    getStatusTooltip,
    checkV2Status,
    checkV2Statuses
  }
}
