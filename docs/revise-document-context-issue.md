# 二次修改上下文丢失问题记录

## 背景

用户先通过参考写作生成第三十六届“冯如杯”竞赛通知，再要求系统把稿件改得更接近原文风格：除“时间安排”可用表格外，申报、评审、交流、要求等章节按原文风格用连续条款，不另拟解释型小标题；组织机构逐项列全称，不合并简称。

这次修改后，文稿质量明显下降。现阶段先记录问题情况和疑似代码区，不进行调试和修复。

## 现象

最新修改任务：

| 字段 | 值 |
|------|----|
| run_id | 2966cf12-eaa1-43d6-a854-13cbcaedf15c |
| session_id | 4 |
| task_type | revise_document |
| status | completed |
| created_at | 2026-08-29 14:40:24 |
| final_len | 3449 |
| source_file_ids | [] |
| base_version | 1 |

改前版本长度约 6287 字，改后约 3449 字，减少约 2838 字。

改后主要退化点：

1. 原有真实日期被替换为“待定”。
2. 原有组委会主任、副主任、委员、秘书、办公室地点和电话被替换为“组委会组成人员名单：〔待补充〕”。
3. 原有 9 个附件被替换为“附件：〔待补充〕”。
4. 导语中的政治背景、政策依据和校内依据被大幅删除。
5. “四、申报工作”“五、评审工作”“六、交流活动”“七、工作要求”被改成 `## 四、`、`## 五、`、`## 六、`、`## 七、`，只剩编号，没有标题文字。
6. 正文仍引用附件1、附件2、附件3，但末尾附件清单已丢失，形成前后矛盾。

## 当前判断

这更像架构设计问题，不是单纯提示词问题。

`revise_document` 只拿到了当前文章和用户的局部修改要求，没有继承上一轮参考写作中的上传材料、材料使用方案、证据摘录或结构化事实清单。校验阶段又继续使用“只允许用户要求和证据中的事实”的规则。在 `source_file_ids=[]`、`source_materials=[]`、`evidence=[]` 的情况下，校验器容易把当前正文中已经存在的真实日期、人员、附件、专项竞赛、评审比例误判为“无证据具体事实”。

随后自动修订会根据这些错误 issue 删除或占位真实信息，导致越改越差。

## 数据证据

最新修改任务的 `issues_json` 包含以下错误：

| code | 问题 |
|------|------|
| unsupported_specific_facts | 把“一杯五赛”、专项竞赛名称、承办单位、主赛道分组、评审比例、时间流程等判定为未在用户要求或证据中提供的具体事实 |
| placeholder_not_allowed | 改后正文出现“待补充”“待定”等占位符 |
| abbreviation_org | 抄送栏单位使用简称，不符合逐项列全称要求 |
| unrelated_unit | 抄送栏单位与可用依据不一致 |
| attachment_mismatch | 正文引用附件1至附件3，但末尾附件栏只有“〔待补充〕” |
| empty_heading | `## 四、`、`## 五、`、`## 六、`、`## 七、` 只有编号无标题 |

这说明系统一方面在修改中删掉事实，另一方面校验阶段又识别出了删除后的错误，但最终仍将结果完成并应用。

## 疑似问题代码区

### 1. 创建修改任务时没有继承上一轮事实上下文

位置：`backend/app/agent/manager.py`

相关代码：

- `create_run` 只把当前 session 正文放入 `base_article`，没有记录或恢复该正文来源于哪个上游 run。
- `_execute` 只根据当前 request 的 `source_file_ids` 重新加载材料。对于 `revise_document`，这次请求的 `source_file_ids=[]`，因此 `source_materials=[]`。

重点行：

```text
backend/app/agent/manager.py:163-165
backend/app/agent/manager.py:215-229
```

风险：

二次修改无法知道当前文章中的事实来自上一轮参考材料或规格书，只能把这些事实当成无来源正文文本处理。

### 2. `revise_document` 工作流缺少显式上下文恢复阶段

位置：`backend/app/agent/workflow.py`

相关代码：

```text
backend/app/agent/workflow.py:16
```

当前 `revise_document` 阶段为：

```text
prepare -> skill -> draft -> validation -> finalize
```

风险：

