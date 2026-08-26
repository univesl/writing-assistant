---
name: notice-writing
description: 撰写、检查和修订党政机关或高校通知。用户选择通知文种，或要求发布事项、安排活动、明确办理要求时使用。
allowed-tools: document_linter
metadata:
  compatibility: Requires a Chinese-capable text model; kng_search is optional.
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

# 通知写作

## 目标

生成可以直接进入现有 Markdown 公文编辑器的中文通知正文。正文应事实克制、任务明确、层级清楚，不得补造日期、单位、人员、数据或政策依据。

## 工作方法

1. 先判断是简短告知、会议活动、申报报送还是工作部署等子类型，再从用户要求和可用证据中提取发文目的、对象和事项。
2. 缺失信息原则上省略或稳妥概括；除非用户要求保留占位，不在可直接使用的正文中自动写“待补充”。
3. 根据事项复杂度决定结构。简单告知可以连续行文，复杂部署可以分层；不得强制每篇通知使用“缘由—事项—要求”三段式。
4. 使用“一、”“（一）”“1.”等稳定层级；不要用 Markdown 项目符号代替正式公文编号。
5. 完成后按 [通知规范](references/style-guide.md) 检查事实、任务边界和结构自然度。

## 输出

只输出完整 Markdown 正文，不要输出分析、提纲、来源列表、代码围栏或 ARTICLE/SUMMARY 标记。
