"""Postgres AuditStore 的行为对齐 tests/wbr/phase7/test_audit_store.py。

内核夹具绑死了内存和 SQLite 的私有篡改入口，这里按同一契约在 Postgres 上重放。
"""
from __future__ import annotations

import json
import threading
import uuid

import pytest
from sqlalchemy import text

from tests.wbr.factories import coordinator_contract, expert_contract, verifier_contract
from wbr.core.audit.chain import GENESIS, audit_record_hash
from wbr.core.audit.models import AuditEvent, AuditEventType
from wbr.core.audit.store import SCHEMA_VERSION, AuditRunScope
from wbr.core.audit.trail import AuditTrail
from wbr.core.exceptions import AuditChainBroken, AuditSchemaError
from wbr.core.orchestration.invoker import ScriptedInvoker
from wbr.core.orchestration.review import ReviewSession
from wbr.core.token.meter import BudgetAction, BudgetPolicy, TokenBudget, TokenMeter
from wbr_studio.audit_store import PostgresAuditStore
from wbr_studio.db import get_sessionmaker
from wbr_studio.models import User, Workspace


def _event(
    trace_id: str = "trace-1",
    event_type: AuditEventType = AuditEventType.SESSION_STARTED,
    *,
    role_id: str | None = None,
    ts: float | None = None,
    **payload,
) -> AuditEvent:
    kwargs = {
        "event_type": event_type,
        "trace_id": trace_id,
        "role_id": role_id,
        "payload": payload,
    }
    if ts is not None:
        kwargs["ts"] = ts
    return AuditEvent(**kwargs)


def _workspace() -> uuid.UUID:
    db = get_sessionmaker()()
    try:
        user = User(email=f"{uuid.uuid4().hex}@example.com", password_hash="x")
        db.add(user)
        db.flush()
        workspace = Workspace(name="chain", owner_id=user.id)
        db.add(workspace)
        db.commit()
        return workspace.id
    finally:
        db.close()


@pytest.fixture
def store(db):
    opened = PostgresAuditStore(db, _workspace())
    yield opened
    opened.close()


def test_append_links_kernel_hash(store):
    first = store.append(_event("trace-a", n=1))
    second = store.append(
        _event("trace-b", AuditEventType.EXPERT_SKIPPED, role_id="expert_b"),
        run_id="run-1",
        session_id="sess-1",
    )
    assert first.seq == 0 and first.prev_hash == GENESIS
    assert second.seq == 1 and second.prev_hash == first.event_hash
    assert first.run_id == "trace-a" and first.session_id == ""
    assert second.run_id == "run-1" and second.session_id == "sess-1"
    assert first.event_hash == audit_record_hash(
        GENESIS, 0, first.event, run_id=first.run_id, session_id=first.session_id
    )
    assert store.verify().ok is True
    assert store.verify().checked == 2
    assert [row.seq for row in store] == [0, 1]


def test_query_filters_match_the_kernel_contract(store):
    store.append(_event("t-early", ts=10, n=1), run_id="run-a", session_id="s1")
    store.append(
        _event("t-mid", AuditEventType.TOKEN_BUDGET_EXCEEDED, role_id="expert_a", ts=20),
        run_id="run-a",
        session_id="s2",
    )
    store.append(
        _event("t-late", AuditEventType.EXPERT_SKIPPED, role_id="expert_b", ts=30),
        run_id="run-b",
        session_id="s2",
    )
    assert [row.event.trace_id for row in store.query(run_id="run-a")] == ["t-early", "t-mid"]
    assert [row.event.trace_id for row in store.query(session_id="s2")] == ["t-mid", "t-late"]
    assert store.query(event_type=AuditEventType.EXPERT_SKIPPED)[0].event.role_id == "expert_b"
    assert store.query(event_type="token_budget_exceeded")[0].event.trace_id == "t-mid"
    assert [row.event.trace_id for row in store.query(since=20, until=20)] == ["t-mid"]
    assert [row.seq for row in store.query(limit=1)] == [0]
    assert store.query(trace_id="missing") == []


def test_tamper_and_delete_break_the_chain(store, db):
    store.append(_event(n=1))
    store.append(_event("trace-2", AuditEventType.TOKEN_RECORD, role_id="expert_a", n=2))
    with db.begin() as conn:
        row = conn.execute(
            text("SELECT event_json FROM audit_events WHERE workspace_id = :id AND seq = 1"),
            {"id": store.workspace_id},
        ).one()
        payload = json.loads(row.event_json)
        payload["payload"]["n"] = 999
        conn.execute(
            text(
                "UPDATE audit_events SET event_json = :event_json "
                "WHERE workspace_id = :id AND seq = 1"
            ),
            {"event_json": json.dumps(payload, ensure_ascii=False), "id": store.workspace_id},
        )
    result = store.verify()
    assert result.ok is False and result.broken_at == 1
    with pytest.raises(AuditChainBroken) as exc:
        store.verify(strict=True)
    assert exc.value.details["broken_at"] == 1


