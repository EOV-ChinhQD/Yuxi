<template>
  <div class="mindmap-section">
    <div class="section-content">
      <!-- Trạng thái tải -->
      <div v-if="loading" class="loading-state">
        <a-spin size="small" />
        <span>Đang tải...</span>
      </div>

      <!-- Đang tạo trạng thái -->
      <div v-else-if="generating" class="generating-state">
        <a-spin size="small" />
        <span>AI Tạo bản đồ tư duy...</span>
      </div>

      <!-- Trạng thái trống -->
      <div v-else-if="!mindmapData" class="empty-state">
        <div class="empty-icon">
          <MapIcon :size="24" />
        </div>
        <p class="empty-title">Chưa có bản đồ tư duy</p>
        <p class="empty-description">Tạo bản đồ có cấu trúc từ nội dung cơ sở kiến thức hiện tại。</p>
        <button
          type="button"
          class="lucide-icon-btn mindmap-primary-action"
          @click="generateMindmap"
        >
          <Sparkles :size="14" />
          <span>Tạo bản đồ tư duy</span>
        </button>
      </div>

      <!-- hiển thị bản đồ tư duy -->
      <div v-else class="mindmap-container">
        <div class="mindmap-toolbar">
          <a-space :size="8">
            <button
              type="button"
              class="lucide-icon-btn mindmap-toolbar-btn"
              :disabled="generating"
              @click="refreshMindmap"
              title="tái sinh"
            >
              <RefreshCw :size="14" :class="{ spin: generating }" />
              <span class="toolbar-text">tái sinh</span>
            </button>
            <button
              v-if="isIncremental && mindmapData"
              type="button"
              class="lucide-icon-btn mindmap-toolbar-btn mindmap-toolbar-btn--accent"
              :disabled="generating"
              @click="incrementalUpdate"
              title="cập nhật gia tăng"
            >
              <Plus :size="14" />
              <span class="toolbar-text">cập nhật gia tăng</span>
              <span v-if="mindmapDiff?.added_files?.length" class="mindmap-badge">
                {{ mindmapDiff.added_files.length }}
              </span>
            </button>
            <button
              type="button"
              class="lucide-icon-btn mindmap-toolbar-btn"
              @click="fitView"
              title="Thích ứng với chế độ xem"
            >
              <Maximize2 :size="14" />
              <span class="toolbar-text">Thích ứng với chế độ xem</span>
            </button>
          </a-space>
        </div>
        <div class="mindmap-svg-container">
          <svg ref="mindmapSvg" class="mindmap-svg"></svg>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { RefreshCw, Map as MapIcon, Sparkles, Maximize2, Plus } from 'lucide-vue-next'
import { mindmapApi } from '@/apis/knowledge_api'
import { Markmap } from 'markmap-view'
import { Transformer } from 'markmap-lib'

const props = defineProps({
  kbId: {
    type: String,
    required: true
  }
})

// ============================================================================
// Quản lý trạng thái
// ============================================================================

const loading = ref(false)
const generating = ref(false)
const mindmapData = ref(null)
const mindmapSvg = ref(null)
const mindmapDiff = ref(null)
const isIncremental = ref(false)
let markmapInstance = null
let textMeasureContext = null

const SVG_NS = 'http://www.w3.org/2000/svg'
const MARKMAP_MAX_WIDTH = 200
const MARKMAP_PADDING_X = 8
const MARKMAP_LINE_HEIGHT = 20
const MARKMAP_TEXT_BASELINE = 16
const SAFARI_FALLBACK_FONT = '300 16px sans-serif'

const useSvgTextFallback = (() => {
  if (typeof navigator === 'undefined') return false

  const userAgent = navigator.userAgent || ''
  const vendor = navigator.vendor || ''
  const isAppleWebKit = userAgent.includes('AppleWebKit')
  const isDesktopChromium =
    /(Chrome|Chromium|Edg|OPR)\//.test(userAgent) && !/(CriOS|FxiOS|EdgiOS)\//.test(userAgent)
  const isAppleBrowser = vendor.includes('Apple') || /(Safari|iPhone|iPad|iPod)/.test(userAgent)

  return isAppleWebKit && isAppleBrowser && !isDesktopChromium
})()

