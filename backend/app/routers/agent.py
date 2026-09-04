import asyncio
import json
import time

from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from ..agent.runtime.manager import (
    TERMINAL_STATUSES,
    ActiveRunError,
    AgentRunNotFoundError,
    get_agent_run_manager,
)
from ..agent.model_registry import get_model_registry
from ..agent.schemas import AgentRunView, CreateAgentRunRequest, ModelProfileView, SkillView
from ..agent.skill_registry import get_skill_registry


router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/runs", response_model=AgentRunView, status_code=status.HTTP_202_ACCEPTED)
async def create_run(payload: CreateAgentRunRequest):
    try:
        return await get_agent_run_manager().create_run(payload)
    except ActiveRunError as exc:
        raise HTTPException(status_code=409, detail={"code": "active_run_exists", "run_id": str(exc)})
    except AgentRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/runs", response_model=list[AgentRunView])
def list_runs(session_id: int | None = None, limit: int = Query(default=20, ge=1, le=100)):
    return get_agent_run_manager().list_runs(session_id=session_id, limit=limit)


@router.get("/runs/{run_id}", response_model=AgentRunView)
def get_run(run_id: str):
    try:
        return get_agent_run_manager().get_run(run_id)
    except AgentRunNotFoundError:
        raise HTTPException(status_code=404, detail="Agent run not found")


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: str,
    after: int = Query(default=0, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    if last_event_id and last_event_id.isdigit():
        after = max(after, int(last_event_id))
    manager = get_agent_run_manager()
    try:
        manager.get_run(run_id)
    except AgentRunNotFoundError:
        raise HTTPException(status_code=404, detail="Agent run not found")

    async def event_stream():
        cursor = after
        last_heartbeat = time.monotonic()
        while True:
            events = await asyncio.to_thread(manager.events_after, run_id, cursor)
            for event in events:
                cursor = event.id
                payload = event.model_dump(mode="json")
                yield f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            run = await asyncio.to_thread(manager.get_run, run_id)
            if run.status in TERMINAL_STATUSES and cursor >= run.last_event_seq:
                break
            if time.monotonic() - last_heartbeat >= 15:
                yield ": heartbeat\n\n"
                last_heartbeat = time.monotonic()
            await asyncio.sleep(0.35)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/runs/{run_id}/cancel", response_model=AgentRunView)
async def cancel_run(run_id: str):
    try:
        return await get_agent_run_manager().cancel(run_id)
    except AgentRunNotFoundError:
        raise HTTPException(status_code=404, detail="Agent run not found")


@router.post("/runs/{run_id}/retry", response_model=AgentRunView, status_code=status.HTTP_202_ACCEPTED)
async def retry_run(run_id: str):
    try:
        return await get_agent_run_manager().retry(run_id)
    except AgentRunNotFoundError:
        raise HTTPException(status_code=404, detail="Agent run not found")
    except ActiveRunError as exc:
        raise HTTPException(status_code=409, detail={"code": "run_not_retryable", "run_id": str(exc)})


@router.get("/models", response_model=list[ModelProfileView])
def list_models():
    return [
        ModelProfileView(
            id=profile.id,
            label=profile.label,
            provider=profile.provider,
            model=profile.model,
            enabled=profile.enabled,
            capabilities=list(profile.capabilities),
        )
        for profile in get_model_registry().list()
    ]


@router.get("/skills", response_model=list[SkillView])
def list_skills():
    views = []
    for skill in get_skill_registry().list():
        app_metadata = skill.metadata.get("writing-assistant")
        if not isinstance(app_metadata, dict):
            app_metadata = skill.metadata
        roles = app_metadata.get("roles") or ([app_metadata["role"]] if app_metadata.get("role") else [])
        task_types = app_metadata.get("task-types") or app_metadata.get("task_types") or []
        if isinstance(task_types, str):
            task_types = [task_types]
        views.append(SkillView(
            name=skill.name,
            description=skill.description,
            status=skill.status,
            compatibility=skill.compatibility,
            missing_tools=list(skill.missing_tools),
            disabled_scripts=list(skill.disabled_scripts),
            resources=list(skill.resources),
            capability_level=skill.capability_level,
            managed=skill.managed,
            roles=list(roles),
            task_types=list(task_types),
        ))
    return views
