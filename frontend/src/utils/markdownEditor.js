const ARTICLE_MARKER = '---ARTICLE---'
const SUMMARY_MARKER = '---SUMMARY---'
const ENCODED_LINE_BREAK_PATTERN = /(?:&amp;#xA;|&#xA;|&#10;|&NewLine;)/gi

export function stripGeneratedOutputMarkers(markdown) {
  if (!markdown) return ''

  const articleIndex = markdown.indexOf(ARTICLE_MARKER)
  let content = articleIndex >= 0
    ? markdown.slice(articleIndex + ARTICLE_MARKER.length)
    : markdown

  const summaryIndex = content.indexOf(SUMMARY_MARKER)
  if (summaryIndex >= 0) {
    content = content.slice(0, summaryIndex)
  }

  return content.trimStart()
}

export function normalizeMarkdownStructure(markdown) {
  const content = stripGeneratedOutputMarkers(markdown)
  if (!content) return ''

  return content
    .split('\n')
    .flatMap((line) => {
      ENCODED_LINE_BREAK_PATTERN.lastIndex = 0
      if (!/^(#{1,6})\s+/.test(line) || !ENCODED_LINE_BREAK_PATTERN.test(line)) {
        ENCODED_LINE_BREAK_PATTERN.lastIndex = 0
        return [line]
      }

      ENCODED_LINE_BREAK_PATTERN.lastIndex = 0
      const parts = line.split(ENCODED_LINE_BREAK_PATTERN)
      const heading = parts.shift()?.trimEnd() || ''
      const rest = parts.join('\n').trimStart()
      return rest ? [heading, '', ...rest.split('\n')] : [heading]
    })
    .join('\n')
}

function decodeBasicHtmlEntities(text) {
  return text
    .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCodePoint(Number.parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number.parseInt(code, 10)))
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
}

export function cleanHeadingText(text) {
  ENCODED_LINE_BREAK_PATTERN.lastIndex = 0
  const withoutEncodedBreaks = text.split(ENCODED_LINE_BREAK_PATTERN)[0]
  ENCODED_LINE_BREAK_PATTERN.lastIndex = 0

  return decodeBasicHtmlEntities(withoutEncodedBreaks)
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*\*/g, '')
    .replace(/[_`~]/g, '')
    .replace(/<[^>]*>/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}
