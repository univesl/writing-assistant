# AI 写作助手

一个基于 React + FastAPI 的智能公文写作辅助工具，支持快速写作、参考写作、模板管理等功能。集成 h3i 平台 Qwen2.5-72B-Instruct 模型生成能力和 KnG 知识图谱 RAG 检索。

## 功能特性

### 写作功能
- **快速写作**：选择文体（通知/规章制度/讲话稿/通用），输入要求，AI 快速生成公文
- **Agent 快速写作**：基于 LangGraph 执行 Skill、可选 KnG 检索、提纲、草稿、校验和最多两次定向修订
- **可恢复运行**：运行事件和正文草稿持久化，支持 SSE 重连、取消、刷新恢复和安全检查点重试；同会话串行、不同会话默认最多3个并行
- **自适应参考写作**：逐份分析上传材料，按用户要求区分内容、结构、风格、背景和排除材料，再生成统一的新文稿
- **校对润色**：在编辑界面通过对话对已有文章进行修改、润色、续写
- **RAG 增强**：可选启用知识库检索（KnG），生成时参考知识库内容
- **模板管理**：上传 .docx 导出模板，设置默认模板，导出时自动套用格式
- **导出文档**：支持导出为 .docx 格式，使用自定义模板样式

### 会话管理
- 创建、删除、重命名会话
- 多会话并行编辑，内容自动保存
- 切换会话保留完整上下文

### 文件处理
- 上传参考文档（.docx/.md/.txt/.pdf）
- PDF 自动解析为 Markdown（MinerU API）
- 公文字段自动提取
- 解析内容用于参考写作

## 技术栈

### 前端
- **框架**：React 18
- **构建工具**：Vite
- **HTTP 客户端**：Axios
- **样式**：CSS3

### 后端
- **框架**：FastAPI
- **数据库**：SQLite（SQLAlchemy ORM）
- **AI 模型**：Qwen2.5-72B-Instruct（h3i 平台）
- **Agent 编排**：LangGraph；统一支持 OpenAI-compatible、OpenAI Responses、Anthropic Messages 和 Gemini
- **PDF 解析**：MinerU API（mineru.net）
- **RAG 引擎**：KnG 知识图谱检索（服务器端）
- **文档转换**：Pandoc（docx 解析 + 导出）
- **字段提取**：基于 LLM 的公文关键字段提取

## 快速开始

### 前置要求
- Node.js 18+
- Python 3.11+
- Conda（推荐）

### 1. 克隆

```bash
git clone https://github.com/univesl/writing-assistant.git
cd writing-assistant
```

### 2. 后端

```bash
cd backend

# 创建并激活 Conda 环境
conda create -n writing python=3.11
conda activate writing
pip install -r requirements.txt

# 首次部署或升级数据库
alembic upgrade head

# 配置 .env（API Key）
# backend/.env 中填入:
# LLM_API_KEY=你的h3i平台API_KEY

# 启动（端口 9000）
uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload
```

### 3. 前端

```bash
cd frontend
npm install

# 启动开发服务器（端口 7500）
npx vite --port 7500 --host
```

浏览器打开 `http://localhost:7500` 即可使用。

## 项目结构

```
writing-assistant/
├── frontend/
│   ├── src/
│   │   ├── api/           # API 调用
│   │   ├── components/    # React 组件
│   │   │   ├── StartPage.jsx     # 开始页面（写作模式选择）
│   │   │   ├── MainContent.jsx   # 编辑/润色对话
│   │   │   ├── EditorSidebar.jsx # 编辑器侧栏
│   │   │   ├── Sidebar.jsx       # 会话列表
│   │   │   └── TopNav.jsx        # 顶部导航
│   │   ├── App.jsx        # 主应用
│   │   └── App.css        # 样式
│   └── vite.config.js     # Vite 配置
├── backend/
│   ├── app/
│   │   ├── main.py        # 应用入口
│   │   ├── models.py      # 数据库模型
│   │   ├── schemas.py     # 数据验证
│   │   ├── database.py    # 数据库配置
│   │   ├── utils.py       # 工具函数
│   │   ├── routers/       # API 路由
│   │   ├── agent/         # LangGraph 状态、节点、模型/Skill 适配、运行管理
│   │   │   ├── write.py        # 快速写作 / 保存
│   │   │   ├── session.py      # 会话管理
│   │   │   ├── content.py      # 内容 / 导出
│   │   │   ├── templates.py    # 模板管理
│   │   │   ├── upload.py       # 文件上传
│   │   │   ├── generate.py     # 文档生成
│   │   │   └── official_document_extractions.py  # 公文字段提取
│   │   └── services/
│   │       ├── llm.py              # LLM 客户端（h3i OpenAI 接口）
│   │       ├── prompt_builder.py   # Prompt 构建
│   │       ├── kng_rag_service.py  # KnG RAG 检索
│   │       ├── document_generator.py  # 文档生成
│   │       ├── document_processor.py  # 文件上传/解析/字段提取
│   │       ├── mineru_service.py      # MinerU PDF → Markdown 解析
│   │       └── field_extractor.py     # 公文字段提取器
│   └── .env                # 环境变量（API Key）
├── skills/                  # 通知、制度、讲话稿、材料分析、通用公文及公文审查 Agent Skills
└── README.md
```

