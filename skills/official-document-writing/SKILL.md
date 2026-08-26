---
name: official-document-writing
description: 起草、检查和修订通知以外的通用党政机关公文及政务材料，包括请示、报告、批复、函、纪要、决定、意见、通报、通告、工作总结和方案；用户选择通用公文或未明确文种时使用。
allowed-tools: document_linter
metadata:
  compatibility: Requires a Chinese-capable text model; kng_search is optional and document_linter is required.
  version: "1.1"
  role: writer
  task-types: [draft, reference, reply, imitate, revise_document, revise_selection, review]
  sources:
    - https://github.com/zhaohui-yang/official-document-drafting
    - https://github.com/KaguraNanaga/official-document-writing-skill
    - https://github.com/Liuxiangjian-ai/official-document-skill
  workflow:
    outline: required
    model-review: true
    max-revisions: 1
    references:
      planning: [references/document-type-routing.md]
      outline: [references/document-type-routing.md]
      draft: [references/drafting-guide.md]
      validation: [references/quality-review.md]
      revision: [references/drafting-guide.md, references/quality-review.md]
---

# 通用公文写作

## 目标

先根据行文关系、目的和是否需要回应确定文种，再生成事实可靠、文种正确、结构可用的 Markdown 正文。不得虚构政策、文号、权限、数据、人物、日期或办理结果。

## 工作原则

1. 用户已明确文种时尊重其选择；只有选择明显冲突时才在正文外的校验问题中提示。
2. 用户未明确文种时，按 [文种路由](references/document-type-routing.md) 收敛文种，并在标题、正文结构和结语中保持一致。
3. 起草时按需参考 [起草指南](references/drafting-guide.md)，不要把模板占位符或来源说明写进正文。
4. 缺少必要事实时省略、使用稳妥概括或明确“待补充”，不得补造。
5. 审查时使用 [质量检查](references/quality-review.md)，优先修复文种错误、事实越界、权限错位和请求事项不清。

## 输出

只输出完整 Markdown 正文。字体、页边距、印章和版记属于 DOCX 导出层，不在 Markdown 中伪造。
