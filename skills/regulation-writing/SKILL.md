---
name: regulation-writing
description: 撰写、检查和修订高校规章制度、办法、细则和管理规定。用户选择规章制度文种或要求形成条款化制度时使用。
allowed-tools: document_linter
metadata:
  compatibility: Requires a Chinese-capable text model; kng_search is recommended for governing-basis checks.
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

# 规章制度写作

## 目标

生成边界明确、职责可执行、程序闭环的条款化制度。不得虚构上位文件、文号、组织机构、处罚权限或生效日期。

## 工作方法

1. 先判断是办法、规定、细则、阶段性方案还是简短行为规范，再选择适合其稳定性和复杂度的结构。
2. 有证据时保持上位制度名称和术语准确；没有证据时避免写具体文号。
3. 长期且规则较多的制度可使用章条结构；内容较少的制度不强行分章，阶段性方案也不机械改写成长期制度。
4. 检查主体、条件、动作、时限、例外和责任是否齐全。
5. 不自动补造主管部门、处罚、解释权、生效日期或上位文件；完成后按 [制度规范](references/style-guide.md) 检查冲突和授权边界。

## 输出

只输出完整 Markdown 正文，不要输出分析、提纲、来源列表、代码围栏或 ARTICLE/SUMMARY 标记。
