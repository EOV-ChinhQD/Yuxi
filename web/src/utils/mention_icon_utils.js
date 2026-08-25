import { BookOpen, Bot, Plug, WandSparkles } from 'lucide-vue-next'
import { getSkillIcon } from './skill_icon_utils.js'

export const MENTION_ICON_SIZE = 15
export const MENTION_ICON_STROKE_WIDTH = 2.2

// Lưu ý：file Loại biểu tượng được làm bằng FileTypeIcon Các thành phần được hiển thị trực tiếp，Ở đây chỉ giải quyết phần còn lại mention Loại。
const MENTION_TYPE_ICON_COMPONENTS = {
  knowledge: BookOpen,
  skill: WandSparkles,
  mcp: Plug,
  subagent: Bot
}

export const getMentionIconComponent = (type, value) =>
  type === 'skill' ? getSkillIcon(value) : MENTION_TYPE_ICON_COMPONENTS[type] || Plug

export const getMentionIconStyle = () => null
