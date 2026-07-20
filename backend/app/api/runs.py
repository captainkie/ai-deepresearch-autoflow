"""Run endpoints: create/list/detail, the SSE stream, plan approval, and cancel."""

from __future__ import annotations

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
from app.services.run_service import RunService

router = APIRouter(prefix="/api", tags=["runs"])


@router.post("/runs", status_code=201)
async def create_run(
    body: CreateRun, svc: RunService = Depends(get_run_service)
) -> CreateRunResponse:
    run_id = await svc.create(body)
    return CreateRunResponse(run_id=run_id)


@router.get("/runs")
async def list_runs(svc: RunService = Depends(get_run_service)) -> RunsResponse:
    return RunsResponse(runs=[RunSummary(**row) for row in await svc.list_runs()])


@router.get("/runs/{run_id}")
async def get_run(run_id: str, svc: RunService = Depends(get_run_service)) -> RunDetail:
    detail = await svc.get_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunDetail(**detail)


@router.get("/runs/{run_id}/stream")
async def stream_run(
    run_id: str, svc: RunService = Depends(get_run_service)
) -> EventSourceResponse:
    if not await svc.exists(run_id):
        raise HTTPException(status_code=404, detail="run not found")

    async def event_source():
        async for event in svc.subscribe(run_id):
            yield event.model_dump_json()

    return EventSourceResponse(event_source())


@router.post("/runs/{run_id}/plan")
async def submit_plan(
    run_id: str, body: PlanSubmit, svc: RunService = Depends(get_run_service)
) -> OkResponse:
    if not await svc.exists(run_id):
        raise HTTPException(status_code=404, detail="run not found")
    if not await svc.submit_plan(run_id, body):
        raise HTTPException(status_code=409, detail="run is not awaiting plan approval")
    return OkResponse()


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, svc: RunService = Depends(get_run_service)) -> OkResponse:
    if not await svc.exists(run_id):
        raise HTTPException(status_code=404, detail="run not found")
    await svc.cancel(run_id)
    return OkResponse()
