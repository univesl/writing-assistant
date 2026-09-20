# 公文审查与字段提取接口文档

## 1. 基本信息

- **接口地址**: `https://85af8f.xhang.buaa.edu.cn:52811`
- **请求方式**: RESTful HTTP API
- **数据格式**: 请求/响应均为 JSON
- **文件内容**: Base64 编码传输
- **支持文件格式**: PDF、DOCX、Markdown、TXT
- **说明**: 服务使用自签名 HTTPS 证书，调用时需关闭证书校验（curl 加 `-k`，Python 加 `verify=False`）

内容审查包括三项能力：

1. 敏感内容和风险检测
2. 不规范表述检测
3. 错别字检测

上传文件在解析完成后立即删除，服务端不做留存。

### 接口一览

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/documents/file-guard | POST | 文件内容审查（敏感 + 不规范表述 + 错别字） |
| /api/documents/text-guard | POST | 文本内容审查（同上，直接接收文本） |
| /api/documents/extractions | POST | 公文字段提取（11 项标准字段） |
| /api/health | GET | 健康检查 |

---

## 2. 文件内容审查

### 接口

```txt
POST /api/documents/file-guard
```

接口接收文件，解析正文并执行敏感内容、不规范表述和错别字检测。

### 请求示例

```json
{
    "filename": "公文.docx",
    "content_base64": "文件内容的 Base64 编码"
}
```

### 请求字段

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| filename | 是 | string | 文件名（含扩展名） |
| content_base64 | 是 | string | 文件内容的 Base64 编码 |

### 成功响应（HTTP 200）

```json
{
    "filename": "公文.docx",
    "file_type": "docx",
    "content_length": 173,
    "parsed_content": "关于开展科研项目管理培训的通知……会议记要已存档。",
    "review": {
        "harmful": "false",
        "harmful_type": "normal",
        "harmful_type_label": "正常",
        "harmful_reason": "该文本为正式通知，属于正常的校内行政公文，不涉及任何违规内容。",
        "harmful_words": "",
        "harmful_degree": "none",
        "harmful_degree_label": "无",
        "confidence": "high",
        "confidence_label": "高",
        "highlight_spans": [],
        "stage": null,
        "issues": [
            {
                "start": 22,
                "end": 24,
                "original": "记要",
                "suggestion": "纪要",
                "error_type": "typo",
                "message": "“记要”应为“纪要”，固定词语误用。",
                "source": "typo",
                "confidence": "high"
            }
        ],
        "corrected": "关于开展科研项目管理培训的通知……会议纪要已存档。",
        "typo_check_error": null
    }
}
```

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| filename | string | 原始文件名 |
| file_type | string | 文件类型：pdf、docx、markdown 或 text |
| content_length | integer | 解析后正文长度 |
| parsed_content | string | 解析后的正文，issues 位置的锚定基准（用法见第 5 节） |
| review | object | 综合审查结果，字段见第 4 节 |

### 错误响应

| 状态码 | 说明 |
|--------|------|
| 400 | 不支持的文件类型 / 无效 Base64 |
| 422 | 参数校验失败 / 文档解析失败 |
| 502 | 审查服务暂时不可用，请稍后重试 |

---

## 3. 文本内容审查

### 接口

```txt
POST /api/documents/text-guard
```

接口直接接收文本并执行敏感内容、不规范表述和错别字检测。

### 请求示例

```json
{
    "text": "我今天心晴很好，会议记要已存档。"
}
```

### 请求字段

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| text | 是 | string | 待审查文本，不能为空 |

### 成功响应（HTTP 200）

```json
{
    "harmful": "false",
    "harmful_type": "normal",
    "harmful_type_label": "正常",
    "harmful_reason": "文本为日常陈述，未发现风险内容。",
    "harmful_words": "",
    "harmful_degree": "none",
    "harmful_degree_label": "无",
    "confidence": "high",
    "confidence_label": "高",
    "highlight_spans": [],
    "stage": null,
    "issues": [
        {
            "start": 4,
            "end": 6,
            "original": "心晴",
            "suggestion": "心情",
            "error_type": "typo",
            "message": "“心晴”为“心情”的形近/音近误用。",
            "source": "typo",
            "confidence": "high"
        },
        {
            "start": 10,
            "end": 12,
            "original": "记要",
            "suggestion": "纪要",
            "error_type": "typo",
            "message": "“记要”应为“纪要”，固定词语误用。",
            "source": "typo",
            "confidence": "high"
        }
    ],
    "corrected": "我今天心情很好，会议纪要已存档。",
    "typo_check_error": null
}
```

### 错误响应

| 状态码 | 说明 |
|--------|------|
| 422 | 文本为空或参数校验失败 |

---

## 4. 综合审查结果字段

| 字段 | 类型 | 说明 |
|------|------|------|
| harmful | string | "true" 表示发现敏感或风险内容，"false" 表示未发现 |
| harmful_type | string | 风险类型编码 |
| harmful_type_label | string | 风险类型名称 |
| harmful_reason | string | 风险判断说明 |
| harmful_words | string | 命中的敏感词或风险词 |
| harmful_degree | string | 风险程度编码 |
| harmful_degree_label | string | 风险程度名称 |
| confidence | string | 敏感内容检测置信度编码 |
| confidence_label | string | 敏感内容检测置信度名称 |
| highlight_spans | array | 命中的文本片段 |
| stage | string/null | 敏感内容检测阶段 |
| issues | array | 问题列表（已去重，同一位置只保留一条） |
| issues[].start | integer | 问题文本起始位置（字符偏移，含起点不含终点） |
| issues[].end | integer | 问题文本结束位置 |
| issues[].original | string | 原始错误文本 |
| issues[].suggestion | string | 建议修改文本 |
| issues[].error_type | string | 问题类型：typo（错别字）或 nonstandard（不规范表述） |
| issues[].message | string | 问题说明 |
| issues[].source | string | 检测来源：typo 或 nonstandard |
| issues[].confidence | string | 该条问题的置信度：high / medium / low |
| corrected | string | 修正后的完整文本；无问题时与原文一致 |
| typo_check_error | string/null | 质量检查异常说明，正常时为 null；非 null 表示检查未完成，此时 issues 可能为空，应提示"检查暂时不可用"而非"没有问题" |

