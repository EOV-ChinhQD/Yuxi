import { ref } from 'vue'

/**
 * @typedef {Object} MentionFile
 * @property {string} path - đường dẫn tập tin
 * @property {string} [content] - Nội dung tập tin
 * @property {string} [modified_at] - thời gian sửa đổi
 * @property {number} [size] - kích thước tập tin
 */

/**
 * @typedef {Object} MentionKnowledgeBase
 * @property {string} kb_id - cơ sở tri thứcID
 * @property {string} name - Tên cơ sở kiến thức
 */

/**
 * @typedef {Object} MentionMcp
 * @property {string} name - MCP Tên
 * @property {string} [description] - Mô tả
 */

/**
 * @typedef {Object} MentionConfig
 * @property {MentionFile[]} [files] - Danh sách tài liệu có thể trích dẫn
 * @property {MentionKnowledgeBase[]} [knowledgeBases] - Danh sách cơ sở kiến thức có thể tham khảo
 * @property {MentionMcp[]} [mcps] - Có thể trích dẫn MCP Danh sách máy chủ
 */

/**
 * @typedef {Object} MentionItem
 * @property {string} value - Các giá trị được hiển thị và chèn vào
 * @property {string} label - hiển thị nhãn
 * @property {'file'|'knowledge'|'mcp'} type - Loại
 * @property {string} [description] - Thông tin mô tả
 */

/**
 * @typedef {Object} UseMentionReturn
 * @property {import('vue').Ref<MentionConfig>} mentionConfig - hiện tại mention Cấu hình
 * @property {Function} setMention - cài đặt mention Cấu hình
 * @property {Function} updateFiles - Cập nhật danh sách tập tin
 * @property {Function} updateKnowledgeBases - Cập nhật danh sách cơ sở kiến thức
 * @property {Function} updateMcps - cập nhật MCP danh sách
 * @property {Function} getFilteredItems - Nhận danh sách ứng viên được lọc dựa trên truy vấn
 */

/**
 * Mention @đề cập đến Quản lý chức năng
 * @returns {UseMentionReturn}
 */
export function useMention() {
  const mentionConfig = ref({
    files: [],
    knowledgeBases: [],
    mcps: []
  })

  /**
   * thiết lập hoàn thành mention Cấu hình
   * @param {MentionConfig} config
   */
  const setMention = (config) => {
    mentionConfig.value = {
      files: config.files || [],
      knowledgeBases: config.knowledgeBases || [],
      mcps: config.mcps || []
    }
  }

  /**
   * Cập nhật danh sách tập tin
   * @param {MentionFile[]} files
   */
  const updateFiles = (files) => {
    mentionConfig.value.files = files || []
  }

  /**
   * Cập nhật danh sách cơ sở kiến thức
   * @param {MentionKnowledgeBase[]} knowledgeBases
   */
  const updateKnowledgeBases = (knowledgeBases) => {
    mentionConfig.value.knowledgeBases = knowledgeBases || []
  }

  /**
   * cập nhật MCP Danh sách máy chủ
   * @param {MentionMcp[]} mcps
   */
  const updateMcps = (mcps) => {
    mentionConfig.value.mcps = mcps || []
  }

  /**
   * Nhận tất cả các ứng viên sau khi phân loại
   * @returns {{ files: MentionItem[], knowledgeBases: MentionItem[], mcps: MentionItem[] }}
   */
  const getCategorizedItems = () => {
    const { files, knowledgeBases, mcps } = mentionConfig.value

    const fileItems = files.map((f) => ({
      value: f.path,
      label: f.path.split('/').pop() || f.path,
      type: 'file',
      description: f.path
    }))

    const kbItems = knowledgeBases.map((kb) => ({
      value: kb.kb_id,
      label: kb.name,
      type: 'knowledge',
      description: kb.kb_id
    }))

    const mcpItems = mcps.map((m) => ({
      value: m.slug,
      label: m.name,
      type: 'mcp',
      description: m.description || ''
    }))

    return {
      files: fileItems,
      knowledgeBases: kbItems,
      mcps: mcpItems
    }
  }

  /**
   * Lọc ứng viên dựa trên chuỗi truy vấn
   * @param {string} query - chuỗi truy vấn（Không chứa @ biểu tượng）
   * @returns {{ files: MentionItem[], knowledgeBases: MentionItem[], mcps: MentionItem[] }}
   */
  const getFilteredItems = (query = '') => {
    const lowerQuery = query.toLowerCase()
    const categorized = getCategorizedItems()

    const filterItems = (items) =>
      items.filter(
        (item) =>
          item.label.toLowerCase().includes(lowerQuery) ||
          item.value.toLowerCase().includes(lowerQuery)
      )

    return {
      files: filterItems(categorized.files),
      knowledgeBases: filterItems(categorized.knowledgeBases),
      mcps: filterItems(categorized.mcps)
    }
  }

  return {
    mentionConfig,
    setMention,
    updateFiles,
    updateKnowledgeBases,
    updateMcps,
    getFilteredItems,
    getCategorizedItems
  }
}
