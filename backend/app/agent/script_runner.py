from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ScriptExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScriptSpec:
    skill_name: str
    relative_path: str
    input_kind: str
    timeout_seconds: float = 10.0
    max_output_chars: int = 20000


APP_ROOT = Path(__file__).resolve().parents[3]
APPROVED_SCRIPTS = {
    "scripts/prose_lint.py": ScriptSpec("official-document-writing", "scripts/prose_lint.py", "text"),
    "scripts/review_document.py": ScriptSpec("official-document-writing", "scripts/review_document.py", "docx"),
}


def registered_executors() -> dict[str, object]:
    """Return only reviewed relative script paths for Skill status validation."""
    return {path: spec for path, spec in APPROVED_SCRIPTS.items()}


async def execute_script(skill_name: str, relative_path: str, payload: Any) -> Any:
    spec = APPROVED_SCRIPTS.get(relative_path)
    if not spec or spec.skill_name != skill_name:
        raise ScriptExecutionError("脚本未被服务端登记")
    script_path = (APP_ROOT / "skills" / skill_name / relative_path).resolve()
    skill_root = (APP_ROOT / "skills" / skill_name).resolve()
    if skill_root not in script_path.parents or not script_path.is_file():
        raise ScriptExecutionError("脚本路径无效")
    if spec.input_kind == "text":
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(script_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(skill_root),
            env={"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"},
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(str(payload or "").encode("utf-8")),
            timeout=spec.timeout_seconds,
        )
    else:
        if not isinstance(payload, str):
            raise ScriptExecutionError("DOCX审查脚本只接受受控文件路径")
        input_path = Path(payload).resolve()
        if input_path.suffix.lower() != ".docx" or skill_root not in input_path.parents:
            raise ScriptExecutionError("DOCX文件不在受控目录")
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(script_path), str(input_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(skill_root),
            env={"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"},
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=spec.timeout_seconds
        )
    if process.returncode != 0:
        raise ScriptExecutionError(stderr.decode("utf-8", errors="replace")[:1000] or "脚本执行失败")
    raw = stdout.decode("utf-8", errors="replace")[: spec.max_output_chars]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScriptExecutionError("脚本输出不是合法JSON") from exc