---

## 5. 位置定位说明

issues 中的 `start/end` 基于**服务端解析后的正文**（text-guard 即传入的原文，file-guard 即返回的 `parsed_content`）。

**推荐做法**（file-guard）：以 `parsed_content` 为高亮/定位基准，并先做自校验：

```
parsed_content[start:end] === original
```

校验不成立时忽略该条位置信息。

**在原始文件上定位**：若界面直接渲染原始文件（如 Word 预览），解析正文与原始排版可能存在细微差异，建议用 `original` 字符串在渲染文本中检索定位，`start/end` 仅用于同一错误词多次出现时区分次序。

字符偏移为 Unicode 码点；JavaScript 的 `slice` 在含 emoji 的文本上会偏移 1 位，公文场景罕见。

---

## 6. 公文字段提取

### 接口

```txt
POST /api/documents/extractions
```

接收文件，解析正文并返回标准公文字段（11 项）。

### 请求示例

```json
{
    "filename": "公文.pdf",
    "content_base64": "文件内容的 Base64 编码",
    "include_parsed_content": false
}
```

### 请求字段

| 字段 | 必填 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| filename | 是 | string | — | 文件名（含扩展名） |
| content_base64 | 是 | string | — | 文件内容的 Base64 编码 |
| include_parsed_content | 否 | boolean | false | 是否返回解析后的正文内容 |

### 成功响应（HTTP 201）

```json
{
    "filename": "公文.pdf",
    "file_type": "pdf",
    "content_length": 2284,
    "fields": {
        "文件标题": "关于做好当前网络安全工作的通知",
        "来文单位": "北京航空航天大学",
        "来文字号": "北航信字〔2020〕4 号",
        "原文日期": "2020年5月20日",
        "紧急程度": "",
        "阅文/办文": "",
        "时间节点": "",
        "收文日期": "",
        "关联文件": "《中华人民共和国网络安全法》",
        "备注": "",
        "是否需明确建议牵头单位": ""
    }
}
```

### 字段说明

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

未识别到的字段返回空字符串。`include_parsed_content=true` 时额外返回 `parsed_content`。

### 错误响应

| 状态码 | 说明 |
|--------|------|
| 400 | 不支持的文件类型 / 无效 Base64 |
| 422 | 参数校验失败 / 文档解析失败 |

---

## 7. 调用示例

### Python

```python
import base64
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://85af8f.xhang.buaa.edu.cn:52811"

# 文本审查
resp = requests.post(f"{BASE}/api/documents/text-guard",
                     json={"text": "会议记要已存档。"},
                     verify=False, timeout=180)
for issue in resp.json()["issues"]:
    print(issue["original"], "→", issue["suggestion"],
          f"({issue['source']}/{issue.get('confidence')})")

# 文件审查（含位置自校验）
with open("公文.docx", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()
resp = requests.post(f"{BASE}/api/documents/file-guard",
                     json={"filename": "公文.docx", "content_base64": b64},
                     verify=False, timeout=300)
data = resp.json()
parsed = data.get("parsed_content") or ""
for issue in data["review"]["issues"]:
    assert parsed[issue["start"]:issue["end"]] == issue["original"]

# 字段提取
resp = requests.post(f"{BASE}/api/documents/extractions",
                     json={"filename": "公文.pdf", "content_base64": b64},
                     verify=False, timeout=300)
fields = resp.json()["fields"]
```

### curl

```bash
# 文本审查
curl -sk -X POST https://85af8f.xhang.buaa.edu.cn:52811/api/documents/text-guard \
  -H "Content-Type: application/json" \
  -d '{"text": "会议记要已存档。"}'

# 文件审查
curl -sk -X POST https://85af8f.xhang.buaa.edu.cn:52811/api/documents/file-guard \
  -H "Content-Type: application/json" \
  -d '{"filename": "公文.docx", "content_base64": "'"$(base64 -w0 公文.docx)"'"}'

# 字段提取
curl -sk -X POST https://85af8f.xhang.buaa.edu.cn:52811/api/documents/extractions \
  -H "Content-Type: application/json" \
  -d '{"filename": "公文.pdf", "content_base64": "'"$(base64 -w0 公文.pdf)"'"}'
```

---

## 8. 注意事项

1. **文件不留存**：上传文件解析完成后立即删除，如需留档请自行保存原件；
2. **超时设置**：文本/文件审查建议 ≥180 秒；字段提取建议 ≥120 秒（大文件解析较慢时可放宽到 300 秒）；
3. **检查状态**：`typo_check_error` 非 null 表示质量检查未完成，此时应以"检查暂时不可用"提示用户，不要当作"没有问题"；
4. **字符保真**：解析正文忠实还原源文件内容（含中文引号、下划线、特殊符号），可直接用于高亮与比对；
5. **并发**：请避免瞬时大量并发请求，重负载场景建议做排队或限速。
