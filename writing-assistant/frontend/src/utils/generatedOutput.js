const ARTICLE_MARKER = '---ARTICLE---'
const SUMMARY_MARKER = '---SUMMARY---'
// 只在行首识别列表编号；允许模型漏掉编号后的空格，但不把 1.5、2026.08
// 这类数字写法误当成公文分点。
const NUMBERED_MARKER_RE = /^\s*(\d{1,2})[.)](?:\s+|(?=[^\d\s]))(.+)$/
const UNORDERED_MARKER_RE = /^(\s*)([*+-])\s+(.+)$/

function chineseOrdinal(number) {
  const digits = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']
  if (number <= 10) return number === 10 ? '十' : digits[number]
  if (number < 20) return `十${digits[number - 10]}`
  if (number % 10 === 0) return `${digits[Math.floor(number / 10)]}十`
  return `${digits[Math.floor(number / 10)]}十${digits[number % 10]}`
}

function isBlankLine(line) {
  return !String(line || '').trim()
}

function countTopLevelBullets(lines, start) {
  let count = 0
  for (let index = start; index < lines.length; index += 1) {
    const line = lines[index]
    if (isBlankLine(line)) break
    const match = line.match(UNORDERED_MARKER_RE)
    if (!match) {
      if (/^\s+/.test(line)) continue
      break
    }
    if (match[1].length === 0) count += 1
  }
  return count
}

/**
 * 把模型偶尔输出的 Markdown 项目符号收敛为公文段落/平级编号。
 *
 * 正式公文仍允许“一、”“二、”“1、”以及制度中的“（一）”，因此这里只
 * 处理 Markdown 的 `*`、`-`、`+` 和 `1.`/`1)`。嵌套无序项并入所属
 * 段落，不删除任何正文文字，也不触碰加粗语法中的星号。
 */
export function normalizeOfficialArticleFormat(article) {
  if (!article) return ''

  const lines = String(article).replace(/\r\n?/g, '\n').split('\n')
  const normalized = []
  let topLevelBulletIndex = 0
  let inTopLevelBulletBlock = false

  lines.forEach((line, index) => {
    const numbered = line.match(NUMBERED_MARKER_RE)
    if (numbered) {
      topLevelBulletIndex = 0
      inTopLevelBulletBlock = false
      normalized.push(`${line.slice(0, line.length - numbered[0].length)}${numbered[1]}、${numbered[2]}`)
      return
    }

    const bullet = line.match(UNORDERED_MARKER_RE)
    if (!bullet) {
      if (isBlankLine(line)) {
        topLevelBulletIndex = 0
        inTopLevelBulletBlock = false
      }
      normalized.push(line)
      return
    }

    const indent = bullet[1].length
    const content = bullet[3].trim()
    if (!content) return

    if (indent > 0 && normalized.length > 0) {
      // 子项目是对上一段的解释，不再保留一个会被编辑器渲染成圆点的块。
      const previousIndex = normalized.length - 1
      const previous = normalized[previousIndex].trimEnd()
      if (previous && !isBlankLine(previous)) {
        normalized[previousIndex] = `${previous} ${content}`
        return
      }
    }

    const blockSize = countTopLevelBullets(lines, index)
    if (indent === 0 && (blockSize > 1 || inTopLevelBulletBlock)) {
      topLevelBulletIndex += 1
      inTopLevelBulletBlock = true
      normalized.push(`${chineseOrdinal(topLevelBulletIndex)}、${content}`)
    } else {
      topLevelBulletIndex = inTopLevelBulletBlock ? topLevelBulletIndex + 1 : 0
      normalized.push(content)
    }
  })

  return normalized.join('\n')
}

