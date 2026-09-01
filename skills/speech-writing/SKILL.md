---
name: speech-writing
description: 撰写、检查和修订高校领导讲话稿、致辞、会议发言、研讨发言和总结部署讲话。用户选择讲话稿文种或要求生成适合口头表达的正式讲话时使用。
allowed-tools: document_linter
metadata:
  compatibility: Requires a Chinese-capable text model; kng_search is optional for facts and prior materials.
  version: "1.3"
  role: writer
  task-types: [draft, reference, imitate, revise_document, revise_selection, review]
  sources:
    - buaa-official-content-writer
    - dknowc-official-doc-writer
  workflow:
    outline: required
    model-review: true
    max-revisions: 1
    references:
      planning: [references/style-guide.md]
      outline: [references/style-guide.md]
      draft: [references/style-guide.md]
      validation: [references/style-guide.md]
      revision: [references/style-guide.md]
---

# 讲话稿写作

## 职责

生成正式、自然、适合现场表达的讲话稿、致辞或发言材料。讲话稿可以有感染力，但事实、数据、案例、称谓、身份和会议背景必须来自用户要求或证据，不能为了增强气势而编造。

## 工作流程

1. 先明确场合、听众、讲话人身份、讲话目的、时长和是否代表单位正式表态。
2. 判断类型：致辞、部署讲话、总结推进讲话、研讨发言、座谈发言、开幕/闭幕讲话。
3. 先组织观点和段落功能，再安排表达节奏；不强行每部分“三点式”。
4. 用户材料中的事实保持原状态强度。工作尚在谋划时，不写成已经完成；个别探索不写成全面成效。
5. 参考历史讲话时，吸收结构、语气和节奏，不照搬旧称谓、活动背景、成绩数据和口号。
6. 定稿前检查是否误写成通知、制度条款、新闻稿或宣传稿。

## 输出

只输出完整 Markdown 正文。需要称谓、开场、主体和结尾时按场合自然呈现；不得输出写作说明、来源列表、代码围栏或聊天式解释。
