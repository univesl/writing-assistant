---
name: official-document-review
description: 对中文公文草稿进行跨文种事实、权限、结构、语言和交付边界审查；作为通知、制度、讲话稿和通用公文 Skill 的审查辅助能力组合使用，不单独生成正文。
allowed-tools: document_linter
metadata:
  compatibility: Requires a Chinese-capable text model and document_linter.
  version: "1.1"
  role: reviewer
  task-types: [draft, reference, reply, imitate, revise_document, revise_selection, review]
  sources:
    - https://github.com/KaguraNanaga/official-document-writing-skill
    - https://github.com/Liuxiangjian-ai/official-document-skill
  workflow:
    outline: skip
    model-review: true
    max-revisions: 1
    references:
      draft: [references/chinese-official-expression.md]
      validation: [references/review-focus.md, references/chinese-official-expression.md]
      revision: [references/review-focus.md, references/chinese-official-expression.md]
---

# 公文审查

仅审查明确、可操作的问题，不输出隐藏推理。确定性校验负责长度、编号和基础格式；本 Skill 重点补充事实一致性、文种适配、权限边界、结构闭环和语言质量。

审查与修订时按 [审查重点](references/review-focus.md) 处理。不得为了“完善”正文而补造事实；没有依据的版式要素不应强行加入正文。