export function extractArticlePreview(output) {
  if (!output) return ''

  const trimmedStart = output.trimStart()
  if (ARTICLE_MARKER.startsWith(trimmedStart) && trimmedStart.length < ARTICLE_MARKER.length) {
    return ''
  }

  const articleIndex = output.indexOf(ARTICLE_MARKER)
  let articleText = articleIndex >= 0
    ? output.slice(articleIndex + ARTICLE_MARKER.length)
    : output

  const summaryIndex = articleText.indexOf(SUMMARY_MARKER)
  if (summaryIndex >= 0) {
    articleText = articleText.slice(0, summaryIndex)
  }

  // 流式预览也经过同一套格式收敛，避免用户在生成尚未结束时先看到圆点列表，
  // 生成结束后再突然改变版式。
  return normalizeOfficialArticleFormat(articleText.trimStart())
}

export function parseGeneratedOutput(output, fallbackSummary = '已生成文章') {
  const articleMatch = output.match(/---ARTICLE---\s*([\s\S]*?)(?=---SUMMARY---|$)/)
  const summaryMatch = output.match(/---SUMMARY---\s*([\s\S]*?)$/)

  return {
    articleContent: normalizeOfficialArticleFormat(
      (articleMatch ? articleMatch[1] : output).trim(),
    ),
    summaryContent: (summaryMatch ? summaryMatch[1] : fallbackSummary).trim() || fallbackSummary,
  }
}

function normalizeBoundaryLine(value) {
  return String(value || '')
    .trim()
    .replace(/^#{1,6}\s+/, '')
    .replace(/^(?:[-+*]|\d+[.)])\s+/, '')
    .replace(/\s+/g, ' ')
}

function meaningfulLines(value) {
  return String(value || '')
    .split(/\r?\n/)
    .map(normalizeBoundaryLine)
    .filter(line => line.length >= 4)
}

function numberedHeadingOrdinal(value) {
  return normalizeBoundaryLine(value).match(/^([一二三四五六七八九十百]+)、/)?.[1] || ''
}

function assertReplacementDoesNotCopyReadOnlyContext(
  replacement,
  { selectedMarkdown = '', contextBefore = '', contextAfter = '' } = {},
) {
  if (!replacement) return

  const replacementLines = meaningfulLines(replacement)
  if (replacementLines.length === 0) return

  const selectedLines = new Set(meaningfulLines(selectedMarkdown))
  const selectedHeadingOrdinals = new Set(
    meaningfulLines(selectedMarkdown).map(numberedHeadingOrdinal).filter(Boolean)
  )
  const firstReplacementLine = replacementLines[0]
  const lastReplacementLine = replacementLines.at(-1)
  const beforeCandidates = meaningfulLines(contextBefore).slice(-3)
  const afterCandidates = meaningfulLines(contextAfter).slice(0, 3)

  const copiedBefore = beforeCandidates.find(line => (
    line === firstReplacementLine && !selectedLines.has(line)
  ))
  if (copiedBefore) {
    throw new Error(`AI 返回内容重复了选区外的前文“${copiedBefore}”，已拒绝应用`)
  }

  const replacementHeadingOrdinal = numberedHeadingOrdinal(firstReplacementLine)
  const copiedHeadingOrdinal = beforeCandidates.find(line => (
    replacementHeadingOrdinal &&
    numberedHeadingOrdinal(line) === replacementHeadingOrdinal &&
    !selectedHeadingOrdinals.has(replacementHeadingOrdinal)
  ))
  if (copiedHeadingOrdinal) {
    throw new Error(`AI 返回内容重复生成了选区外的第“${replacementHeadingOrdinal}”项标题，已拒绝应用`)
  }

  const copiedAfter = afterCandidates.find(line => (
    line === lastReplacementLine && !selectedLines.has(line)
  ))
  if (copiedAfter) {
    throw new Error(`AI 返回内容重复了选区外的后文“${copiedAfter}”，已拒绝应用`)
  }
}

