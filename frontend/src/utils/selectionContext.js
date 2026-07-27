const NEIGHBOR_BLOCK_COUNT = 2
const CONTEXT_SIDE_CHAR_LIMIT = 3000
const DOCUMENT_TITLE_CHAR_LIMIT = 300
const SECTION_PATH_CHAR_LIMIT = 800
const EDITABLE_BLOCK_TYPES = new Set(['heading', 'paragraph', 'quote', 'listitem'])

/**
 * 保存工具栏 pointerdown 时取得的精确选区，并在后续 click 中只消费一次。
 * `null` 也是一次有效的捕获结果，不能在 click 阶段再次读取已经消失的选区。
 */
export function createPreparedSelectionStore() {
  let hasPreparedSelection = false
  let preparedSelection = null

  return {
    prepare(capture) {
      preparedSelection = capture?.() ?? null
      hasPreparedSelection = true
      return preparedSelection
    },

    consume(capture) {
      const selected = hasPreparedSelection
        ? preparedSelection
        : (capture?.() ?? null)
      hasPreparedSelection = false
      preparedSelection = null
      return selected
    },

    clear() {
      hasPreparedSelection = false
      preparedSelection = null
    },

    hasPrepared() {
      return hasPreparedSelection
    },
  }
}

function normalizeContextText(value) {
  return String(value || '')
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function limitContextStart(value, maxLength) {
  const normalized = normalizeContextText(value)
  if (normalized.length <= maxLength) return normalized
  return `${normalized.slice(0, maxLength - 1).trimEnd()}…`
}

function limitContextEnd(value, maxLength) {
  const normalized = normalizeContextText(value)
  if (normalized.length <= maxLength) return normalized
  return `…${normalized.slice(-(maxLength - 1)).trimStart()}`
}

function getHeadingLevel(node) {
  if (node?.getType?.() !== 'heading') return null

  const tag = node.getTag?.()
  const level = Number.parseInt(String(tag || '').replace(/^h/, ''), 10)
  return Number.isInteger(level) && level >= 1 && level <= 6 ? level : null
}

function formatContextBlock(node) {
  const text = normalizeContextText(node?.getTextContent?.())
  if (!text) return ''

  const headingLevel = getHeadingLevel(node)
  if (headingLevel) {
    return `${'#'.repeat(headingLevel)} ${text}`
  }

  const type = node?.getType?.()
  if (type === 'list') return `【列表】\n${text}`
  if (type === 'quote') return `【引用】\n${text}`
  if (type === 'table') return `【表格】\n${text}`
  return text
}

function getTopLevelBlockForPoint(point, root, preferPrevious) {
  const pointNode = point.getNode()
  if (pointNode.is(root)) {
    const childCount = root.getChildrenSize()
    if (childCount === 0) return null

    const rawIndex = preferPrevious ? point.offset - 1 : point.offset
    const childIndex = Math.max(0, Math.min(rawIndex, childCount - 1))
    return root.getChildAtIndex(childIndex)
  }

  let current = pointNode
  let parent = current.getParent()
  while (parent && !parent.is(root)) {
    current = parent
    parent = current.getParent()
  }
  return parent?.is(root) ? current : null
}

function getEditableBlockForPoint(point, root) {
  let current = point.getNode()
  while (current && !current.is(root)) {
    if (EDITABLE_BLOCK_TYPES.has(current.getType?.())) return current
    current = current.getParent?.()
  }
  return null
}

function setPoint(target, source) {
  target.set(source.key, source.offset, source.type)
}

function getBlockBoundaryPoint(block, atEnd) {
  const textNodes = block?.getAllTextNodes?.() || []
  const textNode = atEnd ? textNodes.at(-1) : textNodes[0]
  if (textNode) {
    return {
      key: textNode.getKey(),
      offset: atEnd ? textNode.getTextContentSize() : 0,
      type: 'text',
    }
  }

  return {
    key: block.getKey(),
    offset: atEnd ? (block.getChildrenSize?.() || 0) : 0,
    type: 'element',
  }
}

function getRangeText(selection, startPoint, endPoint) {
  const contextRange = selection.clone()
  setPoint(contextRange.anchor, startPoint)
  setPoint(contextRange.focus, endPoint)
  return normalizeContextText(contextRange.getTextContent())
}

function getDocumentTitle(children) {
  const titleNode = children.find(node => getHeadingLevel(node) === 1)
  return limitContextStart(titleNode?.getTextContent?.(), DOCUMENT_TITLE_CHAR_LIMIT)
}

function getSectionPath(children, selectionStartIndex) {
  const headingPath = []

  for (let index = 0; index <= selectionStartIndex; index += 1) {
    const node = children[index]
    const level = getHeadingLevel(node)
    if (!level || level === 1) continue

    while (headingPath.length && headingPath.at(-1).level >= level) {
      headingPath.pop()
    }
    headingPath.push({
      level,
      text: normalizeContextText(node.getTextContent()),
    })
  }

  return limitContextEnd(
    headingPath.map(item => item.text).filter(Boolean).join(' > '),
    SECTION_PATH_CHAR_LIMIT,
  )
}

function joinContextParts(parts) {
  return parts.map(normalizeContextText).filter(Boolean).join('\n\n')
}

export function shouldUsePlainTextInsertion(replacement, isSingleBlockSelection) {
  if (!isSingleBlockSelection) return false

  const markdown = String(replacement || '')
  const hasBlockMarkdown = /(^|\n)\s{0,3}(?:#{1,6}\s|>|[-+*]\s|\d+[.)]\s|```|~~~)/m.test(markdown)
  const hasInlineMarkdown = /(\*\*|__|~~|`|!\[|\[[^\]]+\]\([^)]+\))/.test(markdown)
  const hasTableMarkdown = /^\s*\|.*\|\s*$/m.test(markdown)
  return !hasBlockMarkdown && !hasInlineMarkdown && !hasTableMarkdown
}

export function insertPlainTextSelectionReplacement(selection, replacement) {
  if (String(replacement).includes('\n')) {
    selection.insertRawText(replacement)
  } else {
    selection.insertText(replacement)
  }
}

/**
 * 浏览器原生 Selection 与 Lexical RangeSelection 会用不同数量的空格、制表符和
 * 换行表示相同的跨块选区。选区端点仍由 DOM Range 决定；这里仅比较可见字符，
 * 用于阻止缓存选区意外多带标题或漏掉正文，不把编辑器内部空白表示当作失败。
 */
export function selectionTextsMatch(nativeText, lexicalText) {
  const normalize = value => String(value ?? '')
    .replace(/[\s\u00a0\u200b\u2060\ufeff]+/gu, '')

  return normalize(nativeText) === normalize(lexicalText)
}

/**
 * 从当前 Lexical RangeSelection 的真实树位置提取只读语义上下文。
 *
 * 这里只读取标题、章节路径、相邻顶层块，以及选区所在块内紧邻选区的
 * 前后文字；不会通过全文字符串搜索选区，也不会改变编辑器当前选区。
 */
export function captureSelectionContext(selection, root) {
  if (!selection || selection.isCollapsed() || !root) return null

  const [logicalStart, logicalEnd] = selection.isBackward()
    ? [selection.focus, selection.anchor]
    : [selection.anchor, selection.focus]
  const startBlock = getTopLevelBlockForPoint(logicalStart, root, false)
  const endBlock = getTopLevelBlockForPoint(logicalEnd, root, true)
  if (!startBlock || !endBlock) return null
  const startEditableBlock = getEditableBlockForPoint(logicalStart, root)
  const endEditableBlock = getEditableBlockForPoint(logicalEnd, root)

  const children = root.getChildren()
  let startIndex = startBlock.getIndexWithinParent()
  let endIndex = endBlock.getIndexWithinParent()
  if (startIndex > endIndex) {
    ;[startIndex, endIndex] = [endIndex, startIndex]
  }

  const beforeInsideStartBlock = getRangeText(
    selection,
    getBlockBoundaryPoint(startBlock, false),
    logicalStart,
  )
  const afterInsideEndBlock = getRangeText(
    selection,
    logicalEnd,
    getBlockBoundaryPoint(endBlock, true),
  )

  const previousBlocks = children
    .slice(Math.max(0, startIndex - NEIGHBOR_BLOCK_COUNT), startIndex)
    .map(formatContextBlock)
  const nextBlocks = children
    .slice(endIndex + 1, endIndex + 1 + NEIGHBOR_BLOCK_COUNT)
    .map(formatContextBlock)

  const contextBefore = joinContextParts([
    ...previousBlocks,
    beforeInsideStartBlock,
  ])
  const contextAfter = joinContextParts([
    afterInsideEndBlock,
    ...nextBlocks,
  ])

  return {
    selectedText: selection.getTextContent(),
    isSingleBlockSelection: Boolean(
      startEditableBlock &&
      endEditableBlock &&
      startEditableBlock.is(endEditableBlock)
    ),
    requestContext: {
      document_title: getDocumentTitle(children),
      section_heading: getSectionPath(children, startIndex),
      context_before: limitContextEnd(contextBefore, CONTEXT_SIDE_CHAR_LIMIT),
      context_after: limitContextStart(contextAfter, CONTEXT_SIDE_CHAR_LIMIT),
    },
  }
}
