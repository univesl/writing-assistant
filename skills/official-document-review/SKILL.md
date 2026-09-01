---
name: official-document-review
description: 对中文公文草稿进行跨文种事实、权限、结构、语言、材料使用和交付边界审查；作为通知、制度、讲话稿和通用公文 Skill 的审查辅助能力组合使用，不单独生成正文。
allowed-tools: document_linter
metadata:
  compatibility: Requires a Chinese-capable text model and document_linter.
  version: "1.2"
  role: reviewer
  task-types: [draft, reference, reply, imitate, revise_document, revise_selection, review]
  sources:
    - buaa-official-content-writer
    - dknowc-official-doc-writer
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

## 职责

审查正文是否能安全进入正式编辑流程。确定性校验负责基础格式；本 Skill 重点检查事实来源、文种适配、权限边界、材料使用、结构闭环和语言质量。

## 审查原则

1. 只报告明确、可操作的问题，不输出隐藏推理。
2. 事实问题优先于语言润色；权限和文种错误优先于表达优化。
3. 不为了“完善”而建议补造事实；缺依据时建议删除、降级表述或提示用户确认。
4. 参考写作必须检查材料角色是否被正确执行，尤其是结构/风格材料中的旧事实是否误入正文。
5. 去 AI 味只改空泛、旁白、机械和重复表达，不改变事实、状态强度、否定范围和专业术语。
6. Markdown 正文审查不宣称红头、版记、印章、页码等 Word 版式已经合规。

## 输出

发现问题时先列问题，再给最小范围修改建议。没有明显问题时说明未发现明显内容风险，并提醒正式使用前确认事实、依据和发文权限。
