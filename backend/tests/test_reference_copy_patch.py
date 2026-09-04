import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent.reference_copy_patch import (
    lint_reference_copy_patch,
    normalize_reference_copy_patch,
)


BASE_NOTICE = """# 北京航空航天大学关于启动第三十五届“冯如杯”竞赛的通知

一、指导思想
保持原文。

二、组织机构
保持原文。

三、时间安排
保持原文。

四、申报工作
保持原文。

五、评审工作
保持原文。

六、交流活动
保持原文。

七、工作要求
保持原文。

附件：
1. 北京航空航天大学第三十五届“冯如杯”竞赛申报书
2. 北京航空航天大学第三十五届“冯如杯”竞赛汇总表
"""


class ReferenceCopyPatchTest(unittest.TestCase):
    def test_normalize_selects_base_and_records_binding(self):
        writing_plan = {}
        result = normalize_reference_copy_patch(
            {
                "task_type": "imitate",
                "document_type": "notice",
                "requirements": "生成第三十六届通知，尽量使用原文",
                "source_materials": [
                    {
                        "file_id": 22,
                        "filename": "第三十五届通知.docx",
                        "content": BASE_NOTICE,
                    }
                ],
            },
            writing_plan,
            [],
            {},
        )

        self.assertEqual(result["reference_base_file_id"], 22)
        self.assertEqual(result["source_bindings"][0]["role"], "base_template")
        self.assertTrue(result["source_bindings"][0]["pass_full_text"])
        self.assertIn("第三十六届", result["reference_working_copy"])
        self.assertEqual(writing_plan["reference_strategy"]["reference_base_file_id"], 22)

    def test_lint_blocks_summary_like_reference_output(self):
        issues = lint_reference_copy_patch({
            "task_type": "imitate",
            "reference_base_text": BASE_NOTICE,
            "draft": "# 北京航空航天大学关于举办第三十六届“冯如杯”竞赛的通知\n\n一、指导思想\n短文。",
            "requirements": "生成第三十六届通知，尽量使用原文",
        })
        codes = {issue["code"] for issue in issues}

        self.assertIn("reference_base_sections_missing", codes)
        self.assertIn("reference_base_title_changed", codes)
        self.assertIn("reference_base_length_short", codes)


if __name__ == "__main__":
    unittest.main()
