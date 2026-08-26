function normalizeLineEndings(value) {
  return String(value ?? '').replace(/\r\n?/g, '\n')
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function findExactRanges(documentText, selectedText) {
  const ranges = []
  let start = 0

  while (true) {
    const index = documentText.indexOf(selectedText, start)
    if (index < 0) return ranges

    ranges.push({ start: index, end: index + selectedText.length })
    // 逐字符前进，连重叠候选也要视为歧义，不能漏掉第二个可能位置。
    start = index + 1
  }
}

/**
 * 编辑器显示的是纯文本，而文章保存的是 Markdown。普通段落通常可以直接
 * 字符串匹配；当编辑器把跨段选区的换行折叠成不同数量的空白时，再使用一个
 * 仅允许空白差异的保守匹配。不会做模糊相似度搜索，也不会在多个候选中猜一个。
 */
function findWhitespaceEquivalentRanges(documentText, selectedText) {
  const normalizedSelection = selectedText.replace(/\s+/g, ' ').trim()
  if (!normalizedSelection) return []

  const tokens = normalizedSelection.split(' ').filter(Boolean)
  if (tokens.length === 0) return []

  const pattern = tokens.map(escapeRegExp).join('\\s+')
  // 用零宽前瞻发现重叠候选；普通全局匹配会跳过第二个重叠位置，
  // 在安全替换场景下那会错误地把“多处可能命中”当成唯一命中。
  const matcher = new RegExp(`(?=(${pattern}))`, 'gu')
  return [...documentText.matchAll(matcher)].map(match => ({
    start: match.index,
    end: match.index + match[1].length,
  }))
}

function getProtectedMarkdownRanges(documentText) {
  const ranges = []

  // 选区来自编辑器的可见文字，不能因为同样的文字恰好出现在链接地址、
  // 图片语法或 HTML 属性中，就把这些用户未选中的 Markdown 元数据替换掉。
  const inlineLinkPattern = /!?\[[^\]]*\]\([^\n)]*\)/gu
  for (const match of documentText.matchAll(inlineLinkPattern)) {
    const start = match.index ?? 0
    const end = start + match[0].length
    if (match[0].startsWith('!')) {
      ranges.push({ start, end })
      continue
    }

    const urlOffset = match[0].indexOf('](')
    if (urlOffset >= 0) {
      ranges.push({
        start: start + urlOffset + 2,
        end: end - 1,
      })
    }
  }

  const htmlPattern = /<[^\n>]+>/gu
  for (const match of documentText.matchAll(htmlPattern)) {
    const start = match.index ?? 0
    ranges.push({ start, end: start + match[0].length })
  }

  return ranges
}

function filterProtectedRanges(ranges, documentText) {
  const protectedRanges = getProtectedMarkdownRanges(documentText)
  if (protectedRanges.length === 0) return ranges

  return ranges.filter(({ start, end }) => !protectedRanges.some(protectedRange => (
    start < protectedRange.end && end > protectedRange.start
  )))
}

/**
 * 在一份文章快照中安全替换选区。
 *
 * 只有选区文本恰好出现一次（或仅存在确定的空白差异）时才返回新文章；
 * 找不到或出现重复候选时一律拒绝，调用方不得用模糊匹配覆盖正文。
 */
export function replaceUniqueTextFragment(
  documentMarkdown,
  selectedText,
  replacementMarkdown,
) {
  const documentText = normalizeLineEndings(documentMarkdown)
  const selectionText = normalizeLineEndings(selectedText)
  const replacementText = normalizeLineEndings(replacementMarkdown)

  if (!selectionText.trim()) {
    return {
      ok: false,
      reason: '原选区为空，未应用后台修改；请重新选择正文内容',
    }
  }

  let ranges = filterProtectedRanges(
    findExactRanges(documentText, selectionText),
    documentText,
  )
  if (ranges.length === 0) {
    ranges = filterProtectedRanges(
      findWhitespaceEquivalentRanges(documentText, selectionText),
      documentText,
    )
  }

  if (ranges.length === 0) {
    return {
      ok: false,
      reason: '原文章内容已无法定位选区，未应用后台修改；请重新选择最新内容',
    }
  }

  if (ranges.length > 1) {
    return {
      ok: false,
      reason: '选区文字在原文章中出现多次，无法安全判断位置；未应用后台修改',
    }
  }

  const [{ start, end }] = ranges
  return {
    ok: true,
    start,
    end,
    matchedText: documentText.slice(start, end),
    content: documentText.slice(0, start) + replacementText + documentText.slice(end),
  }
}

export function sameArticleSnapshot(left, right) {
  return normalizeLineEndings(left) === normalizeLineEndings(right)
}
