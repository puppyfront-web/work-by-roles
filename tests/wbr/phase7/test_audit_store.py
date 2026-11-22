"""审计存储契约：内存与 SQLite 同一套行为，外加重启、篡改与并发。"""
from __future__ import annotations

import json
import sqlite3
import threading
import time

import pytest

from tests.wbr.factories import coordinator_contract, expert_contract, verifier_contract
from tests.wbr.phase1.test_review_flow import GOOD_OUTPUT, plan_for
from wbr.core.audit.chain import GENESIS, HASH_ALG
from wbr.core.audit.models import AuditEvent, AuditEventType
from wbr.core.audit.store import (
    AuditRunScope,
    InMemoryAuditStore,
    SqliteAuditStore,
    resolve_audit_store,
)
from wbr.core.audit.trail import AuditTrail
from wbr.core.exceptions import AuditChainBroken, AuditSchemaError
from wbr.core.orchestration import ReviewSession, ScriptedInvoker
from wbr.core.token.meter import BudgetAction, BudgetPolicy, TokenBudget, TokenMeter


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


def _tamper_payload(store, seq: int, **changes) -> None:
    if isinstance(store, InMemoryAuditStore):
        store._records[seq].event.payload.update(changes)
        return
    row = store._conn.execute(
        "SELECT event_json FROM audit_events WHERE seq = ?", (seq,)
    ).fetchone()
    data = json.loads(row["event_json"])
    data["payload"].update(changes)
    store._conn.execute(
        "UPDATE audit_events SET event_json = ? WHERE seq = ?",
        (json.dumps(data, ensure_ascii=False), seq),
    )


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    if request.param == "memory":
        opened = InMemoryAuditStore()
    else:
        opened = SqliteAuditStore(tmp_path / "audit.db")
    yield opened
    opened.close()


def test_append_links_hash_and_defaults_run_to_trace(store):
    first = store.append(_event("trace-a", payload_n=1))
    second = store.append(
        _event("trace-b", AuditEventType.EXPERT_SKIPPED, role_id="expert_b"),
        run_id="run-1",
        session_id="sess-1",
    )
    assert first.seq == 0 and first.prev_hash == GENESIS
    assert second.seq == 1 and second.prev_hash == first.event_hash
    assert first.run_id == "trace-a" and first.session_id == ""
    assert second.run_id == "run-1" and second.session_id == "sess-1"
    assert store.verify().ok is True
    assert store.verify().checked == 2
    assert [row.seq for row in store] == [0, 1]


def test_query_by_run_session_type_and_time(store):
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
    by_run = store.query(run_id="run-a")
    assert [row.event.trace_id for row in by_run] == ["t-early", "t-mid"]
    by_session = store.query(session_id="s2")
    assert [row.event.trace_id for row in by_session] == ["t-mid", "t-late"]
    by_type = store.query(event_type=AuditEventType.EXPERT_SKIPPED)
    assert len(by_type) == 1 and by_type[0].event.role_id == "expert_b"
    by_name = store.query(event_type="token_budget_exceeded")
    assert len(by_name) == 1 and by_name[0].event.trace_id == "t-mid"
    window = store.query(since=20, until=20)
    assert [row.event.trace_id for row in window] == ["t-mid"]
    assert [row.seq for row in store.query(limit=1)] == [0]
    assert store.query(trace_id="missing") == []


def test_tamper_returns_broken_index_and_strict_raises(store):
    store.append(_event(n=1))
    store.append(_event("trace-2", AuditEventType.TOKEN_RECORD, role_id="expert_a", n=2))
    _tamper_payload(store, 1, n=999)
    result = store.verify()
    assert result.ok is False and result.broken_at == 1
    with pytest.raises(AuditChainBroken) as exc:
        store.verify(strict=True)
    assert exc.value.code == "E5002"
    assert exc.value.details["broken_at"] == 1


def test_deletion_breaks_chain(store):
    for i in range(4):
        store.append(_event(f"t{i}", n=i))
    if isinstance(store, InMemoryAuditStore):
        del store._records[1]
    else:
        store._conn.execute("DELETE FROM audit_events WHERE seq = 1")
    result = store.verify()
    assert result.ok is False and result.broken_at == 1


def test_memory_reorder_breaks_chain():
    store = InMemoryAuditStore()
    for i in range(3):
        store.append(_event(f"t{i}"))
    store._records[0], store._records[1] = store._records[1], store._records[0]
    assert store.verify().ok is False


def test_concurrent_appends_keep_a_single_chain(store):
    count = 32
    barrier = threading.Barrier(count)

    def worker(index: int) -> None:
        barrier.wait()
        store.append(
            _event(f"t{index}", AuditEventType.LOOP_STEP, role_id="expert", i=index)
        )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
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


def test_empty_store_verifies():
    assert InMemoryAuditStore().verify().ok is True


def test_limit_must_be_positive():
    with pytest.raises(ValueError):
        InMemoryAuditStore().query(limit=0)


def test_sqlite_restart_and_schema_meta(tmp_path):
    path = tmp_path / "nested" / "audit.db"
    store = SqliteAuditStore(path)
    store.append(_event("trace-keep", AuditEventType.CACHE_HIT, role_id="expert_a", hit="exact"))
    store.close()

    restored = SqliteAuditStore(path)
    rows = restored.query()
    assert len(rows) == 1
    assert rows[0].event.event_type == AuditEventType.CACHE_HIT
    assert rows[0].event.payload["hit"] == "exact"
    assert restored.verify().ok is True
    meta = dict(restored._conn.execute("SELECT key, value FROM audit_meta"))
    assert meta["schema_version"] == "1"
    assert meta["hash_alg"] == HASH_ALG
    user_version = restored._conn.execute("PRAGMA user_version").fetchone()[0]
    assert user_version == 1
    restored.close()