修改任务没有 `planning`、`retrieval`、`evidence_filter` 等阶段，也没有等价的“继承上次证据”阶段。它适合纯文本润色，但不适合带大量事实约束的正式文件二次修改。

### 3. 起草修改稿时要求“只使用用户要求和证据中的事实”

位置：`backend/app/agent/graph.py`

相关代码：

```text
backend/app/agent/graph.py:41-42
backend/app/agent/graph.py:1326-1348
```

重点逻辑：

- `WRITING_SOURCE_RULES` 规定事实优先级来自用户要求、材料方案确认的摘录、知识库证据。
- `draft` prompt 对 `revise_document` 也拼接了“只使用用户要求和证据中的事实”。
- 但本次修改任务没有证据，只有 `base_article`。

风险：

当前正文中的既有事实没有被声明为可信来源，模型在修改时会倾向于删除或占位。

### 4. 校验阶段仍按证据边界审查全文

位置：`backend/app/agent/graph.py`

相关代码：

```text
backend/app/agent/graph.py:1424-1469
```

重点逻辑：

校验 prompt 要求审查“是否违反用户要求、Skill 或证据边界”，并把 `WRITING_SOURCE_RULES`、`KNG_USAGE_RULES` 和“已筛选证据”传入。由于本次 `evidence=[]`，模型审阅把正文中大量具体事实判为 unsupported。

风险：

对 `revise_document` 来说，校验器没有区分“原文已有事实”和“本次修改新增事实”。它把 base_article 中已存在的事实也按新增事实审查。

### 5. 自动修订会根据错误 issue 继续删事实

位置：`backend/app/agent/graph.py`

相关代码：

```text
backend/app/agent/graph.py:1473-1550
backend/app/agent/graph.py:1617-1623
```

重点逻辑：

- `after_validate` 在存在 error 且未超过修订次数时进入 `revise`。
- `revise` prompt 会把问题清单和空证据一起给模型，并要求“不得新增无依据事实”。

风险：

如果上一轮校验 issue 是误报，自动修订会按照误报删除真实信息。当前案例中，日期、人员、附件等真实信息被替换为“待定”“待补充”，符合这个风险模式。

### 6. 带未解决 error 的结果仍会完成并落地

位置：`backend/app/agent/graph.py`、`backend/app/agent/manager.py`

相关代码：

```text
backend/app/agent/graph.py:1553-1563
backend/app/agent/manager.py:395-424
```

重点逻辑：

- `finalize` 发现还有需要修订的问题时，只追加 `validation_unresolved` warning。
- `_complete_run` 仍将状态置为 `completed`，并在版本匹配时写入 session 正文和 document revision。

风险：

即使 `issues_json` 里仍有多个 severity=error 的问题，用户看到的任务仍可能是 completed，且差稿已经覆盖正文。

### 7. 缩短保护阈值不足以阻止本次退化

位置：`backend/app/agent/graph.py`

相关代码：

```text
backend/app/agent/graph.py:1527-1543
```

当前只在修订稿长度小于原文 70% 时拒绝异常缩短。

风险：

本次从约 6287 字缩到 3449 字，已经丢失大量事实，但具体进入该保护逻辑时的比较基准可能不是用户看到的上一个完整版本，且即便按 70% 阈值判断，也无法覆盖所有“事实字段被替换成占位符”的退化情形。

## 建议后续修复方向

先不在本记录中实现，只标记方向：

1. 为 `revise_document` 引入上下文继承：继承当前正文来源 run 的 `source_file_ids`、`source_materials`、`reference_strategy`、`evidence`、`workflow_plan` 或结构化事实清单。
2. 区分“原文已有事实”和“本次新增事实”：格式调整类修改不得把 base_article 既有事实判为 unsupported。
3. 对仅格式和风格修改建立事实保持约束：日期、人员、单位、附件、专项竞赛、评审比例等字段默认保持不变。
4. 当校验仍存在 severity=error 时，不直接覆盖 session 正文，可改为生成 proposal，等待用户确认。
5. 增强退化保护：除长度阈值外，增加关键事实字段覆盖率、附件数量、日期数量、占位符数量等检查。
6. 对 `revise_document` 的 prompt 做专门化：明确 base_article 是当前可信底稿，除用户明确要求或证据冲突外，不得删除其中具体事实。
