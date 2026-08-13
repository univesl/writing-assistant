# AI 写作助手

一个基于 React + FastAPI 的智能公文写作辅助工具，支持快速写作、参考写作、模板管理等功能。集成 h3i 平台 Qwen2.5-72B-Instruct 模型生成能力和 KnG 知识图谱 RAG 检索。

## 功能特性

### 写作功能
- **快速写作**：选择文体（通知/规章制度/讲话稿/通用），输入要求，AI 快速生成公文
- **参考写作**：上传参考文档，生成回函、仿写或基于内容生成相关公文
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
4. **可选 RAG**：勾选"启用知识库检索"使用 KnG 增强生成（仅快速写作模式）
5. **生成内容**：点击"开始生成"，等待 AI 生成
6. **编辑润色**：生成后可在编辑器中修改，或通过对话进一步润色
7. **导出**：选择模板后导出为 .docx

## 配置说明

### 后端配置

在 `backend/.env` 中：

```
LLM_API_KEY=your-h3i-api-key
MODEL_API_KEY=your-h3i-api-key
KNG_BASE_URL=http://127.0.0.1:50001   # 服务器 KnG 地址
```

### 前端配置

`frontend/vite.config.js` 中 `/api` 代理默认指向 `http://127.0.0.1:9000`，可通过 `BACKEND_PORT` 环境变量修改。

## 许可证

MIT License
