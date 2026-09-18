import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.extractor_main import app


class DocumentExtractionApiContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.base_result = {
            "filename": "公文.pdf",
            "file_type": "pdf",
            "content_length": 8,
            "fields": {"文件标题": "测试公文"},
        }

    @patch("app.routers.official_document_extractions.extract_from_base64")
    def test_default_response_matches_legacy_document(self, mock_extract):
        mock_extract.return_value = dict(self.base_result)

        response = self.client.post(
            "/api/documents/extractions",
            json={
                "filename": "公文.pdf",
                "content_base64": "JVBERg==",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            set(response.json()),
            {"filename", "file_type", "content_length", "fields"},
        )
        self.assertNotIn("parsed_content", response.json())
        mock_extract.assert_called_once_with(
            filename="公文.pdf",
            content_base64="JVBERg==",
            model_name="qwen2.5-72b",
            include_parsed_content=False,
        )

    @patch("app.routers.official_document_extractions.extract_from_base64")
    def test_parsed_content_is_returned_only_when_requested(self, mock_extract):
        mock_extract.return_value = {
            **self.base_result,
            "parsed_content": "# 测试正文",
        }

        response = self.client.post(
            "/api/documents/extractions",
            json={
                "filename": "公文.pdf",
                "content_base64": "JVBERg==",
                "include_parsed_content": True,
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["parsed_content"], "# 测试正文")
        mock_extract.assert_called_once_with(
            filename="公文.pdf",
            content_base64="JVBERg==",
            model_name="qwen2.5-72b",
            include_parsed_content=True,
        )


if __name__ == "__main__":
    unittest.main()
