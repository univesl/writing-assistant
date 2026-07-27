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

assert.throws(
  () => parseSelectionEditOutput(
    '---REPLACEMENT---\n一、全面落实网络安全责任制\n扩写后的正文。\n---SUMMARY---\n已扩写',
    '已完成选区修改',
    {
      selectedMarkdown: '原正文。',
      contextBefore: '一、严格落实网络安全责任制',
      contextAfter: '二、完善网络安全应急预案',
    },
  ),
  /重复生成了选区外的第“一”项标题/,
  'a rewritten copy of the same outside numbered heading must also be rejected',
)

assert.throws(
  () => parseSelectionEditOutput(
    '---REPLACEMENT---\n一、严格落实网络安全责任制\n扩写后的正文。\n---SUMMARY---\n已扩写',
    '已完成选区修改',
    {
      selectedMarkdown: '原正文。',
      contextBefore: '一、严格落实网络安全责任制',
      contextAfter: '二、完善网络安全应急预案',
    },
  ),
  /重复了选区外的前文/,
  'a copied read-only heading must be rejected before it can duplicate outside the selection',
)

assert.deepEqual(
  parseSelectionEditOutput(
    '---REPLACEMENT---\n一、严格落实网络安全责任制\n扩写后的正文。\n---SUMMARY---\n已扩写',
    '已完成选区修改',
    {
      selectedMarkdown: '一、严格落实网络安全责任制\n原正文。',
      contextBefore: '现将有关事项通知如下：',
      contextAfter: '二、完善网络安全应急预案',
    },
  ).replacementMarkdown,
  '一、严格落实网络安全责任制\n扩写后的正文。',
  'a heading that is inside the exact selection remains valid replacement content',
)

assert.equal(
  parseSelectionEditOutput(
    '---REPLACEMENT---\n五、严格网络安全管理制度并加强信息报送  \n各单位应严格执行有关制度。\n---SUMMARY---\n已合并',
  ).replacementMarkdown,
  '五、严格网络安全管理制度并加强信息报送  \n各单位应严格执行有关制度。',
  'the parser must preserve the model fragment instead of rewriting its structure heuristically',
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
