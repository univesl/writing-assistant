# AI 写作助手

一个基于 React + FastAPI 的智能公文写作辅助工具，提供多种写作功能和会话管理。集成了 KnG 知识图谱 RAG 检索能力和 Qwen3-235B 大模型生成能力。

## 功能特性

### 📝 写作功能
- **快速写作**：输入关键词或主题，快速生成文章内容
- **步骤式写作**：基于产品特点、卖点等参数，分步骤生成营销文案
- **校对润色**：检查并优化现有文本，提升写作质量
- **RAG 增强**：通过 KnG 知识图谱检索参考内容，提升生成质量
- **模板支持**：支持通知、规章制度、讲话稿等多种公文模板
- **文件上传**：支持文档上传和字段信息提取

### 💬 会话管理
- 创建、删除、重命名会话
- 多会话并行编辑
- 自动保存会话内容

### 🎨 用户界面
- 响应式设计，适配不同屏幕尺寸
- 简洁直观的操作界面
- 实时内容预览

## 技术栈

### 前端（frontend）
- **框架**：React 18.x
- **构建工具**：Vite 7.x
- **HTTP 客户端**：Axios 1.13.x
- **样式**：CSS3

### 后端（backend）
- **框架**：FastAPI
- **数据库**：SQLite（SQLAlchemy ORM）
- **AI 模型**：Qwen3-235B-A22B-Instruct-2507（通义千问大模型）
- **RAG 引擎**：LightRAG（KnG 知识图谱检索）
- **服务器**：Uvicorn
- **独立提取服务**：FastAPI + FTP + JSON REST API

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           用户访问层                                     │
│                        http://localhost:5173                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        前端服务层 (React + Vite)                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                     前端应用 (端口 5173)                         │   │
│   │  ┌─────────────────┐              ┌────────────────────────┐   │   │
│   │  │   React 组件    │              │      API 客户端        │   │   │
│   │  │   MainContent   │─────────────►│   axios 请求后端       │   │   │
│   │  │   Sidebar       │              │                        │   │   │
│   │  │   FieldExtractionModal        │                        │   │   │
│   │  └─────────────────┘              └────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │ API 请求 http://localhost:9000/api
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         后端服务层 (FastAPI)                            │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                     FastAPI 应用 (端口 9000)                     │   │
│   │  ┌─────────────────┐              ┌────────────────────────┐   │   │
│   │  │   API 路由      │              │      服务层            │   │   │
│   │  │   /sessions     │─────────────►│   document_generator   │   │   │
│   │  │   /messages     │              │   kng_rag_service      │   │   │
│   │  │   /generate     │              │   document_processor   │   │   │
│   │  │   /upload       │              │                        │   │   │
│   │  └─────────────────┘              └────────────────────────┘   │   │
│   │                                                                 │   │
│   │              ┌─────────────────────────────────────────┐        │   │
│   │              │         SQLAlchemy (ORM)                │        │   │
│   │              │    Session / Message / SessionFile      │        │   │
│   │              └─────────────────────────────────────────┘        │   │
│   └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌─────────────────────────────────┐  ┌─────────────────────────────────────┐
│      KnG 服务 (RAG 检索)         │  │     模型服务 (文档生成)              │
│     http://localhost:50000      │  │  http://model.ic.h3i.buaa.edu.cn   │
│                                 │  │                                     │
│  - LightRAG 向量检索             │  │  - Qwen3-235B-A22B-Instruct-2507   │
│  - 知识图谱查询                  │  │  - Qwen3.5-397B-A17B               │
│  - 实体关系抽取                  │  │  - Qwen2.5-72B-Instruct            │
└─────────────────────────────────┘  └─────────────────────────────────────┘
```

## 数据库设计

### 会话表 (Session)

```python
class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    files = relationship("SessionFile", back_populates="session", cascade="all, delete-orphan")
```

### 消息表 (Message)

```python
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    role = Column(String(50), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    session = relationship("Session", back_populates="messages")
```

### 会话文件表 (SessionFile)

```python
class SessionFile(Base):
    __tablename__ = "session_files"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(100))
    file_size = Column(Integer)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    session = relationship("Session", back_populates="files")
