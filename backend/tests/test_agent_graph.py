import unittest
import threading
import time
from unittest.mock import Mock, patch

from langgraph.checkpoint.memory import MemorySaver

from app.agent.graph import (
    AgentExecutionContext,
    MaterialCardAnalysis,
    ReferenceStrategyResult,
    ReviewResult,
    WritingPlan,
    build_writing_graph,
)
from app.agent.skill_registry import SkillRegistry


class FakeModel:
    def __init__(self, review_errors=False):
        self.review_errors = review_errors
        self.revision_calls = 0
        self.prompts = []

    async def stream_text(self, _messages):
        self.prompts.append(("draft", _messages[-1]["content"]))
        yield "# 关于测试工作的通知\n\n一、工作安排\n\n请按期完成。"

    async def complete_text(self, _messages):
        self.revision_calls += 1
        self.prompts.append(("revision", _messages[-1]["content"]))
        return "# 关于测试工作的通知\n\n一、工作安排\n\n请按期完成。"

    async def complete_structured(self, _messages, schema):
        self.prompts.append((schema.__name__, _messages[-1]["content"]))
        if schema.__name__ == "RetrievalPlan":
            return schema(tasks=[{
                "purpose": "查找与写作事项直接相关的依据",
                "query": "测试事项相关制度与既有做法",
                "evidence_needs": ["制度依据"],
                "exclusions": ["无关主题"],
            }])
        if schema.__name__ == "EvidenceFilterResult":
            return schema(items=[])
        if schema.__name__ == "OutlinePlan":
            return schema(title="关于测试工作的通知", sections=["工作安排"])
        if schema is WritingPlan:
            return schema(purpose="测试", must_cover=["工作安排"], structure_strategy="按事项组织")
        issues = []
        if self.review_errors:
            issues = [{
                "code": "forced_review_error",
                "severity": "error",
                "message": "用于验证修订上限",
                "suggestion": "修订",
            }]
        return schema(issues=issues)


class MultiMaterialScenarioModel(FakeModel):
    async def complete_structured(self, messages, schema):
        prompt = messages[-1]["content"]
        self.prompts.append((schema.__name__, prompt))
        if schema is MaterialCardAnalysis:
            if "文件名：骨架.docx" in prompt:
                return schema(
                    topic="校园安全工作部署",
                    document_kind="通知",
                    content_excerpts=[],
                    structure_functions=["说明目的", "分项部署", "提出落实要求"],
                    style_traits=["简洁部署语气"],
                )
            if "文件名：内容.txt" in prompt:
                return schema(
                    topic="网络安全值守",
                    document_kind="工作材料",
                    content_excerpts=["实行网络安全值班和事件报告制度。"],
                    structure_functions=[],
                    style_traits=[],
                )
            return schema(
                topic="旧讲话",
                document_kind="讲话稿",
                content_excerpts=["张某于2024年作出部署。"],
                style_traits=["适合现场朗读"],
            )
        if schema is ReferenceStrategyResult:
            return schema(
                target_document_type="notice",
                document_subtype="工作部署通知",
                material_plans=[
                    {"file_id": 11, "roles": ["structure"], "priority": "primary", "use_scope": "作为骨架"},
                    {"file_id": 12, "roles": ["content"], "priority": "primary", "use_scope": "提供网络安全要求"},
                    {"file_id": 13, "roles": ["style"], "priority": "supporting", "use_scope": "只参考朗读节奏"},
                ],
                structure_source_file_ids=[11],
                style_guidance=["保持简洁、便于传达"],
            )
        if schema is WritingPlan:
            return schema(
                document_subtype="工作部署通知",
                purpose="部署网络安全工作",
                must_cover=["网络安全值班和事件报告"],
                structure_strategy="采用材料11的段落功能",
                material_cards=[
                    {"file_id": 11, "filename": "骨架.docx", "content_excerpts": []},
                    {"file_id": 12, "filename": "内容.txt", "content_excerpts": ["实行网络安全值班和事件报告制度。"]},
                    {"file_id": 13, "filename": "风格.md", "content_excerpts": ["张某于2024年作出部署。"]},
                ],
                reference_strategy={
                    "target_document_type": "notice",
                    "document_subtype": "工作部署通知",
                    "material_plans": [
                        {"file_id": 11, "roles": ["structure"], "priority": "primary"},
                        {"file_id": 12, "roles": ["content"], "priority": "primary"},
                        {"file_id": 13, "roles": ["style"], "priority": "supporting"},
                    ],
                    "structure_source_file_ids": [11],
                },
            )
        if schema.__name__ == "OutlinePlan":
            return schema(title="关于做好网络安全工作的通知", sections=["工作安排", "落实要求"])
        return schema(issues=[])


