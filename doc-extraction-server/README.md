# doc-extraction 公文解析服务

无状态的公文解析微服务，对外提供三类能力：

1. **内容检查**（`file-guard` / `text-guard`）：解析文件 → 原文交给上游二合一检查接口（敏感 + 不规范表述 + 错别字），**响应原样透传**给调用方，不增删改任何字段；
2. **公文字段提取**（`extractions`）：LLM 从解析正文中提取 11 项标准字段（文件标题、来文单位、来文字号、原文日期等）；
3. **文件解析**：PDF / DOCX / MD / TXT → 纯文本（逐字符保真，不引入转义符或 Markdown 标记）。

接口契约（对接调用方）详见 [API.md](API.md)。

---

## 1. 依赖

### 系统依赖

| 依赖 | 必需性 | 安装 | 用途 |
|------|--------|------|------|
| Python ≥ 3.11 | 必需 | — | 运行时 |
| **pandoc** | 必需（DOCX 解析） | `apt install pandoc` | DOCX → 纯文本 |
| libgomp1 | OCR 需要（一般自带） | `apt install libgomp1` | onnxruntime 运行库 |

### Python 依赖（`pip install -r requirements.txt`）

| 包 | 用途 |
|----|------|
| fastapi / uvicorn / pydantic | Web 框架与服务 |
| python-multipart | 文件类请求体解析 |
| requests | 调用上游服务 |
| python-dotenv | 加载 .env 配置 |
| PyMuPDF（fitz） | PDF 页面渲染（供 OCR） |
| rapidocr_onnxruntime | OCR 引擎，**模型权重随 pip 包自带，无需单独下载模型文件** |
| numpy / Pillow | OCR 图像预处理 |

> OCR 整体为**可选依赖**：未安装时代码自动降级跳过，不影响主流程。
> 跑单元测试另需 `pip install httpx`（fastapi TestClient 依赖）。

### 外部服务依赖（部署服务器需网络可达，地址配在 `.env`）

| 用途 | 协议 | 说明 |
|------|------|------|
| 内容检查 | HTTPS | 二合一接口（敏感+不规范+错别字），结果透传 |
| PDF 解析 | HTTPS | MinerU 服务（PDF → Markdown） |
| 字段提取 LLM | HTTPS | OpenAI 兼容 /chat/completions，**需支持流式（stream）**——非流式长请求会被网关 60s 超时掐断 |

自签证书环境若报 SSL 错误，将 CA 证书加入系统信任库（`update-ca-certificates`）。

---

## 2. 代码功能与结构

### 数据流

```
text-guard（批量文本）
    │ {自定义id: 文本}，逐条
    ├──────────────────────────────→ 内容检查(二合一) ──原样──→ 响应
    │
file-guard（文件）
    │ 解析(见下) → 纯文本 ──────────→ 内容检查(二合一) ──原样──→ review 字段
    │（parsed_content 一并返回，作 issues 位置锚定基准）
    │
extractions（字段提取）
    │ 解析 → 纯文本 ──(首页抬头OCR补充，可选)──→ LLM 流式提取 → 11 项字段
```

文件解析分流：**PDF** → MinerU（markdown）→ 清洗为纯文本（还原转义、剥离 markdown 标记、表格转制表符行），并行做首页左上角 OCR；**DOCX** → pandoc `-t plain --wrap=none`（保真）+ ASCII 表格还原；**TXT/MD** → 直接读取（UTF-8/GB18030 自动识别）。

### 目录与模块职责

```
doc-extraction-server/
├── start.sh / start-screen.sh        # 启动脚本（前台 / screen 后台），读 .env
├── .env.example                      # 配置模板（变量说明见注释）
├── requirements.txt
├── API.md                            # 对外接口文档
└── app/
    ├── extractor_main.py             # FastAPI 入口：加载 .env、CORS、健康检查、异常处理
    ├── schemas.py                    # 请求/响应模型（review 为 dict——透传不固定字段）
    ├── routers/
    │   └── official_document_extractions.py   # 三个接口的路由与入参校验
    └── services/
        ├── official_document_extractor.py     # 编排核心：
        │        ├─ call_all_check()     内容检查调用（3 次退避重试），响应原样返回
        │        ├─ extract_from_base64() 字段提取编排（临时文件、并发解析+OCR）
        │        └─ guard_file_from_base64() 文件审查编排（临时文件，用后即删）
        ├── document_processor.py      # 解析分流 + 字符保真（strip_markdown_escapes /
        │                              #   strip_markdown_syntax / flatten_ascii_tables）
        ├── field_extractor.py         # LLM 字段提取：流式调用聚合（UTF-8 显式解码）、
        │                              #   精简 prompt、429/5xx/超时/空结果重试
        ├── mineru_service.py          # MinerU 客户端（提交任务→轮询→取 markdown）
        └── region_ocr.py              # 可选：PDF 首页左上角 OCR（RapidOCR），缺依赖自动降级
```

### 关键设计点

| 设计 | 原因 |
|------|------|
| 内容检查纯透传（`return response.json()`） | 调用方所见即上游所得；上游字段演进无需改本服务 |
| DOCX 用 pandoc plain 而非 markdown | markdown 输出会给 `_ @ "` 等加转义、把弯引号降级为直引号、粗体变 `**`，污染检查结果 |
| MinerU 输出清洗 | 同上：markdown 标记/转义/HTML 实体/管道表格需剥离为纯文本 |
| 字段提取用流式 | 上游网关对非流式请求 60s 超时，LLM 深度思考会被 504 掐断；流式只限读间隔 |
| 流式响应显式 `response.encoding="utf-8"` | SSE 不带 charset 时 requests 按 latin-1 解码，中文全乱码导致字段匹配失败 |
| 上传文件走系统临时目录、请求结束即删 | 服务承诺不留存用户数据 |

---

## 3. 配置与启动

```bash
cp .env.example .env    # 填写 FIELD_EXTRACTION_API_KEY 等必填项
./start-screen.sh       # screen 后台运行（推荐）
./start.sh              # 或前台运行
curl http://127.0.0.1:8050/api/health   # 验证
```

默认 `0.0.0.0:8050`；`PYTHON_BIN`/`PORT`/`HOST`/`LOG_FILE` 可在 `.env` 覆盖（默认 `python3` / `8050` / `./doc-extract.log`）。

OCR 可调参数：`OCR_TOP_LEFT_REGION`（归一化区域，默认 `0,0,0.42,0.18`）、`OCR_RENDER_SCALE`（渲染倍率，默认 3）。

## 4. 测试

```bash
pip install httpx
python -m unittest discover tests -v    # 契约测试为 mock 上游，无需外部服务
```

## 5. 数据说明

**无本地数据留存**：上传文件写入系统临时目录、请求结束即删除；无数据库。仓库中不含任何解析数据文件。
