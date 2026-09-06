import base64
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests

from .document_processor import (
    extract_fields_from_content,
    get_file_type,
    is_supported_file,
    parse_document,
)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./upload"))
GUARD_API_URL = os.getenv("GUARD_API_URL", "https://07b503.xhang.buaa.edu.cn:52811/guard")
GUARD_API_TIMEOUT = float(os.getenv("GUARD_API_TIMEOUT", "30"))
NONSTANDARD_API_URL = os.getenv("NONSTANDARD_API_URL", "https://07b503.xhang.buaa.edu.cn:52811/nonstandard")
TYPO_API_URL = os.getenv("TYPO_API_URL", "https://07b503.xhang.buaa.edu.cn:52811/typo")
QUALITY_API_TIMEOUT = float(os.getenv("QUALITY_API_TIMEOUT", "60"))


class UnsupportedFileTypeError(Exception):
    """不支持的文件类型"""


class DocumentParseError(Exception):
    """文档解析失败"""


class DocumentGuardError(Exception):
    """内容审查服务调用失败"""


def extract_from_base64(
    filename: str,
    content_base64: str,
    model_name: str = "qwen2.5-72b",
    include_parsed_content: bool = False,
) -> dict:
    """从 Base64 编码的文件内容提取公文字段，文件会保存到 upload 目录"""
    if not is_supported_file(filename):
        raise UnsupportedFileTypeError("不支持的文件类型，请上传 PDF、DOCX、MD 或 TXT 文件")

    file_bytes = base64.b64decode(content_base64)
    safe_filename = filename.replace("..", "_").replace("/", "_")
    file_path = UPLOAD_DIR / safe_filename
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(file_bytes)

    parsed_content = parse_document(file_path)
    if not parsed_content:
        raise DocumentParseError("文档解析失败")

    extracted_fields = extract_fields_from_content(parsed_content, model_name)

    result = {
        "filename": filename,
        "file_type": get_file_type(filename),
        "content_length": len(parsed_content),
        "fields": extracted_fields,
    }

    if include_parsed_content:
        result["parsed_content"] = parsed_content

    return result


def guard_file_from_base64(filename: str, content_base64: str) -> dict:
    """解析文件并审查正文；请求结束后清理临时文件，不持久化解析内容。"""
    if not is_supported_file(filename):
        raise UnsupportedFileTypeError("不支持的文件类型，请上传 PDF、DOCX、MD 或 TXT 文件")

    try:
        file_bytes = base64.b64decode(content_base64, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise DocumentParseError("文件内容不是有效的 Base64 编码") from exc
    if not file_bytes:
        raise DocumentParseError("文件内容为空")

    suffix = Path(filename).suffix.lower()
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="doc-guard-", suffix=suffix, delete=False) as temp_file:
            temp_file.write(file_bytes)
            temp_path = Path(temp_file.name)

        parsed_content = parse_document(temp_path)
        if not parsed_content:
            raise DocumentParseError("文档解析失败")

        return {
            "filename": filename,
            "file_type": get_file_type(filename),
            "content_length": len(parsed_content),
            "review": review_text(parsed_content),
        }
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _call_sensitive_guard(text: str) -> dict[str, Any]:
    try:
        response = requests.post(GUARD_API_URL, json={"text": text}, timeout=GUARD_API_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout as exc:
        raise DocumentGuardError("内容审查服务超时，请稍后重试") from exc
    except requests.exceptions.ConnectionError as exc:
        raise DocumentGuardError("内容审查服务暂时不可用") from exc
    except (requests.exceptions.RequestException, ValueError) as exc:
        raise DocumentGuardError("内容审查服务返回异常") from exc


def _call_quality_api(url: str, text: str, category: str) -> tuple[list, str, str | None]:
    try:
        response = requests.post(url, json={"text": text}, timeout=QUALITY_API_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        issues = []
        for item in result.get("issues", []) or []:
            if not isinstance(item, dict):
                continue
            issues.append({
                "start": item.get("start"),
                "end": item.get("end"),
                "original": item.get("original", ""),
                "suggestion": item.get("suggestion", ""),
                "error_type": item.get("error_type", category),
                "message": item.get("message") or item.get("reason", ""),
                "source": category,
                **({"confidence": item["confidence"]} if "confidence" in item else {}),
            })
        return issues, result.get("corrected_text", result.get("corrected", text)), None
    except requests.exceptions.Timeout:
        return [], text, f"{category}检查服务超时"
    except requests.exceptions.RequestException:
        return [], text, f"{category}检查服务不可用"
    except ValueError:
        return [], text, f"{category}检查服务返回异常"


def _merge_quality_corrections(text: str, issues: list, corrected_candidates: list[str]) -> str:
    """按原文位置合并两类质量接口的修正，重叠位置保留首个结果。"""
    merged = text
    valid = []
    for item in issues:
        try:
            start, end = int(item["start"]), int(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        suggestion = item.get("suggestion")
        if start < 0 or end <= start or end > len(text) or not suggestion:
            continue
        valid.append((start, end, str(suggestion)))
    occupied = []
    for start, end, suggestion in sorted(valid, key=lambda value: value[0], reverse=True):
        if any(start < other_end and end > other_start for other_start, other_end in occupied):
            continue
        merged = merged[:start] + suggestion + merged[end:]
        occupied.append((start, end))
    if valid:
        return merged
    for candidate in corrected_candidates:
        if candidate and candidate != text:
            return candidate
    return text


def review_text(text: str) -> dict:
    """同时执行敏感内容审查和错别字/表述检查。"""
    if not text or not text.strip():
        raise DocumentParseError("审查内容不能为空")
    sensitive = _call_sensitive_guard(text)
    with ThreadPoolExecutor(max_workers=2) as executor:
        nonstandard_future = executor.submit(_call_quality_api, NONSTANDARD_API_URL, text, "nonstandard")
        typo_future = executor.submit(_call_quality_api, TYPO_API_URL, text, "typo")
        nonstandard_issues, nonstandard_corrected, nonstandard_error = nonstandard_future.result()
        typo_issues, typo_corrected, typo_error = typo_future.result()
    issues = nonstandard_issues + typo_issues
    corrected = _merge_quality_corrections(text, issues, [nonstandard_corrected, typo_corrected])
    quality_errors = [error for error in (nonstandard_error, typo_error) if error]
    return {
        "harmful": sensitive.get("harmful", "false"),
        "harmful_type": sensitive.get("harmful_type", "none"),
        "harmful_type_label": sensitive.get("harmful_type_label", "无"),
        "harmful_reason": sensitive.get("harmful_reason", ""),
        "harmful_words": sensitive.get("harmful_words", ""),
        "harmful_degree": sensitive.get("harmful_degree", "none"),
        "harmful_degree_label": sensitive.get("harmful_degree_label", "无"),
        "confidence": sensitive.get("confidence", "low"),
        "confidence_label": sensitive.get("confidence_label", "低"),
        "highlight_spans": sensitive.get("highlight_spans", []),
        "stage": sensitive.get("stage"),
        "issues": issues,
        "corrected": corrected,
        "typo_check_error": "; ".join(quality_errors) if quality_errors else None,
    }