class ChineseStyleScenarioModel(FakeModel):
    async def stream_text(self, _messages):
        self.prompts.append(("draft", _messages[-1]["content"]))
        yield (
            "# 关于档案整理工作的方案\n\n"
            "有关部门要凝心聚力、提质增效，全面推动工作走深走实，谱写新篇章。"
        )

    async def complete_text(self, _messages):
        self.revision_calls += 1
        self.prompts.append(("revision", _messages[-1]["content"]))
        return (
            "# 关于档案整理工作的方案\n\n"
            "一、各科室于6月25日前完成本年度档案分类和目录核对。\n\n"
            "二、办公室于6月30日前汇总问题清单，并向各科室反馈需补正事项。"
        )

    async def complete_structured(self, _messages, schema):
        prompt = _messages[-1]["content"]
        self.prompts.append((schema.__name__, prompt))
        if schema.__name__ == "OutlinePlan":
            return schema(title="关于档案整理工作的方案", sections=["整理任务", "汇总反馈"])
        if "有关部门要凝心聚力、提质增效" in prompt and "空泛排比" in prompt:
            return schema(
                issues=[{
                    "code": "empty_ai_style",
                    "severity": "error",
                    "message": "正文只有抽象表态，缺少责任主体、动作和时限",
                    "suggestion": "改为可执行的任务和反馈节点",
                }]
            )
        return schema(issues=[])


class RetrievalScenarioModel(FakeModel):
    async def complete_structured(self, _messages, schema):
        prompt = _messages[-1]["content"]
        self.prompts.append((schema.__name__, prompt))
        if schema.__name__ == "RetrievalPlan":
            return schema(tasks=[
                {
                    "purpose": "查找网络安全责任和处置要求",
                    "query": "校园网络安全值守、风险排查和事件处置制度",
                    "evidence_needs": ["责任要求", "既有处置做法"],
                    "exclusions": ["论文检测"],
                },
                {
                    "purpose": "查找人工智能系统使用安全要求",
                    "query": "校内人工智能系统数据和账号安全管理要求",
                    "evidence_needs": ["数据安全要求"],
                    "exclusions": ["科技成果披露"],
                },
            ])
        if schema.__name__ == "EvidenceFilterResult":
            return schema(items=[{
                "query_index": 0,
                "relevance": "partial",
                "content": "材料明确要求建立网络安全值班和事件报告机制。",
                "source_refs": ["[1] 网络安全值守规定", "[2] 科技成果披露办法"],
            }])
        if schema.__name__ == "OutlinePlan":
            return schema(title="关于测试工作的通知", sections=["工作安排"])
        return schema(issues=[])


class BudgetScenarioModel(FakeModel):
    def __init__(self, initial_count=7, merged_count=3):
        super().__init__()
        self.initial_count = initial_count
        self.merged_count = merged_count
        self.plan_calls = 0

    async def complete_structured(self, _messages, schema):
        self.prompts.append((schema.__name__, _messages[-1]["content"]))
        if schema.__name__ == "RetrievalPlan":
            self.plan_calls += 1
            count = self.initial_count if self.plan_calls == 1 else self.merged_count
            return schema(tasks=[{
                "purpose": f"检索目的 {index}",
                "query": f"独立检索查询 {index}",
                "evidence_needs": [f"依据 {index}"],
                "exclusions": [],
            } for index in range(count)])
        if schema.__name__ == "EvidenceFilterResult":
            return schema(items=[])
        if schema.__name__ == "OutlinePlan":
            return schema(title="关于测试工作的通知", sections=["工作安排"])
        return schema(issues=[])


