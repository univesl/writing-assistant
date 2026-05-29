import base64
from pathlib import Path

from .document_processor import (
    extract_fields_from_content,
    get_file_type,
    is_supported_file,
    parse_document,
)


UPLOAD_DIR = Path("uploads")


class UnsupportedFileTypeError(Exception):
    pass


class DocumentParseError(Exception):
    pass


def extract_from_base64(
    filename: str,
    content_base64: str,
    model_name: str = "qwen2.5-72b",
    include_parsed_content: bool = False,
) -> dict:
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