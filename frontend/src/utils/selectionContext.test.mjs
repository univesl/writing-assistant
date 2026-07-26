import assert from 'node:assert/strict'
import {
  $createParagraphNode,
  $createRangeSelection,
  $createTextNode,
  $getRoot,
  $setSelection,
  createEditor,
} from 'lexical'
import { $createHeadingNode, HeadingNode } from '@lexical/rich-text'

import { captureSelectionContext } from './selectionContext.js'

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
assert.equal(sameBlock.document_title, '关于推进专项工作的通知')
assert.equal(sameBlock.section_heading, '二、工作要求')
assert.match(sameBlock.context_before, /各单位应高度重视并做好组织协调。/)
assert.match(sameBlock.context_before, /各单位$/)
assert.match(sameBlock.context_after, /^。/)
assert.match(sameBlock.context_after, /材料应当真实准确，不得遗漏重要事项。/)
assert.doesNotMatch(sameBlock.context_before, /七月三十日/)

assert.deepEqual(
  captureFixture({ backward: true }),
  sameBlock,
  '反向拖选应当提取与正向拖选相同的结构上下文',
)

const crossBlock = captureFixture({ crossBlock: true })
assert.match(crossBlock.context_before, /各单位$/)
assert.match(crossBlock.context_after, /^真实准确，不得遗漏重要事项。/)
assert.match(crossBlock.context_after, /联系人及联系方式另行通知。/)
assert.doesNotMatch(crossBlock.context_after, /^材料应当/)

console.log('selection context extraction passed')
