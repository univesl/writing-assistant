import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

import requests

from app.services.mineru_service import MinerUService


class MinerUServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pdf_path = Path(self.temp_dir.name) / "测试文件.pdf"
        self.pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
        self.service = MinerUService(
            api_url="https://mineru.example.test",
            vlm_url="https://mineru.example.test",
            request_timeout=5,
            parse_timeout=10,
            poll_interval=0,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("app.services.mineru_service.time.sleep")
    @patch("app.services.mineru_service.requests.get")
    @patch("app.services.mineru_service.requests.post")
    def test_parse_pdf_with_async_task_protocol(self, mock_post, mock_get, mock_sleep):
        mock_post.return_value = self._response({"task_id": "task-123"}, status_code=202)
        mock_get.side_effect = [
            self._response({"status": "processing"}),
            self._response({"status": "completed"}),
            self._response(
                {
                    "results": {
                        "测试文件": {
                            "md_content": "# 解析结果",
                        }
                    }
                }
            ),
        ]

        result = self.service.parse_pdf_to_markdown(str(self.pdf_path))

        self.assertEqual(result, "# 解析结果")
        mock_post.assert_called_once()
        post_url = mock_post.call_args.args[0]
        post_files = mock_post.call_args.kwargs["files"]
        self.assertEqual(post_url, "https://mineru.example.test/tasks")
        self.assertEqual(post_files["files"][0], "测试文件.pdf")
        self.assertEqual(post_files["files"][2], "application/pdf")
        self.assertEqual(
            mock_get.call_args_list,
            [
                call("https://mineru.example.test/tasks/task-123", timeout=5),
                call("https://mineru.example.test/tasks/task-123", timeout=5),
                call("https://mineru.example.test/tasks/task-123/result", timeout=5),
            ],
        )
        mock_sleep.assert_called_once_with(0)

    @patch("app.services.mineru_service.requests.get")
    @patch("app.services.mineru_service.requests.post")
    def test_uses_only_result_when_server_normalizes_file_name(self, mock_post, mock_get):
        mock_post.return_value = self._response({"task_id": "task-456"}, status_code=202)
        mock_get.side_effect = [
            self._response({"status": "completed"}),
            self._response({"results": {"normalized-name": {"md_content": "正文"}}}),
        ]

        result = self.service.parse_pdf_to_markdown(str(self.pdf_path))

        self.assertEqual(result, "正文")

    @patch("app.services.mineru_service.requests.get")
    @patch("app.services.mineru_service.requests.post")
    def test_failed_task_returns_none_without_fetching_result(self, mock_post, mock_get):
        mock_post.return_value = self._response({"task_id": "task-failed"}, status_code=202)
        mock_get.return_value = self._response(
            {"status": "failed", "error": "GPU worker failed"}
        )

        result = self.service.parse_pdf_to_markdown(str(self.pdf_path))

        self.assertIsNone(result)
        mock_get.assert_called_once_with(
            "https://mineru.example.test/tasks/task-failed",
            timeout=5,
        )

    @patch("app.services.mineru_service.requests.post")
    def test_submit_http_error_returns_none(self, mock_post):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("503 Server Error")
        mock_post.return_value = response

        result = self.service.parse_pdf_to_markdown(str(self.pdf_path))

        self.assertIsNone(result)

    @staticmethod
    def _response(payload, status_code=200):
        response = Mock(status_code=status_code)
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response


if __name__ == "__main__":
    unittest.main()
