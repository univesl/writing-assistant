# doc-extraction 公文解析服务

上传公文文件或文本，完成三件事：**内容检查**（敏感 + 不规范表述 + 错别字，结果原样透传）、**公文字段提取**（LLM 提取 11 项标准字段）、**文件解析**（PDF/DOCX/MD/TXT → 保真纯文本）。

接口契约详见 [API.md](API.md)。

| 接口 | 说明 |
|------|------|
| `POST /api/documents/file-guard` | 文件内容审查（解析后透传检查结果） |
| `POST /api/documents/text-guard` | 批量文本审查（`{自定义id: 文本}`，上限 30 条） |
| `POST /api/documents/extractions` | 公文字段提取 |
| `GET /api/health` | 健康检查 |

## 环境要求

- Python 3.11+
- **pandoc**（DOCX 解析必需，系统包）：`apt install pandoc`（或 `yum install pandoc`）
- Python 依赖：`pip install -r requirements.txt`

## 外部服务依赖

服务本身无状态，但依赖三个外部服务，部署服务器需网络可达：

| 用途 | 地址示例 | 说明 |
|------|----------|------|
| 内容检查 | `https://…/all-check` | 敏感+不规范+错别字三合一，响应原样透传 |
| PDF 解析 | `https://…`（MinerU） | PDF 转文本 |
| 字段提取 LLM | `https://…/v1` | OpenAI 兼容接口（GLM 等） |

具体地址在 `.env` 中配置。若调用报 SSL 证书错误（自签环境），需将对应 CA 证书加入系统信任库（如 `update-ca-certificates`）。

## 配置

```bash
cp .env.example .env   # 然后填写 API key 等必填项，变量说明见 .env.example 注释
```

## 启动

```bash
./start-screen.sh      # 推荐：screen 后台运行（自动重启旧会话）
# 或
./start.sh             # 前台运行
```

默认监听 `0.0.0.0:8050`，日志写入 `~/logs/wa-doc-extract.log`（可用环境变量覆盖，见 `.env.example`）。

验证：

```bash
curl http://127.0.0.1:8050/api/health
```

## OCR（可选依赖说明）

PDF 解析时会对**首页左上角**做区域 OCR（识别信笺抬头的文号、单位等补充信息，供字段提取参考）。

- **需要下载/安装的内容只有 pip 包**（`requirements.txt` 已包含，无单独的模型文件要下载）：
  - `rapidocr_onnxruntime` —— OCR 引擎，onnx 模型权重随 pip 包自带
  - `PyMuPDF` —— PDF 页面渲染
  - `numpy` / `Pillow` —— 图像预处理
- Linux 下 `onnxruntime` 需要 `libgomp1`（一般系统自带，缺则 `apt install libgomp1`）
- **不安装也行**：代码在 import 失败时自动降级跳过 OCR，不影响主流程（响应中对应字段会带 `OCR依赖未安装` 标记）
- 可调参数（环境变量）：`OCR_TOP_LEFT_REGION`（归一化区域 `左,上,右,下`，默认 `0,0,0.42,0.18`）、`OCR_RENDER_SCALE`（渲染倍率，默认 3）

## 数据与持久化

**无本地数据留存**：上传文件写入系统临时目录，请求结束即删除；无数据库、无上传目录积累。仓库中不含任何解析数据文件。

## 目录结构

```
├── API.md               # 接口文档（对接调用方用）
├── README.md            # 本文件（部署用）
├── requirements.txt
├── .env.example         # 配置模板
├── start.sh / start-screen.sh
├── app/
│   ├── extractor_main.py        # FastAPI 入口
│   ├── routers/                 # 路由（三个接口）
│   ├── schemas.py               # 请求/响应模型
│   └── services/
│       ├── official_document_extractor.py   # 检查透传 + 字段提取编排
│       ├── document_processor.py            # 文件解析（pandoc/MinerU/文本）+ 字符保真
│       ├── mineru_service.py                # MinerU 客户端
│       └── region_ocr.py                    # 可选：首页抬头 OCR
└── tests/
```
