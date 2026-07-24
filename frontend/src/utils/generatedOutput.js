const ARTICLE_MARKER = '---ARTICLE---'
const SUMMARY_MARKER = '---SUMMARY---'

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

  return articleText.trimStart()
}

export function parseGeneratedOutput(output, fallbackSummary = '已生成文章') {
  const articleMatch = output.match(/---ARTICLE---\s*([\s\S]*?)(?=---SUMMARY---|$)/)
  const summaryMatch = output.match(/---SUMMARY---\s*([\s\S]*?)$/)

  return {
    articleContent: (articleMatch ? articleMatch[1] : output).trim(),
    summaryContent: (summaryMatch ? summaryMatch[1] : fallbackSummary).trim() || fallbackSummary,
  }
}

export function parseSelectionEditOutput(output, fallbackSummary = '已完成选区修改') {
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
  const isDeletion = rawReplacement.length === 0 || rawReplacement === deletionMarker
  const replacementMarkdown = isDeletion ? '' : rawReplacement

  if (replacementMarkdown.includes('---ARTICLE---')) {
    throw new Error('AI 错误返回了整篇文章，已拒绝覆盖编辑器内容')
  }

  return {
    replacementMarkdown,
    summaryContent,
    isDeletion,
  }
}

export function appendKnowledgeSources(summary, references = []) {
  const uniqueReferences = [...new Set(
    references.filter(Boolean).map(reference => String(reference).trim()).filter(Boolean)
  )]
  if (uniqueReferences.length === 0) return summary

  const sourceLines = uniqueReferences.map(reference => `- ${reference}`).join('\n')
  return `${summary.trim()}\n\n知识库来源：\n${sourceLines}`
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
    } catch (error) {
      console.error('Parse error:', error)
    }
  }

  return { buffer: nextBuffer, output: nextOutput, metadata: nextMetadata }
}
