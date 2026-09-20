import base64
import os
import tempfile
import threading
import time
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
from .region_ocr import extract_first_page_top_left


UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./upload"))
GUARD_API_URL = os.getenv("GUARD_API_URL", "https://07b503.xhang.buaa.edu.cn:52811/guard")
GUARD_API_TIMEOUT = float(os.getenv("GUARD_API_TIMEOUT", "180"))
NONSTANDARD_API_URL = os.getenv("NONSTANDARD_API_URL", "https://07b503.xhang.buaa.edu.cn:52811/api/v1/nonstandard-expression/check")
TYPO_API_URL = os.getenv("TYPO_API_URL", "https://07b503.xhang.buaa.edu.cn:52811/api/v1/typo-punctuation/check")
# 2026-09-19 起质量检查改用二合一接口（响应含 nonstandard/typo 两个子结构，引擎 DeepSeek-V4-Flash）
QUALITY_CHECK_URL = os.getenv("QUALITY_CHECK_URL", "https://07b503.xhang.buaa.edu.cn:52811/quality-check")
QUALITY_API_TIMEOUT = float(os.getenv("QUALITY_API_TIMEOUT", "180"))
QUALITY_API_KEY = os.getenv("QUALITY_API_KEY", "")


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
    """从 Base64 编码的文件内容提取公文字段；文件仅存临时目录，用后即删（2026-09-18 起不再持久化到 upload/）"""
    if not is_supported_file(filename):
        raise UnsupportedFileTypeError("不支持的文件类型，请上传 PDF、DOCX、MD 或 TXT 文件")

    file_bytes = base64.b64decode(content_base64)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="doc-extract-", suffix=Path(filename).suffix.lower(), delete=False
        ) as temp_file:
            temp_file.write(file_bytes)
            temp_path = Path(temp_file.name)

        ocr_result = {"text": "", "confidence": 0.0, "error": "仅对 PDF 启用"}
        if Path(filename).suffix.lower() == ".pdf":
            with ThreadPoolExecutor(max_workers=2) as executor:
                parsed_future = executor.submit(parse_document, temp_path)
                ocr_future = executor.submit(extract_first_page_top_left, temp_path)
                parsed_content = parsed_future.result()
                ocr_result = ocr_future.result()
        else:
            parsed_content = parse_document(temp_path)
        if not parsed_content:
            raise DocumentParseError("文档解析失败")

        extracted_fields = extract_fields_from_content(parsed_content, model_name, ocr_result.get("text", ""))

        result = {
            "filename": filename,
            "file_type": get_file_type(filename),
            "content_length": len(parsed_content),
            "fields": extracted_fields,
        }

        if include_parsed_content:
            result["parsed_content"] = parsed_content

        return result
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


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
            "parsed_content": parsed_content,
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


_QUALITY_CHECK_SEMAPHORE = threading.Semaphore(1)


def _call_quality_check(text: str) -> tuple[list, str, str | None]:
    """调用二合一质量检查接口（nonstandard + typo），解析合并响应。"""
    # 上游容量实测为 2 路并发，超出的请求会收到 available=false，故本地限流排队
    with _QUALITY_CHECK_SEMAPHORE:
        # 上游偶发 available=false（后端繁忙），重试一次
        last_errors: str | None = None
        for attempt in range(3):
            try:
                response = requests.post(QUALITY_CHECK_URL, json={"text": text}, timeout=QUALITY_API_TIMEOUT)
                response.raise_for_status()
                result = response.json()

                issues: list = []
                corrected_candidates: list[str] = []
                errors: list[str] = []
                any_available = False
                # 旧的两个类别在新响应中以 nonstandard / typo 两个子对象返回，结构同旧端点
                for category in ("nonstandard", "typo"):
                    section = result.get(category)
                    if not isinstance(section, dict):
                        continue
                    if not section.get("available", True):
                        warning = section.get("upstream_warning") or "服务不可用"
                        errors.append(f"{category}: {warning}")
                        continue
                    any_available = True
                    for item in section.get("issues", []) or []:
                        if not isinstance(item, dict):
                            continue
                        issues.append({
                            "start": item.get("start"),
                            "end": item.get("end"),
                            "original": item.get("original", ""),
                            "suggestion": item.get("suggestion", ""),
                            "error_type": item.get("category") or category,
                            "message": item.get("reason") or item.get("message", ""),
                            "source": category,
                            **({"confidence": item["confidence"]} if "confidence" in item else {}),
                        })
                    corrected = section.get("corrected_text") or section.get("corrected")
                    if corrected:
                        corrected_candidates.append(corrected)

                last_errors = "; ".join(errors) if errors else None
                if not any_available and attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                corrected_candidates.append(result.get("corrected_text") or "")
                return issues, next((c for c in corrected_candidates if c), text), last_errors
            except requests.exceptions.Timeout:
                last_errors = "质量检查服务超时"
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                return [], text, last_errors
            except requests.exceptions.RequestException:
                last_errors = "质量检查服务不可用"
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                return [], text, last_errors
            except ValueError:
                return [], text, "质量检查服务返回异常"
        return [], text, last_errors

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
    """同时执行敏感内容审查和错别字/表述检查（质量检查走二合一接口）。"""
    if not text or not text.strip():
        raise DocumentParseError("审查内容不能为空")
    with ThreadPoolExecutor(max_workers=2) as executor:
        sensitive_future = executor.submit(_call_sensitive_guard, text)
        quality_future = executor.submit(_call_quality_check, text)
        sensitive = sensitive_future.result()
        issues, corrected, quality_error = quality_future.result()
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
        "typo_check_error": quality_error,
    }