## API 概览

启动后端后访问 `http://localhost:9000/docs` 查看完整 Swagger 文档。

### 会话管理
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/session/list | 获取所有会话 |
| POST | /api/session/create | 创建会话 |
| DELETE | /api/session/delete/{id} | 删除会话 |
| PUT | /api/session/rename/{id} | 重命名会话 |

### 写作
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/write/quick | 快速写作（SSE 流式） |
| POST | /api/write/save | 保存对话内容 |

### Agent 运行
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/agent/runs | 创建快速写作运行 |
| GET | /api/agent/runs/{run_id} | 获取运行与文章快照 |
| GET | /api/agent/runs/{run_id}/events | 订阅或重放 SSE 事件 |
| POST | /api/agent/runs/{run_id}/cancel | 取消运行 |
| POST | /api/agent/runs/{run_id}/retry | 从检查点重试 |
| GET | /api/agent/models | 获取不含密钥的模型信息 |
| GET | /api/agent/skills | 获取运维部署的 Skill 兼容状态（只读） |

### 内容
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/content/get/{id} | 获取会话全部内容 |
| GET | /api/content/article/{id} | 获取已生成文章 |
| POST | /api/content/article/save | 保存文章 |
| GET | /api/content/export/{id} | 导出 .docx |

### 模板管理
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/templates/list | 获取模板列表 |
| POST | /api/templates/upload | 上传 .docx 模板 |
| DELETE | /api/templates/delete/{id} | 删除模板 |
| POST | /api/templates/{id}/set-default | 设为默认模板 |

### 文件上传
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/upload/session/{id} | 上传文件 |
| GET | /api/upload/session/{id}/files | 获取文件列表 |
| POST | /api/upload/file/{id}/extract | 提取公文字段 |

### 文档生成
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/generate/document | 生成文档（含 RAG） |
| POST | /api/generate/reference-write | 参考写作 |
| POST | /api/generate/reply | 生成回函 |
| GET | /api/generate/models | 获取可用模型列表 |

## 使用说明

1. **创建会话**：点击左侧栏"新建会话"
2. **选择模式**：在开始页面选择快速写作或参考写作
3. **输入要求**：选择文体 / 上传参考文档，输入写作要求
4. **可选 RAG**：快速写作和参考写作均可勾选“启用知识库检索”，KnG结果会在相关性过滤后使用
5. **生成内容**：点击"开始生成"，等待 AI 生成
6. **编辑润色**：生成后可在编辑器中修改，或通过对话进一步润色
7. **导出**：选择模板后导出为 .docx

## 配置说明

### 后端配置

在 `backend/.env` 中：

```
LLM_API_URL=https://your-openai-compatible-endpoint/v1
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=your-concrete-model-name
KNG_BASE_URL=http://127.0.0.1:50001   # 服务器 KnG 地址
```

Agent 的当前 OpenAI-compatible 模型由 `LLM_MODEL_NAME` 的具体型号标识；
其他可选模型配置见 `backend/config/models.yaml`。

模型 profile 位于 `backend/config/models.yaml`，只保存厂商、模型名和能力声明；密钥必须通过环境变量提供。

### Skill 运维边界

- 网页端只提供 Skill 列表和选择能力，不提供上传、编辑、删除或重载 Skill 的接口。
- 运维人员在服务器的 `AGENT_SKILLS_ROOT` 目录安装或修改 Skill，完成校验后重启后端使其生效；默认目录为项目的 `skills/`。
- Skill 必须采用独立目录与 `SKILL.md`，可带 `references/`、`assets/`、`scripts/`。路径穿越、重名覆盖、文件大小、所需工具和元数据都会在加载时检查。
- Skill 只能选择服务端注册的工具。随 Skill 提供的脚本不会自动运行：未登记时状态为 `degraded`；若 Skill 声明脚本为必需但执行器未登记，则状态为 `incompatible`。执行能力由运维在应用代码中注册，不能由网页用户授权。
- `GET /api/agent/skills` 只返回名称、说明、能力级别、兼容状态和资源清单，不返回服务器路径或脚本内容。

这意味着 Skill 不只是长 Prompt：它还可以声明适用任务、组合角色、按阶段加载参考资料、改变可选写作阶段，并调用受控的检索、校验、解析和渲染能力；但安全、持久化和修订上限仍由应用掌握。

Agent 的校验、持久化、取消、公开事件和修订安全上限是固定运行骨架；具体文体 Skill 决定按阶段加载哪些规则，并允许模型根据任务选择自然结构。参考写作先由材料分析 Skill 建立逐文件画像和用途方案，只有内容材料的原文摘录可以提供新稿事实，结构和风格材料只影响组织与表达。

文档导出采用固定的服务端管线：Markdown以UTF-8交给Pandoc生成DOCX，样式由数据库登记的参考模板决定。网页端不模拟Word分页，也不运行Skill自带脚本；`python-docx`仅用于自动化回读验收。导出接口只接受已登记模板，不能注入任意文件路径或Pandoc参数。

### 前端配置

`frontend/vite.config.js` 中 `/api` 代理默认指向 `http://127.0.0.1:9000`，可通过 `BACKEND_PORT` 环境变量修改。

## 许可证

MIT License
