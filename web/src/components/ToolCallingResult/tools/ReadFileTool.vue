<template>
  <BaseToolCall :tool-call="toolCall">
    <template #header>
      <div class="sep-header">
        <!-- xử lý đặc biệt：SKILL.md Tệp xuất hiện dưới dạng Skill | <Tên thư mục mẹ> -->
        <template v-if="skillName">
          <span class="note skill-note">Skill</span>
          <span class="separator">|</span>
          <span class="description skill-name">{{ skillName }}</span>
        </template>
        <template v-else>
          <span class="note">Read</span>
          <span class="separator" v-if="filePath">|</span>
          <span class="description" :title="filePath">
            <span class="code">{{ fileName }}</span>
            <span class="tag" v-if="lineRange">{{ lineRange }}</span>
          </span>
        </template>
      </div>
    </template>
  </BaseToolCall>
</template>

<script setup>
import { computed } from 'vue'
import BaseToolCall from '../BaseToolCall.vue'

const props = defineProps({
  toolCall: {
    type: Object,
    required: true
  }
})

const parsedArgs = computed(() => {
  const args = props.toolCall.args || props.toolCall.function?.arguments
  if (!args) return {}
  if (typeof args === 'object') return args
  try {
    return JSON.parse(args)
  } catch {
    return {}
  }
})

const filePath = computed(() => parsedArgs.value.file_path || '')

// Chỉ hiển thị tên tệp，Vượt qua trong khi lơ lửng title hiển thị đường dẫn đầy đủ
const fileName = computed(() => {
  const path = filePath.value
  if (!path) return ''
  return path.replace(/\\/g, '/').split('/').pop()
})

const lineRange = computed(() => {
  const offset = parsedArgs.value.offset
  const limit = parsedArgs.value.limit
  if (offset !== undefined && limit !== undefined) {
    return `Lines ${offset}-${Number(offset) + Number(limit)}`
  } else if (limit !== undefined) {
    return `First ${limit} lines`
  }
  return ''
})

// Nếu những gì được đọc là SKILL.md tập tin，Trích xuất tên thư mục cấp trên làm tên kỹ năng
// Ví dụ：mmm/xxx/SKILL.md → skillName = 'xxx'
const skillName = computed(() => {
  const path = filePath.value
  if (!path.endsWith('SKILL.md')) return null
  const parts = path.replace(/\\/g, '/').split('/')
  // Lấy đoạn áp chót（SKILL.md tên thư mục mẹ）
  return parts.length >= 2 ? parts[parts.length - 2] : null
})
</script>

<style lang="less" scoped>
.sep-header {
  .tag {
    color: var(--color-primary-600);
    background-color: var(--color-primary-50);
  }

  // SKILL.md phong cách đặc biệt
  .skill-note {
    color: var(--main-700);
  }

  .skill-name {
    font-weight: 600;
    color: var(--main-600);
  }
}
</style>
