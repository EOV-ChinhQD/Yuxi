<template>
  <div class="kb-result-grouped-list">
    <div v-if="showSummary" class="result-summary">
      tìm thấy {{ normalizedChunks.length }} đoạn tài liệu liên quan，từ {{ fileGroupList.length }} tập tin
    </div>

    <div class="kb-results" v-if="normalizedChunks.length > 0">
      <div v-for="fileGroup in fileGroupList" :key="fileGroup.filename" class="file-group">
        <div
          class="file-header"
          :class="{ expanded: expandedFiles.has(fileGroup.filename) }"
          @click="toggleFile(fileGroup.filename)"
        >
          <div class="file-info">
            <ChevronRight
              v-if="!expandedFiles.has(fileGroup.filename)"
              :size="14"
              class="expand-icon"
            />
            <ChevronDown v-else :size="14" class="expand-icon" />
            <FileText :size="14" color="var(--gray-600)" />
            <span class="file-name">{{ fileGroup.filename }}</span>
            <span class="chunk-count">{{ fileGroup.chunks.length }} chunks</span>
          </div>
          <button
            v-if="fileGroup.kb_id && fileGroup.file_id"
            class="view-file-btn"
            @click.stop="openFileDetail(fileGroup)"
            title="Xem tập tin"
          >
            <Eye :size="14" />
          </button>
        </div>

        <div v-if="expandedFiles.has(fileGroup.filename)" class="chunks-container">
          <div
            v-for="(chunk, index) in fileGroup.chunks"
            :key="getChunkKey(chunk, index)"
            class="chunk-item"
            :class="{ 'high-relevance': typeof chunk.score === 'number' && chunk.score > 0.5 }"
            @click="openChunkDetail(chunk, index + 1)"
          >
            <div class="chunk-summary">
              <span class="chunk-index">#{{ index + 1 }}</span>
              <div class="chunk-scores">
                <span v-if="typeof chunk.score === 'number'" class="score-item"
                  >Sự tương đồng {{ (chunk.score * 100).toFixed(0) }}%</span
                >
                <span v-if="typeof chunk.rerank_score === 'number'" class="score-item"
                  >Sắp xếp lại {{ (chunk.rerank_score * 100).toFixed(0) }}%</span
                >
                <span v-if="getLineRange(chunk)" class="score-item">{{ getLineRange(chunk) }}</span>
              </div>
              <span class="chunk-preview">{{ getPreviewText(chunk.content) }}</span>
              <Eye :size="14" class="view-icon" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="no-results">
      <p>{{ emptyText }}</p>
    </div>

    <KbChunkDetailModal
      v-model:open="modalVisible"
      :chunk="selectedChunk"
      :title-prefix="`mảnh tài liệu #${selectedChunkIndex || '-'} `"
    />

    <FileDetailModal
      v-model:open="fileDetailOpen"
      :kb-id="fileDetailKbId"
      :file-id="fileDetailFileId"
    />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { FileText, ChevronRight, ChevronDown, Eye } from 'lucide-vue-next'
import KbChunkDetailModal from './KbChunkDetailModal.vue'
import FileDetailModal from '@/components/FileDetailModal.vue'

const props = defineProps({
  chunks: {
    type: [Array, Object],
    default: () => []
  },
  showSummary: {
    type: Boolean,
    default: true
  },
  emptyText: {
    type: String,
    default: 'Không tìm thấy nội dung cơ sở kiến thức liên quan'
  }
})

const expandedFiles = ref(new Set())
const modalVisible = ref(false)
const selectedChunk = ref(null)
const selectedChunkIndex = ref(null)
const fileDetailOpen = ref(false)
const fileDetailKbId = ref('')
const fileDetailFileId = ref('')

const resolveChunks = (input) => {
  if (Array.isArray(input)) return input
  if (!input || typeof input !== 'object') return []

  if (Array.isArray(input.chunks)) return input.chunks
  if (Array.isArray(input.data?.chunks)) return input.data.chunks

  return []
}

const normalizedChunks = computed(() =>
  resolveChunks(props.chunks)
    .filter((item) => item && typeof item === 'object' && item.content)
    .map((item) => {
      const metadata = item.metadata && typeof item.metadata === 'object' ? item.metadata : {}
      const source =
        metadata.source ||
        metadata.file_name ||
        metadata.filename ||
        metadata.title ||
        item.file_name ||
        item.filename ||
        item.file_id ||
        item.kb_id ||
        'nguồn không rõ'

      return {
        ...item,
        score: typeof item.score === 'number' ? item.score : metadata.score,
        metadata: {
          ...metadata,
          source,
          chunk_id: metadata.chunk_id || item.id
        }
      }
    })
)