def test_sqlite_tamper_on_load_raises(tmp_path):
    path = tmp_path / "audit.db"
    store = SqliteAuditStore(path)
    store.append(_event(n=1))
    store.append(_event("t2", n=2))
    store.close()
    _tamper_closed_db(path, 1, n=0)
    with pytest.raises(AuditChainBroken) as exc:
        SqliteAuditStore(path)
    assert exc.value.details["broken_at"] == 1

    opened = SqliteAuditStore(path, verify_on_load=False)
    assert opened.verify().broken_at == 1
    opened.close()


def test_sqlite_rejects_future_schema_and_foreign_hash(tmp_path):
    path = tmp_path / "audit.db"
    store = SqliteAuditStore(path)
    store.close()
    conn = sqlite3.connect(path)
    conn.execute("UPDATE audit_meta SET value = '99' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()
    with pytest.raises(AuditSchemaError) as exc:
        SqliteAuditStore(path)
    assert exc.value.details["schema_version"] == 99

    conn = sqlite3.connect(path)
    conn.execute("UPDATE audit_meta SET value = '1' WHERE key = 'schema_version'")
    conn.execute("UPDATE audit_meta SET value = 'other' WHERE key = 'hash_alg'")
    conn.commit()
    conn.close()
    with pytest.raises(AuditSchemaError) as exc:
        SqliteAuditStore(path)
    assert "other" in exc.value.message


def test_resolve_store_precedence(tmp_path, monkeypatch):
    explicit = InMemoryAuditStore()
    env_path = tmp_path / "env.db"
    monkeypatch.setenv("WBR_AUDIT_DB", str(env_path))
    assert resolve_audit_store(explicit, env_path) is explicit
    assert isinstance(resolve_audit_store(path=""), InMemoryAuditStore)
    chosen = resolve_audit_store()
    assert isinstance(chosen, SqliteAuditStore)
    chosen.close()
    assert env_path.is_file()


def test_trail_without_store_stays_in_memory():
    trail = AuditTrail()
    trail.append(_event())
    assert trail.store is None
    assert len(trail.events) == 1
    assert "events" in trail.to_dict()


def test_trail_reloads_sqlite_events(tmp_path):
    path = tmp_path / "audit.db"
    store = SqliteAuditStore(path)
    trail = AuditTrail()
    trail.attach_store(store)
    trail.append(_event("trace-x", AuditEventType.EXPERT_COMPLETED, role_id="expert_a"), run_id="run-x")
    store.close()

    reopened = SqliteAuditStore(path)
    restored = AuditTrail()
    restored.attach_store(reopened)
    assert len(restored.events) == 1
    assert restored.events[0].trace_id == "trace-x"
    assert reopened.query(run_id="run-x")[0].event_hash
    reopened.close()


def _scripts(assignments: dict[str, str]) -> dict:
    return {
        "coordinator": plan_for(assignments),
        "verifier": {
            "passed": True,
            "scores": {"completeness": 0.8, "accuracy": 0.8},
            "comments": "ok",
            "final_answer": "结论",
        },
        "expert_a": GOOD_OUTPUT,
        "expert_b": GOOD_OUTPUT,
    }


def test_token_saving_events_survive_restart(tmp_path):
    path = tmp_path / "audit.db"
    store = SqliteAuditStore(path)
    trail = AuditTrail()
    trail.attach_store(store)
    scoped = AuditRunScope(trail, run_id="run-save", session_id="sess-save")
    meter = TokenMeter(audit=scoped)
    budget = TokenBudget(
        BudgetPolicy(max_total_tokens=100_000, per_role={"expert_a": 1}, on_exceed=BudgetAction.DEGRADE),
        meter,
    )
    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[expert_contract("expert_a"), expert_contract("expert_b")],
        verifier_contract=verifier_contract(),
        invoker=ScriptedInvoker(_scripts({"expert_a": "只问甲"})),
        audit=scoped,
        token_budget=budget,
        token_meter=meter,
    )
    result = session.run("问题")
    assert result.outcome_by_role("expert_a").skip_reason == "budget"
    assert result.outcome_by_role("expert_b").skip_reason == "unassigned"
    store.close()

    restored = SqliteAuditStore(path)
    rows = restored.query(run_id="run-save")
    kinds = {row.event.event_type for row in rows}
    assert AuditEventType.EXPERT_SKIPPED in kinds
    assert AuditEventType.TOKEN_BUDGET_EXCEEDED in kinds
    assert AuditEventType.TOKEN_RECORD in kinds
    assert restored.verify().ok is True
    assert all(row.session_id == "sess-save" for row in rows)
    restored.close()


def _tamper_closed_db(path, seq: int, **changes) -> None:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT event_json FROM audit_events WHERE seq = ?", (seq,)
    ).fetchone()
    data = json.loads(row["event_json"])
    data.setdefault("payload", {}).update(changes)
    conn.execute(
        "UPDATE audit_events SET event_json = ? WHERE seq = ?",
        (json.dumps(data, ensure_ascii=False), seq),
    )
    conn.commit()
    conn.close()


def test_query_time_uses_event_clock(store):
    store.append(_event(ts=time.time()))
    future = store.query(since=time.time() + 10_000)
    assert future == []
