import asyncio
import unittest
from pathlib import Path

from app.agent.linter import lint_document, normalize_markdown_headings
from app.agent.script_runner import execute_script
from app.agent.skill_registry import SkillRegistry


class AgentV2RulesTest(unittest.TestCase):
    def test_public_document_heading_mapping(self):
        article = "# 标题\n\n# 一、总体要求\n\n# （一）工作安排\n\n# 1.具体事项"
        normalized, warnings = normalize_markdown_headings(article)
        self.assertEqual(
            normalized,
            "# 标题\n\n## 一、总体要求\n\n### （一）工作安排\n\n#### 1.具体事项",
        )
        self.assertEqual(warnings, [])
        issues = lint_document("notice", "", normalized)
        self.assertNotIn("multiple_document_titles", {item["code"] for item in issues})

    def test_ambiguous_extra_h1_is_reported(self):
        normalized, warnings = normalize_markdown_headings("# 标题\n\n# 未知内容")
        self.assertIn("ambiguous_extra_title", {item["code"] for item in warnings})
        self.assertIn("multiple_document_titles", {item["code"] for item in lint_document("notice", "", normalized)})

    def test_approved_skill_scripts_are_ready_and_unknown_scripts_degraded(self):
        skills = {item.name: item for item in SkillRegistry().list()}
        official = skills["official-document-writing"]
        self.assertIn("scripts/prose_lint.py", official.resources)
        self.assertNotIn("scripts/prose_lint.py", official.disabled_scripts)
        self.assertEqual(skills["notice-writing"].status, "ready")

    def test_prose_lint_script_is_read_only_and_json(self):
        result = asyncio.run(execute_script(
            "official-document-writing",
            "scripts/prose_lint.py",
            "作为AI助手，根据用户要求生成正文。",
        ))
        self.assertTrue(result)
        self.assertEqual(result[0]["label"], "thought-leak")


if __name__ == "__main__":
    unittest.main()
