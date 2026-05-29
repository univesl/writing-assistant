# 公文字段提取服务（Base64 方式）

独立的 HTTP API 服务，接收 Base64 编码的文件内容，解析并提取公文结构化字段。

---

## 1. 服务部署

### 1.1 环境依赖

| 项目 | 内容 |
|------|------|
| **Python** | miniconda3/envs/writing (Python 3.11) |
| **路径** | `/home/liubin/miniconda3/envs/writing/bin/python3.11` |
| **服务目录** | `/home/liubin/writing-assistant/doc-extraction-server/` |

### 1.2 启动服务

```bash
cd /home/liubin/writing-assistant/doc-extraction-server
/home/liubin/miniconda3/envs/writing/bin/uvicorn \
  app.extractor_main:app --host 0.0.0.0 --port 8050
```

### 1.3 检查服务是否运行

```bash
curl -s http://localhost:8050/api/documents/models | python3 -m json.tool
```

正常应返回可用模型列表。

---

## 2. 内网穿透（对外暴露）

使用 `p2p-proxy` 工具将本地服务暴露到公网。

```bash
# 语法
# p2p-proxy [clientId] [machineCode] [localAddr]

# doc-extraction-server 公网暴露（当前使用）
/home/liubin/kng-dev/kng-dev/p2p-proxy "85af8f" "85af8f2c-a929-bca0-80a6-c9599a227430" "127.0.0.1:8050"
```

参数说明：
- `clientId`：`85af8f`（subdomain）
- `machineCode`：`85af8f2c-a929-bca0-80a6-c9599a227430`
- `localAddr`：本地服务地址（`127.0.0.1:8050`）

执行后公网访问地址：`https://85af8f.xhang.buaa.edu.cn:52811`

---

## 3. API 说明

### 3.1 接口地址

**Base URL**（内网）：`http://10.70.247.28:8050`
**Base URL**（公网）：`https://85af8f.xhang.buaa.edu.cn:52811`（通过 p2p-proxy 穿透）
**Base URL**（通过 p2p-proxy 暴露后）：由 p2p-proxy 输出的公网地址决定

### 3.2 获取可用模型

```
GET /api/documents/models
Content-Type: application/json
```

响应示例：
```json
{
  "models": [
    {"name": "qwen2.5-72b", "display_name": "Qwen2.5-72B (本地)"},
    {"name": "qwen3-235b", "display_name": "Qwen3-235B (本地)"},
    {"name": "qwen3-235b-h3i", "display_name": "Qwen3-235B (推荐)"},
    {"name": "qwen3.5-397b", "display_name": "Qwen3.5-397B"},
    {"name": "qwen2.5-72b-h3i", "display_name": "Qwen2.5-72B"},
    {"name": "deepseek-r1-70b", "display_name": "DeepSeek-R1-70B"}
  ]
}
```

### 3.3 提取字段

```
POST /api/documents/extractions
Content-Type: application/json
```

**请求体**：

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `filename` | 是 | string | 文件名（含扩展名，如 report.pdf） |
| `content_base64` | 是 | string | 文件内容的 Base64 编码 |
| `model_name` | 否 | string | 提取模型，默认 `qwen2.5-72b` |
| `include_parsed_content` | 否 | boolean | 是否返回解析正文，默认 `false` |

**成功响应**（HTTP 201）：

```json
{
  "filename": "xxx.pdf",
  "file_type": "pdf",
  "model_name": "qwen2.5-72b",
  "content_length": 1632,
  "fields": {
    "文件标题": "...",
    "来文单位": "...",
    "来文字号": "...",
    "原文日期": "...",
    "紧急程度": "",
    "阅文/办文": "...",
    "时间节点": "...",
    "收文日期": "...",
    "关联文件": "...",
    "备注": "",
    "是否需明确建议牵头单位": "..."
  }
}
```

未识别到的字段值返回空字符串。

### 3.4 支持的文件类型

`pdf`、`docx`、`md`、`txt`

---

## 4. 调用示例

### macOS / Linux

```bash
curl -X POST http://10.70.247.28:8050/api/documents/extractions \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "公文.pdf",
    "content_base64": "'"$(base64 -w0 /path/to/公文.pdf)"'",
    "model_name": "qwen2.5-72b"
  }'
```

### Windows（PowerShell）

```powershell
$fileBase64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\path\to\公文.pdf'))
$body = @{ filename="公文.pdf"; content_base64=$fileBase64; model_name="qwen2.5-72b" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://10.70.247.28:8050/api/documents/extractions" -Method Post -Body $body -ContentType "application/json"
```

### Python

```python
import base64, requests

with open("公文.pdf", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

resp = requests.post(
    "http://10.70.247.28:8050/api/documents/extractions",
    json={"filename": "公文.pdf", "content_base64": b64, "model_name": "qwen2.5-72b"},
    timeout=300,
)
print(resp.json())
```

---

## 5. 文件存储

用户上传的文件会保存在服务器以下目录：

```
/home/liubin/writing-assistant/doc-extraction-server/uploads/
```

- 每次调用字段提取接口，文件都会保存到此目录
- 文件名保持原始名称
- 文件不会被自动清理，需定期手动维护

---

## 6. 注意事项

- 大文件建议不超过 50MB（Base64 编码后约膨胀 37%）
- curl 加上 `--max-time 300` 防止超时
- 字段提取依赖 LLM API（`model.ic.h3i.buaa.edu.cn`），需要该服务可访问
- PDF 解析依赖 MinerU 云端 API（`mineru.net`），需要 Token 有效
- 部署时确保 8050 端口未被占用：`ss -tlnp | grep 8050`
- 如使用 p2p-proxy 对外暴露，需确保 p2p-proxy 服务端已配置好对应的 clientId 和 machineCode