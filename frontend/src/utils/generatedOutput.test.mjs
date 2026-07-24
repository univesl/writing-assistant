import assert from 'node:assert/strict'

import {
  appendKnowledgeSources,
  appendSseChunk,
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

console.log('generated output metadata utilities passed')