const fileGroupList = computed(() => {
  const groups = new Map()
  for (const item of normalizedChunks.value) {
    const filename = item?.metadata?.source || 'nguồn không rõ'
    if (!groups.has(filename)) {
      groups.set(filename, {
        filename,
        kb_id: item?.kb_id || '',
        file_id: item?.file_id || '',
        chunks: []
      })
    }
    groups.get(filename).chunks.push(item)
  }

  return Array.from(groups.values()).sort((a, b) => a.filename.localeCompare(b.filename))
})

watch(
  fileGroupList,
  (groups) => {
    // Chỉ dọn sạch các mục mở rộng không hợp lệ khi nhóm các thay đổi，Giữ thu gọn theo mặc định。
    const validFilenames = new Set(groups.map((item) => item.filename))
    expandedFiles.value = new Set(
      [...expandedFiles.value].filter((filename) => validFilenames.has(filename))
    )
  },
  { immediate: true }
)

const toggleFile = (filename) => {
  if (expandedFiles.value.has(filename)) {
    expandedFiles.value.delete(filename)
  } else {
    expandedFiles.value.add(filename)
  }
}

const getChunkKey = (chunk, index) => {
  if (chunk?.metadata?.chunk_id) return `${chunk.metadata.chunk_id}-${index}`
  return `${chunk?.metadata?.source || 'chunk'}-${index}`
}

const getPreviewText = (text = '') => {
  const content = String(text)
  return content.length <= 100 ? content : `${content.substring(0, 100)}...`
}

const getLineRange = (chunk) => {
  const startLine = Number(chunk?.metadata?.start_line || 0)
  const endLine = Number(chunk?.metadata?.end_line || 0)
  if (!startLine || !endLine) return ''
  return startLine === endLine ? `Không. ${startLine} được rồi` : `Không. ${startLine}-${endLine} được rồi`
}

const openChunkDetail = (chunk, index) => {
  selectedChunk.value = chunk
  selectedChunkIndex.value = index
  modalVisible.value = true
}

const openFileDetail = (fileGroup) => {
  fileDetailKbId.value = fileGroup.kb_id || ''
  fileDetailFileId.value = fileGroup.file_id || ''
  fileDetailOpen.value = Boolean(fileDetailKbId.value && fileDetailFileId.value)
}
</script>

<style scoped lang="less">
.kb-result-grouped-list {
  padding: 4px;
  .result-summary {
    padding: 6px 10px;
    background: var(--gray-25);
    font-size: 12px;
    color: var(--gray-700);
    border: 1px solid var(--gray-150);
    border-radius: 8px;
    margin-bottom: 6px;
  }

  .kb-results {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .file-group {
    border: 1px solid var(--gray-150);
    border-radius: 8px;
    background: var(--gray-0);
    overflow: hidden;

    .file-header {
      padding: 5px 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
      background: var(--gray-10);

      &:hover {
        background: var(--gray-25);
      }

      &.expanded {
        background: var(--gray-25);
        border-bottom: 1px solid var(--gray-100);
      }

      .file-info {
        display: flex;
        align-items: center;
        gap: 8px;
        flex: 1;
        min-width: 0;

        .expand-icon {
          flex-shrink: 0;
          color: var(--gray-500);
        }

        .file-name {
          font-size: 13px;
          color: var(--gray-700);
          font-weight: 400;
          flex: 1;
          min-width: 0;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .chunk-count {
          font-size: 11px;
          color: var(--gray-700);
          white-space: nowrap;
        }
      }

      .view-file-btn {
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        border: none;
        background: transparent;
        border-radius: 4px;
        cursor: pointer;
        color: var(--gray-500);
        transition: all 0.15s;

        &:hover {
          background: var(--gray-100);
          color: var(--gray-700);
        }
      }
    }

    .chunk-item {
      padding: 6px 10px;
      border-bottom: 1px solid var(--gray-100);
      cursor: pointer;

      &:last-child {
        border-bottom: none;
      }

      &.high-relevance {
        background: var(--gray-5);
      }

      &:hover {
        background: var(--gray-25);
      }

      .chunk-summary {
        display: flex;
        align-items: center;
        gap: 8px;

        .chunk-index {
          color: var(--gray-700);
          font-size: 11px;
          min-width: 22px;
          text-align: center;
          background: var(--gray-25);
          border-radius: 4px;
          padding: 1px 4px;
        }

        .chunk-scores {
          display: flex;
          gap: 6px;

          .score-item {
            font-size: 11px;
            color: var(--gray-700);
            background: var(--gray-25);
            border: 1px solid var(--gray-100);
            border-radius: 4px;
            padding: 1px 5px;
            white-space: nowrap;
          }
        }

        .chunk-preview {
          flex: 1;
          min-width: 0;
          font-size: 12px;
          color: var(--gray-700);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .view-icon {
          color: var(--gray-700);
          opacity: 0.5;
        }
      }
    }
  }

  .no-results {
    text-align: center;
    color: var(--gray-700);
    padding: 10px;
    font-size: 12px;
    border: 1px dashed var(--gray-200);
    border-radius: 8px;
  }
}
</style>
