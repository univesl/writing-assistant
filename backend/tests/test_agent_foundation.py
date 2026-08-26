import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from app.agent.linter import lint_document, needs_revision
from app.agent.model_registry import ModelRegistry
from app.agent.skill_registry import SkillRegistry, SkillValidationError
from app.agent.workflow import WorkflowCompiler


def write_skill(root: Path, name: str, allowed_tools: str = "document_linter", script=False):
    skill = root / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        "description: A sufficiently clear test skill description.\n"
        f"allowed-tools: {allowed_tools}\n"
        "---\n"
        "Return Markdown only.\n",
        encoding="utf-8",
    )
    if script:
        (skill / "scripts").mkdir()
        (skill / "scripts" / "unsafe.py").write_text("print('disabled')", encoding="utf-8")


class SkillRegistryTest(unittest.TestCase):
    def test_project_registry_exposes_general_writing_and_review_skills(self):
        skills = {skill.name: skill for skill in SkillRegistry().list()}
        self.assertEqual(skills["official-document-writing"].status, "ready")
        self.assertEqual(skills["official-document-review"].status, "ready")

    def test_missing_tool_is_incompatible_and_cannot_load(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_skill(root, "test-skill", "missing_tool")
            registry = SkillRegistry([root])
            descriptor = registry.list()[0]
            self.assertEqual(descriptor.status, "incompatible")
            with self.assertRaises(SkillValidationError):
                registry.get("test-skill")

    def test_unregistered_script_is_degraded_and_never_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_skill(root, "test-skill", script=True)
            descriptor = SkillRegistry([root]).list()[0]
            self.assertEqual(descriptor.status, "degraded")
            self.assertIn("scripts/unsafe.py", descriptor.resources)
            self.assertEqual(descriptor.disabled_scripts, ("scripts/unsafe.py",))

    def test_later_root_explicitly_overrides_duplicate_name(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            write_skill(Path(first), "test-skill")
            write_skill(Path(second), "test-skill")
            descriptor = SkillRegistry([Path(first), Path(second)]).get("test-skill")
            self.assertEqual(descriptor.path.parent, Path(second).resolve())

    def test_reference_is_loaded_only_after_skill_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_skill(root, "test-skill")
            reference_dir = root / "test-skill" / "references"
            reference_dir.mkdir()
            (reference_dir / "guide.md").write_text("reference rules", encoding="utf-8")
            registry = SkillRegistry([root])
            skill = registry.get("test-skill")
            self.assertEqual(registry.read_text_resources(skill), [("references/guide.md", "reference rules")])

    def test_skill_files_are_managed_and_not_user_uploads(self):
        skills = SkillRegistry().list()
        self.assertTrue(skills)
        self.assertTrue(all(skill.managed for skill in skills))

    def test_workflow_compiler_keeps_mandatory_validation(self):
        compiler = WorkflowCompiler(SkillRegistry())
        plan = compiler.compile(
            task_type="draft",
            primary_skill_name="notice-writing",
            supporting_skill_names=("official-document-review",),
        )
        self.assertIn("validation", plan.stages)
        self.assertEqual(plan.policy["max_revisions"], 1)
        self.assertIn("document_linter", plan.tools)


class ModelRegistryTest(unittest.TestCase):
    def test_active_profile_uses_concrete_llm_model_name_as_id(self):
        with patch.dict(
            "os.environ",
            {
                "LLM_MODEL_NAME": "deepseek-v4-flash",
                "LLM_API_URL": "https://opencode.ai/zen/go/v1",
                "LLM_API_KEY": "test-key",
            },
            clear=False,
        ):
            registry = ModelRegistry()
            profile = registry.get_profile()
            self.assertEqual(profile.id, "deepseek-v4-flash")
            self.assertEqual(profile.model, "deepseek-v4-flash")
            self.assertEqual(profile.label, "deepseek-v4-flash")

    def test_legacy_qwen_alias_resolves_to_current_concrete_model(self):
        with patch.dict(
            "os.environ",
            {
                "LLM_MODEL_NAME": "deepseek-v4-flash",
                "LLM_API_URL": "https://opencode.ai/zen/go/v1",
                "LLM_API_KEY": "test-key",
            },
            clear=False,
        ):
            profile = ModelRegistry().get_profile("qwen-default")
            self.assertEqual(profile.id, "deepseek-v4-flash")


class DocumentLinterTest(unittest.TestCase):
    def test_short_regulation_requires_title_but_not_forced_chapters(self):
        issues = lint_document("regulation", "", "普通正文")
        codes = {issue["code"] for issue in issues}
        self.assertIn("missing_title", codes)
        self.assertNotIn("missing_articles", codes)
        self.assertTrue(needs_revision(issues))

    def test_regulation_numbering_is_checked_after_it_is_chosen(self):
        issues = lint_document("regulation", "", "# 管理办法\n\n第二条 本办法适用于校内单位。")
        self.assertIn("article_numbering_start", {issue["code"] for issue in issues})

    def test_notice_with_formal_numbering_has_no_error(self):
        issues = lint_document("notice", "", "# 关于测试事项的通知\n\n一、工作安排\n\n请按期完成。")
        self.assertFalse(needs_revision(issues))

    def test_explicit_focus_topics_must_all_be_covered(self):
        requirements = "重点包括风险排查、账号权限管理、应急值守和事件报告，避免写入处罚。"
        article = "# 通知\n\n一、风险排查\n\n二、账号权限管理\n\n三、应急值守"
        issues = lint_document("notice", requirements, article)
        missing = next(issue for issue in issues if issue["code"] == "missing_required_topics")
        self.assertIn("事件报告", missing["message"])
        self.assertNotIn("处罚", missing["message"])
        self.assertTrue(needs_revision(issues))


if __name__ == "__main__":
    unittest.main()