// ============================================================================
// phương pháp
// ============================================================================

/**
 * Tải bản đồ tư duy
 */
const loadMindmap = async () => {
  if (!props.kbId) return

  try {
    loading.value = true
    const response = await mindmapApi.getByDatabase(props.kbId)

    const mindmap = response.mindmap || null
    mindmapData.value = mindmap

    if (markmapInstance) {
      markmapInstance.destroy()
      markmapInstance = null
    }

    if (mindmap) {
      await nextTick()

      // Hiển thị bị trì hoãn，đảm bảoDOMcập nhật đầy đủ
      setTimeout(() => {
        renderMindmap(mindmap)
      }, 100)
    }

    await checkMindmapDiff()
  } catch (error) {
    // nếu có404Lỗi，Mô tả chưa được tạo，Xử lý im lặng
    if (
      error?.message?.includes('404') ||
      error?.message?.includes('không tồn tại') ||
      error?.message?.includes('Chưa được tạo')
    ) {
      mindmapData.value = null
    } else {
      console.error('Không tải được bản đồ tư duy:', error)
      const errorMsg = error?.message || String(error)
      message.error('Không tải được bản đồ tư duy: ' + errorMsg)
    }
  } finally {
    loading.value = false
  }
}

/**
 * Tạo bản đồ tư duy
 */
const generateMindmap = async () => {
  if (!props.kbId) return

  try {
    generating.value = true

    const response = await mindmapApi.generateMindmap(
      props.kbId,
      [], // sử dụng tất cả các tập tin
      '' // Không có lời nhắc tùy chỉnh
    )

    mindmapData.value = response.mindmap

    // chờ đãDOMcập nhật
    await nextTick()

    // trì hoãn lâu hơn một chút，đảm bảoSVGPhần tử được hiển thị đầy đủ
    setTimeout(() => {
      renderMindmap(response.mindmap)
      message.success('Bản đồ tư duy được tạo thành công！')
    }, 100)

    await checkMindmapDiff()
  } catch (error) {
    console.error('Không tạo được bản đồ tư duy:', error)
    const errorMsg = error?.message || String(error)
    message.error('Xây dựng không thành công: ' + errorMsg)
  } finally {
    generating.value = false
  }
}

/**
 * Làm mới bản đồ tư duy
 */
const refreshMindmap = async () => {
  await generateMindmap()
}

/**
 * Phát hiện những thay đổi trong bản đồ tư duy
 */
const checkMindmapDiff = async () => {
  if (!props.kbId || !mindmapData.value) {
    isIncremental.value = false
    mindmapDiff.value = null
    return
  }
  try {
    const diff = await mindmapApi.getDiff(props.kbId)
    mindmapDiff.value = diff
    isIncremental.value = diff.needs_update
  } catch {
    isIncremental.value = false
    mindmapDiff.value = null
  }
}

/**
 * Cập nhật dần dần bản đồ tư duy
 */
const incrementalUpdate = async () => {
  if (!props.kbId) return

  try {
    generating.value = true

    const response = await mindmapApi.generateMindmap(props.kbId, [], '', true)

    mindmapData.value = response.mindmap

    await nextTick()

    setTimeout(() => {
      renderMindmap(response.mindmap)
      if (response.no_ai_needed) {
        message.success('Bản đồ tư duy đã được cập nhật（Tự động dọn dẹp các tập tin đã xóa）')
      } else {
        message.success('Đã hoàn tất cập nhật gia tăng！')
      }
    }, 100)

    await checkMindmapDiff()
  } catch (error) {
    console.error('Cập nhật gia tăng không thành công:', error)
    const errorMsg = error?.message || String(error)
    message.error('Cập nhật gia tăng không thành công: ' + errorMsg)
  } finally {
    generating.value = false
  }
}