class TruncatingRevisionModel(FakeModel):
    async def stream_text(self, _messages):
        yield (
            "# 关于测试工作的通知\n\n"
            "一、风险排查\n\n全面排查网络风险。\n\n"
            "二、账号权限管理\n\n及时清理无效账号。\n\n"
            "三、应急值守\n\n落实应急值守。\n\n"
            "四、事件报告\n\n发现事件后及时报告。"
        )

    async def complete_text(self, _messages):
        self.revision_calls += 1
        return "# 关于测试工作的通知\n\n一、风险排查"

    async def complete_structured(self, _messages, schema):
        if schema.__name__ == "OutlinePlan":
            return schema(title="关于测试工作的通知", sections=["风险排查", "事件报告"])
        if schema.__name__ == "ReviewResult":
            return schema(issues=[{
                "code": "forced_review_error",
                "severity": "error",
                "message": "强制进入修订",
                "suggestion": "修订但不得删减",
            }])
        return await super().complete_structured(_messages, schema)


class SelectionBoundaryModel(FakeModel):
    async def stream_text(self, _messages):
        yield "首次替换文本。"

    async def complete_text(self, _messages):
        self.revision_calls += 1
        return "最终替换文本。"

    async def complete_structured(self, _messages, schema):
        if schema is ReviewResult and self.revision_calls == 0:
            return schema(issues=[{
                "code": "selection_tone",
                "severity": "error",
                "message": "选区语气需要调整",
                "suggestion": "使选区更正式",
            }])
        if schema is WritingPlan:
            return schema(purpose="修改选区", structure_strategy="保持上下文不变")
        return await super().complete_structured(_messages, schema)


BASE_35_TEXT = (
    "# 北京航空航天大学关于启动第三十五届“冯如杯”竞赛的通知\n\n"
    "各有关单位：\n\n"
    "为做好第三十五届“冯如杯”竞赛的各项工作，现将相关事宜通知如下。\n\n"
    "# 一、指导思想\n\n"
    "本届竞赛注重传承发扬冯如精神，弘扬空天报国情怀，营造航空航天特色学术科技氛围，提升竞赛覆盖面。\n\n"
    "# 二、组织机构\n\n"
    "主办单位：北京航空航天大学学生工作部\n\n"
    "# 三、时间安排\n\n"
    "2025年3月27日14:00-2025年4月9日12:00 全部赛道 网上申报\n\n"
    "# 四、申报工作\n\n"
    "1.各学院（书院）成立竞赛领导小组，负责参赛项目选拔和推荐。\n"
    "2.主赛道专项竞赛包括“互联世界”专项竞赛。\n\n"
    "# 五、评审工作\n\n"
    "1.在学校有效性审查前，各学院（书院）完成所有项目有效性审查和院级评审。\n"
    "2.主赛道项目采用院级评审、网上评审和现场评审相结合的方式。\n\n"
    "# 六、交流活动\n\n"
    "1.组委会将于5月中旬举办冯如文化节活动。\n"
    "2.组委会将于竞赛期间邀请专家举办科技创新方法讲座。\n\n"
    "# 七、工作要求\n\n"
    "1.“冯如杯”竞赛的组织和参赛工作要与学校教学和人才培养工作紧密结合。\n"
    "2.为确保第三十五届“冯如杯”竞赛顺利进行，各相关部处、学院（书院）要加强领导。\n\n"
    "特此通知。\n\n"
    "附件：\n"
    "1.北京航空航天大学第三十五届“冯如杯”竞赛章程\n"
    "2.北京航空航天大学第三十五届“冯如杯”竞赛申报流程\n"
    "3.北京航空航天大学第三十五届“冯如杯”竞赛学院（书院）审核说明\n\n"
    "北京航空航天大学\n\n"
    "2025年3月3日"
)


