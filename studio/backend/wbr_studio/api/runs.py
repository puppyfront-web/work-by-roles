"""创建运行、读取结果、列出审计事件并校验工作区哈希链。"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from wbr.core.exceptions import AuditSchemaError
from wbr_studio.audit_store import PostgresAuditStore
from wbr_studio.db import get_engine
from wbr_studio.deps import WorkspaceContext, get_db, read_workspace, write_workspace
from wbr_studio.models import ProviderKey, Run, Team, utcnow
from wbr_studio.present import run_out
from wbr_studio.queue import enqueue_run
from wbr_studio.schemas import RunCreate

router = APIRouter()
_log = logging.getLogger("wbr_studio.runs")


def _uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{label} 不是有效 id") from exc


def _run_or_404(db: Session, ctx: WorkspaceContext, run_id: uuid.UUID) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="运行不存在")
    return run


def _key_for_run(db: Session, ctx: WorkspaceContext, body: RunCreate) -> ProviderKey:
    if body.provider_key_id:
        key = db.get(ProviderKey, _uuid(body.provider_key_id, "provider_key_id"))
        if key is None or key.workspace_id != ctx.workspace.id:
            raise HTTPException(status_code=404, detail="供应商密钥不存在")
        return key
    key = db.scalars(
        select(ProviderKey)
        .where(ProviderKey.workspace_id == ctx.workspace.id)
        .order_by(ProviderKey.created_at.desc())
    ).first()
    if key is None:
        raise HTTPException(status_code=400, detail="请先保存供应商 API Key")
    return key


@router.post("/{workspace_id}/runs", status_code=201)
async def start_run(
    body: RunCreate,
    ctx: WorkspaceContext = Depends(write_workspace),
    db: Session = Depends(get_db),
) -> dict:
    team = db.get(Team, _uuid(body.team_id, "team_id"))
    if team is None or team.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="团队不存在")
    key = _key_for_run(db, ctx, body)
    run = Run(
        workspace_id=ctx.workspace.id,
        team_id=team.id,
        created_by=ctx.user.id,
        provider_key_id=key.id,
        status="queued",
        model=key.model,
        contract_version=team.current_version,
        question=body.question,
        token_budget=body.token_budget,
        input_price=body.input_price,
        output_price=body.output_price,
        cached_input_price=body.cached_input_price,
    )
    db.add(run)
    db.commit()
    try:
        await enqueue_run(str(run.id))
    except Exception as exc:
        _log.warning("enqueue %s failed (%s)", run.id, type(exc).__name__)
        run.status = "failed"
        run.error = "任务队列不可用"
        db.commit()
        raise HTTPException(status_code=503, detail="任务队列不可用") from exc
    db.refresh(run)
    return run_out(run)


@router.get("/{workspace_id}/runs")
def list_runs(ctx: WorkspaceContext = Depends(read_workspace), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(Run).where(Run.workspace_id == ctx.workspace.id).order_by(Run.created_at.desc()).limit(100)
    ).all()
    return [run_out(row) for row in rows]


@router.get("/{workspace_id}/runs/{run_id}")
def get_run(
    run_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(read_workspace),
    db: Session = Depends(get_db),
) -> dict:
    return run_out(_run_or_404(db, ctx, run_id))


@router.post("/{workspace_id}/runs/{run_id}/cancel")
def cancel_run(
    run_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(write_workspace),
    db: Session = Depends(get_db),
) -> dict:
    run = _run_or_404(db, ctx, run_id)
    now = utcnow()
    queued = db.execute(
        update(Run)
        .where(Run.id == run_id, Run.status == "queued")
        .values(status="cancelled", error="已取消", finished_at=now, cancel_requested=True)
    )
    if not queued.rowcount:
        db.execute(
            update(Run)
            .where(Run.id == run_id, Run.status == "running")
            .values(cancel_requested=True)
        )
    db.commit()
    db.refresh(run)
    if run.status in {"completed", "failed"}:
        raise HTTPException(status_code=409, detail="运行已结束")
    return run_out(run)


@router.get("/{workspace_id}/runs/{run_id}/audit")
def run_audit(
    run_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(read_workspace),
    db: Session = Depends(get_db),
) -> dict:
    run = _run_or_404(db, ctx, run_id)
    store = PostgresAuditStore(get_engine(), ctx.workspace.id)
    try:
        chain = store.verify()
    except AuditSchemaError as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    rows = store.query(run_id=str(run.id))
    return {
        "run_id": str(run.id),
        "chain": {"ok": chain.ok, "checked": chain.checked, "broken_at": chain.broken_at},
        "events": [_event_out(row) for row in rows],
    }


@router.get("/{workspace_id}/audit/verify")
def verify_chain(ctx: WorkspaceContext = Depends(read_workspace)) -> dict:
    store = PostgresAuditStore(get_engine(), ctx.workspace.id)
    try:
        chain = store.verify()
    except AuditSchemaError as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    return {"ok": chain.ok, "checked": chain.checked, "broken_at": chain.broken_at}


def _event_out(row) -> dict:
    event = row.event
    return {
        "seq": row.seq,
        "prev_hash": row.prev_hash,
        "event_hash": row.event_hash,
        "run_id": row.run_id,
        "session_id": row.session_id,
        "event_type": event.event_type.value,
        "ts": event.ts,
        "role_id": event.role_id,
        "trace_id": event.trace_id,
        "payload": event.payload,
    }
