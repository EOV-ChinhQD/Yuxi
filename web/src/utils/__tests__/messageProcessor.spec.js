import assert from 'node:assert/strict'

import { MessageProcessor } from '../messageProcessor.js'

const databases = [
  { name: 'Thư viện tài chính và thuế' },
  { name: 'DifyKB' },
  { name: 'LightGraphKB' }
]

const run = () => {
  const conv = {
    messages: [
      {
        type: 'ai',
        tool_calls: [
          {
            name: 'Thư viện tài chính và thuế',
            tool_call_result: {
              content: JSON.stringify([
                {
                  content: 'A',
                  score: 0.9,
                  metadata: { source: 'doc-a', chunk_id: 'c1', file_id: 'f1', chunk_index: 1 }
                },
                {
                  content: 'A',
                  score: 0.8,
                  metadata: { source: 'doc-a', chunk_id: 'c1', file_id: 'f1', chunk_index: 1 }
                }
              ])
            }
          },
          {
            name: 'LightGraphKB',
            tool_call_result: {
              content: JSON.stringify({
                data: {
                  chunks: [
                    {
                      content: 'B',
                      score: 0.4,
                      metadata: { source: 'doc-b', chunk_id: 'c2', file_id: 'f2', chunk_index: 2 }
                    }
                  ]
                }
              })
            }
          },
          {
            name: 'not_kb_tool',
            tool_call_result: {
              content: JSON.stringify([{ content: 'X', score: 0.99, metadata: { chunk_id: 'cx' } }])
            }
          },
          {
            name: 'DifyKB',
            tool_call_result: { content: 'not-json' }
          }
        ]
      }
    ]
  }

  const chunks = MessageProcessor.extractKnowledgeChunksFromConversation(conv, databases)

  // 1. Milvus/Dify Trích xuất mảng
  assert.equal(
    chunks.some((c) => c.content === 'A' && c.kb_name === 'Thư viện tài chính và thuế'),
    true
  )

  // 2. Đối tượng được bọc data.chunks Trích xuất
  assert.equal(
    chunks.some((c) => c.content === 'B' && c.kb_name === 'LightGraphKB'),
    true
  )

  // 3. Bị bỏ qua bởi các công cụ cơ sở không có kiến thức
  assert.equal(
    chunks.some((c) => c.content === 'X'),
    false
  )

  // 4. bất hợp pháp JSON tự động bỏ qua
  assert.equal(
    chunks.some((c) => c.kb_name === 'DifyKB'),
    false
  )

  // 5. Việc loại bỏ trùng lặp có hiệu lực（chunk_id=c1 Chỉ có một）
  assert.equal(chunks.filter((c) => c.metadata?.chunk_id === 'c1').length, 1)

  // 6. Sắp xếp điểm（A 0.9 trong B 0.4 trước đây）
  const idxA = chunks.findIndex((c) => c.content === 'A')
  const idxB = chunks.findIndex((c) => c.content === 'B')
  assert.equal(idxA < idxB, true)

  const conversations = MessageProcessor.convertServerHistoryToMessages([
    { type: 'human', content: 'Vui lòng chọn ngôn ngữ' },
    { type: 'ai', content: 'Vui lòng chọn ngôn ngữ đầu ra' },
    {
      type: 'human',
      content: '{"language":"python"}',
      extra_metadata: { source: 'ask_user_question_resume' }
    },
    { type: 'ai', content: 'Đây là Python Phiên bản' }
  ])

  assert.equal(conversations.length, 1)
  assert.equal(conversations[0].messages.length, 3)
  assert.equal(conversations[0].messages.at(-1).content, 'Đây là Python Phiên bản')
  assert.equal(conversations[0].messages.at(-1).isLast, true)
  assert.equal(conversations[0].status, 'finished')

  const assistantBody = MessageProcessor.parseAssistantMessageBody({
    type: 'ai',
    content: '<think>quá trình suy luận</think>câu trả lời cuối cùng'
  })
  assert.deepEqual(assistantBody, {
    content: 'câu trả lời cuối cùng',
    reasoningContent: 'quá trình suy luận'
  })

  console.log('messageProcessor extractKnowledgeChunksFromConversation: all assertions passed')
}

run()
