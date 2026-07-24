import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from starlette.datastructures import UploadFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import reference_material_service
from app.services.reference_material_service import (
    ReferenceMaterialError,
    format_reference_materials,
    parse_reference_uploads,
)


class ReferenceMaterialServiceTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def make_upload(filename, content):
        return UploadFile(filename=filename, file=BytesIO(content))

    async def test_all_files_are_parsed_in_upload_order_and_removed(self):
        uploads = [
            self.make_upload("one.txt", b"UNIQUE_A"),
            self.make_upload("two.md", b"UNIQUE_B"),
            self.make_upload("three.txt", b"UNIQUE_C"),
        ]
        parsed_paths = []

        def fake_parse(path):
            parsed_paths.append(Path(path))
            return Path(path).read_text(encoding="utf-8")

        with patch.object(reference_material_service, "parse_document", side_effect=fake_parse):
            materials = await parse_reference_uploads(uploads)

        self.assertEqual([item["filename"] for item in materials], ["one.txt", "two.md", "three.txt"])
        combined = format_reference_materials(materials)
        self.assertLess(combined.index("UNIQUE_A"), combined.index("UNIQUE_B"))
        self.assertLess(combined.index("UNIQUE_B"), combined.index("UNIQUE_C"))
        self.assertTrue(all(not path.exists() for path in parsed_paths))
        self.assertTrue(all(upload.file.closed for upload in uploads))

    async def test_one_failed_file_rejects_the_whole_request(self):
        uploads = [
            self.make_upload("good.txt", b"good"),
            self.make_upload("bad.txt", b"bad"),
        ]

        def fake_parse(path):
            return None if "bad.txt" in str(path) else "ok"

        with patch.object(reference_material_service, "parse_document", side_effect=fake_parse):
            with self.assertRaisesRegex(ReferenceMaterialError, "bad.txt"):
                await parse_reference_uploads(uploads)

        self.assertTrue(all(upload.file.closed for upload in uploads))

    async def test_unsupported_file_is_rejected_before_parsing(self):
        upload = self.make_upload("bad.exe", b"not a document")
        with patch.object(reference_material_service, "parse_document") as parse_document:
            with self.assertRaisesRegex(ReferenceMaterialError, "格式不支持"):
                await parse_reference_uploads([upload])
        parse_document.assert_not_called()

    async def test_parsed_text_limit_is_not_silently_truncated(self):
        uploads = [
            self.make_upload("one.txt", b"1234"),
            self.make_upload("two.txt", b"5678"),
        ]

        def fake_parse(path):
            return Path(path).read_text(encoding="utf-8")

        with (
            patch.object(reference_material_service, "parse_document", side_effect=fake_parse),
            patch.object(reference_material_service, "REFERENCE_MAX_PARSED_CHARS", 7),
        ):
            with self.assertRaisesRegex(ReferenceMaterialError, "超过长度限制"):
                await parse_reference_uploads(uploads)


if __name__ == "__main__":
    unittest.main()