class BaseTuningReferenceModel(FakeModel):
    async def stream_text(self, _messages):
        prompt = _messages[-1]["content"]
        self.prompts.append(("draft", prompt))
        text = BASE_35_TEXT.replace("第三十五届", "第三十六届").replace("2025年3月3日", "2026年3月23日")
        yield text + "\n4.北京航空航天大学第三十六届“冯如杯”竞赛院级项目成果审查报告"

    async def complete_structured(self, _messages, schema):
        self.prompts.append((schema.__name__, _messages[-1]["content"]))
        if schema is WritingPlan:
            return schema(
                purpose="生成第三十六届通知",
                structure_strategy="以第三十五届为底稿最小修订",
                material_cards=[
                    {"file_id": 21, "filename": "北京航空航天大学关于启动第三十四届“冯如杯”竞赛的通知.pdf"},
                    {"file_id": 22, "filename": "北京航空航天大学关于启动第三十五届“冯如杯”竞赛的通知.pdf"},
                ],
                reference_strategy={
                    "target_document_type": "notice",
                    "material_plans": [],
                },
            )
        return schema(issues=[])


class BadBaseTuningReferenceModel(BaseTuningReferenceModel):
    async def stream_text(self, _messages):
        prompt = _messages[-1]["content"]
        self.prompts.append(("draft", prompt))
        yield (
            "# 北京航空航天大学关于举办第三十六届“冯如杯”竞赛的通知\n\n"
            "现将有关事项通知如下。\n\n"
            "一、组织机构\n\n主办单位：北京航空航天大学。\n\n"
            "附件：\n1.新增附件"
        )


