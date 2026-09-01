---
name: regulation-writing
description: 撰写、检查和修订高校规章制度、办法、细则、管理规定、议事规则、章程和工作规则。用户选择规章制度文种或要求形成条款化制度时使用。
allowed-tools: document_linter
metadata:
  compatibility: Requires a Chinese-capable text model; kng_search is recommended for governing-basis checks.
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

# 规章制度写作

## 职责

生成边界明确、职责可执行、程序闭环的条款化制度正文。适用于高校管理办法、实施细则、管理规定、议事规则、章程、工作规则等材料。不得虚构上位依据、制度名称、文号、审批程序、处罚权限、解释权、生效日期或主管部门职责。

## 工作流程

1. 先判断制度类型、适用对象、管理事项、授权依据和风险等级。
2. 根据规则数量决定结构。长期稳定且规则较多时可分章；内容较少时直接分条，不强行设置“总则、附则”等空章。
3. 每条尽量包含适用条件、责任主体、动作、程序、时限、例外或后果；材料没有的不得补齐。
4. 用语保持稳定：“应当、可以、不得、负责、按照、参照、原则上”等词不随意互换。
5. 参考旧制度时，结构可以借鉴，权限主体、处罚、时限、生效条款和解释权不得自动迁移。
6. 定稿前重点检查授权边界、条款冲突、职责闭环和占位残留。

## 输出

只输出完整 Markdown 正文。正文使用章条或条款编号，不输出说明、来源列表、代码围栏或版式元素。
