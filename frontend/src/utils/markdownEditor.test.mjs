import assert from 'node:assert/strict'

import {
  cleanHeadingText,
  normalizeMarkdownStructure,
  stripGeneratedOutputMarkers,
} from './markdownEditor.js'

const generatedOutput = [
  '---ARTICLE---',
  '# 正文标题',
  '',
  '正文内容',
  '---SUMMARY---',
  '生成摘要',
].join('\n')

assert.equal(
  stripGeneratedOutputMarkers(generatedOutput),
  '# 正文标题\n\n正文内容\n',
  'generated output markers should not enter the editor state',
)

assert.equal(
  normalizeMarkdownStructure('# 标题&amp;#xA;被误带入标题的正文\n\n下一段'),
  '# 标题\n\n被误带入标题的正文\n\n下一段',
  'encoded soft line breaks inside headings should be split back into normal content',
)

assert.equal(
  normalizeMarkdownStructure('## 标题&#10;正文第一句&#xA;正文第二句'),
  '## 标题\n\n正文第一句\n正文第二句',
  'multiple encoded line break forms should be normalized',
)

assert.equal(
  cleanHeadingText('**标题&amp;#xA;正文** &amp; 说明'),
  '标题',
  'toc heading text should decode entities and ignore content after encoded breaks',
)

console.log('markdownEditor utilities passed')