class AgentGraphTest(unittest.IsolatedAsyncioTestCase):
    async def run_graph(self, model, document_type="notice", use_kng=False):
        events = []
        drafts = []

        async def emit(event_type, data, stage=None):
            events.append((event_type, data, stage))

        async def persist(_state, _stage):
            return None

        async def update_draft(draft):
            drafts.append(draft)

        context = AgentExecutionContext(
            model=model,
            skills=SkillRegistry(),
            checkpointer=MemorySaver(),
            emit=emit,
            persist_state=persist,
            update_draft=update_draft,
            is_cancelled=lambda: False,
        )
        graph = build_writing_graph(context)
        result = await graph.ainvoke(
            {
                "run_id": "test-run",
                "session_id": 1,
                "task_type": "quick",
                "document_type": document_type,
                "requirements": "测试",
                "use_kng": use_kng,
                "model_profile_id": "fake",
                "revision_count": 0,
            },
            config={"configurable": {"thread_id": "test-run"}},
        )
        return result, events, drafts

    async def run_reference_graph(self, model, task_type="reference"):
        events = []

        async def emit(event_type, data, stage=None):
            events.append((event_type, data, stage))

        context = AgentExecutionContext(
            model=model,
            skills=SkillRegistry(),
            checkpointer=MemorySaver(),
            emit=emit,
            persist_state=lambda _state, _stage: _async_none(),
            update_draft=lambda _draft: _async_none(),
            is_cancelled=lambda: False,
        )
        graph = build_writing_graph(context)
        result = await graph.ainvoke({
            "run_id": "reference-run",
            "session_id": 1,
            "task_type": task_type,
            "document_type": "notice",
            "requirements": "以骨架.docx为结构，内容.txt只作内容，风格.md只参考表达",
            "source_materials": [
                {"file_id": 11, "filename": "骨架.docx", "content": "一、工作安排\n二、落实要求"},
                {"file_id": 12, "filename": "内容.txt", "content": "实行网络安全值班和事件报告制度。"},
                {"file_id": 13, "filename": "风格.md", "content": "张某于2024年作出部署。"},
            ],
            "use_kng": False,
            "model_profile_id": "fake",
            "revision_count": 0,
        }, config={"configurable": {"thread_id": "reference-run"}})
        return result, events

    async def run_base_tuning_reference_graph(self, model):
        events = []

        async def emit(event_type, data, stage=None):
            events.append((event_type, data, stage))

        context = AgentExecutionContext(
            model=model,
            skills=SkillRegistry(),
            checkpointer=MemorySaver(),
            emit=emit,
            persist_state=lambda _state, _stage: _async_none(),
            update_draft=lambda _draft: _async_none(),
            is_cancelled=lambda: False,
        )
        graph = build_writing_graph(context)
        result = await graph.ainvoke({
            "run_id": "base-tuning-reference-run",
            "session_id": 1,
            "task_type": "imitate",
            "document_type": "notice",
            "requirements": "用第三十四届和第三十五届参考生成第三十六届，尽量使用原文，只有提到修改的地方再改",
            "source_materials": [
                {
                    "file_id": 21,
                    "filename": "北京航空航天大学关于启动第三十四届“冯如杯”竞赛的通知.pdf",
                    "content": BASE_35_TEXT.replace("第三十五届", "第三十四届"),
                },
                {
                    "file_id": 22,
                    "filename": "北京航空航天大学关于启动第三十五届“冯如杯”竞赛的通知.pdf",
                    "content": BASE_35_TEXT,
                },
            ],
            "use_kng": False,
            "model_profile_id": "fake",
            "revision_count": 0,
        }, config={"configurable": {"thread_id": "base-tuning-reference-run"}})
        return result, events

    async def test_completes_and_streams_public_content(self):
        result, events, drafts = await self.run_graph(FakeModel())
        self.assertTrue(result["final_article"].startswith("# "))
        self.assertTrue(drafts)
        self.assertIn("content.delta", [event[0] for event in events])
        self.assertNotIn("reasoning", [event[0] for event in events])

    async def test_validation_revision_is_capped_at_two(self):
        model = FakeModel(review_errors=True)
        result, events, _drafts = await self.run_graph(model)
        self.assertEqual(result["revision_count"], 1)
        self.assertEqual(model.revision_calls, 1)
        self.assertIn("validation_unresolved", {item["code"] for item in result["warnings"]})
        replacement_events = [event for event in events if event[0] == "content.delta" and event[1]["mode"] == "replace"]
        self.assertEqual(len(replacement_events), 1)

    async def test_general_skill_routes_references_by_phase(self):
        model = FakeModel()
        result, _events, _drafts = await self.run_graph(model, document_type="general")
        prompts = {name: prompt for name, prompt in model.prompts}
        self.assertEqual(result["skill_name"], "buaa-official-content-writer")
        self.assertIn("Skill：buaa-official-content-writer", prompts["WritingPlan"])
        self.assertIn("北航语境", prompts["draft"])
        self.assertIn("事实克制", prompts["draft"])
        self.assertNotIn("审查输出格式", prompts["draft"])
        self.assertIn("审查输出格式", prompts["ReviewResult"])

    async def test_chinese_style_review_repairs_empty_ai_language(self):
        model = ChineseStyleScenarioModel()
        result, _events, _drafts = await self.run_graph(model, document_type="general")
        self.assertEqual(result["revision_count"], 1)
        self.assertNotIn("谱写新篇章", result["final_article"])
        self.assertIn("办公室于6月30日前汇总问题清单", result["final_article"])

    async def test_kng_failure_is_nonfatal_and_regulation_is_marked_unverified(self):
        service = Mock()
        service.retrieve_for_document_generation.return_value = {"content": "", "references": []}
        with patch("app.agent.nodes.retrieval.get_kng_rag_service", return_value=service):
            result, _events, _drafts = await self.run_graph(
                FakeModel(), document_type="regulation", use_kng=True
            )
        warning_codes = {item["code"] for item in result["warnings"]}
        self.assertIn("kng_unavailable", warning_codes)
        self.assertIn("regulation_basis_unverified", warning_codes)

    async def test_dynamic_hybrid_queries_are_filtered_before_writing(self):
        model = RetrievalScenarioModel()
        service = Mock()

        def retrieve(*, topic, requirements, mode):
            self.assertEqual(requirements, "")
            self.assertEqual(mode, "hybrid")
            if "校园网络安全" in topic:
                return {
                    "content": "材料明确要求建立网络安全值班和事件报告机制。",
                    "references": ["[1] 网络安全值守规定", "[2] 科技成果披露办法"],
                }
            return {
                "content": "论文检测、科技成果披露与保密审查流程。",
                "references": ["[2] 科技成果披露办法"],
            }

        service.retrieve_for_document_generation.side_effect = retrieve
        with patch("app.agent.nodes.retrieval.get_kng_rag_service", return_value=service):
            result, events, _drafts = await self.run_graph(model, use_kng=True)

        self.assertEqual(len(result["retrieval_plan"]), 2)
        self.assertEqual(service.retrieve_for_document_generation.call_count, 2)
        self.assertEqual(result["references"], ["[1] 网络安全值守规定"])
        self.assertEqual(len(result["evidence"]), 1)
        self.assertIn("网络安全值班", result["evidence"][0]["content"])
        self.assertNotIn("科技成果披露", result["evidence"][0]["content"])
        writing_prompts = "\n".join(
            prompt for name, prompt in model.prompts if name in {"OutlinePlan", "draft", "ReviewResult"}
        )
        self.assertNotIn("论文检测、科技成果披露", writing_prompts)
        added_sources = [event[1]["reference"] for event in events if event[0] == "source.added"]
        self.assertEqual(added_sources, ["[1] 网络安全值守规定"])

    async def test_over_budget_plan_is_merged_and_kng_concurrency_is_two(self):
        model = BudgetScenarioModel(initial_count=7, merged_count=4)
        service = Mock()
        active = 0
        peak_active = 0
        lock = threading.Lock()

        def retrieve(*, topic, requirements, mode):
            nonlocal active, peak_active
            with lock:
                active += 1
                peak_active = max(peak_active, active)
            try:
                time.sleep(0.04)
                return {"content": "", "references": []}
            finally:
                with lock:
                    active -= 1

        service.retrieve_for_document_generation.side_effect = retrieve
        with patch("app.agent.nodes.retrieval.get_kng_rag_service", return_value=service):
            result, _events, _drafts = await self.run_graph(model, use_kng=True)

        self.assertEqual(model.plan_calls, 2)
        self.assertEqual(len(result["retrieval_plan"]), 4)
        self.assertEqual(service.retrieve_for_document_generation.call_count, 4)
        self.assertEqual(peak_active, 2)

    async def test_truncated_revision_keeps_the_more_complete_draft(self):
        model = TruncatingRevisionModel()
        result, events, _drafts = await self.run_graph(model)
        self.assertIn("四、事件报告", result["final_article"])
        self.assertEqual(result["revision_count"], 1)
        warning_codes = {item["code"] for item in result["warnings"]}
        self.assertIn("revision_rejected_incomplete", warning_codes)
        replacement_events = [event for event in events if event[0] == "content.delta" and event[1]["mode"] == "replace"]
        self.assertEqual(replacement_events, [])

    async def test_reference_materials_are_routed_by_role_before_drafting(self):
        model = MultiMaterialScenarioModel()
        result, events = await self.run_reference_graph(model)
        self.assertEqual(result["document_type"], "notice")
        self.assertIsNone(result.get("reference_base_file_id"))
        self.assertEqual(result["reference_strategy"]["structure_source_file_ids"], [11])
        self.assertEqual(len(result["evidence"]), 1)
        self.assertEqual([item["file_id"] for item in result["evidence"]], [12])
        self.assertNotIn("底稿微调上下文", "\n".join(prompt for name, prompt in model.prompts if name == "draft"))
        writing_prompts = "\n".join(
            prompt for name, prompt in model.prompts if name == "draft"
        )
        self.assertNotIn("张某于2024年", writing_prompts)
        used_files = [
            event[1]["reference"]["file_id"] for event in events
            if event[0] == "source.added" and isinstance(event[1].get("reference"), dict)
        ]
        self.assertEqual(used_files, [11, 12, 13])

    async def test_reference_detects_base_tuning_and_passes_full_base_to_draft(self):
        model = BaseTuningReferenceModel()
        result, events = await self.run_base_tuning_reference_graph(model)
        self.assertEqual(result["reference_base_file_id"], 22)
        self.assertEqual(result["evidence"][0]["file_id"], 22)
        self.assertIn(BASE_35_TEXT, result["reference_base_text"])
        self.assertIn("第三十五届", result["reference_change_plan"]["global_replace"][0]["from"])
        self.assertIn("第三十六届", result["reference_change_plan"]["global_replace"][0]["to"])
        draft_prompt = "\n".join(prompt for name, prompt in model.prompts if name == "draft")
        self.assertIn("底稿微调上下文", draft_prompt)
        self.assertIn(BASE_35_TEXT, draft_prompt)
        material_plan = result["workflow_plan"]["material_plan"]
        self.assertEqual(material_plan["reference_base_file_id"], 22)
        base_binding = [item for item in material_plan["source_bindings"] if item["file_id"] == 22][0]
        self.assertTrue(base_binding["pass_full_text"])
        warning_codes = {item["code"] for item in result["warnings"]}
        self.assertIn("reference_base_selected", warning_codes)
        self.assertEqual(result["outcome"], "document")

    async def test_base_tuning_without_edition_signal_still_selects_a_base(self):
        result, _events = await self.run_reference_graph(FakeModel(), task_type="imitate")
        self.assertEqual(result["reference_base_file_id"], 11)
        self.assertTrue(result["reference_change_plan"]["keep_rules"])

    async def test_bad_base_tuning_reference_is_saved_as_proposal(self):
        model = BadBaseTuningReferenceModel()
        result, _events = await self.run_base_tuning_reference_graph(model)
        self.assertEqual(result["outcome"], "proposal")
        self.assertTrue(result["quality_gate"]["block_apply"])
        issue_codes = {item["code"] for item in result["issues"]}
        self.assertIn("reference_base_sections_missing", issue_codes)
        self.assertIn("reference_base_length_short", issue_codes)

    async def test_selection_revision_cannot_change_text_outside_selection(self):
        events = []

        async def emit(event_type, data, stage=None):
            events.append((event_type, data, stage))

        context = AgentExecutionContext(
            model=SelectionBoundaryModel(),
            skills=SkillRegistry(),
            checkpointer=MemorySaver(),
            emit=emit,
            persist_state=lambda _state, _stage: _async_none(),
            update_draft=lambda _draft: _async_none(),
            is_cancelled=lambda: False,
        )
        graph = build_writing_graph(context)
        base = "前文不得变化。\n\n原选区文字。\n\n后文也不得变化。"
        result = await graph.ainvoke({
            "run_id": "selection-run",
            "session_id": 1,
            "task_type": "revise_selection",
            "document_type": "notice",
            "requirements": "改得更正式",
            "base_article": base,
            "selection": {
                "selected_markdown": "原选区文字。",
                "context_before": "前文不得变化。",
                "context_after": "后文也不得变化。",
            },
            "use_kng": False,
            "model_profile_id": "fake",
            "revision_count": 0,
        }, config={"configurable": {"thread_id": "selection-run"}})
        self.assertEqual(result["final_article"], "前文不得变化。\n\n最终替换文本。\n\n后文也不得变化。")
        self.assertFalse(any(event[0] == "content.delta" for event in events))


async def _async_none():
    return None


if __name__ == "__main__":
    unittest.main()
