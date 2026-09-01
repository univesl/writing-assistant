# 参考写作 Agent 瓶颈评估与优化设计

## 1. 结论

当前问题不适合继续通过提示词硬拧，也不建议新增新的用户侧功能或 task_type。应在现有“参考写作”能力上做内部增强，让 reference 工作流同时支持两种场景：

1. 综合参考：多份材料提供事实、结构、风格，生成一篇新文稿。
2. 底稿修订式参考：某份参考材料是主底稿，另一份材料只辅助确认风格或结构，输出应接近“在主底稿上局部替换”。

第三十六届“冯如杯”通知属于第二类。用户说“尽量使用原文”“只有提到修改的地方再改”“三十六届和之前文章内容差不多”时，系统不应该继续把任务理解成普通仿写或材料综合，而应该在 reference 内部切换为“主底稿优先”的生成策略。

## 2. 实践证据

### 2.1 最近生成效果

| run_id | session | task_type | model | final_len | 主要问题 |
|---|---:|---|---|---:|---|
| 4c711cd0-bd62-4929-8cbe-5ea9e18bf5ff | 12 | reference | deepseek-v4-pro | 3895 | 开头、指导思想、申报、评审、交流、工作要求被概括重写 |
| b917d041-159f-4ec4-91de-ff711928cc02 | 11 | reference | deepseek-v4-pro | 1781 | 只写变更项，漏掉指导思想、评审、交流、要求等章节 |
| aa5fedf4-7f4e-4332-91ab-1dda5824410d | 10 | reference | deepseek-v4-pro | 3688 | 结构较完整，但仍偏摘要化 |
| 7d8b5068-14d1-4ef3-bf0e-7780f3bf41ea | 6 | reference | deepseek-v4-pro | 4565 | 结构顺序仍有问题 |

第三十五届参考材料解析后约 5425 字。最新输出 3895 字，且模型审查已经给出 `overall_length_short`、`opening_section_reduced`、`guideline_section_rewritten`、`application_section_original_items_lost` 等错误。

### 2.2 模型情况

容器中实际使用：

- `LLM_MODEL_NAME=deepseek-v4-pro`
- `LLM_API_URL=https://api.deepseek.com`
- 同时存在 `GLM_API_MODEL=GLM5.1-PD_e8Qi79Xa102U2FnQ`，但最近几次 reference run 没有使用 GLM。

判断：模型不是第一瓶颈。`deepseek-v4-pro` 能在 review 中识别出自己输出的缺陷，说明主要问题是链路没有把“主底稿全文”和“最小改动约束”变成可执行上下文。

### 2.3 关键状态证据

最新失败 run 中：

- `state_json.evidence = []`
- `reference_strategy.material_plans = []`
- `references_json` 有上传文件，但第三十五届原文没有作为 content evidence 传入 draft。

这意味着 draft 阶段看不到第三十五届正文，只看到“第三十五届是主模板”这类规划摘要。模型无法稳定执行“原文打补丁”，只能凭要求仿写。

## 3. 当前 reference 链路瓶颈

### 3.1 材料角色识别过度依赖模型

位置：

- `backend/app/agent/graph.py:835`：`plan_writing` 依赖模型输出 `WritingPlan`。
- `backend/app/agent/graph.py:879`：从模型规划中读取 `material_plans`。
- `backend/app/agent/graph.py:886`：只有角色包含 `content` 的材料才进入 `uploaded_evidence`。
- `backend/app/agent/graph.py:975`：把 `uploaded_evidence` 写入 state。

问题：

模型一旦没有把第三十五届材料标为 `content`，后续 evidence 就为空。最新 run 就是这种情况。

优化方向：

在 reference 的 planning 结果之后增加确定性归一化，不新增任务类型。对明显的底稿修订式参考，系统应强制把主底稿材料绑定为 content + structure + style。

### 3.2 参考材料被画像化，底稿全文丢失

位置：

- `backend/app/agent/graph.py:82`：`MaterialCardAnalysis.content_excerpts` 最多 16 条。
- `backend/app/agent/graph.py:484`：`analyze_materials` 做材料画像。
- `backend/app/agent/graph.py:837`：planning 给模型的单份材料内容截断为 9000 字。
- `backend/app/agent/graph.py:903`：进入 evidence 的摘录再次截断为 12000 字。

问题：

