import { nextTick } from 'vue'

/**
 * Công cụ điều khiển cuộn
 */
export class ScrollController {
  constructor(containerSelector = '.chat', options = {}) {
    this.containerSelector = containerSelector
    this.options = {
      threshold: 100,
      scrollDelay: 100,
      retryDelays: [50, 150],
      ...options
    }

    this.scrollTimer = null
    this.isUserScrolling = false
    this.shouldAutoScroll = true
    this.isProgrammaticScroll = false

    // Bind the context of 'this' for the event handler
    this.handleScroll = this.handleScroll.bind(this)
  }

  /**
   * Nhận thùng chứa cuộn
   * @returns {Element|null}
   */
  getContainer() {
    return document.querySelector(this.containerSelector)
  }

  /**
   * Kiểm tra xem nó có ở dưới cùng không
   * @returns {boolean}
   */
  isAtBottom() {
    const container = this.getContainer()
    if (!container) return false

    const { threshold } = this.options
    return container.scrollHeight - container.scrollTop - container.clientHeight <= threshold
  }

  /**
   * Xử lý các sự kiện cuộn
   */
  handleScroll() {
    if (this.scrollTimer) {
      clearTimeout(this.scrollTimer)
    }

    // Nếu đó là cuộn theo chương trình，Bỏ qua sự kiện này
    if (this.isProgrammaticScroll) {
      this.isProgrammaticScroll = false
      return
    }

    // Người dùng gắn cờ đang cuộn
    this.isUserScrolling = true

    // Kiểm tra xem nó có ở dưới cùng không
    this.shouldAutoScroll = this.isAtBottom()

    // Đặt lại trạng thái cuộn của người dùng một thời gian sau khi quá trình cuộn kết thúc
    this.scrollTimer = setTimeout(() => {
      this.isUserScrolling = false
    }, this.options.scrollDelay)
  }

  /**
   * chờ đã DOM Bố cục ổn định
   * @returns {Promise<void>}
   */
  async waitForLayoutStable() {
    // sử dụng requestAnimationFrame đảm bảo DOM Kết xuất hoàn tất
    await new Promise((resolve) => requestAnimationFrame(resolve))
    // Chờ một thời gian ngắn để đảm bảo CSS Bố cục đã hoàn thành
    await new Promise((resolve) => setTimeout(resolve, 50))
  }

  /**
   * Cuộn thông minh xuống dưới cùng
   * @param {boolean} force - Có buộc cuộn hay không
   */
  async scrollToBottom(force = false) {
    await nextTick()
    // chờ đã DOM Bố cục ổn định
    await this.waitForLayoutStable()

    // Chỉ được thực thi khi tính năng tự động cuộn được cho là sẽ xảy ra（trừ khi bị ép buộc）
    if (!force && !this.shouldAutoScroll) return

    const container = this.getContainer()
    if (!container) return

    // Được đánh dấu để cuộn theo chương trình
    this.isProgrammaticScroll = true

    // Ghi lại chiều cao của container trước khi cuộn
    const initialHeight = container.scrollHeight

    const scrollOptions = {
      top: container.scrollHeight,
      behavior: 'smooth'
    }

    // Cuộn ngay bây giờ
    container.scrollTo(scrollOptions)

    // Thử lại nhiều lần để đảm bảo cuộn thành công，Bao gồm cả việc chờ hoàn thành bố cục của các phần tử động như hộp nhập liệu
    const retryDelays = [50, 100, 200, 400]
    retryDelays.forEach((delay, index) => {
      setTimeout(() => {
        if (force || this.shouldAutoScroll) {
          this.isProgrammaticScroll = true
          const behavior = index === retryDelays.length - 1 ? 'auto' : 'smooth'

          // Nếu chiều cao thay đổi，Cho biết rằng có thể có nội dung động đang được hiển thị，đợi lại
          if (container.scrollHeight !== initialHeight && index < retryDelays.length - 1) {
            this.waitForLayoutStable().then(() => {
              container.scrollTo({
                top: container.scrollHeight,
                behavior
              })
            })
          } else {
            container.scrollTo({
              top: container.scrollHeight,
              behavior
            })
          }
        }
      }, delay)
    })
  }

  async scrollToBottomStaticForce() {
    await nextTick()
    await this.waitForLayoutStable()
    const container = this.getContainer()
    if (!container) return

    // Được đánh dấu để cuộn theo chương trình
    this.isProgrammaticScroll = true

    const scrollOptions = {
      top: container.scrollHeight,
      behavior: 'auto'
    }

    container.scrollTo(scrollOptions)

    const retryDelays = [50, 150]
    retryDelays.forEach((delay) => {
      setTimeout(() => {
        this.isProgrammaticScroll = true
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'auto'
        })
      }, delay)
    })
  }

  /**
   * Bật tính năng tự động cuộn
   */
  enableAutoScroll() {
    this.shouldAutoScroll = true
  }

  /**
   * Tắt tính năng tự động cuộn
   */
  disableAutoScroll() {
    this.shouldAutoScroll = false
  }

  /**
   * Nhận trạng thái cuộn
   */
  getScrollState() {
    return {
      isUserScrolling: this.isUserScrolling,
      shouldAutoScroll: this.shouldAutoScroll,
      isAtBottom: this.isAtBottom()
    }
  }

  /**
   * Hẹn giờ dọn dẹp
   */
  cleanup() {
    if (this.scrollTimer) {
      clearTimeout(this.scrollTimer)
      this.scrollTimer = null
    }
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
 * Tạo một phiên bản bộ điều khiển cuộn mặc định
 */
export const createScrollController = (containerSelector, options) => {
  return new ScrollController(containerSelector, options)
}

export default ScrollController
