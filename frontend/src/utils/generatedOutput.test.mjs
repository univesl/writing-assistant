import assert from 'node:assert/strict'

import {
  appendKnowledgeSources,
  appendSseChunk,
  extractArticlePreview,
  formatReferenceLabel,
  normalizeOfficialArticleFormat,
  normalizeKnowledgeSourcesInMessage,
  parseSelectionEditOutput,
  sortKnowledgeReferences,
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
  '生成完成\n\n知识库来源：\n- 来源文件\n- 另一文件',
  'knowledge sources should be shown outside the formal article and deduplicated',
)

assert.deepEqual(
  sortKnowledgeReferences(['[3] 文件C', '[1] 文件A', '[2] 文件B', '未编号来源']),
  ['文件A', '文件B', '文件C', '未编号来源'],
  'knowledge source references should be displayed in ascending citation order',
)

assert.deepEqual(
  sortKnowledgeReferences(['- [3] 文件C', '[1] 文件A']),
  ['文件A', '文件C'],
  'source sorting should also recognize a reference that already carries a bullet marker',
)

assert.equal(
  formatReferenceLabel('[5] buaa_corpus_20260811/现行有效制度/中共北京航空航天大学委员会网络意识形态工作责任制实施细则.pdf'),
  '中共北京航空航天大学委员会网络意识形态工作责任制实施细则.pdf',
  'knowledge source paths should display only the filename',
)

assert.deepEqual(
  sortKnowledgeReferences([
    '[5] buaa_corpus_20260811/现行有效制度/同名文件.pdf',
    '[9] buaa_corpus_20260811\\通知公告\\同名文件.pdf',
  ]),
  ['同名文件.pdf'],
  'different source paths with the same filename should be deduplicated for display',
)

assert.equal(
  normalizeKnowledgeSourcesInMessage(
    '已生成。\n\n知识库来源：\n- [3] 文件C\n- [1] 文件A\n- [2] 文件B',
  ),
  '已生成。\n\n知识库来源：\n- 文件A\n- 文件B\n- 文件C',
  'historical chat messages should also display source numbers in ascending order',
)

assert.equal(
  normalizeOfficialArticleFormat(
    '1. **严格执行网络安全预案**\n   * 各单位应按预案落实相关要求。\n2. **加强信息报送**\n   - 发生事件应及时报告。',
  ),
  '1、**严格执行网络安全预案** 各单位应按预案落实相关要求。\n2、**加强信息报送** 发生事件应及时报告。',
  'Markdown nested bullets should become flat official paragraphs',
)

assert.equal(
  normalizeOfficialArticleFormat('1.第一项工作\n2)第二项工作\n1.5不是分点'),
  '1、第一项工作\n2、第二项工作\n1.5不是分点',
  'a missing list-marker space should still be normalized without touching decimals',
)

assert.equal(
  normalizeOfficialArticleFormat('* 第一项工作。\n* 第二项工作。'),
  '一、第一项工作。\n二、第二项工作。',
  'parallel unordered items should use an official flat numbering form',
)

assert.equal(
  normalizeOfficialArticleFormat('一、已有正式编号\n\n1、已有阿拉伯编号\n（一）已有分款'),
  '一、已有正式编号\n\n1、已有阿拉伯编号\n（一）已有分款',
  'existing official numbering should remain unchanged',
)

assert.equal(
  extractArticlePreview('---ARTICLE---\n1. 第一项\n2. 第二项\n---SUMMARY---\n已完成'),
  '1、第一项\n2、第二项\n',
  'streaming article previews should not expose Markdown dot numbering',
)

assert.equal(
  appendKnowledgeSources('生成完成', []),
  '生成完成',
  'an empty source list should not create an empty warning section',
)

assert.equal(
  appendKnowledgeSources('已使用上传材料', [{ kind: 'uploaded_file', name: '骨架.docx' }]),
  '已使用上传材料',
  'uploaded material objects should not be rendered as knowledge-base object strings',
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

assert.throws(
  () => parseSelectionEditOutput('---REPLACEMENT---\n\n---SUMMARY---\n已删除重复内容'),
  /未使用明确的删除标记/,
  'an empty or truncated replacement must not be treated as a destructive edit',
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
  () => parseSelectionEditOutput(
    '---REPLACEMENT---\n[[DELETE_SELECTION]]\n补充说明\n---SUMMARY---\n已删除所选内容',
  ),
  /删除标记格式异常/,
  'the deletion marker must be the complete replacement instead of mixed with visible text',
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