```

## 核心功能实现

### RAG 检索 + 文档生成流程

```
用户输入 ──> 后端接收 ──> KnG RAG 检索 ──> 构建提示词 ──> Qwen3-235B 生成 ──> 返回结果
                │              │                              │
                │              │                              │
                ▼              ▼                              ▼
           参数校验      hybrid 模式检索              流式/非流式输出
                      (实体+关系+文本块)
```

### 文件上传与字段提取

支持通过 FTP 拉取或本地上传文档，调用 KnG 进行文档解析，提取公文关键字段信息。

## 安装与运行

### 前置要求
- Node.js 18+（前端）
- Python 3.11+（后端）
- Conda（推荐，后端依赖管理）

### 1. 克隆仓库

```bash
git clone <仓库地址>
cd writing-assistant
```

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境（可选但推荐）
python -m venv venv

# 激活虚拟环境
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动后端服务器（开发端口 8000，生产可改用 9000）
python -m uvicorn app.main:app --reload
```

后端服务将在 `http://localhost:8000`（或 `http://localhost:9000`）运行。

#### 使用 Conda 环境

```bash
# 创建并激活 Conda 环境
conda create -n writing python=3.11
conda activate writing
pip install fastapi uvicorn sqlalchemy requests

# 启动后端
python -m uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload
```

#### 独立公文字段提取服务

如果只需要"公文字段提取"能力，可以单独启动独立服务：

```bash
cd backend
python -m uvicorn app.extractor_main:app --reload --port 8001
```

独立服务默认运行在 `http://localhost:8001`，提供 FTP 拉取文件并返回 JSON 结果的接口。

### 3. 前端设置

```bash
cd frontend

# 安装依赖
npm install

# 启动前端开发服务器
npm run dev
```

前端应用将在 `http://localhost:5173`（或 `http://localhost:7500`）运行。

### 完整启动脚本

```bash
#!/bin/bash
# start_services.sh

echo "=== 启动写作助手服务 ==="

# 激活环境
source ~/miniconda3/bin/activate writing

# 启动后端
echo "[1/2] 启动后端服务..."
cd ~/writing-assistant/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload &
BACKEND_PID=$!
echo "后端服务已启动 (PID: $BACKEND_PID)"

# 启动前端
echo "[2/2] 启动前端服务..."
cd ~/writing-assistant/frontend
npm run dev &
FRONTEND_PID=$!
echo "前端服务已启动 (PID: $FRONTEND_PID)"

echo ""
echo "前端地址: http://localhost:7500"
echo "后端地址: http://localhost:9000"
echo "API 文档: http://localhost:9000/docs"
echo ""
echo "按 Ctrl+C 停止服务"

wait
```

### 依赖服务检查

写作助手依赖以下外部服务：

| 服务 | 地址 | 用途 | 检查命令 |
|------|------|------|----------|
| KnG 服务 | http://localhost:50000 | RAG 检索 | `curl http://localhost:50000/api/status` |
| 模型服务 | http://model.ic.h3i.buaa.edu.cn | 文档生成 | `curl http://model.ic.h3i.buaa.edu.cn/v1/models` |

## 项目结构

