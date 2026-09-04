---
name: buaa-official-content-writer
slug: buaa-official-content-writer
display_name: 北航公文写作
display_name_en: BUAA Official Writing
description: 面向北京航空航天大学校内行政、公务写作场景，起草、改写、整理、审校公文正文内容，并约束正文标题层级和基础样式；新闻类文章作为公文内容的一种按同一套正文规则处理；不负责红头、版记、正式文号、印章、签发人等正式版式元素。
description_en: Supports drafting, rewriting, organizing, and reviewing BUAA official document content. News-style articles are treated as one content type under the same writing rules.
description_zh: >
  北航公文写作是面向北京航空航天大学校内行政、公务、综合文秘、机关部处、学院办公室和直属单位的正文写作 Skill，用于起草、改写、整理和审校通知、请示、报告、函、复函、会议纪要、管理办法、实施细则、管理规定、议事规则、章程、实施方案、指导意见、工作总结、工作要点、通报、公示、公告、征求意见情况报告，以及新闻类文章、网站稿、活动报道和宣传稿等北航高频材料。新闻类文章作为公文内容的一种，正文规则与公文共用。本 Skill 负责正文内容、标题层级和基础样式契约，不负责红头、版记、正式文号、印章、签发人等正式版式元素。写作必须以用户本轮材料、用户上传文件和北航本地知识库为事实来源；通用公文知识只能提供结构和语气，不能补造事实。不得编造学校党委常委会、校长办公会、专题会、委员会决定，不得编造制度名称、文号、日期、金额、人数、排名、职责分工、审批结论、经费安排、编制岗位、人事任免、招生指标、学位事项、涉密和安全事故结论。默认使用高校行政语体，避免地方政府化、企业宣传化、空泛口号化和 AI 套话。正文不得混入写作过程、检索日志或格式说明。
category: 通用办公
version: 0.1.0
author: BUAA Official Docs
allowed-tools: document_linter
tags:
  - 公文
  - 北航
  - 写作
metadata:
  short-description: 北航校内公文正文起草、改写和审校
  writing-assistant:
    roles:
      - primary
    task-types:
      - draft
      - reference
      - reply
      - imitate
      - revise_document
      - revise_selection
      - review
      - format
    workflow:
      outline: embedded_in_planning
      model-review: true
      max-revisions: 1
      references:
        planning:
          - references/task_router.md
          - references/buaa_context.md
          - references/fact_discipline.md
          - references/doc_types/index.md
        outline:
          - references/task_router.md
          - references/fact_discipline.md
          - references/doc_types/index.md
        draft:
          - references/buaa_context.md
          - references/fact_discipline.md
          - references/doc_types/index.md
        validation:
          - references/fact_discipline.md
          - references/review_checklist.md
        revision:
          - references/fact_discipline.md
          - references/review_checklist.md
        analysis:
          - references/task_router.md
          - references/fact_discipline.md
---

# 北航公文写作

本 Skill 用于北京航空航天大学校内公文、综合材料和新闻类文章的内容写作。它的职责是把用户提供的主题、事实、会议记录、制度依据、历史材料或初稿，整理成符合北航高校行政语境的正文内容，并约束正文标题层级和基础样式；红头、版记、正式文号、印章、签发人和正式签发不属于本 Skill 的职责。

## 工作原则

- 负责正文内容、标题层级和基础样式契约。正式公文生成 Word 文件时，输出应遵循 `references/output_contract.md`，交给外层 docx 排版能力处理。
- 用户本轮材料优先；用户上传文件和北航本地知识库次之；通用公文知识只能提供结构和语气，不能补造事实。
- 不编造学校会议决定、制度名称、文号、日期、金额、人数、排名、职责分工、审批结论、签发意见和对外承诺。
- 默认使用高校行政语体，避免地方政府化、企业宣传化、空泛口号化和明显 AI 套话。
- 缺少会改变文种、对象、结论或风险的关键信息时，先追问；缺少一般细节时，可生成草稿并列出待确认事项。

## 渐进式读取

按任务只读取必要参考文件：

| 文件 | 何时读取 |
| --- | --- |
| `references/task_router.md` | 所有任务开始时，判断文种、复杂度和是否需要追问。 |
| `references/buaa_context.md` | 所有正式写作、改写、审校任务。 |
| `references/fact_discipline.md` | 所有正式写作、改写、压缩、总结、审校任务。 |
| `references/output_contract.md` | 需要输出正式公文 Word 文件时。 |
| `references/review_checklist.md` | 用户要求审查，或任务涉及请示、复函、制度、会议纪要、经费、人事、安全、保密、意识形态等高风险事项时。 |
| `references/doc_types/index.md` | 需要先总览北航文种体系时读取。 |
| `references/doc_types/*.md` | 按命中的文种读取对应具体文件。 |

文种路由优先参考 `references/task_router.md`。北航高频写作场景包括通知、印发通知、请示、报告、函、会议纪要、制度办法、实施细则、管理规定、实施方案、意见、通报公示、总结计划和新闻稿；命中这些场景时应读取对应文种文件。

## 输出要求

- 起草任务：输出正文，不输出写作过程、内部判断、检索日志或说明书式解释。
- 审查任务：先列问题，再给修改建议；没有明显问题时说明仍需人工确认事实、依据和发文权限。
- 正式公文 Word 任务：直接交付 Word 成稿，第一行按标题写法处理，不得包裹代码围栏，不得加入“以下是”等引导语。
- 如正文需要附件，只写 `附件：1.附件名称` 及必要附件正文；不要生成红头、文号、签发人、版记、页码等格式元素。

## 北航文种优先级

优先覆盖下列北航高频场景：

- 通知：普通事项通知、会议通知、报送通知、印发通知、修订通知。
- 请示/报告：校内一般事项请示报告、重大事项请示报告、工作情况报告、征求意见情况报告。
- 函/复函：校内商洽、对外联系、征求意见、逐项回复来函。
- 会议纪要：例会、专题会、委员会会议、工作推进会。
- 制度类：管理办法、实施办法、实施细则、管理规定、议事规则、章程、工作规则。
- 方案/意见/总结计划：实施方案、行动方案、指导意见、工作总结、工作要点、重点工作计划。
- 通报/公示/公告：情况通报、结果公示、名单公示、事项公告。

低频法定文种如决议、决定、批复、通告等，按用户明确要求或历史材料语境处理，不主动把普通校内事项升级为这些文种。
