"""Run endpoints: create/list/detail, the SSE stream, plan approval, and cancel.

Every route requires a logged-in user. A member sees and manages only their own
runs; an admin (or superadmin) may access any run. Non-owners get 404 rather than
403 so a run's existence isn't leaked.
"""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_run_service
from app.api.schemas_api import (
    CreateRun,
    CreateRunResponse,
    OkResponse,
    PlanSubmit,
    RunDetail,
    RunsResponse,
    RunSummary,
)
from app.security.rbac import ROLE_RANK, get_current_user, require_member
from app.services.run_service import RunService

router = APIRouter(prefix="/api", tags=["runs"])


def _is_admin(user: aiosqlite.Row) -> bool:
    return ROLE_RANK.get(user["role"], -1) >= ROLE_RANK["admin"]


async def _authorize_run(run_id: str, user: aiosqlite.Row, svc: RunService) -> None:
    if not await svc.exists(run_id):
        raise HTTPException(status_code=404, detail="run not found")
    if _is_admin(user):
        return
    if await svc.get_owner(run_id) != user["id"]:
        # Hide existence from non-owners.
        raise HTTPException(status_code=404, detail="run not found")


@router.post("/runs", status_code=201)
async def create_run(
    body: CreateRun,
    svc: RunService = Depends(get_run_service),
    user: aiosqlite.Row = Depends(require_member),
) -> CreateRunResponse:
    run_id = await svc.create(body, owner_id=user["id"])
    return CreateRunResponse(run_id=run_id)


@router.get("/runs")
async def list_runs(
    svc: RunService = Depends(get_run_service),
    user: aiosqlite.Row = Depends(get_current_user),
) -> RunsResponse:
    owner = None if _is_admin(user) else user["id"]
    return RunsResponse(runs=[RunSummary(**row) for row in await svc.list_runs(owner)])


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    svc: RunService = Depends(get_run_service),
    user: aiosqlite.Row = Depends(get_current_user),
) -> RunDetail:
    await _authorize_run(run_id, user, svc)
    detail = await svc.get_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunDetail(**detail)


@router.get("/runs/{run_id}/stream")
async def stream_run(
    run_id: str,
    svc: RunService = Depends(get_run_service),
    user: aiosqlite.Row = Depends(get_current_user),
) -> EventSourceResponse:
    await _authorize_run(run_id, user, svc)

    async def event_source():
        async for event in svc.subscribe(run_id):
            yield event.model_dump_json()

    return EventSourceResponse(event_source())


@router.post("/runs/{run_id}/plan")
async def submit_plan(
    run_id: str,
    body: PlanSubmit,
    svc: RunService = Depends(get_run_service),
    user: aiosqlite.Row = Depends(require_member),
) -> OkResponse:
    await _authorize_run(run_id, user, svc)
    if not await svc.submit_plan(run_id, body):
        raise HTTPException(status_code=409, detail="run is not awaiting plan approval")
    return OkResponse()


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    svc: RunService = Depends(get_run_service),
    user: aiosqlite.Row = Depends(require_member),
) -> OkResponse:
    await _authorize_run(run_id, user, svc)
    await svc.cancel(run_id)
    return OkResponse()
