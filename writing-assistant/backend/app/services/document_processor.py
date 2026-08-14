"""文档解析服务：把上传的参考文件解析为 Markdown 文本。"""

import os
from pathlib import Path
from typing import Optional

from ..services.mineru_service import mineru_service


def parse_document(file_path: Path) -> Optional[str]:
    """
    解析文档为 Markdown
    支持 PDF、DOCX、MD、TXT
    """
    file_extension = file_path.suffix.lower()

    try:
        if file_extension == ".pdf":
            return mineru_service.parse_pdf_to_markdown(str(file_path))
        elif file_extension == ".docx":
            import subprocess

            md_temp_path = str(file_path) + ".md"
            result = subprocess.run(
                [
                    "pandoc",
                    "-f",
                    "docx",
                    "-t",
                    "markdown",
                    "-o",
                    md_temp_path,
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and os.path.exists(md_temp_path):
                with open(md_temp_path, "r", encoding="utf-8") as f:
                    content = f.read()
                os.unlink(md_temp_path)
                return content
            return None
        elif file_extension == ".md":
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        elif file_extension == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return None
    except Exception as e:
        print(f"[ERROR] 解析文档失败: {e}")
        return None


def is_supported_file(filename: str) -> bool:
    """检查是否支持该文件类型"""
    ext = Path(filename).suffix.lower()
    return ext in [".pdf", ".docx", ".md", ".txt"]
