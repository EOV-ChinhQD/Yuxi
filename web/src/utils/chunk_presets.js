export const CHUNK_PRESET_OPTIONS = [
  {
    value: 'general',
    label: 'General',
    description: 'Phân chia phổ quát：Chia theo dấu phân cách và độ dài，Thích hợp cho hầu hết các tài liệu thông thường。'
  },
  {
    value: 'qa',
    label: 'QA',
    description: 'Phân chia câu hỏi và trả lời：Ưu tiên trích xuất câu hỏi-Cấu trúc câu trả lời，thích hợp cho FAQ、ngân hàng câu hỏi、Hướng dẫn hỏi đáp。'
  },
  {
    value: 'book',
    label: 'Book',
    description: 'Sách nhỏ：Tăng cường nhận dạng tiêu đề chương và thực hiện hợp nhất theo thứ bậc，Phù hợp làm tài liệu giảng dạy、Hướng dẫn sử dụng、tài liệu dài。'
  },
  {
    value: 'laws',
    label: 'Laws',
    description: 'Ngăn chặn quy định：Tổ chức, thống nhất theo cấp độ pháp lý，Phù hợp với pháp luật và các quy định、Văn bản quy phạm thể chế。'
  },
  {
    value: 'semantic',
    label: 'Semantic',
    description: 'phân đoạn ngữ nghĩa：Phân đoạn ngữ nghĩa bằng thuật toán nhúng và phân cụm，và tự động nâng cao bối cảnh tiêu đề。'
  },
  {
    value: 'separator',
    label: 'Separator',
    description: 'sự tách biệt nghiêm ngặt：Nhấn dấu phân cách để phân chia，Chỉ những đoạn rất dài mới tiếp tục được chia theo chiều dài。'
  }
]

export const CHUNK_PRESET_LABEL_MAP = Object.fromEntries(
  CHUNK_PRESET_OPTIONS.map((item) => [item.value, item.label])
)

export const CHUNK_PRESET_DESCRIPTION_MAP = Object.fromEntries(
  CHUNK_PRESET_OPTIONS.map((item) => [item.value, item.description])
)

export const getChunkPresetDescription = (presetId) =>
  CHUNK_PRESET_DESCRIPTION_MAP[presetId] || CHUNK_PRESET_DESCRIPTION_MAP.general

export const isPlainObject = (value) =>
  value !== null && typeof value === 'object' && !Array.isArray(value)

export const buildChunkParserConfigPayload = (source, { includeSizeOverlap = true } = {}) => {
  if (!isPlainObject(source)) {
    return {}
  }

  const config = {}
  if (includeSizeOverlap) {
    if (source.chunk_token_num !== undefined && source.chunk_token_num !== null) {
      config.chunk_token_num = source.chunk_token_num
    }
    if (source.overlapped_percent !== undefined && source.overlapped_percent !== null) {
      config.overlapped_percent = source.overlapped_percent
    }
  }
  if (source.delimiter) {
    config.delimiter = source.delimiter
  }

  return config
}

export const buildChunkParamsPayload = (source, options = {}) => {
  if (!isPlainObject(source)) {
    return {}
  }

  const payload = {}
  const chunkParserConfig = buildChunkParserConfigPayload(source.chunk_parser_config, options)
  if (Object.keys(chunkParserConfig).length > 0) {
    payload.chunk_parser_config = chunkParserConfig
  }
  if (source.chunk_preset_id) {
    payload.chunk_preset_id = source.chunk_preset_id
  }

  return payload
}
