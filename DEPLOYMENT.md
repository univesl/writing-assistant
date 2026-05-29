# Writing Assistant 部署文档

## 服务状态

### Screen会话列表

| 会话名称 | PID | 启动时间 | 状态 |
|---------|-----|---------|------|
| `writing-assistant` | 1805943 | 2026-05-28 17:22:32 | ✅ 运行中 |
| `p2p-proxy-backend` | 49443 | 2026-05-28 14:32:53 | ✅ 运行中 |
| `p2p-proxy` | 4183410 | 2026-05-28 14:26:33 | ✅ 运行中 |
| `extraction` | 4183406 | 2026-05-28 14:26:33 | ✅ 运行中 |
| `kng` | 1935795 | 2026-05-19 19:23:01 | ✅ 运行中 |

### 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端服务 | 9000 | FastAPI + 前端静态文件 |
| KNG RAG服务 | 50001 | 知识库检索服务 |
| 公文字段提取 | 8050 | 文档解析服务 |

### 访问地址

| 访问方式 | 地址 |
|---------|------|
| 本地访问 | http://localhost:9000 |
| 公网穿透(后端) | https://ab5140.xhang.buaa.edu.cn:52811 |
| 公网穿透(字段提取) | https://85af8f.xhang.buaa.edu.cn:52811 |

---

## 环境配置

### LLM配置

```bash
API_BASE=http://model.ic.h3i.buaa.edu.cn/v1
API_KEY=cXSAd9JGYdQNg59ORWdRFo4KA4AKYBomyOq2Z6vwRpWMY9P9
MODEL_NAME=Qwen2.5-72B-Instruct
```

### 数据库配置

- **类型**: SQLite
- **路径**: `/home/liubin/writing-assistant/backend/data/sqlite.db`

### 会话文件存储

- **目录**: `/home/liubin/writing-assistant/session_files/{session_id}/`
- **说明**: 上传文件按会话独立存储，删除会话时自动清理

---

## 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI | 最新 |
| 前端框架 | React + Vite | 最新 |
| 语言模型 | Qwen2.5-72B-Instruct | h3i平台 |
| 知识库 | KNG RAG | 本地部署 |
| 内网穿透 | p2p-proxy | 自定义 |

---

## 操作命令

### 查看服务状态

```bash
screen -list
ss -tlnp | grep -E "9000|50001|8050"
```

### 进入Screen会话

```bash
screen -r writing-assistant    # 后端服务
screen -r p2p-proxy-backend    # 后端内网穿透
screen -r p2p-proxy            # 字段提取内网穿透
screen -r extraction           # 字段提取服务
screen -r kng                  # KNG服务
```

### 重启后端服务

```bash
screen -XS writing-assistant quit
screen -dmS writing-assistant bash -c "cd /home/liubin/writing-assistant/backend && BACKEND_PORT=9000 KNG_BASE_URL=http://127.0.0.1:50001 /home/liubin/miniconda3/envs/writing/bin/uvicorn app.main:app --host 0.0.0.0 --port 9000"
```

### 停止服务

```bash
screen -XS writing-assistant quit
screen -XS p2p-proxy-backend quit
```

---

## 知识库信息

- **文档总数**: 552个
- **已完成索引**: 551个
- **检索模式**: local（本地知识库）
- **平均检索时间**: 20-60秒（取决于查询复杂度）

---

## 更新日志

### 2026-05-28
- ✅ 将后端服务和P2P穿透迁移到Screen持久化运行
- ✅ 配置LLM为Qwen2.5-72B-Instruct（h3i平台）
- ✅ 修复中文编码问题
- ✅ RAG检索模式改为local

### 2026-05-27
- ✅ 完成前后端端口固定配置
- ✅ 配置前端dist由后端统一提供服务
- ✅ 配置双P2P内网穿透

---

## 注意事项

1. **端口占用**: 确保端口9000、50001、8050未被其他服务占用
2. **环境变量**: 启动时需要设置BACKEND_PORT和KNG_BASE_URL
3. **日志查看**: 通过screen会话查看服务日志
4. **服务依赖**: 后端服务依赖KNG服务和LLM服务正常运行

---

## 联系信息

- 部署时间: 2026-05-28
- 部署人: Liubin
- 维护方式: 通过screen管理服务生命周期
