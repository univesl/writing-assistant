"""Request-scoped parsing for reference-writing uploads."""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Sequence

from fastapi import UploadFile

from .document_processor import is_supported_file, parse_document


REFERENCE_MAX_FILES = int(os.getenv("REFERENCE_MAX_FILES", "8"))
REFERENCE_MAX_FILE_BYTES = int(float(os.getenv("REFERENCE_MAX_FILE_MB", "20")) * 1024 * 1024)
REFERENCE_MAX_TOTAL_BYTES = int(float(os.getenv("REFERENCE_MAX_TOTAL_MB", "50")) * 1024 * 1024)
REFERENCE_MAX_PARSED_CHARS = int(os.getenv("REFERENCE_MAX_PARSED_CHARS", "40000"))
REFERENCE_PARSE_CONCURRENCY = max(1, int(os.getenv("REFERENCE_PARSE_CONCURRENCY", "2")))
UPLOAD_CHUNK_BYTES = 1024 * 1024


class ReferenceMaterialError(ValueError):
    """Raised when one or more reference materials cannot be used completely."""


def _safe_filename(filename: str, index: int) -> str:
    name = Path(filename or f"reference-{index}").name.replace("\x00", "").strip()
    return name or f"reference-{index}"


async def _copy_upload(upload: UploadFile, destination: Path, total_bytes: int) -> tuple[int, int]:
    file_bytes = 0
    with destination.open("wb") as output:
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_BYTES)
            if not chunk:
                break
            file_bytes += len(chunk)
            total_bytes += len(chunk)
            if file_bytes > REFERENCE_MAX_FILE_BYTES:
                raise ReferenceMaterialError(f"文件“{upload.filename}”超过单文件大小限制")
            if total_bytes > REFERENCE_MAX_TOTAL_BYTES:
                raise ReferenceMaterialError("全部参考文件超过总大小限制")
            output.write(chunk)

    if file_bytes == 0:
        raise ReferenceMaterialError(f"文件“{upload.filename}”为空")
    return file_bytes, total_bytes


async def _parse_saved_file(
    index: int,
    filename: str,
    path: Path,
    size_bytes: int,
    semaphore: asyncio.Semaphore,
) -> Dict[str, Any]:
    async with semaphore:
        content = await asyncio.to_thread(parse_document, path)

    if not content or not content.strip():
        raise ReferenceMaterialError(f"文件“{filename}”解析失败或正文为空")

    return {
        "index": index,
        "filename": filename,
        "size_bytes": size_bytes,
        "content": content.strip(),
        "content_length": len(content.strip()),
    }


async def parse_reference_uploads(
    files: Sequence[UploadFile],
    progress: Any = None,
) -> List[Dict[str, Any]]:
    """Parse every upload and remove all raw files before returning.

    progress: 可选 async 回调，每份文件解析完成时收到
        {"type": "parse", "index": i, "total": n, "filename": name}
    """
    uploads = list(files)
    if not uploads:
        raise ReferenceMaterialError("请至少上传一份参考文件")
    if len(uploads) > REFERENCE_MAX_FILES:
        raise ReferenceMaterialError(f"参考文件数量超过限制，最多允许 {REFERENCE_MAX_FILES} 份")

    async def report(index: int, total: int, filename: str):
        if not progress:
            return
        try:
            await progress(
                {"type": "parse", "index": index, "total": total, "filename": filename}
            )
        except Exception:
            pass

    try:
        with tempfile.TemporaryDirectory(prefix="wa-reference-") as temp_dir:
            root = Path(temp_dir)
            saved_files = []
            total_bytes = 0

            for index, upload in enumerate(uploads, start=1):
                filename = _safe_filename(upload.filename, index)
                if not is_supported_file(filename):
                    raise ReferenceMaterialError(
                        f"文件“{filename}”格式不支持，仅支持 PDF、DOCX、MD、TXT"
                    )

                path = root / f"{index:02d}_{filename}"
                file_bytes, total_bytes = await _copy_upload(upload, path, total_bytes)
                saved_files.append((index, filename, path, file_bytes))

            total = len(saved_files)
            semaphore = asyncio.Semaphore(REFERENCE_PARSE_CONCURRENCY)

            async def parse_one(index, filename, path, size_bytes):
                content = await _parse_saved_file(
                    index, filename, path, size_bytes, semaphore
                )
                await report(index, total, filename)
                return content

            results = await asyncio.gather(
                *[
                    parse_one(index, filename, path, size_bytes)
                    for index, filename, path, size_bytes in saved_files
                ],
                return_exceptions=True,
            )

            failures = [str(item) for item in results if isinstance(item, Exception)]
            if failures:
                raise ReferenceMaterialError("；".join(failures))

            materials = sorted(results, key=lambda item: item["index"])
            total_chars = sum(item["content_length"] for item in materials)
            if total_chars > REFERENCE_MAX_PARSED_CHARS:
                raise ReferenceMaterialError(
                    "全部参考文件解析后的正文超过长度限制"
                    f"（{total_chars} > {REFERENCE_MAX_PARSED_CHARS} 字符）"
                )
            return materials
    finally:
        await asyncio.gather(
            *[upload.close() for upload in uploads],
            return_exceptions=True,
        )


def format_reference_materials(materials: Sequence[Dict[str, Any]]) -> str:
    """Keep file boundaries explicit so every parsed material reaches the prompt."""
    blocks = []
    for material in materials:
        blocks.append(
            f"【参考材料 {material['index']}：{material['filename']}】\n"
            f"{material['content']}"
        )
    return "\n\n".join(blocks)


def summarize_reference_filenames(materials: Sequence[Dict[str, Any]]) -> str:
    return "、".join(material["filename"] for material in materials)
