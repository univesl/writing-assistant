# 公文字段提取与文件内容审查 API

## 1. 基本信息

- 服务地址：`https://85af8f.xhang.buaa.edu.cn:52811`
- 请求方式：RESTful HTTP API
- 数据格式：请求和响应均为 JSON
- 文件传输：文件内容使用 Base64 编码
- 支持格式：PDF、DOCX、Markdown、TXT

当前服务使用自签名 HTTPS 证书。测试时，`curl` 可使用 `-k`，Python `requests` 可设置 `verify=False`。

## 2. 文件内容审查

### 接口

```text
POST /api/documents/file-guard
```

该接口接收文件，先将文件解析为文本，再调用内容审查服务。解析正文仅在本次请求期间使用，不会保存到数据库或持久化上传目录；请求结束后会清理临时文件。

### 请求参数

```json
{
  "filename": "公文.pdf",
  "content_base64": "文件内容的 Base64 编码"
}
```

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| filename | 是 | string | 文件名，必须包含扩展名 |
| content_base64 | 是 | string | 文件内容的 Base64 编码 |

### 成功响应（HTTP 200）

```json
{
  "filename": "公文.pdf",
  "file_type": "pdf",
  "content_length": 2048,
  "review": {
    "harmful": "false",
    "harmful_type": "normal",
    "harmful_type_label": "正常",
    "harmful_reason": "",
    "harmful_words": "",
    "harmful_degree": "none",
    "harmful_degree_label": "无",
    "confidence": "high",
    "confidence_label": "高",
    "highlight_spans": [],
    "stage": "fragment"
  }
}
```

### 审查结果字段

| 字段 | 类型 | 说明 |
|---|---|---|
| harmful | string | `false` 表示未发现违规，`true` 表示发现违规 |
| harmful_type | string | 违规类型编码 |
| harmful_type_label | string | 违规类型名称 |
| harmful_reason | string | 审查原因或说明 |
| harmful_words | string | 命中的违规词 |
| harmful_degree | string | 风险程度编码 |
| harmful_degree_label | string | 风险程度名称 |
| confidence | string | 置信度编码 |
| confidence_label | string | 置信度名称 |
| highlight_spans | array | 命中的文本片段 |
| stage | string/null | 审查阶段 |

服务端只返回审查结果，不自动决定是否继续字段提取；调用方根据 `review.harmful` 自行编排业务流程。

### 错误响应

| HTTP 状态码 | 说明 |
|---|---|
| 400 | 文件类型不支持或请求参数错误 |
| 422 | Base64 无效或文件解析失败 |
| 502 | 内容审查服务不可用或返回异常 |

## 3. 公文字段提取

### 接口

```text
POST /api/documents/extractions
```

该接口接收文件，解析后提取 11 个标准公文字段。原有字段提取行为保持不变。

### 请求参数

```json
{
  "filename": "公文.pdf",
  "content_base64": "文件内容的 Base64 编码",
  "include_parsed_content": false
}
```

| 字段 | 必填 | 类型 | 默认值 | 说明 |
|---|---|---|---|---|
| filename | 是 | string | — | 文件名，必须包含扩展名 |
| content_base64 | 是 | string | — | 文件内容的 Base64 编码 |
| include_parsed_content | 否 | boolean | `false` | 是否在响应中返回解析正文 |

### 成功响应（HTTP 201）

```json
{
  "filename": "公文.pdf",
  "file_type": "pdf",
  "content_length": 2048,
  "fields": {
    "文件标题": "关于印发《示例办法》的通知",
    "来文单位": "北京航空航天大学",
    "来文字号": "北航校字〔2026〕42号",
    "原文日期": "2026-05-26",
    "紧急程度": "",
    "阅文/办文": "阅文",
    "时间节点": "",
    "收文日期": "",
    "关联文件": "",
    "备注": "",
    "是否需明确建议牵头单位": "否"
  },
  "parsed_content": null
}
```

当 `include_parsed_content=true` 时，`parsed_content` 返回解析后的正文；默认不返回。该参数仅用于需要正文的调用场景，内容是否由调用方暂存由调用方自行负责。

### 字段说明

| 字段名 | 说明 |
|---|---|
| 文件标题 | 公文标题全文 |
| 来文单位 | 发文机关或单位名称 |
| 来文字号 | 公文文号 |
| 原文日期 | 公文原始日期 |
| 紧急程度 | 加急、特急、普通等 |
| 阅文/办文 | 需要阅览还是办理 |
| 时间节点 | 截止时间、完成时限等 |
| 收文日期 | 收文登记日期 |
| 关联文件 | 相关依据或关联文件 |
| 备注 | 补充说明 |
| 是否需明确建议牵头单位 | 是否需要指定主办部门 |

未识别到的字段返回空字符串，属于正常情况。

### 错误响应

| HTTP 状态码 | 说明 |
|---|---|
| 400 | 文件类型不支持或请求参数错误 |
| 422 | 文件解析失败 |
| 500 | 服务内部错误 |

## 4. Python 调用示例

```python
import base64
import requests

base_url = "https://85af8f.xhang.buaa.edu.cn:52811"
file_path = "公文.pdf"

with open(file_path, "rb") as f:
    content_base64 = base64.b64encode(f.read()).decode("ascii")

response = requests.post(
    f"{base_url}/api/documents/file-guard",
    json={
        "filename": file_path,
        "content_base64": content_base64,
    },
    timeout=300,
    verify=False,
)
response.raise_for_status()
print(response.json()["review"])
```

## 5. 调用建议

- 单个文件建议不超过 50 MB。
- PDF 文件解析可能需要较长时间，客户端超时建议设置为 300 秒或更长。
- 不建议并发提交大量请求。
- 内容审查接口与字段提取接口相互独立；可以先调用 `file-guard`，再根据审查结果决定是否调用 `extractions`。
