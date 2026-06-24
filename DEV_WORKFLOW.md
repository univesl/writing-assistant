# 开发工作流程规范

## 概述

本项目在三个环境间同步开发：
- **本地开发机** (Windows)
- **A100 服务器** (Linux, SSH: `A100`)
- **GitHub 仓库** (`https://github.com/univesl/writing-assistant.git`)

**本文件仅作为本地开发参考，不提交到 GitHub 仓库。**

## 核心原则

1. **不要直接在服务器上修改代码**。服务器仅用于部署和测试。
2. **所有修改先在本地完成**，测试通过后推送到 GitHub，再从服务器拉取部署。
3. **三地代码按需同步**。

## 端口固定说明（重要）

所有端口已固定，**不要随意修改**：

| 服务 | 端口 | 说明 |
|------|------|------|
| **后端 (FastAPI)** | **9000** | 本地和服务器统一使用 9000，**必须带 `--reload`** |
| **前端 (Vite 开发)** | **7500** | 本地开发前端端口，固定不变 |
| **前端 (生产)** | 80 (nginx) | 服务器上 build 产物由 nginx 托管 |
| **KnG RAG** | 50001 | 仅服务器可访问 |
| **公文字段提取** | 8050 | 服务器上独立服务 |

**本地启动前后端时，必须严格使用以上端口。端口被占用则先 kill 再启动，不能改端口。**

## 分支策略

- **`main`** — 稳定分支，生产环境代码。
- **`dev`** — 开发分支，日常开发在此进行。

开发流程：
```
本地 dev 开发 → git push → GitHub dev → 服务器拉取 dev → 测试 → 合并 main → 服务器拉取 main
```

### 标准开发流程

```bash
# 1. 切换到 dev 分支
git checkout dev
git pull github dev

# 2. 本地开发修改

# 3. 提交并推送到 dev
git add <files>
git commit -m "feat: 描述改动内容"
git push github dev

# 4. 服务器拉取 dev 测试
ssh A100 "cd ~/writing-assistant && git pull github dev"

# 5. 测试通过后合并到 main
git checkout main
git pull github main
git merge dev
git push github main

# 6. 服务器拉取 main
ssh A100 "cd ~/writing-assistant && git pull github main"
```

### 提交信息规范

```
<type>: <简短描述>
类型: feat / fix / refactor / docs / chore / style / test
示例: feat: 添加模板管理功能
      fix: 修复文档导出编码问题
```

---

## 本地开发环境

### LLM 模型 API

1. **当前使用的模型**: `Qwen2.5-72B-Instruct`，通过 h3i 平台调用（`http://model.ic.h3i.buaa.edu.cn/v1`），API Key 在 `backend/.env` 中。
2. **本地必须关闭代理**才能访问 h3i（开了代理会连不上）。
3. **h3i 偶见 502**：curl 直调正常但 OpenAI SDK 有时失败，属已知环境问题，不影响服务器。
4. 快速测试 h3i 是否可达：
   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://model.ic.h3i.buaa.edu.cn/v1/models
   # 401 = 可达（无 key），000 = 不可达
   ```

### 本地启动前后端

**每次启动前先确保端口未被占用。如果被占用，先 kill 再启动，不能改端口。**

```bash
# === 1. 清理旧进程（杀掉占用了 9000 和 7500 端口的进程）===

# Windows PowerShell：
# 杀掉占用 9000 端口的所有进程
Get-NetTCPConnection -LocalPort 9000 -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

# 杀掉占用 7500 端口的所有进程
Get-NetTCPConnection -LocalPort 7500 -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
```

```bash
# === 2. 启动后端（端口 9000，带 --reload）===
cd D:/writing-assistant/backend
uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload
```

```bash
# === 3. 启动前端（端口 7500，固定）===
cd D:/writing-assistant/frontend
npx vite --port 7500 --host
```

```bash
# === 4. 浏览器打开 ====
http://localhost:7500
```

### 关于 --reload（必须使用）

**本地和服务器的后端都必须在启动时加 `--reload` 参数。**

原因：`--reload` 让 uvicorn 自动监听文件变化。当从 GitHub 拉取新代码后，后端会自动重启加载新代码，**不需要手动 kill 再启动**。如果不加 `--reload`，拉取代码后服务仍然是旧代码，不会生效。

- ✅ `uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload`
- ❌ `uvicorn app.main:app --host 0.0.0.0 --port 9000`（没有 --reload，代码更新后不会自动重启）

### vite.config.js 说明

前端 `/api` 代理默认指向 `http://127.0.0.1:9000`（与后端端口一致），可通过环境变量覆盖：
- `BACKEND_PORT` — 后端端口（默认 9000）
- `FRONTEND_PORT` — 前端端口（默认 7500）

### 本地其他依赖

