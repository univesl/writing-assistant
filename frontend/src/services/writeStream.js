import {
  appendSseChunk,
  extractArticlePreview,
  parseGeneratedOutput,
  parseSelectionEditOutput,
} from '../utils/generatedOutput'

export async function streamQuickWrite({
  payload,
  signal,
  timeoutMs = 120000,
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
    let metadata = {}

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const parsed = appendSseChunk(buffer, output, value, decoder, metadata)
      buffer = parsed.buffer
      output = parsed.output
      metadata = parsed.metadata

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
      metadata,
      rag: metadata.rag,
      ...parseGeneratedOutput(output, fallbackSummary),
    }
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('AI 生成超过2分钟，已停止等待，请重试')
    }
    throw error
  } finally {
    if (timeoutId) clearTimeout(timeoutId)
  }
}

export async function streamSelectionEdit({
  payload,
  signal,
  timeoutMs = 120000,
  fallbackSummary = '已完成选区修改',
}) {
  const controller = !signal && timeoutMs ? new AbortController() : null
  const timeoutId = controller ? setTimeout(() => controller.abort(), timeoutMs) : null

  try {
    const response = await fetch('/api/write/edit-selection', {
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
    }

    if (!output.trim() || output.trimStart().startsWith('生成失败：')) {
      throw new Error(output.trim() || 'AI 未返回可用内容')
    }

    return {
      output,
      ...parseSelectionEditOutput(output, fallbackSummary, {
        selectedMarkdown: payload.selected_markdown,
        contextBefore: payload.context_before,
        contextAfter: payload.context_after,
      }),
    }
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('AI 修改超过2分钟，已停止等待，请重试')
    }
    throw error
  } finally {
    if (timeoutId) clearTimeout(timeoutId)
  }
}

/**
 * 多文件参考写作使用 fetch 直接上传 FormData；这里补上和其他生成路径一致的
 * 两分钟上限，并把流读取封装起来，避免某个后台会话无限占用任务槽。
 */
export async function streamReferenceWriteFiles({
  formData,
  timeoutMs = 120000,
  onArticle,
}) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch('/api/generate/reference-write-files', {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    })

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => null)
      throw new Error(errorPayload?.detail || errorPayload?.msg || `请求失败: ${response.status}`)
    }
    if (!response.body?.getReader) {
      const text = await response.text()
      throw new Error(text || '响应格式错误')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let fullContent = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      fullContent += decoder.decode(value, { stream: true })
      const liveArticle = extractArticlePreview(fullContent)
      if (liveArticle) onArticle?.(liveArticle, fullContent)
    }

    fullContent += decoder.decode()
    return fullContent
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('参考写作超过2分钟，已停止等待，请重试')
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}
