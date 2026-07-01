import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChatUIStore = defineStore(
  'chatUI',
  () => {
    // ==================== Giao diện trò chuyện UI Trạng thái ====================
    // Trạng thái tải
    const isLoadingMessages = ref(false)

    // Trạng thái thu gọn thanh bên của ứng dụng
    const sidebarCollapsed = ref(false)

    // Thực đơn khác
    const moreMenuOpen = ref(false)
    const moreMenuPosition = ref({ x: 0, y: 0 })

    // ==================== phương pháp ====================
    /**
     * Mở thêm menu
     * @param {number} x - X tọa độ
     * @param {number} y - Y tọa độ
     */
    function openMoreMenu(x, y) {
      moreMenuPosition.value = { x, y }
      moreMenuOpen.value = true
    }

    /**
     * Đóng nhiều menu hơn
     */
    function closeMoreMenu() {
      moreMenuOpen.value = false
    }

    /**
     * thiết lập lại tất cả UI Trạng thái（Không bao gồm trạng thái liên tục）
     */
    function reset() {
      isLoadingMessages.value = false
      moreMenuOpen.value = false
      moreMenuPosition.value = { x: 0, y: 0 }
    }

    return {
      // Trạng thái
      isLoadingMessages,
      sidebarCollapsed,
      moreMenuOpen,
      moreMenuPosition,

      // phương pháp
      openMoreMenu,
      closeMoreMenu,
      reset
    }
  },
  {
    persist: {
      key: 'chat-ui-store',
      storage: localStorage,
      pick: ['sidebarCollapsed']
    }
  }
)
