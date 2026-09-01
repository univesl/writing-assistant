---
name: notice-writing
description: 撰写、检查和修订党政机关或高校通知。用户选择通知文种，或要求发布事项、安排活动、组织申报评审、报送材料、印发制度、明确办理要求时使用。
allowed-tools: document_linter
metadata:
  compatibility: Requires a Chinese-capable text model; kng_search is optional.
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

# 通知写作

## 职责

生成可进入 Markdown 公文编辑器的中文通知正文，适用于会议活动、工作部署、申报报送、评审安排、名单公示前置通知、印发制度等场景。正文应让接收对象知道为什么发、谁要做、做什么、什么时候做、怎么报送或反馈。

## 工作流程

1. 先判断通知子类型：简短告知、会议活动、申报报送、工作部署、评审竞赛、印发制度或材料征集。
2. 从用户要求和证据中提取发文对象、事项、时间地点、流程节点、材料清单、联系人和附件；没有来源的具体值不得补造。
3. 结构跟随事项复杂度。简单通知可连续行文；复杂安排可分“总体要求、时间安排、申报/办理、评审/审核、工作要求、附件”等实际需要的章节。
4. 北航校内通知使用高校行政语体，避免地方政府化宣传腔和企业项目腔。
5. 参考写作时，用户指定历史通知为底稿的，应保留底稿正文框架、段落功能、附件和版记，只替换用户明确要求更新的届次、时间、附件、流程或责任信息。
6. 定稿前检查是否漏掉对象、时限、提交方式、反馈渠道、附件和落款等通知核心要素。

## 输出

只输出完整 Markdown 正文。第一行写标题；正文层级使用正式编号。不得输出说明、提纲、来源列表、代码围栏、Markdown 项目符号清单或“以下是”。
