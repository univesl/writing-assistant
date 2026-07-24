import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers.write import write_edit_selection
from app.schemas import SaveArticleIn, WriteSelectionEditIn
from app.services.prompt_builder import build_selection_edit_prompt


async def _collect_stream(response):
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    return "".join(chunks)


class SelectionEditPromptTest(unittest.TestCase):
    def test_prompt_contains_only_selection_and_instruction(self):
        messages = build_selection_edit_prompt(
            selected_markdown="需要修改的句子。",
            instruction="改得更正式",
            style="notice",
        )
        prompt = "\n".join(message["content"] for message in messages)

        self.assertIn("需要修改的句子。", prompt)
        self.assertIn("改得更正式", prompt)
        self.assertIn("---REPLACEMENT---", prompt)
        self.assertIn("---SUMMARY---", prompt)
        self.assertIn("[[DELETE_SELECTION]]", prompt)
        self.assertIn("不得用 ***、---", prompt)
        self.assertIn("禁止续写、补写或复述选区之外的文章", prompt)
        self.assertNotIn("前置段落保持不变", prompt)
        self.assertNotIn("后置段落保持不变", prompt)

    def test_request_schema_has_no_full_article_field(self):
        payload = WriteSelectionEditIn(
            session_id=1,
            selected_markdown="选区",
            instruction="精简",
        )
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()

        self.assertIn("selected_markdown", data)
        self.assertNotIn("article_content", data)
        self.assertEqual(payload.llm_model, "xhang")

    def test_article_schema_allows_persisting_full_selection_deletion(self):
        payload = SaveArticleIn(session_id=1, article_content="")

        self.assertEqual(payload.article_content, "")


class SelectionEditRouteTest(unittest.IsolatedAsyncioTestCase):
    async def test_route_streams_selection_contract_without_database_write(self):
        payload = WriteSelectionEditIn(
            session_id=8,
            selected_markdown="原句",
            instruction="改为规范表述",
            style="notice",
        )
        captured = {}

        async def fake_stream(messages, llm_model):
            captured["messages"] = messages
            captured["llm_model"] = llm_model
            yield "---REPLACEMENT---\n新句\n"
            yield "---SUMMARY---\n已规范表述"

        with patch("app.routers.write.stream_text_from_llm", new=fake_stream):
            response = await write_edit_selection(payload)
            body = await _collect_stream(response)

        events = [
            json.loads(line.removeprefix("data: "))
            for line in body.splitlines()
            if line.startswith("data: ")
        ]
        self.assertEqual(captured["llm_model"], "xhang")
        self.assertIn("原句", captured["messages"][1]["content"])
        self.assertTrue(events[-1]["finish"])
        self.assertIn("---REPLACEMENT---", "".join(event["content"] for event in events))


if __name__ == "__main__":
    unittest.main()
