import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers.write import _retrieve_rag_content
from app.schemas import WriteQuickIn
from app.services.kng_rag_service import KnGRAGService


class KnGRAGContractTest(unittest.TestCase):
    def test_is_ready_uses_status_endpoint(self):
        service = KnGRAGService(base_url="http://kng.test")
        response = Mock(status_code=200)

        with patch("app.services.kng_rag_service.requests.get", return_value=response) as request_get:
            self.assertTrue(service.is_ready())

        request_get.assert_called_once_with("http://kng.test/api/status", timeout=5)

    def test_query_uses_openai_compatible_completion_payload(self):
        service = KnGRAGService(base_url="http://kng.test")
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {"message": {"content": "检索结果"}}
            ]
        }

        with patch("app.services.kng_rag_service.requests.post", return_value=response) as request_post:
            content = service.query(
                query="主题",
                mode="local",
                system_prompt="系统提示",
                conversation_history=[{"role": "assistant", "content": "历史"}],
                knowledge_source="kg",
                stream=False,
            )

        self.assertEqual(content, "检索结果")
        request_post.assert_called_once()
        url = request_post.call_args.args[0]
        payload = request_post.call_args.kwargs["json"]
        self.assertEqual(url, "http://kng.test/api/v1/chats_openai/default/chat/completions")
        self.assertEqual(payload["model"], "kng")
        self.assertEqual(payload["mode"], "local")
        self.assertEqual(payload["knowledge_source"], "kg")
        self.assertFalse(payload["stream"])
        self.assertEqual([message["role"] for message in payload["messages"]], ["system", "assistant", "user"])

    def test_retrieve_for_document_generation_success_shape(self):
        service = KnGRAGService(base_url="http://kng.test")

        with patch.object(service, "query", return_value="参考内容"):
            result = service.retrieve_for_document_generation("通知", requirements="正式", mode="local")

        self.assertEqual(result["content"], "参考内容")
        self.assertIn("通知", result["query"])
        self.assertIn("timing", result)

    def test_retrieve_for_document_generation_failure_shape(self):
        service = KnGRAGService(base_url="http://kng.test")

        with patch.object(service, "query", side_effect=RuntimeError("service down")):
            result = service.retrieve_for_document_generation("通知", requirements="", mode="local")

        self.assertEqual(result["content"], "")
        self.assertIn("通知", result["query"])
        self.assertEqual(result["error"], "service down")
        self.assertIn("timing", result)


class WriteRAGFallbackTest(unittest.TestCase):
    def make_payload(self, **overrides):
        data = {
            "session_id": 1,
            "mode": "quick",
            "style": "general",
            "user_requirements": "写一篇通知",
            "reference_content": "",
            "reference_filename": "",
            "rag_content": "",
            "rag_references": [],
            "quotes": [],
            "article_content": "",
            "extracted_fields": {},
            "model_type": "general",
            "llm_model": "qwen",
            "use_rag": False,
        }
        data.update(overrides)
        return WriteQuickIn(**data)

    def test_use_rag_false_does_not_call_kng(self):
        payload = self.make_payload(use_rag=False)

        with patch("app.routers.write.get_kng_rag_service") as get_service:
            content, references = _retrieve_rag_content(payload)

        self.assertEqual(content, "")
        self.assertEqual(references, [])
        get_service.assert_not_called()

    def test_supplied_rag_content_skips_kng(self):
        payload = self.make_payload(use_rag=True, rag_content="外部检索内容", rag_references=[{"id": 1}])

        with patch("app.routers.write.get_kng_rag_service") as get_service:
            content, references = _retrieve_rag_content(payload)

        self.assertEqual(content, "外部检索内容")
        self.assertEqual(references, [{"id": 1}])
        get_service.assert_not_called()

    def test_kng_failure_falls_back_without_content(self):
        payload = self.make_payload(use_rag=True)

        with patch("app.routers.write.get_kng_rag_service", side_effect=RuntimeError("not available")):
            content, references = _retrieve_rag_content(payload)

        self.assertEqual(content, "")
        self.assertEqual(references, [])


if __name__ == "__main__":
    unittest.main()