export function parseSelectionEditOutput(
  output,
  fallbackSummary = '已完成选区修改',
  selectionBoundary = {},
) {
  const replacementMarker = '---REPLACEMENT---'
  const summaryMarker = '---SUMMARY---'
  const deletionMarker = '[[DELETE_SELECTION]]'
  const replacementIndex = output.indexOf(replacementMarker)
  const summaryIndex = output.indexOf(summaryMarker)

  if (replacementIndex < 0 || summaryIndex < 0 || summaryIndex < replacementIndex) {
    throw new Error('AI 返回格式异常，未获得可安全应用的选区替换内容')
  }

  const rawReplacement = output
    .slice(replacementIndex + replacementMarker.length, summaryIndex)
    .trim()
  const summaryContent = output.slice(summaryIndex + summaryMarker.length).trim() || fallbackSummary
  if (!rawReplacement) {
    throw new Error('AI 返回的选区替换内容为空，且未使用明确的删除标记；已拒绝应用')
  }
  if (rawReplacement.includes(deletionMarker) && rawReplacement !== deletionMarker) {
    throw new Error('AI 返回的删除标记格式异常，已拒绝应用')
  }

  const isDeletion = rawReplacement === deletionMarker
  const replacementMarkdown = isDeletion ? '' : rawReplacement

  if (replacementMarkdown.includes('---ARTICLE---')) {
    throw new Error('AI 错误返回了整篇文章，已拒绝覆盖编辑器内容')
  }

  assertReplacementDoesNotCopyReadOnlyContext(replacementMarkdown, selectionBoundary)

  return {
    replacementMarkdown,
    summaryContent,
    isDeletion,
  }
}

export function sortKnowledgeReferences(references = []) {
  const uniqueReferences = [...new Set(
    references.filter(Boolean).map(reference => String(reference).trim()).filter(Boolean)
  )]

  return uniqueReferences
    .map((reference, index) => ({
      reference,
      index,
      number: reference.match(/^\s*(?:[-*+]\s+)?\[(\d+)\]/)?.[1],
    }))
    .sort((left, right) => {
      if (left.number && right.number) {
        const difference = Number(left.number) - Number(right.number)
        return difference || left.index - right.index
      }
      if (left.number) return -1
      if (right.number) return 1
      return left.index - right.index
    })
    .map(item => item.reference)
}

export function appendKnowledgeSources(summary, references = []) {
  const sortedReferences = sortKnowledgeReferences(references)
  if (sortedReferences.length === 0) return summary

  const sourceLines = sortedReferences.map(reference => `- ${reference}`).join('\n')
  return `${summary.trim()}\n\n知识库来源：\n${sourceLines}`
}

/** 重新打开历史会话时，也把已经保存的来源段落按编号整理。 */
export function normalizeKnowledgeSourcesInMessage(message) {
  const text = String(message || '')
  const marker = '知识库来源：'
  const markerIndex = text.indexOf(marker)
  if (markerIndex < 0) return message

  const summary = text.slice(0, markerIndex).trim()
  const sourceLines = text
    .slice(markerIndex + marker.length)
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean)
    .map(line => line.replace(/^[-*+]\s+/, '').trim())
  const sortedReferences = sortKnowledgeReferences(sourceLines)
  if (sortedReferences.length === 0) return message

  return `${summary}\n\n${marker}\n${sortedReferences.map(reference => `- ${reference}`).join('\n')}`
}

export function appendSseChunk(
  buffer,
  output,
  value,
  decoder = new TextDecoder('utf-8'),
  metadata = {},
) {
  let nextBuffer = buffer + decoder.decode(value, { stream: true })
  let nextOutput = output
  let nextMetadata = metadata

  const events = nextBuffer.split('\n\n')
  nextBuffer = events.pop() || ''

  for (const event of events) {
    if (!event.startsWith('data:')) continue

    try {
      const dataStr = event.slice(5).trim()
      if (!dataStr) continue

      const data = JSON.parse(dataStr)
      if (data.content) {
        nextOutput += data.content
      }
      if (data.rag) {
        nextMetadata = { ...nextMetadata, rag: data.rag }
      }
      if (data.finish) {
        nextMetadata = { ...nextMetadata, finish: true }
      }
    } catch (error) {
      console.error('Parse error:', error)
    }
  }

  return { buffer: nextBuffer, output: nextOutput, metadata: nextMetadata }
}
