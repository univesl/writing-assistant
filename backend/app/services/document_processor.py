#!/usr/bin/env python3
"""
文档处理服务
职责：处理会话级文件的上传、解析、字段提取
"""

import json
import html
import os
import re
import shutil
from pathlib import Path
from typing import Dict, Optional
import asyncio

from .field_extractor import FieldExtractor, AVAILABLE_MODELS

from ..services.mineru_service import mineru_service


# 会话文件存储根目录（与 KNG 的持久化知识库分开）
SESSION_FILES_ROOT = Path(os.getenv("SESSION_FILES_ROOT") or (Path(__file__).resolve().parents[3] / "session_files"))


def ensure_session_dir(session_id: int) -> Path:
    """确保会话目录存在"""
    session_dir = SESSION_FILES_ROOT / str(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def get_session_dir(session_id: int) -> Path:
    """获取会话目录路径"""
    return SESSION_FILES_ROOT / str(session_id)


def save_uploaded_file(session_id: int, filename: str, content: bytes) -> Path:
    """保存上传的文件到会话目录"""
    session_dir = ensure_session_dir(session_id)
    # 清理文件名，避免特殊字符
    safe_filename = Path(filename).name.replace('..', '_').replace('/', '_')
    file_path = session_dir / safe_filename
    
    with open(file_path, 'wb') as f:
        f.write(content)
    
    return file_path


def decode_uploaded_text(content: bytes) -> str:
    """Decode Chinese text without silently replacing damaged characters."""
    if content.startswith(b"\xef\xbb\xbf"):
        return content.decode("utf-8-sig")
    for encoding in ("utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeError("文本编码无法识别，请将文件保存为 UTF-8 或 GB18030 后重试")


# pandoc/MinerU 转 markdown 时会给 _ @ " 等字符加转义反斜杠（如 zhang\_san\@x.com、\"引号\"），
# 下游错别字/标点检查会把转义符误判为原文错误，解析后统一还原。
_MD_ESCAPE_RE = re.compile(r'\\([\\`*_{}\[\]()#+\-.!|\"<>~$%&/,;:?@])')

# markdown 语法标记（粗体、斜体、标题、列表、链接、图片、行内代码、HTML、表格）不属于正文，
# MinerU(PDF) 输出的 markdown 保留这些标记，进入检查会被报"多余星号/方括号/竖线"等幻影错误
_MD_BOLD_RE = re.compile(r'(\*\*|__)(?=\S)(.+?)(?<=\S)\1')
# 斜体仅剥离"短且无空白、含中文、两侧非数字"的星号包裹（MinerU 强调中文术语），
# 避免 5*6=30、a*b*c 这类字面星号被误删
_MD_ITALIC_RE = re.compile(r'(?<![\d*])\*([^*\s]{1,30}[\u4e00-\u9fff][^*\s]{0,30})\*(?!\d)')
_MD_HEADING_RE = re.compile(r'^#{1,6}\s+', re.M)
_MD_LIST_RE = re.compile(r'^\s*([-*+]|\d+[.、])\s+', re.M)
_MD_LINK_RE = re.compile(r'\[([^\]]*)\]\([^)]*\)')
_MD_IMAGE_RE = re.compile(r'!\[[^\]]*\]\([^)]*\)')
_MD_CODE_RE = re.compile(r'`([^`\n]+)`')
_MD_HTML_BR_RE = re.compile(r'<br\s*/?>', re.I)
_MD_HTML_TAG_RE = re.compile(r'</?[a-zA-Z][^<>]*>')
# pandoc -t plain 会把 docx 表格渲染成 ASCII 网格（-------- 边框 + 空格填充）
_ASCII_BORDER_RE = re.compile(r'^\s*-+(?:\s+-+)*\s*$')


def strip_markdown_escapes(text: Optional[str]) -> Optional[str]:
    """还原 pandoc/MinerU markdown 输出中的转义反斜杠"""
    if not text:
        return text
    return _MD_ESCAPE_RE.sub(r'\1', text)


def _flatten_pipe_tables(text: str) -> str:
    """markdown 管道表格（|a|b|）转为制表符分隔的纯文本行"""
    if '|' not in text:
        return text
    out = []
    for line in text.split('\n'):
        s = line.strip()
        if s.startswith('|') and s.endswith('|') and len(s) > 1:
            cells = [c.strip() for c in s[1:-1].split('|')]
            if cells and all(re.fullmatch(r':?-{2,}:?', c) for c in cells):
                continue
            out.append('\t'.join(cells))
        else:
            out.append(line)
    return '\n'.join(out)


def flatten_ascii_tables(text: Optional[str]) -> Optional[str]:
    """pandoc plain 输出的 ASCII 表格还原为制表符分隔行（丢弃边框线）"""
    if not text:
        return text
    lines = text.split('\n')
    if not any(_ASCII_BORDER_RE.match(line) for line in lines):
        return text
    out, in_table = [], False
    for line in lines:
        if _ASCII_BORDER_RE.match(line):
            in_table = True
            continue
        if in_table:
            if not line.strip():
                in_table = False
                out.append(line)
            else:
                out.append(re.sub(r'\s{2,}', '\t', line.strip()))
        else:
            out.append(line)
    return '\n'.join(out)


def strip_markdown_syntax(text: Optional[str]) -> Optional[str]:
    """剥离 markdown 语法标记，只保留正文文字（用于 MinerU 等 markdown 输出的清洗）"""
    if not text:
        return text
    text = _MD_HTML_BR_RE.sub('\n', text)
    text = _MD_IMAGE_RE.sub('', text)
    text = _MD_LINK_RE.sub(r'\1', text)
    text = _MD_CODE_RE.sub(r'\1', text)
    text = _MD_BOLD_RE.sub(r'\2', text)
    text = _MD_ITALIC_RE.sub(r'\1', text)
    text = _MD_HEADING_RE.sub('', text)
    text = _MD_LIST_RE.sub('', text)
    text = _MD_HTML_TAG_RE.sub('', text)
    text = html.unescape(text)
    text = _flatten_pipe_tables(text)
    return text


def parse_document(file_path: Path) -> Optional[str]:
    """
    解析文档为纯文本（保留段落分隔）
    支持 PDF、DOCX、MD、TXT
    """
    file_extension = file_path.suffix.lower()

    try:
        if file_extension == '.pdf':
            md = mineru_service.parse_pdf_to_markdown(str(file_path))
            return strip_markdown_syntax(strip_markdown_escapes(md))
        elif file_extension == '.docx':
            import subprocess
            md_temp_path = str(file_path) + '.txt'
            result = subprocess.run(
                ['pandoc', '-f', 'docx', '-t', 'plain', '--wrap=none', '-o', md_temp_path, str(file_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0 and os.path.exists(md_temp_path):
                with open(md_temp_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                os.unlink(md_temp_path)
                return flatten_ascii_tables(content)
            return None
        elif file_extension in {'.md', '.txt'}:
            with open(file_path, 'rb') as f:
                return decode_uploaded_text(f.read())
        else:
            return None
    except UnicodeError:
        raise
    except Exception as e:
        print(f"[ERROR] 解析文档失败: {e}")
        return None


def extract_fields_from_content(content: str, model_name: str = "qwen2.5-72b") -> Dict[str, str]:
    """
    从文档内容提取字段
    """
    try:
        extractor = FieldExtractor.from_model(model_name)
        results = extractor.extract(content)
        return results
    except Exception as e:
        print(f"[ERROR] 字段提取失败: {e}")
        return {}


def delete_session_files(session_id: int) -> bool:
    """删除会话的所有文件"""
    try:
        session_dir = get_session_dir(session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir)
            print(f"[INFO] 已删除会话 {session_id} 的文件目录: {session_dir}")
        return True
    except Exception as e:
        print(f"[ERROR] 删除会话文件失败: {e}")
        return False


def get_file_type(filename: str) -> str:
    """获取文件类型"""
    ext = Path(filename).suffix.lower()
    type_map = {
        '.pdf': 'pdf',
        '.docx': 'docx',
        '.md': 'markdown',
        '.txt': 'text'
    }
    return type_map.get(ext, 'unknown')


def is_supported_file(filename: str) -> bool:
    """检查是否支持该文件类型"""
    ext = Path(filename).suffix.lower()
    return ext in ['.pdf', '.docx', '.md', '.txt']
