import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { brandApi } from '@/apis/system_api'

export const useInfoStore = defineStore('info', () => {
  // Trạng thái
  const infoConfig = ref({})
  const isLoading = ref(false)
  const isLoaded = ref(false)
  const debugMode = ref(false)

  // Thuộc tính tính toán - tổ chức thông tin
  const organization = computed(
    () =>
      infoConfig.value.organization || {
        name: '',
        logo: '',
        avatar: ''
      }
  )

  // Thuộc tính tính toán - Thông tin thương hiệu
  const branding = computed(
    () =>
      infoConfig.value.branding || {
        name: '',
        title: '',
        subtitle: '',
        subtitles: []
      }
  )

  // Thuộc tính tính toán - Thông tin chân trang
  const footer = computed(() => ({
    copyright: '',
    user_agreement_url: '',
    privacy_policy_url: '',
    ...(infoConfig.value.footer || {})
  }))

  // phương pháp hành động
  function setInfoConfig(newConfig) {
    infoConfig.value = newConfig
    isLoaded.value = true
  }

  function toggleDebugMode() {
    debugMode.value = !debugMode.value
  }

  async function loadInfoConfig(force = false) {
    // Nếu nó đã được tải và không buộc phải làm mới，sau đó không tải lại
    if (isLoaded.value && !force) {
      return infoConfig.value
    }

    try {
      isLoading.value = true
      const response = await brandApi.getInfoConfig()

      if (response.success && response.data) {
        setInfoConfig(response.data)
        console.debug('Cấu hình thông tin được tải thành công:', response.data)
        return response.data
      } else {
        console.warn('Tải cấu hình thông tin không thành công，Sử dụng cấu hình mặc định')
        return null
      }
    } catch (error) {
      console.error('Đã xảy ra lỗi khi tải cấu hình thông tin:', error)
      return null
    } finally {
      isLoading.value = false
    }
  }

  return {
    // Trạng thái
    infoConfig,
    isLoading,
    isLoaded,
    debugMode,

    // Thuộc tính tính toán
    organization,
    branding,
    footer,

    // phương pháp
    toggleDebugMode,
    loadInfoConfig
  }
})
