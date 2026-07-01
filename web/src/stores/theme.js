import { ref } from 'vue'
import { defineStore } from 'pinia'
import { theme } from 'ant-design-vue'

export const useThemeStore = defineStore('theme', () => {
  // từ localStorage Đọc chủ đề đã lưu，Mặc định là nhẹ
  const isDark = ref(localStorage.getItem('theme') === 'dark')

  // Cấu hình chủ đề công khai
  const commonTheme = {
    token: {
      fontFamily:
        "'HarmonyOS Sans SC', Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;",
      colorPrimary: '#24839b',
      colorLink: 'var(--main-color)',
      colorLinkHover: 'var(--main-600)',
      colorLinkActive: 'var(--main-800)',
      borderRadius: 8,
      wireframe: false
    }
  }

  // Cấu hình chủ đề nhẹ
  const lightTheme = {
    ...commonTheme
  }

  // Cấu hình chủ đề tối
  const darkTheme = {
    ...commonTheme,
    algorithm: theme.darkAlgorithm
  }

  // Cấu hình chủ đề hiện tại
  const currentTheme = ref(isDark.value ? darkTheme : lightTheme)

  // chuyển đổi chủ đề
  function toggleTheme() {
    setTheme(!isDark.value)
  }

  // Đặt chủ đề
  function setTheme(dark) {
    isDark.value = dark
    currentTheme.value = dark ? darkTheme : lightTheme
    localStorage.setItem('theme', dark ? 'dark' : 'light')
    updateDocumentTheme()
  }

  // cập nhật document lớp chủ đề
  function updateDocumentTheme() {
    if (isDark.value) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  // Đặt chủ đề khi khởi tạo
  updateDocumentTheme()

  return {
    isDark,
    currentTheme,
    toggleTheme,
    setTheme
  }
})