/**
 * sẽJSONChuyển đổi thànhMarkdown
 */
const jsonToMarkdown = (node, level = 0) => {
  if (!node || !node.content) return ''

  const indent = '#'.repeat(level + 1)
  let markdown = `${indent} ${node.content}\n\n`

  if (node.children && node.children.length > 0) {
    for (const child of node.children) {
      markdown += jsonToMarkdown(child, level + 1)
    }
  }

  return markdown
}

const ensureSvgViewportSize = () => {
  const svg = mindmapSvg.value
  const container = svg?.parentElement
  if (!svg || !container) return false

  const { width, height } = container.getBoundingClientRect()
  if (width <= 0 || height <= 0) return false

  svg.setAttribute('width', `${Math.round(width)}`)
  svg.setAttribute('height', `${Math.round(height)}`)
  return true
}

const createSvgElement = (tagName) => document.createElementNS(SVG_NS, tagName)

const getNodeText = (html) => {
  const element = document.createElement('div')
  element.innerHTML = html || ''
  return (element.textContent || '').replace(/\s+/g, ' ').trim()
}

const getTextMeasureContext = () => {
  if (!textMeasureContext) {
    const canvas = document.createElement('canvas')
    textMeasureContext = canvas.getContext('2d')
  }

  if (textMeasureContext) {
    const font = mindmapSvg.value ? getComputedStyle(mindmapSvg.value).font : ''
    textMeasureContext.font = font || SAFARI_FALLBACK_FONT
  }

  return textMeasureContext
}

