# AI 写作助手 — 操作手册

## 1. 系统架构

```
浏览器 (localhost:7500)
     │
     ▼  Vite 代理 (/api → :9000)
writing-assistant 后端 (FastAPI :9000)
     │
     ├── LLM API（快速写作/润色）
     │     ├── 北航小航 (api.xhang.buaa.edu.cn:28119)
     │     └── Qwen3 (10.70.247.113:4000)
     │
     ├── MinerU API（PDF 解析）
     │     └── mineru.net/api/v4
     │
     └── KnG RAG 服务 (:50001)
           └── 知识库检索 (LLM + Embedding 通过 model.ic.h3i.buaa.edu.cn)
```

---

## 2. 环境依赖

### 2.1 writing-assistant 后端

| 项目 | 内容 |
|------|------|
| **Python 环境** | `miniconda3/envs/writing` |
| **Python 路径** | `/home/liubin/miniconda3/envs/writing/bin/python3.11` |
| **uvicorn 路径** | `/home/liubin/miniconda3/envs/writing/bin/uvicorn` |
| **依赖文件** | `backend/requirements.txt` |
| **关键依赖** | fastapi, uvicorn, SQLAlchemy, pydantic, requests, openai |
| **环境变量** | `backend/.env` — 北航小航 API Key、Qwen3 API Key |

### 2.2 kng-dev（RAG 知识库）

| 项目 | 内容 |
|------|------|
| **Python 环境** | 项目自带 `.venv`（底层复用 miniconda3/envs/writing 的 Python 3.11） |
| **Python 路径** | `/home/liubin/kng-dev/kng-dev/.venv/bin/python` |
| **激活方式** | `cd /home/liubin/kng-dev/kng-dev && source .venv/bin/activate` |
| **依赖文件** | `kng-dev/pyproject.toml` |
| **关键依赖** | lightrag-hku, fastapi, uvicorn, nano-vectordb, networkx, httpx |
| **模型配置** | 通过命令行参数传入（LLM/Embedding/VLM），不依赖 `.env` |

### 2.3 writing-assistant 前端

| 项目 | 内容 |
|------|------|
| **Node.js** | 系统已安装 |
| **启动方式** | `npm run dev`（端口 7500） |
| **代理配置** | `frontend/vite.config.js` — `/api` 代理到 `http://127.0.0.1:9000` |

---

## 3. 启动服务

### 3.0 一键管理（推荐）

所有服务通过 `screen` 持久化管理，SSH 断开后继续运行。

```bash
cd /home/liubin/writing-assistant

# 启动所有核心服务（extraction + p2p-proxy + backend）
./deploy.sh start

# 查看运行状态
./deploy.sh status

# 停止所有服务
./deploy.sh stop

# 查看某个服务的日志（Ctrl+A+D 退出）
./deploy.sh logs extraction
./deploy.sh logs p2p-proxy
./deploy.sh logs backend
```

### 3.1 手动启动（逐个服务）

按以下顺序启动三个服务：

#### 3.1 启动 kng-dev（RAG 知识库）

```bash
cd /home/liubin/kng-dev/kng-dev
source .venv/bin/activate
python3 kng_server.py ./input --data-dir ./data --port 50001 \
  --llm-base-url "http://model.ic.h3i.buaa.edu.cn/v1" \
  --llm-api-key "<API_KEY>" \
  --embed-base-url "http://model.ic.h3i.buaa.edu.cn/v1" \
  --embed-api-key "<API_KEY>" \
  --embed-model-name "BAAI/bge-large-zh-v1.5" \
  --llm-model-name "Qwen2.5-72B-Instruct"
```

> API Key 从 `backend/app/services/field_extractor.py` 中获取（`qwen3-235b-h3i` 配置项）。

### 3.2 启动 writing-assistant 后端

```bash
cd /home/liubin/writing-assistant/backend
KNG_BASE_URL="http://127.0.0.1:50001" /home/liubin/miniconda3/envs/writing/bin/uvicorn \
  app.main:app --host 0.0.0.0 --port 9000
```

> `KNG_BASE_URL` 指定 kng 服务的地址和端口。如果 kng 在其他端口，相应修改即可。

### 3.3 启动 writing-assistant 前端

```bash
cd /home/liubin/writing-assistant/frontend
npm run dev
```

访问 `http://localhost:7500/` 即可使用。

---

## 4. 停止服务

```bash
# 停止前端 (PID 见 ps 或 kill %1)
pkill -f "vite"  # 谨慎使用，会杀掉所有 vite 进程

# 停止后端
kill <backend_pid>

# 停止 kng
kill <kng_pid>
```

---

## 5. 快速检查服务是否正常

```bash
# 检查端口
ss -tlnp | grep -E '7500|9000|50001'

# 测试后端 API（通过前端代理）
curl -s http://localhost:7500/api/health
curl -s http://localhost:7500/api/upload/models | python3 -m json.tool 2>/dev/null | head -5
curl -s http://localhost:7500/api/session/list | python3 -m json.tool 2>/dev/null | head -5

# 测试 kng 服务
curl -s http://127.0.0.1:50001/api/
```

---

## 6. 功能测试

### 6.1 快速写作