当前机制适合“从材料中取事实写新稿”，不适合“保留一份底稿全文，只改少量地方”。底稿修订式任务需要完整段落、附件、版记、表格关系，不能只传摘要或短摘录。

优化方向：

在 reference 中新增内部数据通道，不作为用户侧新功能：

```python
reference_base_file_id: int | None
reference_base_text: str
reference_mode: Literal["synthesize", "base_revision"]
```

其中 `reference_mode` 只用于内部路由：

- `synthesize`：当前普通参考写作。
- `base_revision`：主底稿优先，未列明修改处保留原文。

### 3.3 draft 指令仍是“起草新公文”

位置：

- `backend/app/agent/graph.py:1326`：`draft` 节点。
- `backend/app/agent/graph.py:1332`：`reference` 的系统级指令是“按照材料使用方案起草一篇新的公文”。
- `backend/app/agent/graph.py:1346`：draft 依赖 `_evidence_text(state)`。

问题：

用户要求“尽量使用原文”时，系统级指令仍把模型推向“起草新文”。即使用户提示词说最小改动，agent 的内层语义仍是生成而不是修订。

优化方向：

reference 不新增 task_type，但 draft 指令按内部 `reference_mode` 分叉：

- `synthesize`：维持现有“基于材料起草”。
- `base_revision`：改为“以 reference_base_text 为底稿，按用户要求做最小修订并输出完整正文”。

### 3.4 校验没有比较底稿差异

位置：

- `backend/app/agent/linter.py:43`：`lint_document` 只审单篇成稿。
- `backend/app/agent/graph.py:1424`：`validate` 只审当前 draft。
- `backend/app/agent/graph.py:1433`：模型 review 仍围绕用户要求、材料方案和 evidence。

问题：

当前校验知道“这篇文是否像公文”，但不知道“它相对第三十五届底稿改了哪些不该改的内容”。因此未变更章节被重写、压缩、删除时，缺少确定性阻断。

优化方向：

在现有 validate 内增加 reference-base diff 检查，不新增新阶段：

- 章节是否缺失。
- 未授权章节相似度是否过低。
- 总长度是否明显短于底稿。
- 是否出现“按第三十五届执行”“参照上届执行”“待补充”“待定”。
- 附件数量是否异常减少。

### 3.5 自动修订会放大错误

位置：

- `backend/app/agent/graph.py:1473`：`revise` 根据问题清单全文修订。
- `backend/app/agent/graph.py:1502`：非选区修订仍输出完整正文。
- `backend/app/agent/graph.py:1527`：只用 70% 长度阈值拦截异常缩短。

问题：

如果第一版 draft 已经偏离底稿，自动修订继续让模型全文改，可能越修越远。此前二次修改中已经出现真实日期、人员名单、附件被占位符替换的问题。

优化方向：

对 `reference_mode=base_revision`：

- 自动修订只允许处理 diff_validation 指出的具体问题。
- 如果修订稿相对底稿的未授权章节差异更大，应拒绝该修订，保留上一版。
- 保护阈值不只看长度，还看章节数、附件数、占位符数、关键字段覆盖率。

### 3.6 有 error 仍可能覆盖正文

位置：

- `backend/app/agent/graph.py:1553`：`finalize` 发现 unresolved error 只追加 warning。
- `backend/app/agent/manager.py:395`：`_complete_run` 统一把 run 标记为 completed。
- `backend/app/agent/manager.py:421`：outcome 为 document 时直接覆盖 session 正文。

问题：

用户看到“完成”，但文稿可能仍有严重 error，并可能覆盖较好版本。

优化方向：

不新增用户侧功能，但内部使用现有 `outcome` 和 `proposal_content`：

- 当存在严重 error 时，将 outcome 置为 `proposal` 或阻止应用正文。
- 保留生成结果供用户查看，但不覆盖 session.article_content。
- summary 明确说明“生成了候选稿，因存在严重问题未自动应用”。

## 4. 优化目标

### 4.1 不做的事

- 不新增用户侧入口。
- 不新增新的 task_type。
- 不要求用户额外选择“底稿修订模式”。
- 不把问题继续推给提示词。

### 4.2 要做的事

- 在 reference 内部识别“底稿修订式参考”。
- 强制主底稿全文进入 draft。
- 保留普通参考写作能力，不影响综合材料生成。
- 对底稿修订式参考增加差异校验。
- 有严重 error 时不自动覆盖正文。

