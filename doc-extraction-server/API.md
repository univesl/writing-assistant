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
| /api/documents/text-guard | POST | 文本内容审查（同上，批量 key-value 形态） |
| /api/documents/extractions | POST | 公文字段提取（11 项标准字段） |
| /api/health | GET | 健康检查 |

---

## 2. 文件内容审查

### 接口

```txt
POST /api/documents/file-guard
```

接口接收文件，解析正文后交给内容检查服务，检查结果**原样返回**。

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
    "parsed_content": "解析后的正文……",
    "review": { "……": "内容检查服务的完整原始返回，见第 4 节" }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| filename | string | 原始文件名 |
| file_type | string | 文件类型：pdf、docx、markdown 或 text |
| content_length | integer | 解析后正文长度 |
| parsed_content | string | 解析后的正文，issues 位置的锚定基准（见第 5 节） |
| review | object | 内容检查结果，字段结构与内容检查服务返回完全一致（见第 4 节） |

### 错误响应

| 状态码 | 说明 |
|--------|------|
| 400 | 不支持的文件类型 / 无效 Base64 |
| 422 | 参数校验失败 / 文档解析失败 |
| 502 | 内容检查服务暂时不可用（已自动重试 3 次） |

---

## 3. 文本内容审查

### 接口

```txt
POST /api/documents/text-guard
```

接口接收批量文本（「调用方自定义 id → 待审文本」的映射），逐条交给内容检查服务，每个 id 下返回该条的**原始检查结果**。

### 请求

```json
{
    "id1": "请程书记签发",
    "id2": "请程记书签发，记要存档"
}
```

| 要求 | 说明 |
|------|------|
| 键（id） | 调用方自定义幂等键，响应原样带回作为 key；非空、长度 ≤64 |
| 值（文本） | 待审查文本，1-5000 字符 |
| 数量 | 最多 30 条 |

### 成功响应（HTTP 200）

```json
{
    "id1": { "……": "该条文本的完整原始检查结果，见第 4 节" },
    "id2": { "……": "同上" }
}
```

单条检查失败不影响其他条目，失败条目仅含 `{"error": "失败原因"}`。耗时随条目数线性增长（每条约 3-8 秒），客户端超时建议 ≥300 秒。

### 错误响应

| 状态码 | 说明 |
|--------|------|
| 422 | 参数校验失败（非 JSON 对象 / 空 body / 超过 30 条 / id 超长 / 文本为空或超过 5000 字符） |

---

## 4. 内容检查结果字段

审查类接口返回的检查结果（file-guard 的 `review`、text-guard 每个 id 下的对象）与内容检查服务的返回**完全一致**，主要结构如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| completed | boolean | 本次检查是否完整完成 |
| has_issue | boolean | 是否发现任何问题 |
| issue_count | integer | 问题总数 |
| issues | array | 问题列表（已合并去重） |
| issues[].category / type | string | 问题分类（如"语法格式"） |
| issues[].original | string | 原始错误文本；恒等于 `解析正文[start:end]` |
| issues[].suggestion | string | 建议修改文本 |
| issues[].reason | string | 问题说明 |
| issues[].start / end | integer | 问题文本位置（字符偏移，含起点不含终点） |
| issues[].confidence | string | 置信度：high / medium / low |
| issues[].risk_level(_label) | string | 该条风险等级及名称 |
| issues[].source | string | 检测来源：typo / nonstandard / safety |
| risk_level(_label) | string | 整体风险等级及名称 |
| safety | object | 内容安全（敏感）检测结果子对象：harmful、harmful_type(_label)、harmful_reason、harmful_words、harmful_degree(_label)、highlight_spans、stage 等 |
| nonstandard | object | 不规范表述检测结果子对象 |
| typo | object | 错别字/标点检测结果子对象 |
| summary | object | 统计信息（各类问题数、去重数） |

注：字段以上游内容检查服务实际返回为准，本服务原样透传、不增删改；新增字段会自动出现在响应中。

---

## 5. 位置定位说明

issues 中的 `start/end` 基于**服务端解析后的正文**（text-guard 即该条传入的原文，file-guard 即返回的 `parsed_content`）。

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
3. **检查状态**：检查结果中的 `completed` 为 false 或条目仅含 `{"error": ...}` 时表示该次检查未完成，应以"检查暂时不可用"提示用户，不要当作"没有问题"；
4. **字符保真**：解析正文忠实还原源文件内容（含中文引号、下划线、特殊符号），可直接用于高亮与比对；
5. **并发**：请避免瞬时大量并发请求，重负载场景建议做排队或限速。
