#!/usr/bin/env python3
"""
字段提取模块
职责：从文档内容提取标准字段（混合策略：规则+LLM）
"""

import json
import re
from typing import Dict, List
from dataclasses import dataclass, field
from pathlib import Path
import requests


# 预定义模型配置（从 test_and_call_models.py 和 test_qwen.py 收集）
AVAILABLE_MODELS = {
    # 原配置
    "qwen2.5-72b": {
        "model": "xhang_nlp_qwen2.5-72b",
        "base_url": "http://10.70.247.113:4000/v1",
        "api_key": "sk-ofd5T_1rbfsa4JJxMI38HQ"
    },
    # test_qwen.py 中的模型
    "qwen3-235b": {
        "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        "base_url": "http://10.70.247.113:4000/v1",
        "api_key": "sk-I8oiGaYzHqcIXhjKz7D0fQ"
    },
    # test_and_call_models.py 中的模型
    "qwen3-235b-h3i": {
        "model": "Qwen3-235B-A22B-Instruct-2507",
        "base_url": "http://model.ic.h3i.buaa.edu.cn/v1",
        "api_key": "4QrJphMpZvfeeN5dgPa4eJVoRJVvXEDjbCK1wjR7SFgNupgh"
    },
    "qwen3.5-397b": {
        "model": "Qwen3.5-397B-A17B",
        "base_url": "http://model.ic.h3i.buaa.edu.cn/v1",
        "api_key": "4QrJphMpZvfeeN5dgPa4eJVoRJVvXEDjbCK1wjR7SFgNupgh"
    },
    "qwen2.5-72b-h3i": {
        "model": "Qwen2.5-72B-Instruct",
        "base_url": "http://model.ic.h3i.buaa.edu.cn/v1",
        "api_key": "4QrJphMpZvfeeN5dgPa4eJVoRJVvXEDjbCK1wjR7SFgNupgh"
    },
    "deepseek-r1-70b": {
        "model": "DeepSeek-R1-Distill-Llama-70B",
        "base_url": "http://model.ic.h3i.buaa.edu.cn/v1",
        "api_key": "4QrJphMpZvfeeN5dgPa4eJVoRJVvXEDjbCK1wjR7SFgNupgh"
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
            model_name: 模型名称，默认使用 qwen3-235b-h3i (Qwen3-235B-A22B-Instruct-2507)
        """
        # 默认使用 Qwen3-235B 模型（与文档生成保持一致）
        if model_name is None:
            model_name = "qwen3-235b-h3i"
        
        if model_name not in AVAILABLE_MODELS:
            raise ValueError(f"未知模型: {model_name}. 可用模型: {list(AVAILABLE_MODELS.keys())}")
        return cls(model_name=model_name)

    def extract(self, content: str) -> Dict[str, str]:
        """
        从文档内容提取字段（全部使用大模型）
        
        Args:
            content: 文档文本内容
            
        Returns:
            {字段名: 提取值}
        """
        # 全部使用 LLM 提取
        llm_results = self._extract_by_llm(content, self.fields)

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

    def _extract_by_llm(self, content: str, fields: List[FieldDef]) -> Dict[str, str]:
        """LLM 提取（使用大模型从文档中提取所有字段）"""
        if not fields:
            return {}

        fields_desc = "\n".join([
            f"- {f.name}: {f.description}" for f in fields
        ])

        max_chars = 8000
        truncated = content[:max_chars] if len(content) > max_chars else content

        system_prompt = f"""你是一位专业的文档分析助手。请从以下文档中提取指定字段的信息。

需要提取的字段：
{fields_desc}

提取规则：
1. 仔细阅读文档内容，准确提取每个字段对应的信息
2. 如果某个字段在文档中未提及，返回空字符串""
3. 保持原文的表述，不要添加额外解释

【字段格式规范】
- 文件标题：提取具体的、语义相关的标题，如"关于开展XX工作的通知"。不要提取通用模板性文字如"北京航空航天大学文件"、"XX单位文件"等。
- 来文字号：必须与原文格式完全一致，包括所有标点符号（如〔〕、[]、【】等），不得篡改或转换。
- 日期：提取标准的年月日格式（如"2024年3月15日"或"2024-03-15"），不能只写数字如"20240315"或"201458"。
- 时间节点：提取文档中所有截止时间、完成时限、上报期限、会议时间、执行期限等关键时间信息。时间仅保留到日期级别（如"5月30日下午4点开会"简化为"5月30日"），不包含具体事项。如有多个时间节点，用分号分隔。
- 紧急程度：从文档中找到对应的关键词（如特急、急件、加急、平件等）。
- 来文单位：提取完整的发文单位名称。

请以JSON格式返回结果，格式如下：
{{"字段名": "提取的值", ...}}

只返回JSON，不要返回其他内容。"""

        try:
            response = requests.post(
                f"{self.llm_config['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.llm_config.get('api_key', '')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.llm_config.get("model", "xhang_nlp_qwen2.5-72b"),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": truncated}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2000
                },
                timeout=120
            )

            if response.status_code == 200:
                result = response.json()
                text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                return self._parse_llm_response(text, fields)

            print(f"[字段提取] API 返回错误: {response.status_code}")
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
