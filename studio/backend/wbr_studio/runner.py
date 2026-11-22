"""执行一次会审：解密工作区密钥，调用内核 ReviewSession，把用量写回 Run。"""
from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from wbr.adapters.llm import OpenAICompatInvoker
from wbr.core.audit.store import AuditRunScope
from wbr.core.audit.trail import AuditTrail
from wbr.core.orchestration.invoker import ModelInvoker
from wbr.core.orchestration.review import ReviewSession, ReviewStatus
from wbr.core.token.meter import BudgetAction, BudgetPolicy, TokenBudget, TokenMeter
from wbr_studio.audit_store import PostgresAuditStore
from wbr_studio.contracts import TeamContractError, parse_stored_contracts
from wbr_studio.db import get_engine, get_sessionmaker
from wbr_studio.models import ProviderKey, Run, Team, utcnow
from wbr_studio.security import SecretError, decrypt_secret

_log = logging.getLogger("wbr_studio.runner")

InvokerBuilder = Callable[[str, str, str], ModelInvoker]


def default_invoker_builder(base_url: str, api_key: str, model: str) -> OpenAICompatInvoker:
    return OpenAICompatInvoker(base_url=base_url, api_key=api_key, model=model)


_builder: InvokerBuilder = default_invoker_builder


def set_invoker_builder(builder: InvokerBuilder | None) -> None:
    global _builder
    _builder = default_invoker_builder if builder is None else builder


def execute_run(run_id: str) -> None:
    db = get_sessionmaker()()
    secret_box: list[str] = []
    try:
        run = db.get(Run, uuid.UUID(run_id))
        if run is None or run.status != "queued":
            return
        run.status = "running"
        run.started_at = utcnow()
        db.commit()
        try:
            _perform(db, run, secret_box)
        except Exception as exc:
            db.rollback()
            failed = db.get(Run, uuid.UUID(run_id))
            if failed is not None and failed.status != "completed":
                failed.status = "failed"
                failed.error = _public_error(exc, secret_box[0] if secret_box else None)
                failed.finished_at = utcnow()
                db.commit()
            _log.warning("run %s failed (%s)", run_id, type(exc).__name__)
    finally:
        db.close()


def _perform(db: Session, run: Run, secret_box: list[str]) -> None:
    team = db.get(Team, run.team_id)
    if team is None or team.workspace_id != run.workspace_id:
        raise RuntimeError("团队不存在")
    key = _load_key(db, run)
    try:
        coordinator, experts, verifier = parse_stored_contracts(team.contracts)
    except TeamContractError as exc:
        raise RuntimeError(str(exc)) from exc
    plaintext = decrypt_secret(key.ciphertext)
    secret_box.append(plaintext)
    invoker = _builder(key.base_url, plaintext, key.model)
    store = PostgresAuditStore(get_engine(), run.workspace_id)
    trail = AuditTrail()
    trail.attach_store(store)
    scoped = AuditRunScope(trail, run_id=str(run.id), session_id=str(run.id))
    meter = TokenMeter(audit=scoped)
    budget = None
    if run.token_budget:
        budget = TokenBudget(
            BudgetPolicy(max_total_tokens=run.token_budget, on_exceed=BudgetAction.DEGRADE),
            meter,
        )
    session = ReviewSession(
        coordinator_contract=coordinator,
        expert_contracts=experts,
        verifier_contract=verifier,
        invoker=invoker,
        audit=scoped,
        token_meter=meter,
        token_budget=budget,
        session_id=str(run.id),
    )
    result = session.run(run.question)
    _save_result(run, result, meter)
    db.commit()


def _load_key(db: Session, run: Run) -> ProviderKey:
    if run.provider_key_id is not None:
        key = db.get(ProviderKey, run.provider_key_id)
        if key is None or key.workspace_id != run.workspace_id:
            raise RuntimeError("供应商密钥不存在")
        return key
    key = db.scalars(
        select(ProviderKey)
        .where(ProviderKey.workspace_id == run.workspace_id)
        .order_by(ProviderKey.created_at.desc())
    ).first()
    if key is None:
        raise RuntimeError("请先保存供应商 API Key")
    run.provider_key_id = key.id
    return key


def _save_result(run: Run, result: Any, meter: TokenMeter) -> None:
    records = meter.records
    run.prompt_tokens = sum(item.prompt_tokens for item in records)
    run.completion_tokens = sum(item.completion_tokens for item in records)
    run.cached_prompt_tokens = sum(item.cached_prompt_tokens for item in records)
    if run.input_price is not None and run.output_price is not None:
        cost = meter.estimate_cost(
            input_price=run.input_price,
            output_price=run.output_price,
            cached_input_price=run.cached_input_price,
        )
    else:
        cost = {"total": 0.0, "baseline_total": 0.0, "savings": 0.0}
    run.cost_total = float(cost["total"])
    run.cost_baseline = float(cost["baseline_total"])
    run.cost_savings = float(cost["savings"])
    payload = result.model_dump(mode="json")
    payload["usage_by_role"] = [
        {
            "role_id": item.role_id,
            "step": item.step,
            "prompt_tokens": item.prompt_tokens,
            "completion_tokens": item.completion_tokens,
            "cached_prompt_tokens": item.cached_prompt_tokens,
            "cache_scope": item.cache_scope,
        }
        for item in records
    ]
    run.result_json = payload
    run.trace_id = result.trace_id or None
    run.error = result.error
    run.status = "failed" if result.status == ReviewStatus.FAILED else "completed"
    run.finished_at = utcnow()


def _public_error(exc: BaseException, secret: str | None) -> str:
    if isinstance(exc, SecretError):
        text = str(exc)
    else:
        text = str(exc).strip() or type(exc).__name__
    if secret:
        text = text.replace(secret, "***")
    return text[:800]
