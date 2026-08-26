import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.agent.graph import OutlinePlan, ReviewResult, WritingPlan
from app.main import app


class FakeModel:
    async def stream_text(self, _messages):
        await asyncio.sleep(0.05)
        yield "# 关于测试工作的通知\n\n一、工作安排\n\n请按期完成。"

    async def complete_text(self, _messages):
        return "# 关于测试工作的通知\n\n一、工作安排\n\n请按期完成。"

    async def complete_structured(self, _messages, schema):
        if schema is OutlinePlan:
            return OutlinePlan(title="测试", sections=["安排"])
        if schema is WritingPlan:
            return WritingPlan(purpose="测试", must_cover=["安排"], structure_strategy="按事项组织")
        return ReviewResult(issues=[])


class FakeRegistry:
    def __init__(self, model_factory=FakeModel):
        self.model_factory = model_factory

    def get_profile(self, _profile_id=None):
        return SimpleNamespace(id="fake")

    def get_adapter(self, _profile_id=None):
        return self.model_factory()


class SlowFakeModel(FakeModel):
    async def stream_text(self, _messages):
        await asyncio.sleep(2)
        yield "# 关于测试工作的通知\n\n一、工作安排\n\n请按期完成。"


class ConflictFakeModel(FakeModel):
    async def stream_text(self, _messages):
        await asyncio.sleep(0.3)
        yield "# Agent 修改后的正文\n\n一、更新安排"


class ParallelFakeModel(FakeModel):
    async def stream_text(self, _messages):
        await asyncio.sleep(0.35)
        yield "# 并行任务正文\n\n一、工作安排"


