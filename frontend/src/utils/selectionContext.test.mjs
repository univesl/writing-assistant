import assert from 'node:assert/strict'
import {
  $createLineBreakNode,
  $createParagraphNode,
  $createRangeSelection,
  $createTextNode,
  $getRoot,
  $setSelection,
  createEditor,
} from 'lexical'
import { $createHeadingNode, HeadingNode } from '@lexical/rich-text'

import {
  captureSelectionContext,
  insertPlainTextSelectionReplacement,
  selectionTextsMatch,
  shouldUsePlainTextInsertion,
} from './selectionContext.js'

function paragraph(text) {
  return $createParagraphNode().append($createTextNode(text))
}

function heading(tag, text) {
  return $createHeadingNode(tag).append($createTextNode(text))
}

function captureFixture({ backward = false, crossBlock = false } = {}) {
  const editor = createEditor({
    namespace: `selection-context-${backward}-${crossBlock}`,
    nodes: [HeadingNode],
    onError(error) {
      throw error
    },
  })
  let result = null

  editor.update(() => {
    const root = $getRoot()
    const title = heading('h1', '关于推进专项工作的通知')
    const section = heading('h2', '二、工作要求')
    const previous = paragraph('各单位应高度重视并做好组织协调。')
    const target = paragraph('各单位要在七月三十日前提交完整材料。')
    const next = paragraph('材料应当真实准确，不得遗漏重要事项。')
    const contact = paragraph('联系人及联系方式另行通知。')
    root.clear()
    root.append(title, section, previous, target, next, contact)

    const startNode = target.getFirstChild()
    const endNode = crossBlock ? next.getFirstChild() : startNode
    const startOffset = '各单位'.length
    const endOffset = crossBlock
      ? '材料应当'.length
      : '各单位要在七月三十日前提交完整材料'.length
    const selection = $createRangeSelection()

    if (backward) {
      selection.anchor.set(endNode.getKey(), endOffset, 'text')
      selection.focus.set(startNode.getKey(), startOffset, 'text')
    } else {
      selection.anchor.set(startNode.getKey(), startOffset, 'text')
      selection.focus.set(endNode.getKey(), endOffset, 'text')
    }
    $setSelection(selection)
    result = captureSelectionContext(selection, root)
  }, { discrete: true })

  return result
}

const sameBlock = captureFixture()
assert.equal(sameBlock.requestContext.document_title, '关于推进专项工作的通知')
assert.equal(sameBlock.requestContext.section_heading, '二、工作要求')
assert.match(sameBlock.requestContext.context_before, /各单位应高度重视并做好组织协调。/)
assert.match(sameBlock.requestContext.context_before, /各单位$/)
assert.match(sameBlock.requestContext.context_after, /^。/)
assert.match(sameBlock.requestContext.context_after, /材料应当真实准确，不得遗漏重要事项。/)
assert.doesNotMatch(sameBlock.requestContext.context_before, /七月三十日/)
assert.equal(sameBlock.selectedText, '要在七月三十日前提交完整材料')
assert.equal(sameBlock.isSingleBlockSelection, true)

assert.deepEqual(
  captureFixture({ backward: true }),
  sameBlock,
  '反向拖选应当提取与正向拖选相同的结构上下文',
)

const crossBlock = captureFixture({ crossBlock: true })
assert.match(crossBlock.requestContext.context_before, /各单位$/)
assert.match(crossBlock.requestContext.context_after, /^真实准确，不得遗漏重要事项。/)
assert.match(crossBlock.requestContext.context_after, /联系人及联系方式另行通知。/)
assert.doesNotMatch(crossBlock.requestContext.context_after, /^材料应当/)
assert.equal(crossBlock.isSingleBlockSelection, false)

assert.equal(
  shouldUsePlainTextInsertion('五、严格网络安全管理制度，加强信息报送。\n\n各单位应严格执行有关制度。', true),
  true,
)
assert.equal(shouldUsePlainTextInsertion('## 二、工作要求\n\n正文', true), false)
assert.equal(shouldUsePlainTextInsertion('普通替换文本', false), false)

assert.equal(selectionTextsMatch('第一段\n第二段', '第一段\n\n第二段'), true)
assert.equal(selectionTextsMatch('正文内容', '一、严格落实网络安全责任制\n正文内容'), false)
assert.equal(selectionTextsMatch('正文内容', '正文内容补充'), false)
assert.equal(selectionTextsMatch(' 正文内容', '正文内容'), false)

const exactEditor = createEditor({
  namespace: 'exact-selection-replacement',
  onError(error) {
    throw error
  },
})
let exactCapture = null
let exactResult = ''
exactEditor.update(() => {
  const root = $getRoot()
  const section = $createParagraphNode()
  const headingText = $createTextNode('一、严格落实网络安全责任制')
  const bodyText = $createTextNode('各二级单位应明确网络安全管理职责。原有后句。')
  root.clear()
  section.append(headingText, $createLineBreakNode(), bodyText)
  root.append(section)

  const selection = $createRangeSelection()
  selection.anchor.set(bodyText.getKey(), 0, 'text')
  selection.focus.set(bodyText.getKey(), '各二级单位应明确网络安全管理职责。'.length, 'text')
  $setSelection(selection)
  exactCapture = captureSelectionContext(selection, root)
  insertPlainTextSelectionReplacement(selection, '各二级单位应进一步明确网络安全管理职责。')
  exactResult = root.getTextContent()
}, { discrete: true })

assert.equal(exactCapture.selectedText, '各二级单位应明确网络安全管理职责。')
assert.match(exactCapture.requestContext.context_before, /一、严格落实网络安全责任制/)
assert.equal((exactResult.match(/一、严格落实网络安全责任制/g) || []).length, 1)
assert.equal(
  exactResult,
  '一、严格落实网络安全责任制\n各二级单位应进一步明确网络安全管理职责。原有后句。',
)

console.log('selection context extraction passed')
