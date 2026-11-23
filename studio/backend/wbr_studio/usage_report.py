"""按工作区汇总已结束运行的 token、缓存命中和估算费用。"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from wbr.core.orchestration.invoker import TokenUsage
from wbr_studio.models import Run, utcnow


def cache_hit_rate(cached: int, prompt: int) -> float:
    if prompt <= 0:
        return 0.0
    return round(cached / prompt, 4)


def _empty() -> dict[str, Any]:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_prompt_tokens": 0,
        "cost_total": 0.0,
        "runs": 0,
    }


def _finish(bucket: dict[str, Any]) -> dict[str, Any]:
    bucket["cache_hit_rate"] = cache_hit_rate(bucket["cached_prompt_tokens"], bucket["prompt_tokens"])
    return bucket


def _add(bucket: dict[str, Any], prompt: int, completion: int, cached: int, cost: float, *, run: bool) -> None:
    bucket["prompt_tokens"] += prompt
    bucket["completion_tokens"] += completion
    bucket["cached_prompt_tokens"] += cached
    bucket["cost_total"] += cost
    if run:
        bucket["runs"] += 1


def _role_cost(item: dict[str, Any], run: Run) -> float:
    if run.input_price is None or run.output_price is None:
        return 0.0
    usage = TokenUsage(
        prompt_tokens=int(item.get("prompt_tokens") or 0),
        completion_tokens=int(item.get("completion_tokens") or 0),
        cached_prompt_tokens=int(item.get("cached_prompt_tokens") or 0),
        cache_scope=str(item.get("cache_scope") or "unknown"),
    )
    return float(
        usage.estimate_cost(
            input_price=run.input_price,
            output_price=run.output_price,
            cached_input_price=run.cached_input_price,
        )["total"]
    )


def build_usage(db: Session, workspace_id: uuid.UUID, days: int, now: datetime | None = None) -> dict[str, Any]:
    moment = now or utcnow()
    start = moment - timedelta(days=days)
    rows = db.scalars(
        select(Run)
        .where(
            Run.workspace_id == workspace_id,
            Run.status.in_(("completed", "failed", "cancelled")),
            Run.finished_at.is_not(None),
            Run.finished_at >= start,
            Run.finished_at <= moment,
        )
        .order_by(Run.finished_at.asc())
    ).all()
    totals = _empty()
    by_day: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    by_role: dict[str, dict[str, Any]] = {}
    for run in rows:
        finished = run.finished_at
        if finished is None:
            continue
        day = finished.astimezone(timezone.utc).date().isoformat()
        model = run.model or "unknown"
        _add(totals, run.prompt_tokens, run.completion_tokens, run.cached_prompt_tokens, run.cost_total, run=True)
        _add(by_day.setdefault(day, _empty()), run.prompt_tokens, run.completion_tokens, run.cached_prompt_tokens, run.cost_total, run=True)
        _add(by_model.setdefault(model, _empty()), run.prompt_tokens, run.completion_tokens, run.cached_prompt_tokens, run.cost_total, run=True)
        payload = run.result_json or {}
        for item in payload.get("usage_by_role") or []:
            if not isinstance(item, dict):
                continue
            role_id = str(item.get("role_id") or "unknown")
            bucket = by_role.setdefault(role_id, _empty())
            _add(
                bucket,
                int(item.get("prompt_tokens") or 0),
                int(item.get("completion_tokens") or 0),
                int(item.get("cached_prompt_tokens") or 0),
                _role_cost(item, run),
                run=False,
            )
    return {
        "from": start.astimezone(timezone.utc).isoformat(),
        "to": moment.astimezone(timezone.utc).isoformat(),
        "days": days,
        "totals": _finish(totals),
        "by_day": [{"day": day, **_finish(bucket)} for day, bucket in by_day.items()],
        "by_model": [
            {"model": name, **_finish(bucket)}
            for name, bucket in sorted(by_model.items(), key=lambda item: item[1]["cost_total"], reverse=True)
        ],
        "by_role": [
            {"role_id": name, **_public_role(bucket)}
            for name, bucket in sorted(by_role.items(), key=lambda item: item[1]["prompt_tokens"], reverse=True)
        ],
    }


def _public_role(bucket: dict[str, Any]) -> dict[str, Any]:
    finished = _finish(bucket)
    finished.pop("runs", None)
    return finished
