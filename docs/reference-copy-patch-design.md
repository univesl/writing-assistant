# 参考写作三模式设计

## 1. 目标

参考写作不再是唯一流程，而是同一入口下的三种明确方式：

1. `reply`：生成回函。识别来文事项和诉求，逐项形成正式回复。
2. `imitate`：底稿微调。选定一个主底稿，尽量保留原文结构和大部分正文，只做必要修改。
3. `reference`：智能参考写作。分析多份材料的内容、结构、风格和背景用途，综合生成新文稿。

三种方式共享上传、材料解析、Skill、检索和审查能力，但材料使用策略不同。尤其是底稿微调才进入 copy-patch 链路，智能参考写作不能默认选择主底稿。

## 2. Skill 加载

运行时默认使用目录下的统一 Skill：

```text
skills/buaa-official-content-writer
```

旧 Skill 名称只作为兼容别名映射到这个 Skill，例如：

- `official-document-writing`
- `notice-writing`
- `regulation-writing`
- `speech-writing`
- `official-document-review`
- `reference-material-analysis`

加载方式不是把完整 `SKILL.md` 直接拼进每个提示词。当前做法是：

1. `SKILL.md` frontmatter 保存 app 侧元数据，包括 workflow、阶段引用和文种引用。
2. prompt 中只放 Skill 运行契约：名称、用途、适配范围。
3. 各阶段按需读取 `references/*.md`，例如 planning、draft、validation、revision。
4. 文种和任务类型会追加精确引用，例如回函追加 `references/doc_types/letter.md`，通知追加 `notice.md`。

这样 Skill 更像能力与规则包，而不是一个无边界提示词块。

## 3. 三种参考方式

### 3.1 生成回函

后端任务类型：`reply`

内部 `reference_mode`：`reply`

材料策略：

- 上传材料优先视为来文、附件或背景说明。
- 必须识别对方诉求、需回应事项、事实边界和不能承诺的内容。
- 输出应是正式回函，不把来文改写成通知、总结或材料摘要。

Skill 侧追加 `references/doc_types/letter.md`。

### 3.2 底稿微调

后端任务类型：`imitate`

内部 `reference_mode`：`base_tuning`

材料策略：

- 必须选择一个主底稿。
- 主底稿强制承担 `content`、`structure`、`style` 基础作用。
- 其他材料只作为支持依据、局部变更来源或排除材料。
- 先复制主底稿，再按用户要求、届次年份等稳定变量和支持材料做局部修改。
- 未被明确要求修改的段落、附件、编号和表述默认保留。

底稿微调专用字段：

```python
reference_base_file_id: int | None
reference_base_text: str
reference_supporting_file_ids: list[int]
reference_change_plan: dict[str, Any]
reference_working_copy: str
reference_patch_log: list[dict[str, Any]]
source_bindings: list[dict[str, Any]]
```

copy-patch、底稿校验和主底稿选择只在 `task_type == "imitate"` 时启用。

### 3.3 智能参考写作

后端任务类型：`reference`

内部 `reference_mode`：`synthesize`

材料策略：

- 逐份判断材料角色：`content`、`structure`、`style`、`background`、`negative_example`、`irrelevant`。
- 只有被规划为 `content` 的材料摘录可以成为新稿事实。
- `structure` 和 `style` 材料只提供组织方式或表达风格，不能带入旧年份、旧人名、旧单位、旧数字和旧事项。
- 不默认选主底稿，也不把多份材料机械拼接成摘要。

这条路径适合从多份参考材料重新组织新文稿，而不是修订某一份旧稿。

## 4. 状态与可观测性

`reference_mode` 保留为内部可观测字段，用于面板展示和 prompt 分支：

```python
reference_mode: "reply" | "base_tuning" | "synthesize" | ""
```

`workflow_plan.material_plan` 应展示：

- `reference_mode`
- `reference_base_file_id`
- `reference_base_filename`
- `reference_supporting_file_ids`
- `reference_change_plan`
- `source_bindings`
- `materials`

用户可以看到系统当前按哪种参考方式理解材料，方便排查“为什么没有按底稿改”或“为什么没有综合多份材料”。

## 5. 检索规则

KnG 和 web 只在前端显式勾选后使用。

- 未勾选时，不在参考链路内部偷偷启用检索。
- 底稿微调中，检索只能辅助核对或补足变更点，不能覆盖主底稿。
- 智能参考写作中，检索证据和上传材料都要经过材料使用方案约束。
- 回函中，检索只能补足政策依据或事实背景，不能替来文创造诉求。

## 6. 测试重点

1. 默认 Skill 加载 `buaa-official-content-writer`。
2. 旧 Skill 名称能通过别名映射到统一 Skill。
3. prompt 不包含完整 `SKILL.md` 主体，只包含运行契约和阶段引用。
4. `reply` 追加回函文种引用。
5. `imitate` 选择主底稿并生成 copy-patch 上下文。
6. `reference` 不触发主底稿选择和 copy-patch 上下文。
7. 面板展示三种 `reference_mode` 的中文标签。
