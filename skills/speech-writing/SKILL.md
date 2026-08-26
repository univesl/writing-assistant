---
name: speech-writing
description: 撰写、检查和修订高校领导讲话稿、致辞和会议发言。用户选择讲话稿文种或要求生成可口头表达的正式讲话时使用。
allowed-tools: document_linter
metadata:
  compatibility: Requires a Chinese-capable text model; kng_search is optional for facts and prior materials.
  version: "1.2"
  role: writer
  task-types: [draft, reference, imitate, revise_document, revise_selection, review]
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

## 目标

生成正式、自然、适合现场表达的讲话稿。事实、数据、案例和身份称谓必须来自用户要求或证据，不能为了增强感染力而编造。

## 工作方法

1. 明确场合、听众、讲话人身份、主题和预计篇幅。
2. 判断是部署、总结推进、致辞还是座谈发言，再按场合选择自然顺序；称谓、开场、任务和结尾都是候选功能，不是每篇必须齐全的模板。
3. 段落应适合朗读，避免过长复句和连续堆砌口号。
4. 将新闻或知识库材料转化为事实素材，不照抄新闻稿文风。
5. 不把讲话稿写成通知、新闻稿或规章条款，完成后按 [讲话稿规范](references/style-guide.md) 检查语气和事实。

## 输出

只输出完整 Markdown 正文，不要输出分析、提纲、来源列表、代码围栏或 ARTICLE/SUMMARY 标记。
