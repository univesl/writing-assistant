import unittest

from app.agent.linter import lint_document, normalize_markdown_headings
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

    def test_current_skill_uses_project_reference_files(self):
        skills = {item.name: item for item in SkillRegistry().list()}
        skill = skills["buaa-official-content-writer"]
        self.assertEqual(skill.status, "ready")
        self.assertIn("references/task_router.md", skill.resources)
        self.assertIn("references/fact_discipline.md", skill.resources)
        self.assertIn("references/doc_types/notice.md", skill.resources)


if __name__ == "__main__":
    unittest.main()
