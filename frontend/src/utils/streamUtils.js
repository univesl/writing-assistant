/**
 * 流式 SSE 解析通用工具
 *
 * 用于处理 /api/write/quick 返回的 text/event-stream 流式响应
 * 格式：data: {"content": "...", "finish": false}\n\n
 */

/**
 * 解析 SSE chunk，返回解析出的事件列表
 */
export function parseSSEBuffer(buffer) {
  const events = buffer.split('\n\n')
  const complete = events.slice(0, -1)
  const remainder = events[events.length - 1] || ''
  const results = []
  for (const event of complete) {
    if (event.startsWith('data:')) {
      try {
        const data = JSON.parse(event.slice(5).trim())
        results.push(data)
      } catch (e) {
        // 跳过解析失败的 chunk
      }
    }
  }
  return { results, remainder }
}

/**
 * 从 LLM 返回的完整文本中提取文章正文和摘要
 * 格式：
 *   ---ARTICLE---
 *   [文章正文]
 *   ---SUMMARY---
 *   [摘要]
 */
export function extractArticleAndSummary(fullText) {
  let articleContent = fullText
  let summaryContent = ''

  const articleMatch = fullText.match(/---ARTICLE---\n?([\s\S]*?)(?=---SUMMARY---|$)/)
  const summaryMatch = fullText.match(/---SUMMARY---\n?([\s\S]*?)$/)

  if (articleMatch) {
    articleContent = articleMatch[1].trim()
  }
  if (summaryMatch) {
    summaryContent = summaryMatch[1].trim()
  }

  return { articleContent, summaryContent }
}