## 5. 设计方案

### 5.1 在 reference 内部识别 reference_mode

新增内部函数：

```python
def infer_reference_mode(requirements: str, source_materials: list[dict]) -> str:
    ...
```

识别 `base_revision` 的信号：

- 用户要求包含“原文”“底稿”“尽量使用原文”“只有提到修改的地方再改”“最小改动”“仿照前两届格式内容生成这一届”。
- 上传文件中存在明显连续届次材料，如“第三十四届”“第三十五届”。
- 用户目标是生成后一届或新版通知。

默认仍为 `synthesize`。

建议写入 state：

```python
reference_mode: str
reference_base_file_id: int | None
reference_base_text: str
reference_supporting_file_ids: list[int]
```

### 5.2 材料规划后做确定性归一化

在 `plan_writing` 得到模型规划后，增加内部修复函数：

```python
def normalize_reference_materials(state, writing_plan, strategy, material_cards):
    ...
```

规则：

1. 如果 `reference_mode=base_revision`，必须选出一个 `reference_base_file_id`。
2. 对冯如杯案例，文件名含“第三十五届”的材料优先作为主底稿。
3. 主底稿材料强制加入 roles：`content`、`structure`、`style`。
4. 主底稿 priority 强制为 `primary`。
5. 如果模型输出的 `material_cards` 不含 `content_excerpts`，用原始 `source_materials.content` 修复。
6. evidence 为空时，直接把主底稿全文注入 evidence。

这一层是确定性兜底，不能依赖模型自觉。

### 5.3 保留主底稿全文

在 `plan_writing` 或 prepare 后设置：

```python
state["reference_base_text"] = source_material["content"]
```

对底稿修订式参考：

- draft prompt 必须显式包含 `reference_base_text`。
- `_evidence_text` 可以继续提供普通 evidence，但不能替代主底稿全文。
- 如果全文太长，再按章节切块传入，而不是摘要化。

当前冯如杯材料约 5425 字，完全可以整篇进入上下文。

### 5.4 draft 指令按模式分叉

修改 `draft` 中 task_instruction：

```python
if task_type == "reference" and state.get("reference_mode") == "base_revision":
    task_instruction = (
        "以【主底稿全文】为基础进行修订。输出必须是完整正文。"
        "未被用户明确要求修改的段落、句式、附件项和版记默认保留。"
        "不要概括、不要重写、不要只写变更项。"
    )
else:
    task_instruction = "按照材料使用方案起草一篇新的公文，不得把多份材料拼成摘要。"
```

prompt 中增加：

```text
主底稿全文：
{reference_base_text}
```

这样不需要新增功能，只是让 reference 依据任务类型选择更准确的内部写法。

### 5.5 在 validate 内增加底稿差异校验

新增内部函数：

```python
def lint_reference_base_revision(base_text, draft_text, requirements, state) -> list[dict]:
    ...
```

只在 `reference_mode=base_revision` 时调用。

确定性检查：

- `指导思想`、`组织机构`、`时间安排`、`申报工作`、`评审工作`、`交流活动`、`工作要求` 是否仍存在。
- 标题是否仍为“关于启动……”。
- 是否出现“关于举办……”。
- 是否出现“继续按照第三十五届通知执行”“参照上届执行”“按原通知执行”。
- 是否出现“待补充”“待定”“〔待补充〕”。
- 附件数量是否少于主底稿，除非用户明确要求删附件。
- 总长度是否低于主底稿 85%。

进阶检查：

- 对未授权章节做文本相似度。
- 对日期、文号、电话、附件编号、人员名单等关键字段做覆盖率。
- 检查新增具体事实是否来自用户变更清单。

### 5.6 自动修订保护

在 `revise` 中增加底稿修订模式保护：

1. 修订前记录上一版 draft 的 diff score。
2. 修订后重新计算 diff score。
3. 如果修订后更短、章节更少、附件更少、占位符更多，拒绝修订稿。
4. 如果 unresolved error 仍然存在，不继续多轮全文改写。

短期可先加简单规则：

```python
if reference_mode == "base_revision":
    if len(revised) < len(reference_base_text) * 0.85:
        reject_revision()
    if count_sections(revised) < count_sections(reference_base_text):
        reject_revision()
    if count_attachments(revised) < count_attachments(reference_base_text):
        reject_revision()
```

