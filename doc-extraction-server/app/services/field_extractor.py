#!/usr/bin/env python3
"""
字段提取模块
职责：从文档内容提取标准字段（混合策略：规则+LLM）
"""

import json
import re
import os
import time
from typing import Dict, List
from dataclasses import dataclass, field
from pathlib import Path
import requests


# 预定义模型配置（2026-09-16 移除 h3i 平台默认值，部署环境必须显式配置 FIELD_EXTRACTION_API_URL）
def _field_base_url() -> str:
    api_url = os.getenv("FIELD_EXTRACTION_API_URL") or os.getenv("LLM_API_URL")
    if api_url:
        return api_url.rstrip("/")
    base = os.getenv("FIELD_EXTRACTION_API_BASE") or os.getenv("MODEL_API_BASE", "")
    base = base.rstrip("/")
    return base if base.endswith("/v1") else f"{base}/v1"


FIELD_EXTRACTION_MODEL_ID = os.getenv("FIELD_EXTRACTION_MODEL_ID", "qwen2.5-72b")
FIELD_EXTRACTION_MODEL_NAME = (
    os.getenv("FIELD_EXTRACTION_MODEL_NAME")
    or os.getenv("LLM_MODEL_NAME")
    or os.getenv("DEFAULT_MODEL", "Qwen2.5-72B-Instruct")
)
FIELD_EXTRACTION_API_KEY = os.getenv("FIELD_EXTRACTION_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("MODEL_API_KEY", "")
FIELD_EXTRACTION_TIMEOUT = float(os.getenv("FIELD_EXTRACTION_TIMEOUT", os.getenv("LLM_REQUEST_TIMEOUT", "180")))


AVAILABLE_MODELS = {
    FIELD_EXTRACTION_MODEL_ID: {
        "model": FIELD_EXTRACTION_MODEL_NAME,
        "base_url": _field_base_url(),
        "api_key": FIELD_EXTRACTION_API_KEY
    },
}


@dataclass
class FieldDef:
    """字段定义"""
    name: str
    description: str
    field_type: str = "text"
    rule_extractable: bool = True
    patterns: List[str] = field(default_factory=list)


# 标准字段配置（11个字段）
DEFAULT_FIELDS = [
    FieldDef("文件标题", "文档的标题名称", "text", True, [
        r'#\s*([^\n]+)',
        r'关于印发[《《]([^》]+)[》》]',
    ]),
    FieldDef("来文单位", "发文单位/机构", "text", True, [
        r'([\u4e00-\u9fa5]{2,}(?:大学|学院|委员会|部|厅|局))',
    ]),
    FieldDef("来文字号", "发文字号", "text", True, [
        r'([\u4e00-\u9fa5]+字[〔\[]\d{4}[〕\]]\s*\d+\s*号)',
    ]),
    FieldDef("原文日期", "文档原始日期", "date", True, [
        r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
        r'(\d{4}-\d{2}-\d{2})',
    ]),
    FieldDef("紧急程度", "文档紧急程度", "select", True, [
        r'紧急程度[：:]\s*(急件|特急|加急|平件)',
    ]),
    FieldDef("阅文/办文", "文档处理类型", "select", False),
    FieldDef("时间节点", "文档中提及的关键时间节点，包括但不限于：截止日期、完成时限、上报期限、会议时间、执行期限等。提取时应包含具体日期/时间和对应的事项要求，例如'3月15日前完成报送'、'请于2024年5月1日前提交'等。如有多个时间节点，请分条列出。", "text", False),
    FieldDef("收文日期", "收到文档的日期", "date", False),
    FieldDef("关联文件", "相关关联文件", "text", False),
    FieldDef("备注", "备注说明", "text", False),
    FieldDef("是否需明确建议牵头单位", "是否需要明确牵头单位", "checkbox", False),
]


class FieldExtractor:
    """字段提取器"""

    def __init__(self, llm_config: Dict = None, fields: List[FieldDef] = None, model_name: str = None):
        """
        初始化
        
        Args:
            llm_config: {"model": "", "base_url": "", "api_key": ""}
                     如果为None，可以使用 model_name 选择预定义模型
            fields: 字段定义列表，默认使用 DEFAULT_FIELDS
            model_name: 预定义模型名称，如 "qwen3-235b", "deepseek-r1-70b" 等
        """
        if llm_config:
            self.llm_config = llm_config
        elif model_name and model_name in AVAILABLE_MODELS:
            self.llm_config = AVAILABLE_MODELS[model_name]
        else:
            # 默认使用第一个模型
            self.llm_config = list(AVAILABLE_MODELS.values())[0]
        
        self.fields = fields or DEFAULT_FIELDS
    
    @classmethod
    def list_available_models(cls) -> List[str]:
        """列出所有可用的预定义模型"""
        return list(AVAILABLE_MODELS.keys())
    
    @classmethod
    def from_model(cls, model_name: str = None):
        """通过模型名称快速创建提取器
        
        Args:
            model_name: 模型名称，默认使用 qwen2.5-72b (Qwen2.5-72B-Instruct)
        """
        # 默认使用 Qwen2.5-72B 模型（与文档生成保持一致）
        if model_name is None:
            model_name = FIELD_EXTRACTION_MODEL_ID
        
        if model_name not in AVAILABLE_MODELS:
            raise ValueError(f"未知模型: {model_name}. 可用模型: {list(AVAILABLE_MODELS.keys())}")
        return cls(model_name=model_name)

    def extract(self, content: str, supplemental_content: str = "") -> Dict[str, str]:
        """
        从文档内容提取字段（全部使用大模型）
        
        Args:
            content: 文档文本内容
            
        Returns:
            {字段名: 提取值}
        """
        # 全部使用 LLM 提取
        llm_results = self._extract_by_llm(content, self.fields, supplemental_content)

        # 确保所有字段都有值（找不到的填空字符串）
        final_results = llm_results.copy()
        for field in self.fields:
            if field.name not in final_results:
                final_results[field.name] = ""

        return final_results

    def extract_from_file(self, file_path: Path) -> Dict[str, str]:
        """从 Markdown 文件提取字段"""
        if not file_path.exists():
            return {f.name: "" for f in self.fields}

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 截断避免过长
        max_len = 8000
        if len(content) > max_len:
            content = content[:max_len] + "\n..."

        return self.extract(content)

    def batch_extract(self, doc_paths: List[Path]) -> Dict[str, Dict[str, str]]:
        """批量提取多个文档"""
        results = {}
        for path in doc_paths:
            print(f"处理: {path.name}")
            results[path.name] = self.extract_from_file(path)
        return results

    def _extract_by_rules(self, content: str) -> Dict[str, str]:
        """规则提取"""
        results = {}

        for field in self.fields:
            if not field.rule_extractable:
                continue

            for pattern in field.patterns:
                matches = re.findall(pattern, content)
                if matches:
                    match = matches[0]
                    if isinstance(match, tuple):
                        value = ''.join(match).strip()
                    else:
                        value = match.strip()

                    value = self._clean_value(value, field.name)

                    if value:
                        results[field.name] = value
                        break

        return results

    def _extract_by_llm(self, content: str, fields: List[FieldDef], supplemental_content: str = "") -> Dict[str, str]:
        """LLM 提取（使用大模型从文档中提取所有字段）"""
        if not fields:
            return {}

        max_chars = 8000
        truncated = content[:max_chars] if len(content) > max_chars else content

        # 2026-09-21: 精简 prompt——冗长规则措辞会触发 GLM 超长思考（1.5万+字），
        # 耗尽 max_tokens 导致正文为空；紧凑版实测可正常输出全部字段
        field_names = "、".join(f.name for f in fields)
        system_prompt = f"""从公文中提取字段，输出JSON对象（键为字段名，未提及的字段值为""），只输出JSON不输出其他内容。
字段：{field_names}
规则：文件标题取具体事由标题（如"关于XX的通知"），不取"XX大学文件"类版头；来文字号按原文样式保留标点（〔〕[]【】）；日期输出"2024年3月15日"格式；时间节点列出全部时限，格式"时间：事项"，多个用分号；紧急程度取关键词（特急/急件/加急/平件）。"""

        if supplemental_content:
            supplemental_prompt = f"\n\n【OCR 补充识别结果】\n第1页左上角：\n{supplemental_content[:3000]}\n"
        else:
            supplemental_prompt = ""
        user_content = truncated + supplemental_prompt

        # 2026-09-16: 对上游瞬时故障(限流/网关超时/网络抖动)自动重试，避免静默返回空字段
        retryable_status = {429, 500, 502, 503, 504}
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                # 2026-09-21: 上游网关对非流式请求有 60s 硬超时，GLM 长思考会被 504 掐断，
                # 改用流式调用并聚合 content（流式下网关只限制读间隔，token 持续流出即可）
                with requests.post(
                    f"{self.llm_config['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.llm_config.get('api_key', '')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.llm_config.get("model", "GLM5.2-FP8_dpQ4saJqACejWnD9"),
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 4000,
                        "stream": True
                    },
                    timeout=FIELD_EXTRACTION_TIMEOUT,
                    stream=True
                ) as response:
                    # SSE 流未带 charset 时 requests 会用 latin-1 解码，中文全部变乱码导致字段匹配失败
                    response.encoding = "utf-8"
                    if response.status_code != 200:
                        if response.status_code in retryable_status and attempt < max_attempts:
                            print(f"[字段提取] API 返回错误: {response.status_code}（第 {attempt}/{max_attempts} 次，稍后重试）")
                            time.sleep(5 * attempt)
                            continue
                        print(f"[字段提取] API 返回错误: {response.status_code}")
                        return {f.name: "" for f in fields}

                    chunks = []
                    for line in response.iter_lines(decode_unicode=True):
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            delta = (json.loads(data).get("choices") or [{}])[0].get("delta") or {}
                        except (ValueError, IndexError):
                            continue
                        if delta.get("content"):
                            chunks.append(delta["content"])
                    text = "".join(chunks)

                parsed = self._parse_llm_response(text, fields)
                if any(parsed.values()) or attempt >= max_attempts:
                    return parsed
                # GLM 思考过程较长时可能耗尽 max_tokens 导致正文为空，重试
                print(f"[字段提取] 模型返回空结果（第 {attempt}/{max_attempts} 次，重试）")
                time.sleep(3)
                continue

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < max_attempts:
                    print(f"[字段提取] 网络异常: {e}（第 {attempt}/{max_attempts} 次，稍后重试）")
                    time.sleep(5 * attempt)
                    continue
                print(f"[字段提取] LLM提取失败: {e}")
                return {f.name: "" for f in fields}
            except Exception as e:
                print(f"[字段提取] LLM提取失败: {e}")
                return {f.name: "" for f in fields}

    def _parse_llm_response(self, text: str, fields: List[FieldDef]) -> Dict[str, str]:
        """解析 LLM 返回"""
        field_names = {f.name for f in fields}
        results = {name: "" for name in field_names}
        invalid = {"未提及", "无", "null", "None", "不详", ""}

        try:
            data = json.loads(text)
            for key in field_names:
                if key in data:
                    value = str(data[key]).strip()
                    if value and value not in invalid:
                        results[key] = value
            return results
        except json.JSONDecodeError:
            # 尝试提取 JSON 块
            import re
            match = re.search(r'\{[\s\S]*?\}', text)
            if match:
                try:
                    data = json.loads(match.group())
                    for key in field_names:
                        if key in data:
                            value = str(data[key]).strip()
                            if value and value not in invalid:
                                results[key] = value
                except:
                    pass
            return results

    def _clean_value(self, value: str, field_name: str) -> str:
        """清理值"""
        if not value:
            return ""
        value = value.strip()
        if field_name == "文件标题":
            value = value.lstrip('#').strip()
        return value

    def get_stats(self, results: Dict[str, str]) -> Dict:
        """获取统计信息"""
        filled = sum(1 for v in results.values() if v)
        return {
            "total": len(self.fields),
            "filled": filled,
            "fill_rate": f"{filled/len(self.fields)*100:.1f}%"
        }
