#!/usr/bin/env python3
"""
文档处理服务
职责：处理会话级文件的上传、解析、字段提取
"""

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Optional
import asyncio

from .field_extractor import FieldExtractor, AVAILABLE_MODELS

from ..services.mineru_service import mineru_service


# 会话文件存储根目录（与 KNG 的持久化知识库分开）
SESSION_FILES_ROOT = Path("/home/liubin/writing-assistant/session_files")


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


def parse_document(file_path: Path) -> Optional[str]:
    """
    解析文档为 Markdown
    支持 PDF、DOCX、MD、TXT
    """
    file_extension = file_path.suffix.lower()
    
    try:
        if file_extension == '.pdf':
            return mineru_service.parse_pdf_to_markdown(str(file_path))
        elif file_extension == '.docx':
            import subprocess
            md_temp_path = str(file_path) + '.md'
            result = subprocess.run(
                ['pandoc', '-f', 'docx', '-t', 'markdown', '-o', md_temp_path, str(file_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0 and os.path.exists(md_temp_path):
                with open(md_temp_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                os.unlink(md_temp_path)
                return content
            return None
        elif file_extension == '.md':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        elif file_extension == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return None
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
