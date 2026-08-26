import io
import shutil
import unittest
import zipfile

from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.services.document_processor import decode_uploaded_text


class UploadedTextDecodingTest(unittest.TestCase):
    def test_utf8_bom_and_gb18030_are_preserved(self):
        text = "关于做好网络安全工作的通知"
        self.assertEqual(decode_uploaded_text(b"\xef\xbb\xbf" + text.encode("utf-8")), text)
        self.assertEqual(decode_uploaded_text(text.encode("gb18030")), text)

    def test_invalid_truncated_multibyte_input_is_rejected(self):
        with self.assertRaisesRegex(UnicodeError, "编码无法识别"):
            decode_uploaded_text(b"\x81")


@unittest.skipUnless(shutil.which("pandoc"), "Pandoc is required for DOCX export")
class DocxExportTest(unittest.TestCase):
    def test_fake_docx_template_is_rejected(self):
        with TestClient(app) as client:
            response = client.post(
                "/api/templates/upload",
                data={"name": "伪模板"},
                files={"file": ("fake.docx", b"not-a-zip", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )
        self.assertEqual(response.json()["code"], 400)

    def test_exported_docx_round_trips_chinese_without_replacement_characters(self):
        article = (
            "# 关于做好网络安全工作的通知\n\n"
            "一、加强值班值守\n\n"
            "各单位要落实网络安全值班和事件报告要求。"
        )
        with TestClient(app) as client:
            session_id = client.post(
                "/api/session/create", json={"session_name": "中文导出测试"}
            ).json()["data"]["session_id"]
            try:
                client.post(
                    "/api/content/article/save",
                    json={"session_id": session_id, "article_content": article},
                )
                templates = client.get("/api/templates/list").json()["data"]
                default_template = next(item for item in templates if item["is_default"])
                response = client.get(
                    f"/api/content/export/{session_id}",
                    params={"export_type": "docx", "template_id": default_template["template_id"]},
                )
                self.assertEqual(response.status_code, 200)
                payload = response.content
                with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                    xml = archive.read("word/document.xml").decode("utf-8")
                self.assertNotIn("�", xml)
                self.assertIn("网络安全", xml)
                document = Document(io.BytesIO(payload))
                rendered = "\n".join(paragraph.text for paragraph in document.paragraphs)
                self.assertIn("关于做好网络安全工作的通知", rendered)
                self.assertIn("落实网络安全值班和事件报告要求", rendered)
            finally:
                client.delete(f"/api/session/delete/{session_id}")


if __name__ == "__main__":
    unittest.main()
