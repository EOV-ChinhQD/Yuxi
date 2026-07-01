/**
 * Chart Color Palette Utility
 * Chức năng công cụ bảng biểu đồ thống nhất
 * từ CSS Tự động lấy màu từ biến，Đảm bảo phù hợp với chủ đề
 */

let colorPalette = []
let isInitialized = false

/**
 * Build color palette from CSS variables in base.css
 * từ base.css trong CSS Bảng màu xây dựng có thể thay đổi
 */
const buildColorPalette = () => {
  try {
    const root = document.documentElement
    const styles = getComputedStyle(root)

    const pick = (name, fallback) => {
      const v = styles.getPropertyValue(name)
      return v && v.trim() ? v.trim() : fallback
    }

    // Base chart colors - using new color system
    const baseVars = [
      ['--main-500', '#3996ae'],
      ['--color-success-500', '#52c41a'],
      ['--color-warning-500', '#faad14'],
      ['--color-error-500', '#ff4d4f'],
      ['--color-accent-500', '#13c2c2']
    ]

    // Extended palette colors
    const paletteVars = [
      ['--chart-palette-1', '#265C96'],
      ['--chart-palette-2', '#009485'],
      ['--chart-palette-3', '#E8A035'],
      ['--chart-palette-4', '#D64B55'],
      ['--chart-palette-5', '#7D54C4'],
      ['--chart-palette-6', '#2D9CDB'],
      ['--chart-palette-7', '#F28B30'],
      ['--chart-palette-8', '#65C466'],
      ['--chart-palette-9', '#C2589E'],
      ['--chart-palette-10', '#4F4F4F']
    ]

    const baseColors = baseVars.map(([n, f]) => pick(n, f))
    const paletteColors = paletteVars.map(([n, f]) => pick(n, f))

    // Priority: palette first, then base colors
    const merged = [...paletteColors, ...baseColors]
      .filter(Boolean)
      .filter((c, idx, arr) => arr.indexOf(c) === idx) // Remove duplicates

    colorPalette = merged
    isInitialized = true
  } catch (e) {
    console.warn('Failed to build color palette from CSS variables, using fallback:', e)
    // Fallback palette
    colorPalette = [
      '#3996ae',
      '#52c41a',
      '#faad14',
      '#ff4d4f',
      '#13c2c2',
      '#265C96',
      '#009485',
      '#E8A035',
      '#D64B55',
      '#7D54C4'
    ]
    isInitialized = true
  }
}

/**
 * Get color by index from the palette
 * Nhận màu từ bảng màu dựa trên chỉ mục
 * @param {number} index - Color index
 * @returns {string} Color value
 */
export const getColorByIndex = (index) => {
  if (!isInitialized || colorPalette.length === 0) {
    buildColorPalette()
  }
  return colorPalette[index % colorPalette.length]
}

/**
 * Get the entire color palette
 * Nhận bảng màu đầy đủ
 * @returns {Array<string>} Color palette array
 */
export const getColorPalette = () => {
  if (!isInitialized || colorPalette.length === 0) {
    buildColorPalette()
  }
  return [...colorPalette] // Return a copy
}

/**
 * Truncate legend text for better display
 * Cắt bớt văn bản chú thích để hiển thị tốt hơn
 * @param {string} name - Legend name
 * @param {number} maxLength - Maximum length (default: 20)
 * @returns {string} Truncated name
 */
export const truncateLegend = (name, maxLength = 20) => {
  if (!name) return ''
  return name.length > maxLength ? name.slice(0, maxLength) + '…' : name
}

/**
 * Initialize the color palette (call this when DOM is ready)
 * Khởi tạo bảng màu（trong DOM Được gọi khi sẵn sàng）
 */
export const initColorPalette = () => {
  buildColorPalette()
}

// Auto-initialize when module is loaded
if (typeof window !== 'undefined' && document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initColorPalette)
} else if (typeof window !== 'undefined') {
  initColorPalette()
}
