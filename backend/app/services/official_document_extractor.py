import base64
import os
import tempfile
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
        "model_name": model_name,
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

        try:
            response = requests.post(
                GUARD_API_URL,
                json={"text": parsed_content},
                timeout=GUARD_API_TIMEOUT,
            )
            response.raise_for_status()
            review: dict[str, Any] = response.json()
        except requests.exceptions.Timeout as exc:
            raise DocumentGuardError("内容审查服务超时，请稍后重试") from exc
        except requests.exceptions.ConnectionError as exc:
            raise DocumentGuardError("内容审查服务暂时不可用") from exc
        except (requests.exceptions.RequestException, ValueError) as exc:
            raise DocumentGuardError("内容审查服务返回异常") from exc

        return {
            "filename": filename,
            "file_type": get_file_type(filename),
            "content_length": len(parsed_content),
            "review": {
                "harmful": review.get("harmful", "false"),
                "harmful_type": review.get("harmful_type", "none"),
                "harmful_type_label": review.get("harmful_type_label", "无"),
                "harmful_reason": review.get("harmful_reason", ""),
                "harmful_words": review.get("harmful_words", ""),
                "harmful_degree": review.get("harmful_degree", "none"),
                "harmful_degree_label": review.get("harmful_degree_label", "无"),
                "confidence": review.get("confidence", "low"),
                "confidence_label": review.get("confidence_label", "低"),
                "highlight_spans": review.get("highlight_spans", []),
                "stage": review.get("stage"),
            },
        }
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
