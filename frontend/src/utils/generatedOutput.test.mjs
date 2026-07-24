import assert from 'node:assert/strict'

import {
  appendKnowledgeSources,
  appendSseChunk,
  parseSelectionEditOutput,
} from './generatedOutput.js'

const encoder = new TextEncoder()
const ragEvent = [
  'data: {"content":"正文","finish":false}',
  '',
  'data: {"content":"","finish":true,"rag":{"used":true,"references":["[1] 来源文件"]}}',
  '',
  '',
].join('\n')

const parsed = appendSseChunk(
  '',
  '',
  encoder.encode(ragEvent),
  new TextDecoder('utf-8'),
  {},
)

assert.equal(parsed.output, '正文')
assert.deepEqual(
  parsed.metadata.rag.references,
  ['[1] 来源文件'],
  'final SSE metadata should preserve KnG references',
)

assert.equal(
  appendKnowledgeSources('生成完成', ['[1] 来源文件', '[1] 来源文件', '[2] 另一文件']),
  '生成完成\n\n知识库来源：\n- [1] 来源文件\n- [2] 另一文件',
  'knowledge sources should be shown outside the formal article and deduplicated',
)

assert.equal(
  appendKnowledgeSources('生成完成', []),
  '生成完成',
  'an empty source list should not create an empty warning section',
)

assert.deepEqual(
  parseSelectionEditOutput(
    '---REPLACEMENT---\n## 新标题\n\n新段落\n---SUMMARY---\n已规范标题和段落',
  ),
  {
    replacementMarkdown: '## 新标题\n\n新段落',
    summaryContent: '已规范标题和段落',
    isDeletion: false,
  },
  'selection edit output should return only the replacement fragment',
)

assert.deepEqual(
  parseSelectionEditOutput('---REPLACEMENT---\n\n---SUMMARY---\n已删除重复内容'),
  {
    replacementMarkdown: '',
    summaryContent: '已删除重复内容',
    isDeletion: true,
  },
  'an intentionally empty replacement should represent deletion',
)

assert.deepEqual(
  parseSelectionEditOutput(
    '---REPLACEMENT---\n[[DELETE_SELECTION]]\n---SUMMARY---\n已删除所选内容',
  ),
  {
    replacementMarkdown: '',
    summaryContent: '已删除所选内容',
    isDeletion: true,
  },
  'the explicit deletion marker should never be inserted into the editor',
)

assert.throws(
  () => parseSelectionEditOutput('---ARTICLE---\n整篇文章\n---SUMMARY---\n已修改'),
  /格式异常/,
  'legacy whole-article output must not be accepted by selection editing',
)

const splitEvent = 'data: {"content":"跨分块内容","finish":false}\n\n'
const firstHalf = encoder.encode(splitEvent.slice(0, 18))
const secondHalf = encoder.encode(splitEvent.slice(18))
const partial = appendSseChunk('', '', firstHalf, new TextDecoder('utf-8'), {})
assert.equal(partial.output, '')
const completed = appendSseChunk(
  partial.buffer,
  partial.output,
  secondHalf,
  new TextDecoder('utf-8'),
  partial.metadata,
)
assert.equal(completed.output, '跨分块内容', 'SSE JSON split across chunks should be buffered safely')

console.log('generated output metadata utilities passed')
