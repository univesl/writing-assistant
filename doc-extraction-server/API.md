# 公文字段提取接口文档

## 基本信息

- **接口地址**: `https://85af8f.xhang.buaa.edu.cn:52811`
- **请求方式**: RESTful HTTP API
- **数据格式**: 请求/响应均为 JSON
- **文件内容**: Base64 编码传输

---

## 快速开始

### 提取公文字段

```bash
curl -k -X POST https://85af8f.xhang.buaa.edu.cn:52811/api/documents/extractions \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "公文.pdf",
    "content_base64": "base64编码的文件内容"
  }'
```

### 响应示例（HTTP 201）

```json
{
  "filename": "公文.pdf",
  "file_type": "pdf",
  "content_length": 2048,
  "fields": {
    "文件标题": "关于印发《...》的通知",
    "来文单位": "北京航空航天大学",
    "来文字号": "北航校字〔2022〕42 号",
    "原文日期": "2022-05-26",
    "紧急程度": "",
    "阅文/办文": "阅文",
    "时间节点": "",
    "收文日期": "2022-05-27",
    "关联文件": "",
    "备注": "",
    "是否需明确建议牵头单位": "否"
  }
}
```

---

## 接口详情

### POST /api/documents/extractions

上传文件并提取公文字段。

**请求体**:

| 字段 | 必填 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| filename | 是 | string | — | 文件名（含扩展名），如 `公文.pdf` |
| content_base64 | 是 | string | — | 文件内容的 Base64 编码 |
| include_parsed_content | 否 | boolean | `false` | 是否返回解析后的正文内容 |

**成功响应（HTTP 201）**:

| 字段 | 类型 | 说明 |
|------|------|------|
| filename | string | 文件名 |
| file_type | string | 文件类型（pdf/docx/md/txt） |
| content_length | int | 解析后的正文长度 |
| fields | object | 提取的字段（含 11 个公文字段） |
| parsed_content | string | 仅当 `include_parsed_content=true` 时返回 |

**错误响应**:

| 状态码 | 说明 |
|--------|------|
| 400 | 请求参数错误（如缺失字段、文件为空） |
| 422 | 参数校验失败 |
| 500 | 服务器内部错误 |

---

## 支持的文件类型

| 类型 | 扩展名 | 说明 |
|------|--------|------|
| PDF | `.pdf` | Adobe 便携文档格式 |
| Word | `.docx` | Microsoft Word 文档 |
| Markdown | `.md` | 轻量级标记文件 |
| 纯文本 | `.txt` | 纯文本文件 |

---

## 调用示例

### Python

```python
import base64
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

with open("公文.pdf", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

resp = requests.post(
    "https://85af8f.xhang.buaa.edu.cn:52811/api/documents/extractions",
    json={"filename": "公文.pdf", "content_base64": b64},
    timeout=300,
    verify=False
)

if resp.status_code == 201:
    data = resp.json()
    print(f"提取到 {len(data['fields'])} 个字段:")
    for field_name, value in data["fields"].items():
        print(f"  {field_name}: {value}")
else:
    print(f"请求失败: {resp.status_code} - {resp.text}")
```

### macOS / Linux（curl）

```bash
curl -k -X POST https://85af8f.xhang.buaa.edu.cn:52811/api/documents/extractions \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "公文.pdf",
    "content_base64": "'"$(base64 -w0 ~/Downloads/公文.pdf)"'"
  }' | python3 -m json.tool
```

### Windows（PowerShell）

```powershell
$filePath = "C:\Users\YourName\Downloads\公文.pdf"
$fileBase64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($filePath))
$body = @{ filename = "公文.pdf"; content_base64 = $fileBase64 } | ConvertTo-Json
$result = Invoke-RestMethod -Uri "https://85af8f.xhang.buaa.edu.cn:52811/api/documents/extractions" `
  -Method Post -Body $body -ContentType "application/json" -SkipCertificateCheck
$result.fields | Format-Table
```

---

## 注意事项

1. **Base64 编码**: 文件内容需编码为 Base64 字符串，建议文件不超过 50MB（编码后约膨胀 37%）
2. **超时设置**: 大文件解析可能需要 2-5 分钟，客户端超时应设置至少 300 秒
3. **SSL 证书**: 当前为自签名证书，curl 需加 `-k` 参数，Python 需加 `verify=False`
4. **字段为空**: 未识别到的字段返回空字符串 `""`，属正常现象
5. **并发限制**: 建议不要同时发送过多请求，避免服务器过载

---

## 字段说明

| 字段名 | 说明 | 示例 |
|--------|------|------|
| 文件标题 | 公文标题全文 | 关于印发《...》的通知 |
| 来文单位 | 发文机关/单位名称 | 教育部 |
| 来文字号 | 公文文号 | 教社科司函〔2026〕9号 |
| 原文日期 | 发文日期 | 2026-01-15 |
| 紧急程度 | 加急/特急/普通 | 加急 |
| 阅文/办文 | 需要阅览还是办理 | 阅文 |
| 时间节点 | 需关注时间或截止日期 | 4月17日前提交 |
| 收文日期 | 收文登记日期 | 2026-01-16 |
| 关联文件 | 相关依据文件 | 根据《...》第X条 |
| 备注 | 补充说明 | — |
| 是否需明确建议牵头单位 | 是否需要指定主办部门 | 是 |