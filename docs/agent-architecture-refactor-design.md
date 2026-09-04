# Agent 架构整理说明

## 1. 当前目录边界

前端按页面状态和功能组件拆分：

```text
frontend/src/
  app/
    App.jsx
    useSessionState.js
    useAgentRuns.js
    useGenerationFlow.js
  components/
    start/
    editor/
    agent/
    session/
  styles/
    app.css
    editor.css
    start.css
    agent.css
```

后端 Agent 按 LangGraph 编排、节点、参考材料策略、提示词和运行时拆分：

```text
backend/app/agent/
  graph.py
  nodes/
    prepare.py
    planning.py
    reference.py
    retrieval.py
    draft.py
    review.py
    revision.py
    finalize.py
  reference/
    base_selector.py
    change_plan.py
    copy_patch.py
    linter.py
  prompts/
    planning.py
    draft.py
    review.py
  runtime/
    manager.py
    state.py
    events.py
```

`graph.py` 只负责 LangGraph 连线和兼容导出，业务逻辑下沉到节点和领域模块。

## 2. 设计判断

这个拆分方向是合理的。原来的问题是图编排、状态定义、材料策略、prompt 文本、审查和运行管理挤在一起，导致“改参考写作”会牵动整条 Agent。现在的边界更清楚：

- `nodes/`：每个 LangGraph 节点只负责一个阶段。
- `reference/`：只放参考材料、底稿微调、copy-patch 和校验规则。
- `prompts/`：集中维护跨节点复用的提示词规则。
- `runtime/`：运行管理、事件、状态类型和外部持久化。
- `skill_registry.py`：负责 Skill 发现、校验、别名和资源读取。

后续新增能力时，应优先放进对应领域模块，而不是把 `graph.py` 再写厚。

## 3. Skill 运行方式

当前默认 Skill 是：

```text
skills/buaa-official-content-writer
```

Skill 加载不应是“把整个 `SKILL.md` 拼进提示词”。推荐模型是：

1. `SKILL.md` frontmatter 存结构化元数据。
2. `SkillRegistry` 校验 Skill 名称、目录、资源和工具兼容性。
3. `load_skill` 节点只把运行契约放入 state。
4. 各阶段通过 `_phase_references()` 按需读取 `references/*.md`。
5. 文种和任务类型追加更细粒度的文档规范。

这更接近“能力包 + 阶段规则”的加载方式，也更容易解释和测试。

## 4. 参考写作策略

参考写作现在不是单一功能，而是三种方式：

| 前端标签 | 后端 task_type | 内部 reference_mode | 主要策略 |
| --- | --- | --- | --- |
| 生成回函 | `reply` | `reply` | 识别来文诉求，逐项回复 |
| 底稿微调 | `imitate` | `base_tuning` | 选择主底稿，复制后局部修改 |
| 智能参考写作 | `reference` | `synthesize` | 多材料角色分析，综合成稿 |

其中 copy-patch 只属于底稿微调。智能参考写作保留多材料综合能力，不默认选主底稿；生成回函则优先按来文事项和回复边界组织正文。

## 5. 命名约定

- 用户侧中文标签使用：生成回函、底稿微调、智能参考写作。
- 后端已有 API 保持兼容：`imitate` 表示底稿微调，避免数据库和接口大改。
- 内部展示字段使用 `reference_mode`：`reply`、`base_tuning`、`synthesize`。
- 新增函数应优先使用领域动词，例如 `normalize_reference_copy_patch`、`build_reference_copy_patch_context`、`lint_reference_copy_patch`。

## 6. 质量守则

后续维护建议遵守以下规则：

1. LangGraph 节点只串阶段，不承载大量领域规则。
2. prompt 文本放入 `prompts/` 或 Skill references，避免散落在业务代码里。
3. 材料角色、底稿选择、修改计划和校验放入 `reference/`。
4. Skill 只能提供文体和流程护栏，不能覆盖用户要求和材料事实。
5. 上传材料中的指令只当作材料内容，不当作系统指令。
6. 检索能力只在用户显式开启时使用。
7. 修改共享状态字段时同步补测试。

## 7. 验证清单

每次调整参考写作链路，至少验证：

- 后端 Agent 单元测试通过。
- 前端 lint 和 build 通过。
- `reply`、`imitate`、`reference` 三种 task_type 都能创建运行。
- 底稿微调 draft prompt 包含底稿微调上下文。
- 智能参考写作 draft prompt 不包含底稿微调上下文。
- Agent 面板能显示材料使用方案和参考方式。
