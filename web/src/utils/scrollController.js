import { nextTick } from 'vue'

/**
 * Lớp tiện ích điều khiển cuộn
 */
export class ScrollController {
  constructor(containerSelector = '.chat', options = {}) {
    this.containerSelector = containerSelector
    this.options = {
      threshold: 40,
      scrollDelay: 100,
      retryDelays: [50, 150],
      ...options
    }

    this.scrollTimer = null
    this.scrollRetryTimers = []
    this.programmaticScrollTimer = null
    this.isUserScrolling = false
    this.shouldAutoScroll = true
    this.isProgrammaticScroll = false

    // Bind the context of 'this' for the event handler
    this.handleScroll = this.handleScroll.bind(this)
  }

  /**
   * Lấy container cuộn
   * @returns {Element|null}
   */
  getContainer() {
    if (typeof this.containerSelector === 'function') {
      return this.containerSelector()
    }
    if (typeof this.containerSelector === 'string') {
      return document.querySelector(this.containerSelector)
    }
    return this.containerSelector || null
  }

  /**
   * Kiểm tra xem có ở cuối không
   * @returns {boolean}
   */
  isAtBottom() {
    const container = this.getContainer()
    if (!container) return false

    const { threshold } = this.options
    return this.getBottomOffset(container) <= threshold
  }

  getBottomOffset(container = this.getContainer()) {
    if (!container) return Number.POSITIVE_INFINITY
    return Math.max(0, container.scrollHeight - container.scrollTop - container.clientHeight)
  }

  cancelPendingScrolls() {
    this.scrollRetryTimers.forEach((timer) => clearTimeout(timer))
    this.scrollRetryTimers = []
  }

  markProgrammaticScroll() {
    if (this.programmaticScrollTimer) {
      clearTimeout(this.programmaticScrollTimer)
    }
    this.isProgrammaticScroll = true
    this.programmaticScrollTimer = setTimeout(() => {
      this.isProgrammaticScroll = false
      this.programmaticScrollTimer = null
    }, this.options.scrollDelay)
  }

  /**
   * Xử lý sự kiện cuộn
   */
  handleScroll() {
    if (this.scrollTimer) {
      clearTimeout(this.scrollTimer)
    }

    // Nếu đó là cuộn theo chương trình, vẫn đồng bộ trạng thái dựa trên vị trí hiện tại, tránh đánh dấu tồn đọng dẫn đến việc vô tình nuốt cuộn lên của người dùng。
    if (this.isProgrammaticScroll) {
      const atBottom = this.isAtBottom()
      this.shouldAutoScroll = atBottom
      this.isProgrammaticScroll = false
      if (this.programmaticScrollTimer) {
        clearTimeout(this.programmaticScrollTimer)
        this.programmaticScrollTimer = null
      }
      if (!atBottom) {
        this.cancelPendingScrolls()
        this.isUserScrolling = true
        this.scrollTimer = setTimeout(() => {
          this.isUserScrolling = false
        }, this.options.scrollDelay)
      }
      return
    }

    this.cancelPendingScrolls()

    // Đánh dấu người dùng đang cuộn
    this.isUserScrolling = true

    // Kiểm tra xem có ở cuối không
    this.shouldAutoScroll = this.isAtBottom()

    // Đặt lại trạng thái cuộn của người dùng sau một khoảng thời gian khi cuộn kết thúc
    this.scrollTimer = setTimeout(() => {
      this.isUserScrolling = false
    }, this.options.scrollDelay)
  }

  /**
   * Chờ DOM bố cục ổn định
   * @returns {Promise<void>}
   */
  async waitForLayoutStable() {
    // Sử dụng requestAnimationFrame Đảm bảo DOM Render完成
    await new Promise((resolve) => requestAnimationFrame(resolve))
    await new Promise((resolve) => requestAnimationFrame(resolve))
  }

  scrollContainerToBottom(container, behavior = 'auto') {
    if (!container) return
    this.markProgrammaticScroll()
    container.scrollTo({
      top: Math.max(0, container.scrollHeight - container.clientHeight),
      behavior
    })
  }

  /**
   * Cuộn thông minh xuống dưới
   * @param {boolean} force - có bắt buộc cuộn không
   */
  async scrollToBottom(force = false) {
    await nextTick()
    // Chờ DOM bố cục ổn định
    await this.waitForLayoutStable()

    // Chỉ thực hiện khi nên tự động cuộn (trừ khi được ép buộc）
    if (!force && !this.shouldAutoScroll) return

    const container = this.getContainer()
    if (!container) return

    this.cancelPendingScrolls()

    this.scrollContainerToBottom(container, 'auto')

    // Nội dung động vẫn có thể lấp đầy chiều cao ở khung tiếp theo, giữ lại một số ít thử lại, nhưng cuộn thủ công của người dùng sẽ hủy ngay lập tức。
    this.options.retryDelays.forEach((delay) => {
      const timer = setTimeout(() => {
        if (force || this.shouldAutoScroll) {
          this.scrollContainerToBottom(container, 'auto')
        }
      }, delay)
      this.scrollRetryTimers.push(timer)
    })
  }

  async scrollToBottomStaticForce() {
    const container = this.getContainer()
    if (!container) return

    this.cancelPendingScrolls()
    await nextTick()
    await this.waitForLayoutStable()
    this.scrollContainerToBottom(container, 'auto')
    this.shouldAutoScroll = true
  }

  /**
   * Kích hoạt cuộn tự động
   */
  enableAutoScroll() {
    this.shouldAutoScroll = true
  }

  /**
   * Tắt cuộn tự động
   */
  disableAutoScroll() {
    this.shouldAutoScroll = false
  }

  /**
   * Lấy trạng thái cuộn
   */
  getScrollState() {
    return {
      isUserScrolling: this.isUserScrolling,
      shouldAutoScroll: this.shouldAutoScroll,
      isAtBottom: this.isAtBottom()
    }
  }

  /**
   * Dọn dẹp bộ định thời
   */
  cleanup() {
    if (this.scrollTimer) {
      clearTimeout(this.scrollTimer)
      this.scrollTimer = null
    }
    if (this.programmaticScrollTimer) {
      clearTimeout(this.programmaticScrollTimer)
      this.programmaticScrollTimer = null
    }
    this.cancelPendingScrolls()
  }

  /**
   * Đặt lại trạng thái cuộn
   */
  reset() {
    this.cleanup()
    this.isUserScrolling = false
    this.shouldAutoScroll = true
    this.isProgrammaticScroll = false
  }
}

/**
 * Tạo một thể hiện bộ điều khiển cuộn mặc định
 */
export const createScrollController = (containerSelector, options) => {
  return new ScrollController(containerSelector, options)
}

export default ScrollController
