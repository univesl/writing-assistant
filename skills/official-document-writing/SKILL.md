---
name: official-document-writing
description: 起草、检查和修订通知以外的通用党政机关公文及高校政务材料，包括请示、报告、批复、函、纪要、决定、意见、通报、通告、工作总结、方案和汇报材料；用户选择通用公文或未明确文种时使用。
allowed-tools: document_linter
metadata:
  compatibility: Requires a Chinese-capable text model; kng_search is optional and document_linter is required.
  version: "1.3"
  role: writer
  task-types: [draft, reference, reply, imitate, revise_document, revise_selection, review]
  sources:
    - buaa-official-content-writer
    - dknowc-official-doc-writer
  workflow:
    outline: required
    model-review: true
    max-revisions: 1
    references:
      planning: [references/document-type-routing.md, references/drafting-guide.md]
      outline: [references/document-type-routing.md, references/drafting-guide.md]
      draft: [references/drafting-guide.md]
      validation: [references/quality-review.md]
      revision: [references/drafting-guide.md, references/quality-review.md]
---

# 通用公文写作

## 职责

把用户提供的主题、事实、初稿、会议记录、历史材料或检索证据整理成可进入编辑器的中文公文正文。当前 Skill 只负责正文内容、标题层级和 Markdown 结构；红头、正式文号、印章、签发人、版记、页码和 Word 版式由外层流程处理，不在正文中伪造。

## 写作流程

1. 先判断任务是起草、参考写作、回复、仿写、全文修改、选区修改还是审查，再判断文种和行文方向。
2. 以用户本轮要求为最高约束；上传材料、知识库证据和历史文稿只能在被用户要求或与任务明确相关时进入正文。
3. 先锁定事实边界，再组织结构。没有材料支撑的单位、政策、文号、时间、金额、人数、结论、审批意见和职责分工不得补造。
4. 参考写作时区分内容、结构、风格和背景材料。内容材料提供事实；结构和风格材料只提供段落功能、语气和表达节奏。
5. 改写和修订以用户给出的最新版正文为主线，未要求修改的正确事实和必要段落应保留。
6. 定稿前按审查规则检查文种、权限、事实、结构闭环、语言密度和输出边界。

## 北航场景

当任务涉及北京航空航天大学、学院、书院、机关部处、直属单位、学生工作、科研竞赛、教学培养、会议活动、制度办法等校内事务时，默认采用高校行政语体：准确、克制、可执行，避免地方政府化、企业宣传化和空泛口号化。不得编造学校会议决定、校领导指示、部门职责、评审结论、经费安排、人员名单、涉密安全事项或纪律处理结果。

## 输出

不得输出模型思考过程、检索日志、代码围栏或“以下是”之类引导语。