1. 打开 `http://localhost:7500`
2. 点击"新建会话"
3. 选择模板类型（通知/规章制度/讲话稿/通用）
4. 输入写作需求，点击"发送"

### 6.2 文件上传与字段提取

1. 上传 PDF/DOCX/MD/TXT 文件
2. 系统自动解析并提取公文字段（文件标题、来文单位、来文字号等 11 个字段）
3. 可在弹窗中查看和编辑提取结果

### 6.3 基于知识库的文档生成

1. 在输入框中描述要生成的公文主题
2. 勾选"使用知识库"
3. 系统先从 kng RAG 检索相关文档，再用 LLM 生成公文

### 6.4 修改润色

1. 切换到"修改润色"模式
2. 选中文章中的文本（可选，用于局部替换）
3. 输入修改要求，点击"发送"

---

## 7. 模型配置说明

### 7.1 各功能使用的模型

| 功能 | 模型来源 | 配置位置 |
|------|---------|---------|
| 快速写作/修改润色（默认） | 北航小航 API | `backend/.env` + `backend/llm.py` |
| 快速写作/修改润色（可选） | Qwen3 (10.70.247.113:4000) | `backend/llm.py` |
| 文件字段提取 | Qwen2.5-72B / Qwen3-235B 等 | `backend/app/services/field_extractor.py` |
| 文档生成（LLM 阶段） | model.ic.h3i.buaa.edu.cn | `backend/app/services/document_generator.py` |
| 文档生成（RAG 阶段） | kng 的 LLM + Embedding | kng 启动命令行参数 |
| PDF 解析 | MinerU API (mineru.net) | `backend/app/services/mineru_service.py` |

### 7.2 后端 API 调用方式

各 API 平台的直接调用方式，用于调试和测试。

#### model.ic.h3i.buaa.edu.cn（校内模型平台）

```bash
curl -X POST http://model.ic.h3i.buaa.edu.cn/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <API_KEY>" \
  -d '{
    "model": "Qwen3-235B-A22B-Instruct-2507",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 500,
    "temperature": 0.7
  }'
```

可用模型：`Qwen3-235B-A22B-Instruct-2507`, `Qwen3.5-397B-A17B`, `Qwen2.5-72B-Instruct`, `DeepSeek-R1-Distill-Llama-70B`, `MiniMax-M2.5`

#### 本地 Qwen3 服务（10.70.247.113:4000）

```python
from openai import OpenAI
client = OpenAI(api_key="<API_KEY>", base_url="http://10.70.247.113:4000/v1")
response = client.chat.completions.create(
    model="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
    messages=[{"role": "user", "content": "你好"}]
)
print(response.choices[0].message.content)
```

#### MinerU PDF 解析 API（mineru.net）

```python
# 1. 获取上传 URL → 2. 上传文件 → 3. 轮询结果 → 4. 下载解析结果
详见: backend/app/services/mineru_service.py
```

### 7.3 修改模型

- **字段提取模型**：修改 `field_extractor.py` 中的 `AVAILABLE_MODELS` 字典
- **文档生成模型**：修改 `document_generator.py` 中的 `MODEL_API_BASE`、`DEFAULT_MODEL`
- **写作模型**：修改 `backend/.env` 中的 `LLM_API_KEY`、`QWEN_API_KEY`

---

## 8. 常见问题

| 问题 | 可能原因 | 解决方法 |
|------|---------|---------|
| 前端页面空白 | Vite 未启动或端口冲突 | 检查 7500 端口是否占用，`pkill -f vite` 后重启 |
| 后端 9000 端口无法启动 | 端口被占用 | `ss -tlnp \| grep 9000` 查看占用进程 |
| RAG 功能（知识库生成）报错 | kng 未启动或配置不对 | 检查 50001 端口，确认 kng 启动参数中的 API Key 有效 |
| PDF 上传解析失败 | MinerU API Key 失效 | 检查 `mineru_service.py` 中的 Token |
| 字段提取失败 | LLM API 不可用 | 检查端口和 API Key，尝试切换模型（如从 qwen3-235b-h3i 切换到 qwen2.5-72b） |
| 知识库检索 500 错误 | 参数兼容性问题 | 不影响主功能，见下方说明 |

> **关于知识库检索 500**：`POST /api/generate/retrieve` 接口因 `generate.py` 传递了 `top_k` 参数而 `retrieve_knowledge_base_content()` 函数签名不兼容导致报错。这是已有的 bug，不影响通过 `POST /api/generate/document` 进行的完整文档生成流程。

---

## 9. 相关文件路径

| 文件 | 说明 |
|------|------|
| `backend/app/main.py` | 后端入口 |
| `backend/app/routers/` | API 路由 |
| `backend/app/services/` | 业务逻辑 |
| `backend/app/services/field_extractor.py` | 字段提取器（已从 former 移植） |
| `backend/app/services/kng_rag_service.py` | kng RAG 检索服务 |
| `backend/app/services/document_generator.py` | 文档生成服务 |
| `backend/app/services/document_processor.py` | 文档处理服务 |
| `backend/llm.py` | LLM 客户端 |
| `frontend/src/` | 前端源码 |
| `frontend/vite.config.js` | 前端代理配置 |