```
writing-assistant/
├── frontend/              # 前端代码
│   ├── public/            # 静态资源
│   ├── src/               # 源代码
│   │   ├── api/           # API 调用模块
│   │   │   ├── axiosConfig.js  # Axios 配置
│   │   │   ├── generateApi.js  # 生成 API
│   │   │   └── uploadApi.js    # 上传 API
│   │   ├── components/    # React 组件
│   │   │   ├── MainContent.jsx       # 主内容区
│   │   │   ├── Sidebar.jsx           # 侧边栏
│   │   │   ├── FieldExtractionModal.jsx  # 字段提取弹窗
│   │   │   └── FileUploadButton.jsx  # 文件上传按钮
│   │   ├── assets/        # 图片等资源
│   │   ├── App.jsx        # 主应用组件
│   │   └── main.jsx       # 应用入口
│   ├── package.json       # 项目配置
│   └── vite.config.js     # Vite 配置
├── backend/               # 后端代码
│   ├── app/               # 主应用包
│   │   ├── main.py        # 应用入口
│   │   ├── models.py      # 数据库模型
│   │   ├── schemas.py     # 数据验证模式
│   │   ├── database.py    # 数据库配置
│   │   ├── utils.py       # 工具函数
│   │   ├── routers/       # API 路由
│   │   │   ├── sessions.py    # 会话管理
│   │   │   ├── messages.py    # 消息管理
│   │   │   ├── generate.py    # 文档生成
│   │   │   └── upload.py      # 文件上传
│   │   └── services/      # 业务逻辑服务
│   │       ├── document_generator.py  # 文档生成服务
│   │       ├── kng_rag_service.py     # RAG 检索服务
│   │       └── document_processor.py  # 文档处理服务
│   ├── requirements.txt   # 依赖列表
│   └── writing_assistant.db  # SQLite 数据库
└── .gitignore            # Git 忽略文件
```

## API 文档

启动后端服务后，可访问以下地址查看 API 文档：
- **Swagger UI**：http://localhost:8000/docs（或 http://localhost:9000/docs）
- **ReDoc**：http://localhost:8000/redoc

### 会话管理接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/sessions | 获取所有会话 |
| POST | /api/sessions/{id} | 创建新会话 |
| DELETE | /api/sessions/{id} | 删除指定会话 |
| PUT | /api/sessions/{id} | 重命名会话 |

### 消息管理接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/messages/{session_id} | 获取消息列表 |
| POST | /api/chat | 发送消息并获取回复 |

### 文档生成接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/generate/models | 获取可用模型列表 |
| POST | /api/generate/document | 生成文档 |
| POST | /api/write/quick | 快速写作 |
| POST | /api/write/step | 步骤式写作 |
| POST | /api/write/polish | 校对润色 |

### 文件上传接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/upload/session/{session_id} | 上传文件到会话 |
| POST | /api/upload/extract-fields | 提取文件字段信息 |
| GET | /api/official-document-extractions/models | 获取字段提取模型列表 |
| POST | /api/official-document-extractions | 从 FTP 文件提取公文字段 |

### 文档生成接口示例

```http
POST /api/generate/document
Content-Type: application/json

{
    "topic": "关于开展2024年度消防安全检查的通知",
    "requirements": "正式通知格式，包含检查时间、范围和要求",
    "model_name": "Qwen3-235B-A22B-Instruct-2507",
    "use_knowledge_base": true,
    "retrieval_mode": "hybrid"
}
```

**响应**：
```json
{
    "code": 200,
    "msg": "文档生成成功",
    "data": {
        "content": "关于开展2024年度消防安全检查的通知...",
        "model_used": "Qwen3-235B-A22B-Instruct-2507",
        "retrieval_info": {
            "mode": "hybrid",
            "used_knowledge_base": true
        }
    }
}
```

### 可用模型列表

```http
GET /api/generate/models
```

**响应**：
```json
{
    "code": 200,
    "data": {
        "models": [
            {"id": "Qwen3-235B-A22B-Instruct-2507", "name": "Qwen3-235B (默认)"},
            {"id": "Qwen3.5-397B-A17B", "name": "Qwen3.5-397B"},
            {"id": "Qwen2.5-72B-Instruct", "name": "Qwen2.5-72B"}
        ]
    }
}
```

### 独立提取服务接口示例

#### 查询可用模型

```bash
curl http://localhost:8001/api/official-document-extractions/models
```

#### 通过 FTP 文件提取公文字段

