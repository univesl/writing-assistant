const TERMINAL_EVENTS = new Set(['run.completed', 'run.failed', 'run.cancelled'])

function normalizeStreamingHeadings(markdown) {
  let titleSeen = false
  return String(markdown || '').split('\n').map((line) => {
    const match = line.match(/^(#{1,6})\s+(.+?)\s*$/)
    if (!match) return line
    const text = match[2]
    if (match[1].length === 1 && !titleSeen) {
      titleSeen = true
      return `# ${text}`
    }
    if (match[1].length === 1 && /^一、/.test(text)) return `## ${text}`
    if (match[1].length === 1 && /^（[一二三四五六七八九十百]+）/.test(text)) return `### ${text}`
    if (match[1].length === 1 && /^(?:\d+|[一二三四五六七八九十百]+)[.、]\s*/.test(text)) return `#### ${text}`
    return line
  }).join('\n')
}

export function parseSseFrame(frame) {
  let id = null
  let event = 'message'
  const data = []
  for (const line of frame.replaceAll('\r\n', '\n').split('\n')) {
    if (!line || line.startsWith(':')) continue
    const separator = line.indexOf(':')
    const field = separator === -1 ? line : line.slice(0, separator)
    const value = separator === -1 ? '' : line.slice(separator + 1).replace(/^ /, '')
    if (field === 'id') id = Number(value)
    if (field === 'event') event = value
    if (field === 'data') data.push(value)
  }
  if (!data.length) return null
  return { id, event, data: JSON.parse(data.join('\n')) }
}

export async function streamAgentRun({
  runId,
  after = 0,
  initialArticle = '',
  signal,
  onEvent,
  onArticle,
  batchMs = 180,
}) {
  let cursor = after
  let article = initialArticle
  let pendingArticle = null
  let flushTimer = null
  let retries = 0

  const flush = () => {
    if (flushTimer) clearTimeout(flushTimer)
    flushTimer = null
    if (pendingArticle !== null) {
      onArticle?.(pendingArticle)
      pendingArticle = null
    }
  }
  const queueArticle = () => {
    pendingArticle = normalizeStreamingHeadings(article)
    if (!flushTimer) flushTimer = setTimeout(flush, batchMs)
  }

  try {
    while (!signal?.aborted) {
      const response = await fetch(
        `/api/agent/runs/${encodeURIComponent(runId)}/events?after=${cursor}`,
        { headers: { Accept: 'text/event-stream', 'Last-Event-ID': String(cursor) }, signal },
      )
      if (!response.ok || !response.body) {
        throw new Error(`事件流连接失败（${response.status}）`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let terminal = false
      let endedCleanly = false
      while (!terminal) {
        const { value, done } = await reader.read()
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
        const frames = buffer.replaceAll('\r\n', '\n').split('\n\n')
        buffer = frames.pop() || ''
        for (const rawFrame of frames) {
          const parsed = parseSseFrame(rawFrame)
          if (!parsed) continue
          cursor = Math.max(cursor, parsed.id || 0)
          const publicEvent = parsed.data
          if (publicEvent.type === 'content.delta') {
            const delta = publicEvent.data || {}
            article = delta.mode === 'replace' ? (delta.content || '') : article + (delta.content || '')
            queueArticle()
          } else if (publicEvent.type === 'run.completed') {
            article = publicEvent.data?.article || article
            pendingArticle = article
            flush()
          }
          onEvent?.(publicEvent)
          terminal = TERMINAL_EVENTS.has(publicEvent.type)
        }
        if (done) {
          endedCleanly = true
          break
        }
      }
      flush()
      if (terminal || signal?.aborted) return { cursor, article }
      if (buffer.trim()) {
        const parsed = parseSseFrame(buffer)
        if (parsed) onEvent?.(parsed.data)
      }
      if (endedCleanly) {
        const snapshotResponse = await fetch(`/api/agent/runs/${encodeURIComponent(runId)}`, { signal })
        if (snapshotResponse.ok) {
          const snapshot = await snapshotResponse.json()
          if (['completed', 'failed', 'cancelled', 'interrupted'].includes(snapshot.status)) {
            return { cursor, article }
          }
        }
      }
      if (++retries > 5) throw new Error('事件流多次断开，请刷新后恢复')
      await new Promise(resolve => setTimeout(resolve, Math.min(500 * retries, 2000)))
    }
    return { cursor, article }
  } finally {
    flush()
  }
}