| 工具 | 说明 | 安装方式 |
|------|------|----------|
| **Pandoc** | 用于 docx 解析和文档导出格式转换 | [pandoc.org](https://pandoc.org/installing.html) |
| **Conda** | 后端 Python 环境管理（Python 3.11） | `conda create -n writing python=3.11` |

---

## A100 服务器运维指南

### 服务概况

| 服务 | Screen 会话 | 端口 | 说明 |
|------|------------|------|------|
| **后端** | `writing-assistant` | 9000 | uvicorn + FastAPI，带 `--reload` |
| **KnG 知识库** | `kng` | 50001 | kng-rag Docker 容器 |
| **内网穿透** | `p2p-proxy` | - | frp |
| **公文字段提取** | `extraction` | 8050 | 文档解析服务 |

### 服务器上 kill 进程的规则

**只能 kill 用户 `liubin` 的进程。** 非 liubin 的进程不能动，不确定时先问。

```bash
# 查看进程所属用户
ps aux | grep uvicorn
# 确认只有 liubin 的进程再 kill

# 正确：只 kill liubin 的 uvicorn 进程
pkill -u liubin -f "uvicorn app.main:app"

# 错误：无用户限制会杀到别人的进程（禁止使用）
# pkill -f "uvicorn"          # ❌
# kill -9 <pid>（未确认用户）  # ❌
```

### 重启后端

```bash
# 1. 杀掉旧的后端进程（只杀 liubin 的）
pkill -u liubin -f "uvicorn app.main:app" 2>/dev/null

# 2. 创建新的 screen 会话（端口 9000）
screen -dmS writing-assistant bash -c '\
  source /home/liubin/miniconda3/etc/profile.d/conda.sh && \
  conda activate writing && \
  cd /home/liubin/writing-assistant/backend && \
  KNG_BASE_URL=http://127.0.0.1:50001 \
  uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload \
  2>&1 | tee /tmp/writing_backend.log'
```

> **`--reload` 是必须的，不能省略。** 有了它，`git pull` 拉取代码后 uvicorn 自动检测文件变化并重载，不需要手动重启服务。

### 构建前端

```bash
cd ~/writing-assistant/frontend
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
npm run build
# build 产物在 dist/，由 nginx 托管在端口 80
```

### 验证服务

```bash
# 后端健康检查
curl http://localhost:9000/api/health

# KnG 服务
curl http://localhost:50001/api/status

# screen 会话列表
screen -list
```

### Screen 常用操作

```bash
screen -r writing-assistant    # 进入会话
# Ctrl+A D                     # 分离（不停止服务）
screen -XS writing-assistant quit  # 杀掉会话
```

---

## KnG 知识库服务

**KnG 只能服务器上运行，本地无法调试和测试。**

### 架构

```
用户请求 → /api/write/quick（仅 use_rag=true 时触发）
  → kng_rag_service.py（KnG 客户端，超时 15s）
    → HTTP 调用 A100 KnG 容器 (:50001)
  → prompt_builder.py（拼装 RAG 结果 + 需求 → prompt）
  → LLM 调用（h3i 平台 Qwen2.5-72B-Instruct）
```

### 前端 RAG 开关

- 开始界面快速写作模式下有 **"启用知识库检索"** 复选框，**默认关闭**。
- 勾选后 API 带 `use_rag: true`，后端才触发 KnG 检索。
- edit 模式不做 RAG。

| 文件 | 作用 |
|------|------|
| `backend/app/services/kng_rag_service.py` | KnG 客户端，超时 15s |
| `backend/app/services/prompt_builder.py` | 统一 prompt 构建 |
| `backend/app/routers/write.py` | 写作 API 路由 |
| `backend/llm.py` | LLM 客户端（h3i OpenAI 兼容接口） |

---

## 文件解析服务

### MinerU PDF 解析

PDF 文件上传后，由 `mineru_service.py` 调用 MinerU 在线服务（mineru.net）将 PDF 转换为 Markdown 文本。

- API 地址：`https://mineru.net/api/v4`
- API Token 配置在 `backend/app/services/mineru_service.py` 中
- Token 约 60 天过期，过期需更新

### 文档解析流程

```
上传文件 → /api/upload/session/{id}
  ├── PDF → MinerU API → Markdown
  ├── DOCX → pandoc → Markdown
  ├── MD/TXT → 直接读取
  └── 解析后可选项：LLM 字段提取（标题/主送机关/文号等）
```

| 文件 | 作用 |
|------|------|
| `backend/app/services/mineru_service.py` | MinerU PDF 解析客户端 |
| `backend/app/services/document_processor.py` | 文档统一解析入口 |
| `backend/app/services/field_extractor.py` | 公文字段提取（基于 LLM） |
| `backend/app/routers/upload.py` | 上传 API |

---

## GitHub 代理配置

服务器 git 通过 SSH RemoteForward 转发到本地 Clash：

```bash
# 服务器已配置，无需手动操作
git config --global http.proxy http://127.0.0.1:7897
```

本地 git 推荐同样配置（否则 push 到 GitHub 可能超时）：
```bash
git config --global http.proxy http://127.0.0.1:7897
```

---

## 注意事项

1. **端口不能改**：后端 9000、前端 7500 是固定端口，所有配置（内网穿透、nginx、代理）都依赖此设置。
2. **启动前先 kill**：端口被占用时先 kill 旧进程再启动，不要改端口号。
3. **服务器上只杀 liubin 的进程**：不确定时先 `ps aux | grep <进程名>` 确认用户，非 liubin 的不要动。
4. **API Key** 在 `backend/.env` 中（h3i 平台）。
5. **Conda 环境**：`conda activate writing`（Python 3.11）。
6. **h3i 502 问题**：本地偶尔报 502，不影响服务器。
