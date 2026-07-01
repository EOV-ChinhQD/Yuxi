/**
 * Lớp công cụ xử lý tin nhắn
 */
export class MessageProcessor {
  /**
   * Hợp nhất kết quả công cụ với tin nhắn
   * @param {Array} msgs - mảng tin nhắn
   * @returns {Array} Mảng tin nhắn được hợp nhất
   */
  static convertToolResultToMessages(msgs) {
    const toolResponseMap = new Map()

    // Xây dựng bản đồ phản hồi của công cụ
    for (const item of msgs) {
      if (item.type === 'tool') {
        // Sử dụng nhiều thứ có thểIDcác trường để khớp với các lệnh gọi công cụ
        const toolCallId = item.tool_call_id || item.id
        if (toolCallId) {
          toolResponseMap.set(toolCallId, item)
        }
      }
    }

    // Hợp nhất các cuộc gọi và phản hồi của công cụ
    const convertedMsgs = msgs.map((item) => {
      if (item.type === 'ai' && item.tool_calls && item.tool_calls.length > 0) {
        return {
          ...item,
          tool_calls: item.tool_calls.map((toolCall) => {
            const toolResponse = toolResponseMap.get(toolCall.id)
            return {
              ...toolCall,
              tool_call_result: toolResponse || null
            }
          })
        }
      }
      return item
    })

    return convertedMsgs
  }

  /**
   * Chuyển đổi lịch sử máy chủ sang định dạng hội thoại
   * @param {Array} serverHistory - Lịch sử máy chủ
   * @returns {Array} mảng đối thoại
   */
  static convertServerHistoryToMessages(serverHistory) {
    // Filter out standalone 'tool' messages since tool results are already in AI messages' tool_calls
    // Backend new storage: tool results are embedded in AI messages' tool_calls array with tool_call_result field
    const filteredHistory = serverHistory.filter(
      (item) =>
        item.type !== 'tool' &&
        !(item.type === 'human' && item.extra_metadata?.source === 'ask_user_question_resume')
    )

    // Nhóm theo cuộc trò chuyện
    const conversations = []
    let currentConv = null

    for (const item of filteredHistory) {
      if (item.type === 'human') {
        // Start new conversation, finalize previous one
        if (currentConv) {
          // Find the last AI message and mark it as final
          for (let i = currentConv.messages.length - 1; i >= 0; i--) {
            if (currentConv.messages[i].type === 'ai') {
              currentConv.messages[i].isLast = true
              currentConv.status = 'finished'
              break
            }
          }
        }
        currentConv = {
          messages: [item],
          status: 'loading'
        }
        conversations.push(currentConv)
      } else if (item.type === 'ai' && currentConv) {
        currentConv.messages.push(item)
      }
    }

    // Mark the last conversation as finished
    if (currentConv && currentConv.messages.length > 0) {
      // Find the last AI message and mark it as final
      for (let i = currentConv.messages.length - 1; i >= 0; i--) {
        if (currentConv.messages[i].type === 'ai') {
          currentConv.messages[i].isLast = true
          currentConv.status = 'finished'
          break
        }
      }
    }

    return conversations
  }

  /**
   * Trích xuất tất cả các khối truy xuất cơ sở tri thức trong một vòng đối thoại
   * @param {Object} conv - cuộc trò chuyện một chiều
   * @param {Array} databases - Danh sách cơ sở kiến thức
   * @returns {Array} Khối tìm kiếm được chuẩn hóa
   */
  static extractKnowledgeChunksFromConversation(conv, databases = []) {
    if (!conv || !Array.isArray(conv.messages) || conv.messages.length === 0) return []

    const databaseNames = new Set(
      (databases || [])
        .map((db) => db?.name)
        .filter((name) => typeof name === 'string' && name.trim())
    )
    if (databaseNames.size === 0) return []

    const normalizedChunks = []
    const dedupSet = new Set()

    const appendChunk = (chunk, kbName) => {
      if (!chunk || typeof chunk !== 'object') return
      const content = typeof chunk.content === 'string' ? chunk.content.trim() : ''
      if (!content) return

      const metadata = chunk.metadata && typeof chunk.metadata === 'object' ? chunk.metadata : {}
      const dedupKey =
        metadata.chunk_id && typeof metadata.chunk_id === 'string'
          ? `${kbName}::${metadata.chunk_id}`
          : `${kbName}::${content}`
      if (dedupSet.has(dedupKey)) return
      dedupSet.add(dedupKey)

      const score = typeof chunk.score === 'number' ? chunk.score : null
      normalizedChunks.push({
        kb_name: kbName,
        content,
        score,
        metadata: {
          source: metadata.source || '',
          file_id: metadata.file_id || '',
          chunk_id: metadata.chunk_id || '',
          chunk_index: metadata.chunk_index
        }
      })
    }

    const parseToolResultContent = (content) => {
      if (Array.isArray(content)) return content
      if (content && typeof content === 'object') return content
      if (typeof content === 'string') {
        try {
          return JSON.parse(content)
        } catch {
          return null
        }
      }
      return null
    }

    for (const msg of conv.messages) {
      if (!msg || msg.type !== 'ai' || !Array.isArray(msg.tool_calls)) continue

      for (const toolCall of msg.tool_calls) {
        const kbName = toolCall?.name || toolCall?.function?.name
        if (!databaseNames.has(kbName)) continue

        const content = toolCall?.tool_call_result?.content
        const parsed = parseToolResultContent(content)
        if (!parsed) continue

        // Milvus / Dify: trực tiếp chunks mảng
        if (Array.isArray(parsed)) {
          for (const chunk of parsed) appendChunk(chunk, kbName)
          continue
        }

        const wrappedChunks = parsed?.data?.chunks
        if (Array.isArray(wrappedChunks)) {
          for (const chunk of wrappedChunks) appendChunk(chunk, kbName)
        }
      }
    }

    normalizedChunks.sort((a, b) => {
      const scoreA = typeof a.score === 'number' ? a.score : Number.NEGATIVE_INFINITY
      const scoreB = typeof b.score === 'number' ? b.score : Number.NEGATIVE_INFINITY
      return scoreB - scoreA
    })

    return normalizedChunks
  }