```bash
curl -X POST http://localhost:8001/api/official-document-extractions \
  -H "Content-Type: application/json" \
  -d '{
    "ftp": {
      "host": "10.0.0.8",
      "port": 21,
      "username": "ftp_user",
      "password": "ftp_password",
      "remote_path": "/incoming/official.docx",
      "passive_mode": true,
      "use_tls": false,
      "timeout_seconds": 30,
      "encoding": "utf-8"
    },
    "model_name": "qwen2.5-72b",
    "include_parsed_content": false
  }'
```

成功响应示例：

```json
{
  "source_type": "ftp",
  "source_path": "/incoming/official.docx",
  "filename": "official.docx",
  "file_type": "docx",
  "model_name": "qwen2.5-72b",
  "content_length": 1234,
  "fields": {
    "标题": "关于xxx的通知",
    "主送机关": "xxx单位"
  }
}
```

## 使用说明

1. **创建会话**：点击左侧栏的"新建会话"按钮
2. **选择写作模式**：在右侧面板选择快速写作、步骤式写作或校对润色
3. **输入参数**：根据选择的模式输入相应的参数
4. **生成内容**：点击生成按钮，等待AI生成内容
5. **编辑和保存**：内容生成后可以继续编辑，系统会自动保存

## 配置

### 后端配置

在 `backend/.env` 文件中配置以下环境变量（可选）：

```
# OpenAI API 密钥（如需使用 OpenAI 模型）
OPENAI_API_KEY=your-openai-api-key

# KnG 服务地址
KNG_BASE_URL=http://localhost:50000

# 服务器端口
PORT=8000

# 数据库路径
DATABASE_URL=sqlite:///./writing_assistant.db
```

### 前端配置

前端 API 基础 URL 配置在 `frontend/src/api/axiosConfig.js` 中：

```javascript
// 默认 API 基础 URL
const API_BASE_URL = 'http://localhost:8000/api'
```

### 前端代理配置

前端开发服务器已配置代理，将 `/api` 请求转发到后端：

```javascript
// vite.config.js
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:9000',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
```

## 开发说明

### 前端开发

```bash
cd frontend

# 运行开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview

# 代码检查
npm run lint
```

### 后端开发

```bash
cd backend

# 启动开发服务器（自动重载）
python -m uvicorn app.main:app --reload

# 运行测试
python -m pytest
```

### 生产部署建议

- **后端**：Gunicorn + Uvicorn
- **前端**：Nginx 托管静态文件
- **数据库**：PostgreSQL（替代 SQLite）

## 常见问题

### 端口被占用

```bash
# 查找占用 9000 端口的进程
lsof -i :9000

# 杀掉进程
kill -9 <PID>
```

### 依赖服务未启动

```bash
# 检查 KnG 服务
curl http://localhost:50000/api/status
```

### 前端跨域问题

开发环境已通过 Vite 代理解决跨域。生产环境需要后端配置 CORS 或前后端使用相同域名。

### Conda 环境激活失败

```bash
# 确保 conda 初始化
~/miniconda3/bin/conda init bash

# 重新加载配置
source ~/.bashrc

# 手动激活
source ~/miniconda3/bin/activate writing
```

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v1.0.0 | 2024-04 | 初始版本，基础对话功能 |
| v1.1.0 | 2024-04 | 集成 KnG RAG 检索 |
| v1.2.0 | 2024-04 | 接入 Qwen3-235B 模型 |
| v1.3.0 | 2024-04 | 添加文件上传和字段提取 |

## 检索模式说明

| 模式 | 说明 |
|------|------|
| hybrid | 混合检索（推荐），结合实体、关系、文本块 |
| local | 本地检索，基于实体和文本块 |
| global | 全局检索，基于关系和全局摘要 |
| mix | 混合知识图谱和向量检索 |
| naive | 纯向量检索，不使用知识图谱 |

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题或建议，请通过以下方式联系：
- 邮箱：your-email@example.com
- GitHub：https://github.com/your-username/writing-assistant