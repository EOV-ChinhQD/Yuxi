import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'
import relativeTime from 'dayjs/plugin/relativeTime'

dayjs.extend(utc)
dayjs.extend(timezone)
dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

const DEFAULT_TZ = 'Asia/Shanghai'
dayjs.tz.setDefault(DEFAULT_TZ)

const NUMERIC_REGEX = /^-?\d+(?:\.\d+)?$/

const coerceDayjs = (value) => {
  if (value === null || value === undefined) {
    return null
  }

  if (typeof value === 'number') {
    return dayjs(value).tz(DEFAULT_TZ)
  }

  const stringValue = String(value).trim()
  if (!stringValue) {
    return null
  }

  if (NUMERIC_REGEX.test(stringValue)) {
    const numeric = Number(stringValue)
    if (Number.isNaN(numeric)) {
      return null
    }

    // giá trị nhỏ hơn 10^12 thời gian được coi là dấu thời gian cấp hai，Mặt khác được coi là mili giây
    if (Math.abs(numeric) < 1e12) {
      return dayjs.unix(numeric).tz(DEFAULT_TZ)
    }
    return dayjs(numeric).tz(DEFAULT_TZ)
  }

  // phân tích cú pháp ISO chuỗi（dayjs Thông tin múi giờ sẽ được tự động nhận dạng，Chẳng hạn như Z Hậu tố chỉ ra UTC）
  // Cần phải chuyển đổi thành UTC Đặt lại múi giờ，Nếu không .tz() sẽ chỉ thay đổi hiển thị mà không chuyển đổi chính xác
  const parsed = dayjs(stringValue)
  if (!parsed.isValid()) {
    return null
  }
  // Đầu tiên chuyển đổi thành UTC（Giữ giá trị thời gian ban đầu），Sau đó chuyển đổi sang múi giờ Thượng Hải
  return parsed.utc().tz(DEFAULT_TZ)
}

export const parseToShanghai = (value) => coerceDayjs(value)

export const formatDateTime = (value, format = 'YYYY-MM-DD HH:mm') => {
  const parsed = coerceDayjs(value)
  if (!parsed) return '-'
  return parsed.format(format)
}

export const formatFullDateTime = (value) => formatDateTime(value, 'YYYY-MM-DD HH:mm:ss')

export const formatRelative = (value) => {
  const parsed = coerceDayjs(value)
  if (!parsed) return '-'
  return parsed.fromNow()
}

export const sortByDatetimeDesc = (items, accessor) => {
  const copy = [...items]
  copy.sort((a, b) => {
    const first = coerceDayjs(accessor(a))
    const second = coerceDayjs(accessor(b))

    if (!first && !second) return 0
    if (!first) return 1
    if (!second) return -1
    return second.valueOf() - first.valueOf()
  })
  return copy
}

export default dayjs
