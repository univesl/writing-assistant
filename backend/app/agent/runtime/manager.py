from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.errors import EmptyInputError
from sqlalchemy import desc

from ...database import SessionLocal
from ...models import AgentEvent, AgentRun, Content, DocumentRevision, Session, SessionFile
from ...services.reference_material_service import REFERENCE_MAX_FILES, REFERENCE_MAX_PARSED_CHARS
from ..graph import AgentCancelled, AgentExecutionContext, build_writing_graph
from ..model_registry import ChatModelAdapter, get_model_registry
from ..schemas import AgentEventView, AgentRunView, CreateAgentRunRequest
from ..skill_registry import get_skill_registry
from .events import ACTIVE_STATUSES, TERMINAL_STATUSES


logger = logging.getLogger(__name__)


class ActiveRunError(RuntimeError):
    pass


class AgentRunNotFoundError(LookupError):
    pass


class DocumentVersionConflict(RuntimeError):
    pass


def _json_loads(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def run_to_view(run: AgentRun) -> AgentRunView:
    error = None
    if run.error_code or run.error_message:
        error = {
            "code": run.error_code or "agent_run_failed",
            "message": run.error_message or "Agent 运行失败",
            "retryable": run.status in {"failed", "interrupted", "cancelled"},
        }
    return AgentRunView(
        run_id=run.run_id,
        session_id=run.session_id,
        task_type=run.task_type,
        document_type=run.document_type,
        model_profile_id=run.model_profile_id,
        status=run.status,
        current_stage=run.current_stage,
        attempt=run.attempt,
        cancel_requested=run.cancel_requested,
        article_snapshot=run.final_article or run.draft_content or "",
        final_article=run.final_article,
        summary=run.summary,
        outcome=run.outcome,
        base_version=run.base_version,
        applied_version=run.applied_version,
        activated_skills=_json_loads(run.activated_skills_json, []),
        workflow_plan=_json_loads(run.workflow_plan_json, {}),
        references=_json_loads(run.references_json, []),
        warnings=_json_loads(run.warnings_json, []),
        issues=_json_loads(run.issues_json, []),
        last_event_seq=run.last_event_seq,
        error=error,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        updated_at=run.updated_at,
    )


def event_to_view(event: AgentEvent) -> AgentEventView:
    return AgentEventView(
        id=event.seq,
        type=event.event_type,
        run_id=event.run_id,
        stage=event.stage,
        data=_json_loads(event.payload_json, {}),
        created_at=event.created_at,
    )


class AgentRunManager:
    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._cancelled: set[str] = set()
        self._event_locks: dict[str, asyncio.Lock] = {}
        self._semaphore = asyncio.Semaphore(max(1, int(os.getenv("AGENT_MAX_CONCURRENT_RUNS", "3"))))
        self._checkpointer_cm = None
        self.checkpointer = None

    async def start(self):
        if self.checkpointer is not None:
            return
        checkpoint_path = Path(os.getenv("AGENT_CHECKPOINT_PATH", "./agent_checkpoints.sqlite"))
        if not checkpoint_path.is_absolute():
            checkpoint_path = (Path(__file__).resolve().parents[2] / checkpoint_path).resolve()
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self._checkpointer_cm = AsyncSqliteSaver.from_conn_string(str(checkpoint_path))
        self.checkpointer = await self._checkpointer_cm.__aenter__()
        await self.checkpointer.setup()
        await asyncio.to_thread(self._mark_orphaned_runs_interrupted)

    async def stop(self):
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        if self._checkpointer_cm is not None:
            await self._checkpointer_cm.__aexit__(None, None, None)
        self._checkpointer_cm = None
        self.checkpointer = None

    def _mark_orphaned_runs_interrupted(self):
        with SessionLocal() as db:
            runs = db.query(AgentRun).filter(AgentRun.status.in_(ACTIVE_STATUSES)).all()
            for run in runs:
                run.status = "interrupted"
                run.error_code = "process_restarted"
                run.error_message = "服务重启后任务已暂停，可从最近检查点重试"
                run.completed_at = datetime.now()
            db.commit()

    async def create_run(self, request: CreateAgentRunRequest) -> AgentRunView:
        model_profile = get_model_registry().get_profile(request.model_profile_id)
        run_id = str(uuid.uuid4())
        with SessionLocal() as db:
            session = db.get(Session, request.session_id)
            if not session:
                raise AgentRunNotFoundError("写作会话不存在")
            if request.source_file_ids:
                # Validate ownership, parsing status and aggregate limits before accepting the run.
                self._load_source_materials(request.session_id, request.source_file_ids)
            active = db.query(AgentRun).filter(
                AgentRun.session_id == request.session_id,
                AgentRun.status.in_(ACTIVE_STATUSES),
            ).first()
            if active:
                raise ActiveRunError(active.run_id)
            request_data = request.model_dump()
            request_data["base_article"] = request.base_article or session.article_content or ""
            request_data["base_version"] = session.article_version
            run = AgentRun(
                run_id=run_id,
                session_id=request.session_id,
                task_type=request.task_type,
                document_type=request.document_type,
                model_profile_id=model_profile.id,
                status="queued",
                request_json=_json_dumps(request_data),
                base_version=session.article_version,
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            view = run_to_view(run)
        self._schedule(run_id, resume=False)
        return view

    def _schedule(self, run_id: str, resume: bool):
        task = asyncio.create_task(self._execute(run_id, resume=resume), name=f"agent-run-{run_id}")
        self._tasks[run_id] = task

        def done(_task):
            if self._tasks.get(run_id) is _task:
                self._tasks.pop(run_id, None)

        task.add_done_callback(done)

    async def _execute(self, run_id: str, resume: bool):
        async with self._semaphore:
            try:
                if self.checkpointer is None:
                    await self.start()
                request, profile_id, attempt = await asyncio.to_thread(self._mark_running, run_id)
                await self.emit(
                    run_id,
                    "run.started",
                    {"attempt": attempt, "model_profile_id": profile_id},
                )
                context = AgentExecutionContext(
                    model=get_model_registry().get_adapter(profile_id),
                    skills=get_skill_registry(),
                    checkpointer=self.checkpointer,
                    emit=lambda event_type, data, stage=None: self.emit(run_id, event_type, data, stage),
                    persist_state=lambda state, stage: self.persist_state(run_id, state, stage),
                    update_draft=lambda draft: self.update_draft(run_id, draft),
                    is_cancelled=lambda: run_id in self._cancelled,
                )
                graph = build_writing_graph(context)
                config = {"configurable": {"thread_id": run_id}}
                source_materials = await asyncio.to_thread(
                    self._load_source_materials,
                    request["session_id"],
                    request.get("source_file_ids", []),
                )
                initial_state = {
                    "run_id": run_id,
                    "session_id": request["session_id"],
                    "task_type": request.get("task_type", "quick"),
                    "document_type": request["document_type"],
                    "requirements": request.get("requirements", ""),
                    "skill_names": request.get("skill_names", []),
                    "source_file_ids": request.get("source_file_ids", []),
                    "source_materials": source_materials,
                    "base_article": request.get("base_article", ""),
                    "selection": request.get("selection") or {},
                    "use_kng": bool(request.get("use_kng")),
                    "use_web_search": bool(request.get("use_web_search")),
                    "model_profile_id": profile_id,
                    "revision_count": 0,
                }
                try:
                    result = await graph.ainvoke(None if resume else initial_state, config=config)
                except EmptyInputError:
                    if not resume:
                        raise
                    # The run may have been cancelled before LangGraph persisted its
                    # first checkpoint.  In that case a retry is a safe fresh start
                    # from the immutable request snapshot.
                    result = await graph.ainvoke(initial_state, config=config)
                if not result:
                    # A missing resumable checkpoint should restart from the request rather than fail silently.
                    result = await graph.ainvoke(initial_state, config=config)
                completed = await asyncio.to_thread(self._complete_run, run_id, result)
                if not completed:
                    return
                completed_view = await asyncio.to_thread(self.get_run, run_id)
                await self.emit(
                    run_id,
                    "run.completed",
                    {
                        "article": result.get("final_article", ""),
                        "summary": result.get("summary", ""),
                        "references": result.get("references", []),
                        "warnings": result.get("warnings", []),
                        "issues": result.get("issues", []),
                        "outcome": result.get("outcome", "document"),
                        "activated_skills": result.get("activated_skills", []),
                        "workflow_plan": result.get("workflow_plan", {}),
                        "applied_version": completed_view.applied_version,
                    },
                    "finalize",
                )
            except AgentCancelled:
                await asyncio.to_thread(self._set_cancelled, run_id)
            except asyncio.CancelledError:
                if run_id in self._cancelled:
                    await asyncio.to_thread(self._set_cancelled, run_id)
                else:
                    await asyncio.to_thread(self._set_interrupted, run_id)
                    await self.emit(
                        run_id,
                        "warning",
                        {"code": "process_stopped", "message": "服务停止，任务已从安全检查点暂停"},
                    )
            except DocumentVersionConflict as exc:
                logger.warning("Agent document version conflict: %s", run_id)
                message = "正文已在任务运行期间发生变化，本次结果未覆盖，请重试"
                await asyncio.to_thread(
                    self._set_failed, run_id, exc, "document_version_conflict", message
                )
                await self.emit(
                    run_id,
                    "run.failed",
                    {"code": "document_version_conflict", "message": message, "retryable": True},
                )
            except Exception as exc:
                logger.exception("Agent run failed: %s", run_id)
                retryable_network = ChatModelAdapter._retryable(exc)
                error_code = "model_network_error" if retryable_network else "agent_run_failed"
                error_message = (
                    "模型接口连接暂时中断，已完成自动重试；可从最近检查点重试"
                    if retryable_network else "Agent 执行失败，可从最近检查点重试"
                )
                await asyncio.to_thread(self._set_failed, run_id, exc, error_code, error_message)
                await self.emit(
                    run_id,
                    "run.failed",
                    {
                        "code": error_code,
                        "message": error_message,
                        "retryable": True,
                    },
                )

    @staticmethod
    def _load_source_materials(session_id: int, file_ids: list[int]) -> list[dict[str, Any]]:
        if not file_ids:
            return []
        if len(file_ids) > REFERENCE_MAX_FILES:
            raise ValueError(f"Reference file count exceeds limit: {REFERENCE_MAX_FILES}")
        if len(set(file_ids)) != len(file_ids):
            raise ValueError("Reference file ids must be unique")
        with SessionLocal() as db:
            rows = db.query(SessionFile).filter(
                SessionFile.session_id == session_id,
                SessionFile.file_id.in_(file_ids),
            ).all()
            found = {row.file_id: row for row in rows}
            missing = [file_id for file_id in file_ids if file_id not in found]
            if missing:
                raise ValueError(f"Reference files do not belong to this session: {missing}")
            materials = []
            total_chars = 0
            for file_id in file_ids:
                row = found[file_id]
                if not row.parsed_content:
                    raise ValueError(f"Reference file is not parsed: {row.original_filename}")
                total_chars += len(row.parsed_content)
                if total_chars > REFERENCE_MAX_PARSED_CHARS:
                    raise ValueError(
                        f"Parsed reference content exceeds limit: {REFERENCE_MAX_PARSED_CHARS} characters"
                    )
                materials.append({
                    "file_id": row.file_id,
                    "filename": row.original_filename,
                    "content": row.parsed_content,
                })
            return materials

    def _mark_running(self, run_id: str):
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if not run:
                raise AgentRunNotFoundError(run_id)
            if run.cancel_requested or run.status == "cancelled":
                raise AgentCancelled()
            run.status = "running"
            run.cancel_requested = False
            run.started_at = datetime.now()
            run.completed_at = None
            run.error_code = None
            run.error_message = None
            request = _json_loads(run.request_json, {})
            profile_id = run.model_profile_id
            attempt = run.attempt
            db.commit()
            return request, profile_id, attempt

    async def persist_state(self, run_id: str, state: dict[str, Any], stage: str):
        await asyncio.to_thread(self._persist_state_sync, run_id, state, stage)

    def _persist_state_sync(self, run_id: str, state: dict[str, Any], stage: str):
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if not run:
                return
            run.current_stage = stage
            if state.get("document_type"):
                run.document_type = state["document_type"]
            run.state_json = _json_dumps(state)
            run.references_json = _json_dumps(state.get("references", []))
            run.warnings_json = _json_dumps(state.get("warnings", []))
            run.issues_json = _json_dumps(state.get("issues", []))
            run.activated_skills_json = _json_dumps(state.get("activated_skills", []))
            run.workflow_plan_json = _json_dumps(state.get("workflow_plan", {}))
            if state.get("draft"):
                run.draft_content = state["draft"]
            db.commit()

    async def update_draft(self, run_id: str, draft: str):
        await asyncio.to_thread(self._update_draft_sync, run_id, draft)

    def _update_draft_sync(self, run_id: str, draft: str):
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if run:
                run.draft_content = draft
                db.commit()

    def _complete_run(self, run_id: str, state: dict[str, Any]):
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if not run:
                return False
            if run.cancel_requested or run.status == "cancelled":
                return False
            article = state.get("final_article") or state.get("draft") or ""
            summary = state.get("summary") or "已完成公文起草"
            run.status = "completed"
            if state.get("document_type"):
                run.document_type = state["document_type"]
            run.current_stage = "finalize"
            run.final_article = article
            run.draft_content = article
            run.summary = summary
            run.outcome = state.get("outcome", "document")
            if run.outcome == "proposal" and article:
                run.proposal_content = article
                run.proposal_status = "pending"
            run.references_json = _json_dumps(state.get("references", []))
            run.warnings_json = _json_dumps(state.get("warnings", []))
            run.issues_json = _json_dumps(state.get("issues", []))
            run.state_json = _json_dumps(state)
            run.activated_skills_json = _json_dumps(state.get("activated_skills", []))
            run.workflow_plan_json = _json_dumps(state.get("workflow_plan", {}))
            run.completed_at = datetime.now()
            session = db.get(Session, run.session_id)
            if session:
                if run.outcome == "document" and article:
                    if session.article_version != run.base_version:
                        raise DocumentVersionConflict(
                            f"expected version {run.base_version}, found {session.article_version}"
                        )
                    session.article_content = article
                    session.article_version += 1
                    run.applied_version = session.article_version
                    db.add(DocumentRevision(
                        revision_id=str(uuid.uuid4()),
                        session_id=session.session_id,
                        version=session.article_version,
                        article_content=article,
                        source_run_id=run.run_id,
                        created_by="agent",
                    ))
                db.add(
                    Content(
                        session_id=run.session_id,
                        content=summary,
                        content_type="quick",
                        content_category="chat",
                        role="assistant",
                    )
                )
            db.commit()
            return True

    def _set_cancelled(self, run_id: str):
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if run and run.status != "completed":
                run.status = "cancelled"
                run.cancel_requested = True
                run.error_code = "cancelled"
                run.error_message = "任务已取消"
                run.completed_at = datetime.now()
                db.commit()

    def _set_failed(
        self,
        run_id: str,
        exc: Exception,
        code: str = "agent_run_failed",
        message: str = "Agent 执行失败，可从最近检查点重试",
    ):
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if run and run.status != "completed":
                run.status = "failed"
                run.error_code = code
                run.error_message = message
                run.completed_at = datetime.now()
                # Detailed exception stays in server logs, not in the public API or event stream.
                db.commit()

    def _set_interrupted(self, run_id: str):
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if run and run.status != "completed":
                run.status = "interrupted"
                run.error_code = "process_stopped"
                run.error_message = "服务停止后任务已暂停，可从最近检查点重试"
                run.completed_at = datetime.now()
                db.commit()

    async def emit(
        self,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        stage: str | None = None,
    ):
        lock = self._event_locks.setdefault(run_id, asyncio.Lock())
        async with lock:
            await asyncio.to_thread(self._emit_sync, run_id, event_type, payload, stage)

    def _emit_sync(self, run_id: str, event_type: str, payload: dict[str, Any], stage: str | None):
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if not run:
                return
            run.last_event_seq += 1
            if stage:
                run.current_stage = stage
            db.add(
                AgentEvent(
                    run_id=run_id,
                    seq=run.last_event_seq,
                    event_type=event_type,
                    stage=stage,
                    payload_json=_json_dumps(payload),
                )
            )
            db.commit()

    def get_run(self, run_id: str) -> AgentRunView:
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if not run:
                raise AgentRunNotFoundError(run_id)
            return run_to_view(run)

    def list_runs(self, session_id: int | None = None, limit: int = 20) -> list[AgentRunView]:
        with SessionLocal() as db:
            query = db.query(AgentRun)
            if session_id is not None:
                query = query.filter(AgentRun.session_id == session_id)
            runs = query.order_by(desc(AgentRun.created_at)).limit(min(max(limit, 1), 100)).all()
            return [run_to_view(run) for run in runs]

    def events_after(self, run_id: str, after: int) -> list[AgentEventView]:
        with SessionLocal() as db:
            exists = db.get(AgentRun, run_id)
            if not exists:
                raise AgentRunNotFoundError(run_id)
            events = db.query(AgentEvent).filter(
                AgentEvent.run_id == run_id,
                AgentEvent.seq > after,
            ).order_by(AgentEvent.seq).all()
            return [event_to_view(event) for event in events]

    async def cancel(self, run_id: str) -> AgentRunView:
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if not run:
                raise AgentRunNotFoundError(run_id)
            if run.status in TERMINAL_STATUSES:
                return run_to_view(run)
            run.cancel_requested = True
            db.commit()
        self._cancelled.add(run_id)
        await asyncio.to_thread(self._set_cancelled, run_id)
        await self.emit(
            run_id,
            "run.cancelled",
            {"message": "任务已取消，上一版已保存正文未被覆盖"},
        )
        task = self._tasks.get(run_id)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return self.get_run(run_id)

    async def retry(self, run_id: str) -> AgentRunView:
        resume = True
        with SessionLocal() as db:
            run = db.get(AgentRun, run_id)
            if not run:
                raise AgentRunNotFoundError(run_id)
            if run.status not in {"failed", "interrupted", "cancelled"}:
                raise ActiveRunError(run_id)
            active = db.query(AgentRun).filter(
                AgentRun.session_id == run.session_id,
                AgentRun.status.in_(ACTIVE_STATUSES),
                AgentRun.run_id != run_id,
            ).first()
            if active:
                raise ActiveRunError(active.run_id)
            if run.error_code == "document_version_conflict":
                session = db.get(Session, run.session_id)
                if not session:
                    raise AgentRunNotFoundError("写作会话不存在")
                request = _json_loads(run.request_json, {})
                request["base_article"] = session.article_content or ""
                request["base_version"] = session.article_version
                run.request_json = _json_dumps(request)
                run.base_version = session.article_version
                # A version conflict invalidates the generated result. Re-run the
                # graph from the refreshed article instead of resuming stale output.
                resume = False
            run.status = "queued"
            run.attempt += 1
            run.cancel_requested = False
            run.error_code = None
            run.error_message = None
            run.completed_at = None
            db.commit()
        self._cancelled.discard(run_id)
        self._schedule(run_id, resume=resume)
        return self.get_run(run_id)


_manager: AgentRunManager | None = None


def get_agent_run_manager() -> AgentRunManager:
    global _manager
    if _manager is None:
        _manager = AgentRunManager()
    return _manager
