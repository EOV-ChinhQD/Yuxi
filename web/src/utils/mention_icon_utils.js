import { BookMarked, BookOpen, Bot, Plug } from 'lucide-vue-next'

export const MENTION_ICON_SIZE = 15
export const MENTION_ICON_STROKE_WIDTH = 2.2

// Lưu ý：file Loại biểu tượng được làm bằng FileTypeIcon Các thành phần được hiển thị trực tiếp，Ở đây chỉ giải quyết phần còn lại mention Loại。
const MENTION_TYPE_ICON_COMPONENTS = {
  knowledge: BookOpen,
  skill: BookMarked,
  mcp: Plug,
  subagent: Bot
}

export const getMentionIconComponent = (type) => MENTION_TYPE_ICON_COMPONENTS[type] || Plug

export const getMentionIconStyle = () => null
