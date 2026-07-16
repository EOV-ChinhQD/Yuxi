<template>
  <div class="chunk-params-config">
    <div class="params-info">
      <p>
        Điều chỉnh tham số chunk có thể kiểm soát cách chia cắt văn bản, ảnh hưởng đến chất lượng
        tìm kiếm và hiệu suất tải tài liệu。
      </p>
    </div>
    <a-form :model="localParams" name="chunkConfig" autocomplete="off" layout="vertical">
      <a-form-item v-if="showPreset" name="chunk_preset_id">
        <template #label>
          <span class="chunk-preset-label">
            Chiến lược phân chia
            <a-tooltip :title="presetDescription">
              <QuestionCircleOutlined class="chunk-preset-help-icon" />
            </a-tooltip>
          </span>
        </template>
        <a-select
          v-model:value="localParams.chunk_preset_id"
          :options="presetOptions"
          :loading="chunkPresetLoading"
          style="width: 100%"
        />
        <p class="param-description">
          Chọn chiến lược phân chia phù hợp với cấu trúc tài liệu hiện tại。
          <span v-if="allowPresetFollowDefault"
            >Sử dụng chiến lược mặc định của cơ sở kiến thức khi để trống。</span
          >
        </p>
      </a-form-item>

      <div class="chunk-row">
        <a-form-item v-if="showChunkSizeOverlap" name="chunk_token_num">
          <template #label>
            <span class="chunk-preset-label">
              Số token tối đa
              <a-tooltip title="Số token tối đa cho mỗi đoạn văn bản. Nếu để trống sẽ sử dụng giá trị mặc định là 512">
                <QuestionCircleOutlined class="chunk-preset-help-icon" />
              </a-tooltip>
            </span>
          </template>
          <a-input-number
            v-model:value="parserConfig.chunk_token_num"
            :min="100"
            :max="10000"
            placeholder="Mặc định 512"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item v-if="showChunkSizeOverlap" name="overlapped_percent">
          <template #label>
            <span class="chunk-preset-label">
              Tỷ lệ chồng lấp (%)
              <a-tooltip
                title="Các đoạn văn bản liền kề theo token Tính tỷ lệ chồng lấn, để trống để dùng giá trị mặc định 0"
              >
                <QuestionCircleOutlined class="chunk-preset-help-icon" />
              </a-tooltip>
            </span>
          </template>
          <a-input-number
            v-model:value="parserConfig.overlapped_percent"
            :min="0"
            :max="99"
            placeholder="Mặc định 0"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item v-if="showQaSplit" name="delimiter">
          <template #label>
            <span class="chunk-preset-label">
              Dấu phân cách
              <a-tooltip
                title="Hỗ trợ các ký tự thoát như \\n, \\t. Nếu để trống sẽ sử dụng dấu phân cách mặc định \\n"
              >
                <QuestionCircleOutlined class="chunk-preset-help-icon" />
              </a-tooltip>
            </span>
          </template>
          <a-input
            v-model:value="parserConfig.delimiter"
            placeholder="Mặc định \\n, có thể nhập liệu \\n\\n\\n hoặc ---"
            style="width: 100%"
          />
        </a-form-item>
      </div>
    </a-form>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { QuestionCircleOutlined } from '@ant-design/icons-vue'
import { useChunkPresetOptions } from '@/composables/useChunkPresetOptions'
import { DEFAULT_CHUNK_PRESET_ID, isPlainObject } from '@/utils/chunkUtils'

const props = defineProps({
  tempChunkParams: {
    type: Object,
    required: true
  },
  showQaSplit: {
    type: Boolean,
    default: true
  },
  showChunkSizeOverlap: {
    type: Boolean,
    default: true
  },
  showPreset: {
    type: Boolean,
    default: true
  },
  allowPresetFollowDefault: {
    type: Boolean,
    default: false
  },
  databasePresetId: {
    type: String,
    default: DEFAULT_CHUNK_PRESET_ID
  }
})

const localParams = computed(() => props.tempChunkParams)
const fallbackParserConfig = ref({})
const {
  chunkPresetSelectOptions,
  chunkPresetLabelMap,
  chunkPresetLoading,
  loadChunkPresetOptions,
  getChunkPresetDescription
} = useChunkPresetOptions()

const parserConfig = computed(() => {
  if (!isPlainObject(props.tempChunkParams.chunk_parser_config)) {
    return fallbackParserConfig.value
  }
  return props.tempChunkParams.chunk_parser_config
})

const presetOptions = computed(() => {
  const options = []
  const defaultPresetLabel =
    chunkPresetLabelMap.value[props.databasePresetId] ||
    props.databasePresetId ||
    DEFAULT_CHUNK_PRESET_ID

  if (props.allowPresetFollowDefault) {
    options.push({
      value: '',
      label: `Tiếp tục sử dụng mặc định của cơ sở kiến thức（${defaultPresetLabel}）`
    })
  }

  options.push(...chunkPresetSelectOptions.value)

  return options
})

const effectivePresetId = computed(
  () => props.tempChunkParams.chunk_preset_id || props.databasePresetId || DEFAULT_CHUNK_PRESET_ID
)
const presetDescription = computed(() => getChunkPresetDescription(effectivePresetId.value))

onMounted(() => {
  loadChunkPresetOptions()
})
</script>

<style scoped>
.chunk-params-config {
  width: 100%;
}

.params-info {
  margin-bottom: 16px;
}

.params-info p {
  margin: 0;
  color: var(--gray-500);
  font-size: 14px;
  line-height: 1.5;
}

.chunk-row {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}

.chunk-row > .ant-form-item {
  flex: 1;
  margin-bottom: 0;
}

.param-description {
  font-size: 12px;
  color: var(--gray-400);
  margin: 4px 0 0 0;
  line-height: 1.4;
}

.chunk-preset-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.chunk-preset-help-icon {
  color: var(--gray-500);
  cursor: help;
  font-size: 14px;
}
</style>