### 5.7 落库保护

在 `_complete_run` 或 finalize 前设置：

```python
quality_gate = {
    "block_apply": True,
    "reason": "reference_base_revision_has_errors",
}
```

当 `quality_gate.block_apply = true`：

- run 可以保存为 completed。
- `final_article` 保留候选稿。
- 不覆盖 `session.article_content`。
- 写入 `proposal_content`，`proposal_status = "pending"`。

这不新增用户侧功能，数据库已有 `proposal_content`、`proposal_status` 字段，可以复用。

## 6. 最小改造路径

### Phase 1：止血版

改动范围小，优先解决当前冯如杯问题。

1. 在 `plan_writing` 后推断 `reference_mode`。
2. 如果识别为 `base_revision`，按文件名选择“第三十五届”为主底稿。
3. 强制主底稿进入 evidence，并写入 `reference_base_text`。
4. draft 中加入主底稿全文，指令改为“基于主底稿修订”。
5. validate 增加长度、章节、附件、占位符、偷懒句检查。
6. 有 error 时不覆盖正文，只保存候选稿。

预期收益：

- 解决 evidence 为空。
- 避免把底稿修订写成摘要。
- 避免严重差稿覆盖当前正文。

### Phase 2：稳态版

继续保持 reference 入口不变。

1. 抽出 `reference_mode`、`reference_base_text`、`source_bindings` 等 state 字段。
2. 将材料角色归一化逻辑单独成函数并加测试。
3. 增加章节解析函数，支持按章节差异校验。
4. 自动修订只修具体问题 span。
5. 对二次修改继承上一轮 reference 上下文。

预期收益：

- reference 同时支持普通综合写作和底稿修订式写作。
- 多轮修改不再丢事实上下文。

### Phase 3：质量与可观测性

仍不新增新入口，只增强现有面板展示。

1. 在 workflow_plan 中展示内部判断：`reference_mode`、主底稿文件、支持材料文件。
2. 在 warnings/summary 中提示未自动应用的原因。
3. 给 run 事件增加材料绑定信息，便于排查。
4. 给测试集增加“35 届生成 36 届”回归用例。

## 7. 测试建议

### 7.1 单元测试

新增或扩展：

- `test_reference_material_mode.py`
- `test_reference_base_revision_linter.py`
- `test_agent_graph.py`

覆盖：

1. 用户要求含“尽量使用原文”时，推断为 `base_revision`。
2. 文件名含“第三十五届”时，选为主底稿。
3. 模型规划 roles 为空时，系统仍能强制生成 content evidence。
4. draft prompt 包含主底稿全文。
5. 输出缺少“评审工作”时，validate 返回 error。
6. 输出长度低于底稿 85% 时，validate 返回 error。
7. 有 error 时 `_complete_run` 不覆盖 session 正文。

### 7.2 回归测试

使用第三十四届、第三十五届通知和第三十六届变更清单：

- 生成结果应保留完整七章结构。
- 输出长度不低于第三十五届 85%。
- 指导思想、评审工作、交流活动、工作要求不得被概括改写。
- 附件数量不得少于第三十五届，并包含新增附件。
- 不得出现“继续按照第三十五届通知执行”。

## 8. 推荐优先级

最高优先级：

1. reference 内部识别 `base_revision`。
2. 强制主底稿全文进入 draft。
3. validate 增加底稿差异校验。
4. 有严重 error 不覆盖正文。

第二优先级：

1. 材料角色归一化函数化。
2. 章节级 diff。
3. 自动修订保护。

第三优先级：

1. 二次修改继承 reference 上下文。
2. run 事件和 workflow_plan 可观测性。
3. 回归测试集。

## 9. 最终判断

不要新增功能，而是在 reference 工作流里增强任务识别和材料传递：

- 普通 reference 继续保持“基于材料生成”。
- 当用户语义明显是“主底稿最小修订”时，reference 内部进入 `base_revision` 策略。
- 第三十五届原文必须作为主底稿全文进入 draft，而不是被材料画像压缩掉。
- 校验必须比较输出与主底稿的差异，而不只是审一篇单独成稿。
- 严重错误结果必须保存为候选，不应覆盖当前正文。

这样对用户来说还是同一个“参考写作”，但底层能力会强很多，也更符合这次冯如杯案例的真实需求。