  /**
   * Trích xuất các nguồn tìm kiếm trên web trong cuộc trò chuyện
   * @param {Object} conv - cuộc trò chuyện một chiều
   * @returns {Array} Nguồn mạng được chuẩn hóa
   */
  static extractWebSourcesFromConversation(conv) {
    if (!conv || !Array.isArray(conv.messages) || conv.messages.length === 0) return []

    const webSources = []
    const dedupSet = new Set()

    const parseToolResultContent = (content) => {
      if (Array.isArray(content)) return content
      if (content && typeof content === 'object') return content
      if (typeof content === 'string') {
        try {
          return JSON.parse(content)
        } catch {
          return null
        }
      }
      return null
    }

    for (const msg of conv.messages) {
      if (!msg || msg.type !== 'ai' || !Array.isArray(msg.tool_calls)) continue

      for (const toolCall of msg.tool_calls) {
        const toolName = (toolCall?.name || toolCall?.function?.name || '').toLowerCase()
        if (!toolName.includes('tavily_search')) continue

        const content = toolCall?.tool_call_result?.content
        const parsed = parseToolResultContent(content)
        const results = Array.isArray(parsed?.results) ? parsed.results : []
        if (results.length === 0) continue

        for (const item of results) {
          const title = typeof item?.title === 'string' ? item.title.trim() : ''
          const url = typeof item?.url === 'string' ? item.url.trim() : ''
          if (!title || !url) continue
          if (dedupSet.has(url)) continue
          dedupSet.add(url)

          webSources.push({
            tool_name: toolCall?.name || toolCall?.function?.name || 'tìm kiếm trên mạng',
            title,
            url,
            score: typeof item?.score === 'number' ? item.score : null,
            content: typeof item?.content === 'string' ? item.content : '',
            published_date: typeof item?.published_date === 'string' ? item.published_date : ''
          })
        }
      }
    }

    webSources.sort((a, b) => {
      const scoreA = typeof a.score === 'number' ? a.score : Number.NEGATIVE_INFINITY
      const scoreB = typeof b.score === 'number' ? b.score : Number.NEGATIVE_INFINITY
      return scoreB - scoreA
    })

    return webSources
  }

  /**
   * Trích xuất nguồn từ một tin nhắn
   * @param {Object} message - đối tượng tin nhắn
   * @param {Array} databases - Danh sách cơ sở kiến thức
   * @returns {{knowledgeChunks: Array, webSources: Array}}
   */
  static extractSourcesFromMessage(message, databases = []) {
    if (!message || message.type !== 'ai') return { knowledgeChunks: [], webSources: [] }

    // Tái sử dụng logic trích xuất，Bằng cách xây dựng một đối tượng hội thoại tạm thời
    const mockConv = { messages: [message] }
    return {
      knowledgeChunks: MessageProcessor.extractKnowledgeChunksFromConversation(mockConv, databases),
      webSources: MessageProcessor.extractWebSourcesFromConversation(mockConv)
    }
  }

  /**
   * Trích xuất tất cả các nguồn trong một cuộc trò chuyện（cơ sở tri thức+tìm kiếm trên mạng）
   * @param {Object} conv - cuộc trò chuyện một chiều
   * @param {Array} databases - Danh sách cơ sở kiến thức
   * @returns {{knowledgeChunks: Array, webSources: Array}}
   */
  static extractSourcesFromConversation(conv, databases = []) {
    return {
      knowledgeChunks: MessageProcessor.extractKnowledgeChunksFromConversation(conv, databases),
      webSources: MessageProcessor.extractWebSourcesFromConversation(conv)
    }
  }

