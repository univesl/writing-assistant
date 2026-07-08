import { appendSseChunk, extractArticlePreview, parseGeneratedOutput } from '../utils/generatedOutput'

export async function streamQuickWrite({
  payload,
  signal,
  timeoutMs,
  fallbackSummary = '已完成',
  onArticle,
  requireArticleMarker = false,
}) {
  const controller = !signal && timeoutMs ? new AbortController() : null
  const timeoutId = controller ? setTimeout(() => controller.abort(), timeoutMs) : null

  try {
    const response = await fetch('/api/write/quick', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: signal || controller?.signal,
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      throw new Error(`请求失败: ${response.status}`)
    }

    if (!response.body?.getReader) {
      throw new Error('浏览器不支持流式读取响应')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let output = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const parsed = appendSseChunk(buffer, output, value, decoder)
      buffer = parsed.buffer
      output = parsed.output

      if (onArticle) {
        const liveArticle = extractArticlePreview(output)
        if (liveArticle) onArticle(liveArticle, output)
      }
    }

    if (!output.trim()) {
      throw new Error('AI 未返回可用内容')
    }

    if (requireArticleMarker && !output.includes('---ARTICLE---')) {
      throw new Error('AI 返回格式异常，未覆盖正文')
    }

    return {
      output,
      ...parseGeneratedOutput(output, fallbackSummary),
    }
  } finally {
    if (timeoutId) clearTimeout(timeoutId)
  }
}
