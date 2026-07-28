import os
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv


load_dotenv()


DEFAULT_MINERU_API_URL = "https://37cb31.xhang.buaa.edu.cn:52811"
MINERU_API_URL = os.getenv("MINERU_API_URL", DEFAULT_MINERU_API_URL).strip().rstrip("/")
MINERU_VLM_URL = os.getenv("MINERU_VLM_URL", MINERU_API_URL).strip().rstrip("/")
MINERU_REQUEST_TIMEOUT = float(os.getenv("MINERU_REQUEST_TIMEOUT", "60"))
MINERU_PARSE_TIMEOUT = float(os.getenv("MINERU_PARSE_TIMEOUT", "600"))
MINERU_POLL_INTERVAL = float(os.getenv("MINERU_POLL_INTERVAL", "2"))


class MinerUService:
    """通过已部署的 MinerU Router 服务将 PDF 解析为 Markdown。"""

    def __init__(
        self,
        api_url: str = MINERU_API_URL,
        vlm_url: str = MINERU_VLM_URL,
        request_timeout: float = MINERU_REQUEST_TIMEOUT,
        parse_timeout: float = MINERU_PARSE_TIMEOUT,
        poll_interval: float = MINERU_POLL_INTERVAL,
    ):
        # 当前部署的 API/VLM 地址相同；优先使用专门的 VLM 地址，保留两个
        # 环境变量是为了兼容后续把路由层和 VLM 层拆分部署的场景。
        self.api_url = api_url.rstrip("/")
        self.vlm_url = (vlm_url or api_url).rstrip("/")
        self.base_url = self.vlm_url
        self.request_timeout = request_timeout
        self.parse_timeout = parse_timeout
        self.poll_interval = poll_interval

    def parse_pdf_to_markdown(self, pdf_path: str) -> Optional[str]:
        """提交 PDF 解析任务并返回 Markdown；失败时返回 ``None``。"""
        file_path = Path(pdf_path)

        try:
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

    def _submit_task(self, file_path: Path) -> Optional[str]:
        url = f"{self.base_url}/tasks"

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
        url = f"{self.base_url}/tasks/{task_id}"
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
        url = f"{self.base_url}/tasks/{task_id}/result"
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
