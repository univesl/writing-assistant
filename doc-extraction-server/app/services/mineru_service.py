import os
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv


load_dotenv()


DEFAULT_MINERU_API_URL = "https://37cb31.xhang.buaa.edu.cn:52811"
MINERU_API_URL = os.getenv("MINERU_API_URL", DEFAULT_MINERU_API_URL).strip().rstrip("/")
MINERU_REQUEST_TIMEOUT = float(os.getenv("MINERU_REQUEST_TIMEOUT", "180"))
MINERU_PARSE_TIMEOUT = float(os.getenv("MINERU_PARSE_TIMEOUT", "600"))
MINERU_POLL_INTERVAL = float(os.getenv("MINERU_POLL_INTERVAL", "2"))
# 2026-11-20 迁移适配：native = 自建原生 mineru-api（同步 /file_parse），router = 旧的共享 Router
MINERU_MODE = os.getenv("MINERU_MODE", "router").strip().lower()
MINERU_NATIVE_LANG = os.getenv("MINERU_NATIVE_LANG", "ch")


class MinerUService:
    """PDF 解析为 Markdown。支持两种后端（MINERU_MODE）：

    - router: 旧的共享 MinerU Router（提交 /tasks + 轮询）；
    - native: 自建原生 mineru-api（同步 POST /file_parse，CPU/GPU 均可）。
    """

    def __init__(
        self,
        api_url: str = MINERU_API_URL,
        request_timeout: float = MINERU_REQUEST_TIMEOUT,
        parse_timeout: float = MINERU_PARSE_TIMEOUT,
        poll_interval: float = MINERU_POLL_INTERVAL,
        mode: str = MINERU_MODE,
    ):
        self.api_url = api_url.rstrip("/")
        self.request_timeout = request_timeout
        self.parse_timeout = parse_timeout
        self.poll_interval = poll_interval
        self.mode = mode if mode in ("router", "native") else "router"

    def parse_pdf_to_markdown(self, pdf_path: str) -> Optional[str]:
        """提交 PDF 解析任务并返回 Markdown；失败时返回 ``None``。"""
        file_path = Path(pdf_path)

        try:
            if self.mode == "native":
                return self._parse_native(file_path)

            task_id = self._submit_task(file_path)
            if not task_id:
                return None

            if not self._wait_for_completion(task_id):
                return None

            markdown_content = self._get_markdown_result(task_id, file_path.stem)
            if not markdown_content:
                print(f"[MinerU] 结果中没有 Markdown: {file_path.name}")
                return None

            print(f"[MinerU] 解析成功: {file_path.name}")
            return markdown_content
        except Exception as exc:
            print(f"[MinerU] 解析异常: {type(exc).__name__}: {exc}")
            return None

    def _parse_native(self, file_path: Path) -> Optional[str]:
        """自建原生 mineru-api：同步 POST /file_parse，一次拿 Markdown。"""
        url = f"{self.api_url}/file_parse"
        with file_path.open("rb") as file_obj:
            response = requests.post(
                url,
                files={"files": (file_path.name, file_obj, "application/pdf")},
                data={"output_format": "md", "language": MINERU_NATIVE_LANG, "backend": "pipeline"},
                timeout=self.parse_timeout,
            )
        response.raise_for_status()
        result = response.json()
        markdown_content = self._extract_native_markdown(result)
        if not markdown_content:
            print(f"[MinerU][native] 结果中没有 Markdown: {file_path.name}, 顶层键={list(result.keys()) if isinstance(result, dict) else type(result).__name__}")
            return None
        print(f"[MinerU][native] 解析成功: {file_path.name}")
        return markdown_content

    @staticmethod
    def _extract_native_markdown(result) -> Optional[str]:
        """从原生 /file_parse 响应中取 markdown 文本，兼容常见返回形态。"""
        if isinstance(result, str):
            return result or None
        if not isinstance(result, dict):
            return None
        for key in ("md_content", "markdown", "md", "text"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value
        results = result.get("results")
        if isinstance(results, dict) and results:
            first = next(iter(results.values()))
            if isinstance(first, dict):
                md = first.get("md_content") or first.get("markdown")
                if isinstance(md, str) and md.strip():
                    return md
        return None

    def _submit_task(self, file_path: Path) -> Optional[str]:
        url = f"{self.api_url}/tasks"

        with file_path.open("rb") as file_obj:
            response = requests.post(
                url,
                files={
                    "files": (
                        file_path.name,
                        file_obj,
                        "application/pdf",
                    )
                },
                timeout=self.request_timeout,
            )

        response.raise_for_status()
        result = response.json()
        task_id = result.get("task_id")

        if not task_id:
            print(f"[MinerU] 提交任务失败，响应中没有 task_id: {file_path.name}")
            return None

        print(f"[MinerU] 任务已提交: {file_path.name}, task_id={task_id}")
        return task_id

    def _wait_for_completion(self, task_id: str) -> bool:
        url = f"{self.api_url}/tasks/{task_id}"
        deadline = time.monotonic() + self.parse_timeout
        last_status = None

        while time.monotonic() < deadline:
            response = requests.get(url, timeout=self.request_timeout)
            response.raise_for_status()
            result = response.json()
            status = str(result.get("status", "")).lower()

            if status != last_status:
                print(f"[MinerU] 当前状态: {status or 'unknown'}, task_id={task_id}")
                last_status = status

            if status in {"completed", "done", "success", "succeeded"}:
                return True

            if status in {"failed", "error", "cancelled", "canceled"}:
                error = result.get("error") or result.get("detail") or "未知错误"
                print(f"[MinerU] 任务失败: {error}, task_id={task_id}")
                return False

            time.sleep(self.poll_interval)

        print(f"[MinerU] 解析超时: task_id={task_id}")
        return False

    def _get_markdown_result(self, task_id: str, file_stem: str) -> Optional[str]:
        url = f"{self.api_url}/tasks/{task_id}/result"
        response = requests.get(url, timeout=self.request_timeout)
        response.raise_for_status()
        result = response.json()
        results = result.get("results") or {}

        file_result = results.get(file_stem)
        if file_result is None and len(results) == 1:
            file_result = next(iter(results.values()))

        if not isinstance(file_result, dict):
            return None

        markdown_content = file_result.get("md_content")
        return markdown_content if isinstance(markdown_content, str) else None


mineru_service = MinerUService()
