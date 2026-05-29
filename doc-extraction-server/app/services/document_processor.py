import os
import shutil
from pathlib import Path
from typing import Dict, Optional

from .field_extractor import FieldExtractor, AVAILABLE_MODELS
from .mineru_service import mineru_service


def parse_document(file_path: Path) -> Optional[str]:
    file_extension = file_path.suffix.lower()

    try:
        if file_extension == '.pdf':
            return mineru_service.parse_pdf_to_markdown(str(file_path))
        elif file_extension == '.docx':
            md_temp_path = str(file_path) + '.md'
            result = __import__('subprocess').run(
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
    try:
        extractor = FieldExtractor.from_model(model_name)
        results = extractor.extract(content)
        return results
    except Exception as e:
        print(f"[ERROR] 字段提取失败: {e}")
        return {}


def get_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    type_map = {
        '.pdf': 'pdf',
        '.docx': 'docx',
        '.md': 'markdown',
        '.txt': 'text'
    }
    return type_map.get(ext, 'unknown')


def is_supported_file(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in ['.pdf', '.docx', '.md', '.txt']