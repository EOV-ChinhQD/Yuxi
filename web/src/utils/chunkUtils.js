/**
 * ChunkHợp nhất các chức năng tiện ích
 * Dùng để hợp nhất nhiềuchunkvà xử lý nội dung chồng chéo
 */

/**
 * Tìm sự chồng chéo giữa hai chuỗi
 * @param {string} str1 - chuỗi đầu tiên
 * @param {string} str2 - chuỗi thứ hai
 * @returns {string} - Nội dung chồng chéo
 */
export function findOverlap(str1, str2) {
  if (!str1 || !str2) return ''

  const maxOverlap = Math.min(str1.length, str2.length)
  let overlap = ''

  // Bắt đầu kiểm tra từ phần chồng chéo dài nhất có thể
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
 * hợp nhấtchunksvà xử lý nội dung chồng chéo
 * @param {Array} chunks - chunkmảng，mỗichunkchứaid, content, chunk_order_index
 * @returns {Object} - Hợp nhất kết quả，chứacontentvàchunksmảng
 */
export function mergeChunks(chunks) {
  if (!chunks || chunks.length === 0) {
    return { content: '', chunks: [] }
  }

  // nhấnordersắp xếp
  const sorted = [...chunks].sort((a, b) => a.chunk_order_index - b.chunk_order_index)
  const merged = []
  let currentContent = ''

  for (let i = 0; i < sorted.length; i++) {
    const chunk = sorted[i]
    const content = chunk.content

    if (i === 0) {
      // cái đầu tiênchunkThêm trực tiếp
      currentContent = content
      merged.push({
        ...chunk,
        startOffset: 0,
        endOffset: content.length
      })
    } else {
      // Tìm sự trùng lặp
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
 * Chia văn bản thành các đoạn văn
 * @param {string} content - nội dung văn bản
 * @returns {Array} - mảng đoạn văn
 */
export function splitIntoParagraphs(content) {
  if (!content) return []

  // Chia theo dòng mới，Giữ đoạn văn trống
  return content.split(/\n\n+/).filter((para) => para.trim() !== '')
}

/**
 * Tìm tương ứngchunk
 * @param {Array} paragraphs - mảng đoạn văn
 * @param {Array} mappedChunks - được ánh xạchunks
 * @returns {Array} - chứachunkđoạn thông tin
 */
export function mapParagraphsToChunks(paragraphs, mappedChunks) {
  if (!paragraphs || !mappedChunks) return []

  let currentOffset = 0
  return paragraphs.map((paragraph) => {
    const paragraphLength = paragraph.length + 2 // +2 for the \n\n

    // Tìm thấy có chứa vị trí nàychunk
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
 * Nhậnchunkvăn bản xem trước
 * @param {string} content - chunknội dung
 * @param {number} maxLength - chiều dài tối đa
 * @returns {string} - Xem trước văn bản
 */
export function getChunkPreview(content, maxLength = 100) {
  if (!content) return ''

  const text = content.replace(/\n+/g, ' ').trim()
  if (text.length <= maxLength) return text

  return text.slice(0, maxLength) + '...'
}
