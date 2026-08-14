import {
  appendSseChunk,
  extractArticlePreview,
  parseGeneratedOutput,
  parseSelectionEditOutput,
} from '../utils/generatedOutput'

export const SILENT_TIMEOUT_MS = 90000
export const STAGE_ABSOLUTE_MS = 300000

const TIMEOUT_MESSAGES = {
  silent: '生成长时间无响应，已停止等待，请重试',
  absolute: '生成超过5分钟，已停止等待，请重试',
  parseAbsolute: '文件解析超过5分钟，已停止等待，请重试',
}

/**
 * 流式请求计时器：
 * - 静默超时：连续 SILENT_TIMEOUT_MS 没有任何数据才中止（防卡死，不误杀慢生成）
 * - 阶段绝对上限：STAGE_ABSOLUTE_MS（防"一直有数据但永不结束"的病态流）
 * 所有结束路径必须调用 clearAll()，保证生成结束后绝不弹出超时错误。
 */
export function createStreamGuard({ controller }) {
  let silentTimer = null
  let absoluteTimer = null
  let firedReason = null

  const clearAll = () => {
    if (silentTimer) {
      clearTimeout(silentTimer)
      silentTimer = null
    }
    if (absoluteTimer) {
      clearTimeout(absoluteTimer)
      absoluteTimer = null
    }
  }

  const fire = (reason) => {
    if (firedReason) return
    firedReason = reason
    clearAll()
    controller.abort()
  }

  return {
    startSilent() {
      if (firedReason || silentTimer) return
      silentTimer = setTimeout(() => fire('silent'), SILENT_TIMEOUT_MS)
    },
    resetSilent() {
      if (firedReason) return
      if (silentTimer) clearTimeout(silentTimer)
      silentTimer = setTimeout(() => fire('silent'), SILENT_TIMEOUT_MS)
    },
    startAbsolute() {
      if (firedReason || absoluteTimer) return
      absoluteTimer = setTimeout(() => fire('absolute'), STAGE_ABSOLUTE_MS)
    },
    clearAll,
    isFired: () => Boolean(firedReason),
    getReason: () => firedReason,
  }
}

function abortMessageFor(guard, parse = false) {
  if (!guard.isFired()) return '请求已中止，请重试'
  const reason = guard.getReason()
  if (reason === 'silent') return TIMEOUT_MESSAGES.silent
  if (reason === 'absolute') {
    return parse ? TIMEOUT_MESSAGES.parseAbsolute : TIMEOUT_MESSAGES.absolute
  }
  return '请求已中止，请重试'
}

function linkExternalSignal(controller, signal) {
  if (!signal) return
  if (signal.aborted) {
    controller.abort()
    return
  }
  signal.addEventListener('abort', () => controller.abort(), { once: true })
}

export async function streamQuickWrite({
  payload,
  signal,
  fallbackSummary = '已完成',
  onArticle,
  requireArticleMarker = false,
}) {
  const controller = new AbortController()
  const guard = createStreamGuard({ controller })
  linkExternalSignal(controller, signal)
  guard.startSilent()

  try {
    const response = await fetch('/api/write/quick', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
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

      guard.startAbsolute()
      guard.resetSilent()

      const parsed = appendSseChunk(buffer, output, value, decoder, metadata)
      buffer = parsed.buffer
      output = parsed.output
      metadata = parsed.metadata

      // finish 事件到达后立即清理计时器，绝不因收尾阶段弹错误
      if (metadata.finish) guard.clearAll()

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
      throw new Error(abortMessageFor(guard))
    }
    throw error
  } finally {
    guard.clearAll()
  }
}

export async function streamSelectionEdit({
  payload,
  signal,
  fallbackSummary = '已完成选区修改',
}) {
  const controller = new AbortController()
  const guard = createStreamGuard({ controller })
  linkExternalSignal(controller, signal)
  guard.startSilent()

  try {
    const response = await fetch('/api/write/edit-selection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
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

      guard.startAbsolute()
      guard.resetSilent()

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
      throw new Error(abortMessageFor(guard))
    }
    throw error
  } finally {
    guard.clearAll()
  }
}

/**
 * 多文件参考写作（SSE 协议）：
 * - 解析阶段：{"type":"parse","index":i,"total":n,"filename":...}（含心跳）
 * - 生成阶段：{"type":"chunk","content":...}
 * - 结束：{"type":"done"} / 失败：{"type":"error","message":...}
 * 解析阶段与生成阶段各有 5 分钟上限；生成阶段另加 90 秒静默超时。
 */
export async function streamReferenceWriteFiles({
  formData,
  onArticle,
  onParseProgress,
}) {
  const controller = new AbortController()
  const parseGuard = createStreamGuard({ controller })
  const genGuard = createStreamGuard({ controller })
  parseGuard.startAbsolute()

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
    const decoder = new TextDecoder('utf-8')
    let raw = ''
    let fullContent = ''
    let phase = 'parse'
    let finished = false

    const processFrame = (frame) => {
      const line = frame.trim()
      if (!line.startsWith('data:')) return 'continue'

      const dataStr = line.slice(5).trim()
      let event = null
      try {
        event = dataStr ? JSON.parse(dataStr) : null
      } catch (error) {
        event = null
      }
      if (!event) return 'continue'

      if (event.type === 'parse') {
        onParseProgress?.(event)
        return 'continue'
      }

      if (event.type === 'chunk') {
        if (phase === 'parse') {
          phase = 'generate'
          parseGuard.clearAll()
          genGuard.startSilent()
          genGuard.startAbsolute()
        }
        genGuard.resetSilent()
        fullContent += event.content || ''
        const liveArticle = extractArticlePreview(fullContent)
        if (liveArticle) onArticle?.(liveArticle, fullContent)
        return 'continue'
      }

      if (event.type === 'done') return 'done'
      if (event.type === 'error') return event.message || '参考材料解析失败'
      return 'continue'
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done || finished) break

      raw += decoder.decode(value, { stream: true })

      let frameEnd = raw.indexOf('\n\n')
      while (frameEnd >= 0) {
        const frame = raw.slice(0, frameEnd)
        raw = raw.slice(frameEnd + 2)

        const outcome = processFrame(frame)
        if (outcome === 'done') {
          finished = true
          parseGuard.clearAll()
          genGuard.clearAll()
          break
        }
        if (outcome !== 'continue') {
          parseGuard.clearAll()
          genGuard.clearAll()
          throw new Error(outcome)
        }

        frameEnd = raw.indexOf('\n\n')
      }
    }

    if (raw.trim() && !finished) {
      const outcome = processFrame(raw)
      if (outcome !== 'continue' && outcome !== 'done') {
        throw new Error(outcome)
      }
    }

    fullContent += decoder.decode()
    if (!fullContent.trim() || fullContent.trimStart().startsWith('生成失败：')) {
      throw new Error(fullContent.trim() || 'AI 未返回可用内容')
    }
    return fullContent
  } catch (error) {
    if (error?.name === 'AbortError') {
      if (parseGuard.isFired()) throw new Error(abortMessageFor(parseGuard, true))
      throw new Error(abortMessageFor(genGuard))
    }
    throw error
  } finally {
    parseGuard.clearAll()
    genGuard.clearAll()
  }
}