class AgentApiTest(unittest.TestCase):
    @staticmethod
    def wait_for_run(client, run_id):
        snapshot = None
        for _ in range(100):
            snapshot = client.get(f"/api/agent/runs/{run_id}").json()
            if snapshot["status"] not in {"queued", "running"}:
                return snapshot
            time.sleep(0.02)
        return snapshot

    def test_run_lifecycle_replay_and_session_concurrency(self):
        with patch("app.agent.manager.get_model_registry", return_value=FakeRegistry()):
            with TestClient(app) as client:
                session_response = client.post(
                    "/api/session/create", json={"session_name": "Agent API test"}
                )
                session_id = session_response.json()["data"]["session_id"]
                try:
                    response = client.post(
                        "/api/agent/runs",
                        json={
                            "session_id": session_id,
                            "document_type": "notice",
                            "requirements": "测试",
                            "use_kng": False,
                        },
                    )
                    self.assertEqual(response.status_code, 202)
                    run_id = response.json()["run_id"]

                    conflict = client.post(
                        "/api/agent/runs",
                        json={
                            "session_id": session_id,
                            "document_type": "notice",
                            "requirements": "并发测试",
                            "use_kng": False,
                        },
                    )
                    self.assertEqual(conflict.status_code, 409)

                    for _ in range(100):
                        snapshot = client.get(f"/api/agent/runs/{run_id}").json()
                        if snapshot["status"] not in {"queued", "running"}:
                            break
                        time.sleep(0.02)

                    self.assertEqual(snapshot["status"], "completed")
                    self.assertTrue(snapshot["final_article"].startswith("# "))
                    replay = client.get(f"/api/agent/runs/{run_id}/events")
                    self.assertEqual(replay.status_code, 200)
                    self.assertIn("event: content.delta", replay.text)
                    self.assertIn("event: run.completed", replay.text)

                    legacy = client.post(
                        "/api/write/quick",
                        json={
                            "session_id": session_id,
                            "mode": "quick",
                            "style": "general",
                            "user_requirements": "旧接口测试",
                            "llm_model": "qwen",
                        },
                    )
                    self.assertEqual(legacy.status_code, 200)
                    self.assertIn("---ARTICLE---", legacy.text)
                    self.assertIn("---SUMMARY---", legacy.text)
                finally:
                    client.delete(f"/api/session/delete/{session_id}")

    def test_cancel_is_immediate_and_retry_completes(self):
        with patch("app.agent.manager.get_model_registry", return_value=FakeRegistry()):
            with TestClient(app) as client:
                session_id = client.post(
                    "/api/session/create", json={"session_name": "Agent cancel test"}
                ).json()["data"]["session_id"]
                try:
                    run = client.post(
                        "/api/agent/runs",
                        json={"session_id": session_id, "document_type": "notice"},
                    ).json()
                    cancelled = client.post(f"/api/agent/runs/{run['run_id']}/cancel")
                    self.assertEqual(cancelled.status_code, 200)
                    self.assertEqual(cancelled.json()["status"], "cancelled")

                    retried = client.post(f"/api/agent/runs/{run['run_id']}/retry")
                    self.assertEqual(retried.status_code, 202)
                    for _ in range(100):
                        snapshot = client.get(f"/api/agent/runs/{run['run_id']}").json()
                        if snapshot["status"] not in {"queued", "running"}:
                            break
                        time.sleep(0.02)
                    self.assertEqual(snapshot["status"], "completed")
                    events = client.get(f"/api/agent/runs/{run['run_id']}/events").text
                    self.assertIn("event: run.cancelled", events)
                    self.assertIn("event: run.completed", events)
                finally:
                    client.delete(f"/api/session/delete/{session_id}")

    def test_shutdown_marks_active_run_interrupted(self):
        registry = FakeRegistry(SlowFakeModel)
        with patch("app.agent.manager.get_model_registry", return_value=registry):
            with TestClient(app) as client:
                session_id = client.post(
                    "/api/session/create", json={"session_name": "Agent restart test"}
                ).json()["data"]["session_id"]
                run_id = client.post(
                    "/api/agent/runs",
                    json={"session_id": session_id, "document_type": "notice"},
                ).json()["run_id"]

            with TestClient(app) as client:
                try:
                    snapshot = client.get(f"/api/agent/runs/{run_id}").json()
                    self.assertEqual(snapshot["status"], "interrupted")
                    self.assertTrue(snapshot["error"]["retryable"])
                finally:
                    client.delete(f"/api/session/delete/{session_id}")

    def test_existing_article_is_atomically_overwritten_on_completion(self):
        with patch("app.agent.manager.get_model_registry", return_value=FakeRegistry()):
            with TestClient(app) as client:
                session_id = client.post(
                    "/api/session/create", json={"session_name": "Proposal test"}
                ).json()["data"]["session_id"]
                try:
                    original = "# 原正文\n\n一、原安排"
                    client.post(
                        "/api/content/article/save",
                        json={"session_id": session_id, "article_content": original},
                    )
                    response = client.post(
                        "/api/agent/runs",
                        json={
                            "session_id": session_id,
                            "task_type": "revise_document",
                            "document_type": "notice",
                            "requirements": "修改正文",
                            "base_article": original,
                        },
                    )
                    self.assertEqual(response.status_code, 202)
                    snapshot = self.wait_for_run(client, response.json()["run_id"])
                    self.assertEqual(snapshot["status"], "completed")
                    self.assertNotIn("proposal", snapshot)
                    self.assertEqual(snapshot["applied_version"], 2)
                    current = client.get(f"/api/content/article/{session_id}").json()["data"]
                    self.assertEqual(current["article_content"], snapshot["final_article"])
                    self.assertEqual(current["article_version"], 2)
                finally:
                    client.delete(f"/api/session/delete/{session_id}")

    def test_version_conflict_preserves_user_article(self):
        registry = FakeRegistry(ConflictFakeModel)
        with patch("app.agent.manager.get_model_registry", return_value=registry):
            with TestClient(app) as client:
                session_id = client.post(
                    "/api/session/create", json={"session_name": "Version conflict test"}
                ).json()["data"]["session_id"]
                try:
                    original = "# 原正文\n\n一、原安排"
                    client.post(
                        "/api/content/article/save",
                        json={"session_id": session_id, "article_content": original},
                    )
                    run = client.post(
                        "/api/agent/runs",
                        json={
                            "session_id": session_id,
                            "task_type": "revise_document",
                            "document_type": "notice",
                            "requirements": "修改正文",
                        },
                    ).json()
                    user_edit = "# 用户刚保存的新正文\n\n一、不得被覆盖"
                    saved = client.post(
                        "/api/content/article/save",
                        json={
                            "session_id": session_id,
                            "article_content": user_edit,
                            "base_version": 1,
                        },
                    )
                    self.assertEqual(saved.json()["code"], 200)
                    snapshot = self.wait_for_run(client, run["run_id"])
                    self.assertEqual(snapshot["status"], "failed")
                    self.assertEqual(snapshot["error"]["code"], "document_version_conflict")
                    current = client.get(f"/api/content/article/{session_id}").json()["data"]
                    self.assertEqual(current["article_content"], user_edit)
                    self.assertEqual(current["article_version"], 2)

                    retried = client.post(f"/api/agent/runs/{run['run_id']}/retry")
                    self.assertEqual(retried.status_code, 202)
                    retry_snapshot = self.wait_for_run(client, run["run_id"])
                    self.assertEqual(retry_snapshot["status"], "completed")
                    self.assertEqual(retry_snapshot["base_version"], 2)
                    self.assertEqual(retry_snapshot["applied_version"], 3)
                    current = client.get(f"/api/content/article/{session_id}").json()["data"]
                    self.assertEqual(current["article_content"], retry_snapshot["final_article"])
                    self.assertEqual(current["article_version"], 3)
                finally:
                    client.delete(f"/api/session/delete/{session_id}")

    def test_three_sessions_run_in_parallel_and_fourth_waits(self):
        registry = FakeRegistry(ParallelFakeModel)
        with patch("app.agent.manager.get_model_registry", return_value=registry):
            with TestClient(app) as client:
                session_ids = [
                    client.post(
                        "/api/session/create", json={"session_name": f"并发会话 {index}"}
                    ).json()["data"]["session_id"]
                    for index in range(4)
                ]
                try:
                    run_ids = [
                        client.post(
                            "/api/agent/runs",
                            json={
                                "session_id": session_id,
                                "document_type": "notice",
                                "requirements": f"并发任务 {index}",
                            },
                        ).json()["run_id"]
                        for index, session_id in enumerate(session_ids)
                    ]
                    snapshots = []
                    for _ in range(100):
                        snapshots = [
                            client.get(f"/api/agent/runs/{run_id}").json() for run_id in run_ids
                        ]
                        if sum(item["status"] == "running" for item in snapshots) == 3:
                            break
                        time.sleep(0.01)
                    self.assertEqual(sum(item["status"] == "running" for item in snapshots), 3)
                    self.assertEqual(sum(item["status"] == "queued" for item in snapshots), 1)
                    completed = [self.wait_for_run(client, run_id) for run_id in run_ids]
                    self.assertTrue(all(item["status"] == "completed" for item in completed))
                finally:
                    for session_id in session_ids:
                        client.delete(f"/api/session/delete/{session_id}")


if __name__ == "__main__":
    unittest.main()
