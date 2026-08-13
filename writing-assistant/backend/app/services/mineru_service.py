"""Direct client for the deployed MinerU Router service.

Writing Assistant keeps this adapter separate from ``doc-extraction-server``.
The public ``parse_pdf_to_markdown`` method is retained for existing upload
flows, while the implementation talks directly to MinerU's asynchronous
``/tasks`` API.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional

import requests


DEFAULT_MINERU_API_URL = "https://37cb31.xhang.buaa.edu.cn:52811"
DEFAULT_REQUEST_TIMEOUT = 15.0
DEFAULT_PARSE_TIMEOUT = 110.0
DEFAULT_POLL_INTERVAL = 2.0


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return max(0.0, float(value))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _nested_value(payload: Any, key: str) -> Any:
    if not isinstance(payload, dict):
        return None
    if key in payload:
        return payload[key]
    data = payload.get("data")
    if isinstance(data, dict):
        return data.get(key)
    return None


class MinerUService:
    """Submit a PDF directly to the deployed MinerU Router and read Markdown."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        timeout: Optional[float] = None,
        verify_ssl: Optional[bool] = None,
        parse_timeout: Optional[float] = None,
        poll_interval: Optional[float] = None,
    ) -> None:
        self.base_url = (
            api_url or os.getenv("MINERU_API_URL") or DEFAULT_MINERU_API_URL
        ).rstrip("/")
        # Keep api_url as an alias for compatibility with existing callers/tests.
        self.api_url = self.base_url
        self.request_timeout = (
            timeout
            if timeout is not None
            else _env_float("MINERU_REQUEST_TIMEOUT", DEFAULT_REQUEST_TIMEOUT)
        )
        self.parse_timeout = (
            parse_timeout
            if parse_timeout is not None
            else _env_float("MINERU_PARSE_TIMEOUT", DEFAULT_PARSE_TIMEOUT)
        )
        self.poll_interval = (
            poll_interval
            if poll_interval is not None
            else _env_float("MINERU_POLL_INTERVAL", DEFAULT_POLL_INTERVAL)
        )
        self.verify_ssl = (
            _env_bool("MINERU_VERIFY_SSL", False)
            if verify_ssl is None
            else verify_ssl
        )

    def parse_pdf_to_markdown(self, pdf_path: str) -> Optional[str]:
        """Parse one PDF through MinerU Router's asynchronous task API."""
        path = Path(pdf_path)
        if not path.is_file():
            print(f"[MinerU] PDF does not exist: {path}")
            return None

        task_id = self._submit_task(path)
        if not task_id:
            return None

        status_payload = self._wait_for_task(task_id, path.name)
        if status_payload is None:
            return None

        result = self._get_task_result(task_id, path.name)
        if not result:
            return None

        print(f"[MinerU] parsed {path.name}, chars={len(result)}")
        return result

    def _submit_task(self, path: Path) -> Optional[str]:
        endpoint = f"{self.base_url}/tasks"
        try:
            with path.open("rb") as file_obj:
                response = requests.post(
                    endpoint,
                    files={
                        "files": (path.name, file_obj, "application/pdf")
                    },
                    timeout=self.request_timeout,
                    verify=self.verify_ssl,
                )
        except requests.RequestException as exc:
            print(f"[MinerU] task submission failed for {path.name}: {exc}")
            return None
        except OSError as exc:
            print(f"[MinerU] could not read {path.name}: {exc}")
            return None

        payload = self._json_or_none(response, f"submit {path.name}")
        if payload is None:
            return None

        task_id = _nested_value(payload, "task_id") or _nested_value(
            payload, "id"
        )
        if not task_id:
            print(f"[MinerU] task submission returned no task_id for {path.name}")
            return None

        task_id = str(task_id)
        print(f"[MinerU] submitted {path.name}, task_id={task_id}")
        return task_id

    def _wait_for_task(
        self, task_id: str, file_name: str
    ) -> Optional[dict[str, Any]]:
        endpoint = f"{self.base_url}/tasks/{task_id}"
        deadline = time.monotonic() + self.parse_timeout
        last_status = "unknown"

        while time.monotonic() <= deadline:
            try:
                response = requests.get(
                    endpoint,
                    timeout=self.request_timeout,
                    verify=self.verify_ssl,
                )
            except requests.RequestException as exc:
                print(f"[MinerU] task status failed for {file_name}: {exc}")
                return None

            payload = self._json_or_none(response, f"status {task_id}")
            if payload is None:
                return None

            raw_status = _nested_value(payload, "status")
            status = str(raw_status or "").strip().lower()
            last_status = status or last_status

            if status in {"completed", "done", "success", "succeeded"}:
                return payload
            if status in {
                "failed",
                "failure",
                "error",
                "cancelled",
                "canceled",
            }:
                detail = _nested_value(payload, "error") or _nested_value(
                    payload, "message"
                )
                print(
                    f"[MinerU] task failed for {file_name}: "
                    f"status={status} detail={detail or 'unknown'}"
                )
                return None

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(self.poll_interval, remaining))

        print(
            f"[MinerU] task timed out for {file_name}: "
            f"task_id={task_id} status={last_status} "
            f"timeout={self.parse_timeout}s"
        )
        return None

    def _get_task_result(
        self, task_id: str, file_name: str
    ) -> Optional[str]:
        endpoint = f"{self.base_url}/tasks/{task_id}/result"
        try:
            response = requests.get(
                endpoint,
                timeout=self.request_timeout,
                verify=self.verify_ssl,
            )
        except requests.RequestException as exc:
            print(f"[MinerU] result request failed for {file_name}: {exc}")
            return None

        payload = self._json_or_none(response, f"result {task_id}")
        if payload is None:
            return None

        content = self._extract_markdown(payload, file_name)
        if not content:
            print(f"[MinerU] empty parsed content for {file_name}")
            return None
        return content.strip()

    @staticmethod
    def _json_or_none(response: Any, operation: str) -> Optional[dict[str, Any]]:
        if not 200 <= response.status_code < 300:
            detail = getattr(response, "text", "")[:300].replace("\n", " ")
            print(
                f"[MinerU] HTTP {response.status_code} during {operation}: "
                f"{detail}"
            )
            return None
        try:
            payload = response.json()
        except ValueError as exc:
            print(f"[MinerU] invalid JSON during {operation}: {exc}")
            return None
        if not isinstance(payload, dict):
            print(f"[MinerU] unexpected response during {operation}")
            return None
        return payload

    @staticmethod
    def _extract_markdown(payload: dict[str, Any], file_name: str) -> Optional[str]:
        results = payload.get("results")
        if not isinstance(results, dict):
            data = payload.get("data")
            results = data.get("results") if isinstance(data, dict) else None

        if isinstance(results, dict):
            stem = Path(file_name).stem
            candidates = [stem, file_name]
            for key in candidates:
                item = results.get(key)
                content = MinerUService._content_from_result(item)
                if content:
                    return content

            if len(results) == 1:
                content = MinerUService._content_from_result(
                    next(iter(results.values()))
                )
                if content:
                    return content

        return MinerUService._content_from_result(payload)

    @staticmethod
    def _content_from_result(value: Any) -> Optional[str]:
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, dict):
            for key in ("md_content", "markdown", "content", "parsed_content"):
                content = value.get(key)
                if isinstance(content, str) and content.strip():
                    return content.strip()
        return None


mineru_service = MinerUService()
