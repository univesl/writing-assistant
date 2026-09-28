import base64
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from .document_processor import (
    extract_fields_from_content,
    get_file_type,
    is_supported_file,
    parse_document,
)
from .region_ocr import extract_first_page_top_left


UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./upload"))
# 2026-09-28 起内容检查只用二合一 /all-check 接口（敏感+不规范+错别字），
# 其响应原样透传给调用方，不做字段拼装；旧 /guard 与 /quality-check 已弃用
ALL_CHECK_URL = os.getenv("ALL_CHECK_URL", "https://07b503.xhang.buaa.edu.cn:52811/all-check")
ALL_CHECK_TIMEOUT = float(os.getenv("ALL_CHECK_TIMEOUT", "180"))


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
            "review": call_all_check(parsed_content),
            "parsed_content": parsed_content,
        }
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def call_all_check(text: str) -> dict:
    """调用二合一内容检查接口，响应 JSON 原样返回（纯透传）。

    上游偶发 503/超时（模型繁忙），带 3 次退避重试；仍失败抛 DocumentGuardError。
    """
    last_error: str | None = None
    for attempt in range(1, 4):
        try:
            response = requests.post(ALL_CHECK_URL, json={"text": text}, timeout=ALL_CHECK_TIMEOUT)
            if response.status_code == 200:
                return response.json()
            last_error = f"内容检查服务返回 {response.status_code}"
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 3:
                time.sleep(3 * attempt)
                continue
            raise DocumentGuardError(last_error)
        except requests.exceptions.Timeout:
            last_error = "内容检查服务超时"
            if attempt < 3:
                time.sleep(3 * attempt)
                continue
        except requests.exceptions.RequestException as exc:
            last_error = "内容检查服务暂时不可用"
            if attempt < 3:
                time.sleep(3 * attempt)
                continue
    raise DocumentGuardError(last_error or "内容检查服务暂时不可用")


def review_text(text: str) -> dict:
    """文本内容检查：解析后原文传给二合一接口，响应原样返回。"""
    if not text or not text.strip():
        raise DocumentParseError("审查内容不能为空")
    return call_all_check(text)