def test_deletion_breaks_chain(store, db):
    for index in range(4):
        store.append(_event(f"t{index}", n=index))
    with db.begin() as conn:
        conn.execute(
            text("DELETE FROM audit_events WHERE workspace_id = :id AND seq = 1"),
            {"id": store.workspace_id},
        )
    result = store.verify()
    assert result.ok is False and result.broken_at == 1


def test_concurrent_appends_keep_one_chain(store):
    count = 32
    barrier = threading.Barrier(count)

    def worker(index: int) -> None:
        barrier.wait()
        store.append(_event(f"t{index}", AuditEventType.LOOP_STEP, role_id="expert", i=index))

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    rows = store.query()
    assert [row.seq for row in rows] == list(range(count))
    assert {row.event.payload["i"] for row in rows} == set(range(count))
    assert store.verify().ok is True
    assert rows[0].prev_hash == GENESIS
    for index in range(1, len(rows)):
        assert rows[index].prev_hash == rows[index - 1].event_hash


def test_empty_store_and_limit(db):
    store = PostgresAuditStore(db, _workspace())
    assert store.verify().ok is True
    with pytest.raises(ValueError):
        store.query(limit=0)


def test_chains_do_not_share_sequence(db):
    left = PostgresAuditStore(db, _workspace())
    right = PostgresAuditStore(db, _workspace())
    left.append(_event("left"))
    right.append(_event("right"))
    assert left.query()[0].seq == 0
    assert right.query()[0].seq == 0
    assert left.verify().checked == 1
    assert right.verify().checked == 1


def test_rejects_foreign_schema_and_hash(store, db):
    store.append(_event(n=1))
    with db.begin() as conn:
        conn.execute(
            text("UPDATE audit_chains SET schema_version = 99 WHERE workspace_id = :id"),
            {"id": store.workspace_id},
        )
    with pytest.raises(AuditSchemaError) as exc:
        PostgresAuditStore(db, store.workspace_id, verify_on_load=True)
    assert exc.value.details["schema_version"] == 99

    with db.begin() as conn:
        conn.execute(
            text(
                "UPDATE audit_chains SET schema_version = :version, hash_alg = 'other' "
                "WHERE workspace_id = :id"
            ),
            {"version": SCHEMA_VERSION, "id": store.workspace_id},
        )
    with pytest.raises(AuditSchemaError) as exc:
        store.append(_event(n=2))
    assert exc.value.details["hash_alg"] == "other"
    with db.begin() as conn:
        row = conn.execute(
            text("SELECT hash_alg FROM audit_chains WHERE workspace_id = :id"),
            {"id": store.workspace_id},
        ).one()
    assert row.hash_alg == "other"


def test_review_session_token_events_stay_on_the_chain(db):
    workspace_id = _workspace()
    store = PostgresAuditStore(db, workspace_id)
    trail = AuditTrail()
    trail.attach_store(store)
    scoped = AuditRunScope(trail, run_id="run-save", session_id="sess-save")
    meter = TokenMeter(audit=scoped)
    budget = TokenBudget(
        BudgetPolicy(
            max_total_tokens=100_000,
            per_role={"expert_a": 1},
            on_exceed=BudgetAction.DEGRADE,
        ),
        meter,
    )
    good = {"conclusion": "采用 JWT 无状态方案", "confidence": 0.9}
    scripts = {
        "coordinator": {
            "assignments": [
                {"expert_role_id": "expert_a", "sub_question": "只问甲"},
                {"expert_role_id": "expert_b", "sub_question": "只问甲"},
            ],
            "strategy": "parallel",
        },
        "verifier": {
            "passed": True,
            "scores": {"completeness": 0.8, "accuracy": 0.8},
            "comments": "ok",
            "final_answer": "结论",
        },
        "expert_a": good,
        "expert_b": good,
    }
    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[expert_contract("expert_a"), expert_contract("expert_b")],
        verifier_contract=verifier_contract(),
        invoker=ScriptedInvoker(scripts),
        audit=scoped,
        token_budget=budget,
        token_meter=meter,
    )
    result = session.run("问题")
    assert result.outcome_by_role("expert_a").skip_reason == "budget"
    rows = store.query(run_id="run-save")
    kinds = {row.event.event_type for row in rows}
    assert AuditEventType.EXPERT_SKIPPED in kinds
    assert AuditEventType.TOKEN_BUDGET_EXCEEDED in kinds
    assert AuditEventType.TOKEN_RECORD in kinds
    assert store.verify().ok is True
    assert all(row.session_id == "sess-save" for row in rows)


def test_worker_job_name():
    from wbr_studio.worker import WorkerSettings, run_review

    assert WorkerSettings.functions == [run_review]
    assert WorkerSettings.max_tries == 1
    assert run_review.__name__ == "run_review"
