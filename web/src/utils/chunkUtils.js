/**
 * Chunk hàm công cụ
 */

export const DEFAULT_CHUNK_PRESET_ID = 'general'

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

/**
 * Tìm phần chồng lấn giữa hai chuỗi
 * @param {string} str1 - Chuỗi đầu tiên
 * @param {string} str2 - Chữ ký thứ hai
 * @returns {string} - Nội dung phần chồng lấp
 */
export function findOverlap(str1, str2) {
  if (!str1 || !str2) return ''

  const maxOverlap = Math.min(str1.length, str2.length)
  let overlap = ''

  // Bắt đầu kiểm tra từ sự chồng lấp dài nhất có thể
  for (let i = maxOverlap; i > 10; i--) {
    const endStr1 = str1.slice(-i)
    const startStr2 = str2.slice(0, i)

    if (endStr1 === startStr2) {
      overlap = endStr1
      break
    }
  }

  return overlap
}

/**
 * GộpchunksVà xử lý nội dung trùng lặp
 * @param {Array} chunks - chunkMảng, mỗichunkChứaid, content, chunk_order_index
 * @returns {Object} - Kết quả hợp nhất, bao gồmcontentvàchunksmảng
 */
export function mergeChunks(chunks) {
  if (!chunks || chunks.length === 0) {
    return { content: '', chunks: [] }
  }

  // Nhấnorder排序
  const sorted = [...chunks].sort((a, b) => a.chunk_order_index - b.chunk_order_index)
  const merged = []
  let currentContent = ''

  for (let i = 0; i < sorted.length; i++) {
    const chunk = sorted[i]
    const content = chunk.content

    if (i === 0) {
      // Đầu tiênchunkThêm trực tiếp
      currentContent = content
      merged.push({
        ...chunk,
        startOffset: 0,
        endOffset: content.length
      })
    } else {
      // Tìm phần chồng lấn
      const overlap = findOverlap(currentContent, content)
      const newContent = content.slice(overlap.length)

      if (newContent.length > 0) {
        const startOffset = currentContent.length
        if (overlap.length > 0) {
          currentContent += newContent
        } else {
          currentContent += `\n${newContent}`
        }
        merged.push({
          ...chunk,
          startOffset,
          endOffset: currentContent.length
        })
      }
    }
  }

  return { content: currentContent, chunks: merged }
}

/**
 * Chia văn bản thành các đoạn
 * @param {string} content - Nội dung văn bản
 * @returns {Array} - Mảng đoạn
 */
export function splitIntoParagraphs(content) {
  if (!content) return []

  // Tách theo ký tự xuống dòng, giữ lại đoạn trống
  return content.split(/\n\n+/).filter((para) => para.trim() !== '')
}

/**
 * Tìm tương ứng cho mỗi đoạn vănchunk
 * @param {Array} paragraphs - Mảng đoạn
 * @param {Array} mappedChunks - Sau khi ánh xạchunks
 * @returns {Array} - ChứachunkĐoạn thông tin
 */
export function mapParagraphsToChunks(paragraphs, mappedChunks) {
  if (!paragraphs || !mappedChunks) return []

  let currentOffset = 0
  return paragraphs.map((paragraph) => {
    const paragraphLength = paragraph.length + 2 // +2 for the \n\n

    // Tìm thấy chứa vị trí nàychunk
    const chunk =
      mappedChunks.find(
        (chunk) => currentOffset >= chunk.startOffset && currentOffset < chunk.endOffset
      ) || mappedChunks[0]

    const result = {
      content: paragraph,
      chunk,
      startOffset: currentOffset,
      endOffset: currentOffset + paragraphLength
    }

    currentOffset += paragraphLength
    return result
  })
}

/**
 * LấychunkVăn bản xem trước
 * @param {string} content - chunknội dung
 * @param {number} maxLength - Độ dài tối đa
 * @returns {string} - Xem trước văn bản
 */
export function getChunkPreview(content, maxLength = 100) {
  if (!content) return ''

  const text = content.replace(/\n+/g, ' ').trim()
  if (text.length <= maxLength) return text

  return text.slice(0, maxLength) + '...'
}