const splitTextTokens = (text) => text.match(/[A-Za-z0-9_.:/#-]+|\s+|./gu) || []

const wrapSvgText = (text, maxWidth) => {
  const context = getTextMeasureContext()
  const measure = (value) => (context ? context.measureText(value).width : value.length * 8)
  const lines = []
  let currentLine = ''

  for (const token of splitTextTokens(text)) {
    const normalizedToken = /^\s+$/.test(token) ? ' ' : token
    if (!currentLine && normalizedToken === ' ') continue

    const nextLine = `${currentLine}${normalizedToken}`
    if (!currentLine || measure(nextLine) <= maxWidth) {
      currentLine = nextLine
      continue
    }

    lines.push(currentLine.trimEnd())

    if (measure(normalizedToken) <= maxWidth) {
      currentLine = normalizedToken.trimStart()
      continue
    }

    currentLine = ''
    for (const char of [...normalizedToken]) {
      const nextCharLine = `${currentLine}${char}`
      if (!currentLine || measure(nextCharLine) <= maxWidth) {
        currentLine = nextCharLine
      } else {
        lines.push(currentLine)
        currentLine = char
      }
    }
  }

  if (currentLine) {
    lines.push(currentLine.trimEnd())
  }

  return lines.length ? lines : [text]
}

const collectVisibleNodes = (node, nodes = []) => {
  if (!node?.state?.rect) return nodes

  nodes.push(node)
  if (!node.payload?.fold) {
    for (const child of node.children || []) {
      collectVisibleNodes(child, nodes)
    }
  }

  return nodes
}

const hideOriginalMarkmapText = (contentGroup) => {
  contentGroup?.querySelectorAll('.markmap-foreign').forEach((element) => {
    element.setAttribute('visibility', 'hidden')
    element.style.setProperty('opacity', '0', 'important')
    element.style.setProperty('visibility', 'hidden', 'important')
    element.style.setProperty('pointer-events', 'none', 'important')
  })
}

const syncSafariTextFallback = () => {
  const svg = mindmapSvg.value
  const contentGroup = markmapInstance?.g?.node?.()
  const data = markmapInstance?.state?.data

  if (!useSvgTextFallback || !svg || !contentGroup || !data) {
    svg?.classList.remove('mindmap-safari-fallback')
    return
  }

  svg.classList.add('mindmap-safari-fallback')
  hideOriginalMarkmapText(contentGroup)
  contentGroup.querySelectorAll('.mindmap-safari-text-layer').forEach((element) => element.remove())

  const layer = createSvgElement('g')
  layer.setAttribute('class', 'mindmap-safari-text-layer')

  for (const node of collectVisibleNodes(data)) {
    const text = getNodeText(node.content)
    const rect = node.state.rect
    if (!text || rect.width <= 0 || rect.height <= 0) continue

    const label = createSvgElement('g')
    label.setAttribute('class', 'mindmap-safari-label')
    label.setAttribute('transform', `translate(${rect.x + MARKMAP_PADDING_X},${rect.y})`)

    const textElement = createSvgElement('text')
    textElement.setAttribute('xml:space', 'preserve')

    wrapSvgText(text, MARKMAP_MAX_WIDTH).forEach((line, index) => {
      const tspan = createSvgElement('tspan')
      tspan.setAttribute('x', '0')
      tspan.setAttribute('y', `${MARKMAP_TEXT_BASELINE + index * MARKMAP_LINE_HEIGHT}`)
      tspan.textContent = line
      textElement.append(tspan)
    })

    label.append(textElement)
    layer.append(label)
  }

  contentGroup.append(layer)
  hideOriginalMarkmapText(contentGroup)
}

const patchSafariTextFallback = () => {
  if (!useSvgTextFallback || !markmapInstance) return

  const originalRenderData = markmapInstance.renderData.bind(markmapInstance)
  markmapInstance.renderData = async (...args) => {
    const result = await originalRenderData(...args)
    syncSafariTextFallback()
    setTimeout(() => {
      hideOriginalMarkmapText(markmapInstance?.g?.node?.())
    }, 350)
    return result
  }
}

/**
 * Kết xuất bản đồ tư duy
 */
const renderMindmap = async (data, retryCount = 0) => {
  if (!data) return

  if (!mindmapSvg.value || !ensureSvgViewportSize()) {
    // nếuSVGHoặc kích thước chưa sẵn sàng，Số lần thử lại tối đa3lần
    if (retryCount < 3) {
      setTimeout(() => {
        renderMindmap(data, retryCount + 1)
      }, 100)
      return
    } else {
      console.error('Không thể có đượcSVGthùng chứa，Hiển thị không thành công')
      message.error('Hiển thị không thành công：không thể tìm thấySVGthùng chứa')
      return
    }
  }

  try {
    // Xóa phiên bản trước đó
    if (markmapInstance) {
      markmapInstance.destroy()
    }
    mindmapSvg.value.classList.remove('mindmap-safari-fallback')

    // sẽJSONChuyển đổi thànhMarkdown
    const markdown = jsonToMarkdown(data)

    // sử dụngTransformerChuyển đổi
    const transformer = new Transformer()
    const { root } = transformer.transform(markdown)

    // tạo raMarkmapVí dụ
    markmapInstance = Markmap.create(mindmapSvg.value, {
      duration: 300,
      maxWidth: MARKMAP_MAX_WIDTH,
      nodeMinHeight: 24,
      paddingX: MARKMAP_PADDING_X,
      spacingVertical: 5,
      spacingHorizontal: 60
    })
    patchSafariTextFallback()

    await markmapInstance.setData(root)
    await markmapInstance.fit()

    // Trì hoãn việc thích ứng trở lại，Đảm bảo bố cục hoàn toàn ổn định
    setTimeout(() => {
      if (markmapInstance) {
        syncSafariTextFallback()
        markmapInstance.fit()
      }
    }, 300)
  } catch (error) {
    console.error('Không thể hiển thị bản đồ tư duy:', error)
    message.error('Hiển thị không thành công: ' + error.message)
  }
}

/**
 * Thích ứng với chế độ xem
 */
const fitView = () => {
  if (markmapInstance) {
    ensureSvgViewportSize()
    syncSafariTextFallback()
    markmapInstance.fit()
  }
}

/**
 * Các phương thức tiếp xúc với thành phần cha
 */
defineExpose({
  refreshMindmap,
  generateMindmap
})

// ============================================================================
// vòng đời
// ============================================================================

// Cơ sở dữ liệu ngheIDthay đổi
watch(
  () => props.kbId,
  (newId) => {
    if (newId) {
      loadMindmap()
    }
  },
  { immediate: true }
)

// Theo dõi sự thay đổi kích thước vùng chứa，Tự động thích ứng
let resizeObserver = null

onMounted(() => {
  // cài đặtResizeObserverTheo dõi sự thay đổi kích thước vùng chứa
  nextTick(() => {
    if (mindmapSvg.value) {
      const container = mindmapSvg.value.parentElement
      if (container) {
        resizeObserver = new ResizeObserver(() => {
          if (markmapInstance) {
            ensureSvgViewportSize()
            syncSafariTextFallback()
            markmapInstance.fit()
          }
        })
        resizeObserver.observe(container)
      }
    }
  })
})

// dọn dẹp
onUnmounted(() => {
  if (markmapInstance) {
    markmapInstance.destroy()
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
})
</script>

<style scoped lang="less">
.mindmap-section {
  display: flex;
  flex-direction: column;
  background: var(--gray-0);
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.section-content {
  flex: 1;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.loading-state,
.generating-state,
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 28px;
  color: var(--gray-500);
  font-size: 13px;
  text-align: center;

  p {
    margin: 0;
  }
}

.empty-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--gray-150);
  border-radius: 12px;
  background: var(--main-30);
  color: var(--main-color);
}

.empty-title {
  margin-top: 2px;
  color: var(--gray-900);
  font-size: 15px;
  font-weight: 600;
}

.empty-description {
  max-width: 280px;
  color: var(--gray-500);
  line-height: 1.5;
}

.mindmap-primary-action {
  min-height: 32px;
  margin-top: 4px;
  padding: 0 14px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: var(--main-600);
  color: var(--main-0);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  appearance: none;
  transition:
    background-color 0.18s ease,
    color 0.18s ease;

  &:hover,
  &:focus-visible {
    background: var(--main-700);
    color: var(--main-0);
    outline: none;
  }

  &:focus-visible {
    box-shadow: 0 0 0 2px var(--main-200);
  }
}

.mindmap-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.mindmap-toolbar {
  padding: 8px 12px;
  background: var(--gray-0);
  border-bottom: 1px solid var(--gray-150);
  display: flex;
  align-items: center;
  justify-content: flex-end;

  .toolbar-text {
    margin-left: 4px;
    font-size: 13px;
  }
}

.mindmap-toolbar-btn {
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--gray-600);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  appearance: none;
  transition:
    background-color 0.18s ease,
    color 0.18s ease;

  &:hover,
  &:focus-visible {
    background: var(--gray-50);
    color: var(--main-color);
    outline: none;
  }

  &:focus-visible {
    box-shadow: 0 0 0 2px var(--main-100);
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  &:disabled:hover {
    background: transparent;
    color: var(--gray-600);
  }
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.mindmap-svg-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: var(--gray-0);
}

.mindmap-svg {
  width: 100%;
  height: 100%;
  min-height: 150px;
  display: block;
}

// Đảm bảo vùng chứa chính có chiều cao
:deep(.markmap) {
  width: 100% !important;
  height: 100% !important;
}

:deep(.mindmap-svg.mindmap-safari-fallback .markmap-foreign) {
  opacity: 0 !important;
  visibility: hidden !important;
  pointer-events: none;
}

:deep(.mindmap-safari-text-layer) {
  pointer-events: none;
}

:deep(.mindmap-safari-label) {
  font: var(--markmap-font);
  fill: var(--markmap-text-color);
}

.mindmap-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  margin-left: 4px;
  border-radius: 9px;
  background: var(--main-600);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
}

.mindmap-toolbar-btn--accent {
  color: var(--main-600);

  &:hover,
  &:focus-visible {
    background: var(--main-30);
    color: var(--main-700);
  }
}
</style>