  /**
   * Phân tích văn bản tin nhắn trợ lý và nội dung lý luận，Tiếp tục hiển thị và chia tách danh sách bằng cách sử dụng cùng một bộ quy tắc。
   * @param {Object} message - AI đối tượng tin nhắn
   * @returns {{content: string, reasoningContent: string}}
   */
  static parseAssistantMessageBody(message) {
    let content = typeof message?.content === 'string' ? message.content.trim() : ''
    let reasoningContent = message?.additional_kwargs?.reasoning_content || ''

    if (!reasoningContent && content) {
      const thinkRegex = /<think>(.*?)<\/think>|<think>(.*?)$/s
      const thinkMatch = content.match(thinkRegex)

      if (thinkMatch) {
        reasoningContent = (thinkMatch[1] || thinkMatch[2] || '').trim()
        content = content.replace(thinkMatch[0], '').trim()
      }
    }

    return { content, reasoningContent }
  }

  /**
   * Hợp nhất các khối tin nhắn
   * @param {Array} chunks - mảng khối tin nhắn
   * @returns {Object|null} Tin nhắn đã hợp nhất
   */
  static mergeMessageChunk(chunks) {
    if (chunks.length === 0) return null

    // Bản sao sâu đầu tiênchunkkết quả là
    const result = JSON.parse(JSON.stringify(chunks[0]))

    // Xử lý định dạng nội dung tin nhắn của người dùng - Đảm bảo văn bản thuần túy được hiển thị
    if (result.type === 'human' || result.role === 'user') {
      // nếucontentlà một định dạng mảng（LangChainnhắn tin đa phương thức），Trích xuất phần văn bản
      if (Array.isArray(result.content)) {
        const textPart = result.content.find((item) => item.type === 'text')
        result.content = textPart ? textPart.text : ''
      } else {
        result.content = result.content || ''
      }
    } else {
      result.content = result.content || ''
    }

    // Hợp nhất theo dõichunks
    for (let i = 1; i < chunks.length; i++) {
      const chunk = chunks[i]

      // Hợp nhất nội dung
      if (chunk.content) {
        result.content += chunk.content
      }

      // hợp nhấtreasoning_content
      if (chunk.reasoning_content) {
        if (!result.reasoning_content) {
          result.reasoning_content = ''
        }
        result.reasoning_content += chunk.reasoning_content
      }

      // hợp nhấtadditional_kwargstrongreasoning_content
      if (chunk.additional_kwargs?.reasoning_content) {
        if (!result.additional_kwargs) result.additional_kwargs = {}
        if (!result.additional_kwargs.reasoning_content) {
          result.additional_kwargs.reasoning_content = ''
        }
        result.additional_kwargs.reasoning_content += chunk.additional_kwargs.reasoning_content
      }

      // hợp nhấttool_calls (Xử lý cấu trúc dữ liệu mới)
      MessageProcessor._mergeToolCalls(result, chunk)
    }

    // Quy trìnhAIMessageChunkLoại
    if (result.type === 'AIMessageChunk') {
      result.type = 'ai'
    }

    return result
  }

  /**
   * Hợp nhất các cuộc gọi công cụ
   * @private
   * @param {Object} result - đối tượng kết quả
   * @param {Object} chunk - khối hiện tại
   */
  static _mergeToolCalls(result, chunk) {
    if (chunk.tool_call_chunks && chunk.tool_call_chunks.length > 0) {
      // đảm bảo result Có tool_calls mảng
      if (!result.tool_calls) result.tool_calls = []

      for (const toolCallChunk of chunk.tool_call_chunks) {
        // sử dụng index để xác định các cuộc gọi công cụ（Bởi vì có thể có nhiều lệnh gọi công cụ）
        const existingToolCallIndex = result.tool_calls.findIndex(
          (t) => t.index === toolCallChunk.index
        )

        if (existingToolCallIndex !== -1) {
          // hợp nhất tương tựindexcủatool call
          const existingToolCall = result.tool_calls[existingToolCallIndex]

          // Cập nhật tên vàID（nếu tồn tại）
          if (toolCallChunk.name && !existingToolCall.function?.name) {
            if (!existingToolCall.function) existingToolCall.function = {}
            existingToolCall.function.name = toolCallChunk.name
          }

          if (toolCallChunk.id && !existingToolCall.id) {
            existingToolCall.id = toolCallChunk.id
          }

          // Hợp nhất các tham số
          if (toolCallChunk.args) {
            if (!existingToolCall.function) existingToolCall.function = {}
            if (!existingToolCall.function.arguments) existingToolCall.function.arguments = ''
            existingToolCall.function.arguments += toolCallChunk.args
          }
        } else {
          // thêm mớitool call
          const newToolCall = {
            index: toolCallChunk.index,
            id: toolCallChunk.id,
            function: {
              name: toolCallChunk.name || null,
              arguments: toolCallChunk.args || ''
            }
          }
          result.tool_calls.push(newToolCall)
        }
      }
    }
  }
}

export default MessageProcessor
