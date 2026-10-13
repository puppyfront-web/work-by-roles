"""TC-4-API-R-1 / TC-4-API-H-1 / TC-4-API-A-1 / TC-4-TASK-*：任务、会审、回归、审计 API。"""
from __future__ import annotations

import asyncio

import pytest

from tests.wbr.factories import EXPERT_OUTPUT_SCHEMA
from wbr.app.tasks.queue import (
    InlineTaskQueue,
    InProcessTaskQueue,
    JsonTaskStore,
    TaskKind,
    TaskRecord,
    TaskStatus,
)


REVIEW_BODY = {
    "question": "如何设计登录认证？",
    "coordinator": "coordinator",
    "experts": ["expert_a"],
    "verifier": "verifier",
}


def make_suite_payload():
    return {
        "suite_id": "suite-api-1",
        "cases": [{
            "case_id": "c1",
            "question": "如何设计登录认证？",
            "expected_keywords": [],
            "expert_role_ids": ["expert_a"],
        }],
    }


# ---- 会审 API（InlineQueue 同步路径）----
def test_review_submit_and_result(seeded):
    r = seeded.post("/api/v1/reviews", json=REVIEW_BODY)
    assert r.status_code == 202
    task_id = r.json()["task_id"]
    result = seeded.get(f"/api/v1/reviews/{task_id}").json()
    assert result["status"] == "done", result
    res = result["result"]
    assert res["status"] == "completed"
    assert res["final_answer"]
    assert any(o["role_id"] == "expert_a" for o in res["expert_outcomes"])
    # 列表
    lst = seeded.get("/api/v1/reviews").json()
    assert any(t["task_id"] == task_id for t in lst)


def test_review_unknown_contract_404(seeded):
    r = seeded.post("/api/v1/reviews", json={**REVIEW_BODY, "experts": ["ghost"]})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "E9003"


# ---- Harness 回归 API ----
def test_harness_suite_and_regression(seeded):
    r = seeded.post("/api/v1/harness/suites", json=make_suite_payload())
    assert r.status_code == 201
    suite_id = r.json()["suite_id"]
    assert seeded.get(f"/api/v1/harness/suites/{suite_id}").status_code == 200

    r = seeded.post("/api/v1/harness/regressions", json={
        "contract_ids": ["coordinator", "expert_a", "verifier"],
        "suite": make_suite_payload(),
        "stability_runs": 2,
    })
    assert r.status_code == 202
    task_id = r.json()["task_id"]
    rep = seeded.get(f"/api/v1/harness/regressions/{task_id}").json()
    assert rep["status"] == "done"
    report = rep["report"]
    metrics = report["metrics"]
    for key in ("contract_compliance_rate", "schema_pass_rate", "forbidden_violation_rate",
                "evidence_completeness_rate", "overall_pass_rate"):
        assert key in metrics, metrics
    assert report["case_results"][0]["case_id"] == "c1"


# ---- 审计导出 API ----
def test_audit_export(seeded):
    seeded.post("/api/v1/reviews", json=REVIEW_BODY)
    r = seeded.get("/api/v1/audits/export")
    assert r.status_code == 200
    pack = r.json()
    assert pack["format_version"] == "1.0"
    assert pack["integrity"]["event_count"] > 0
    # 脱敏开关
    r2 = seeded.get("/api/v1/audits/export?contents=true")
    assert r2.status_code == 200
    # trace 过滤
    if pack["events"]:
        tid = pack["events"][0]["trace_id"]
        r3 = seeded.get(f"/api/v1/audits/export?trace_id={tid}")
        assert all(e["trace_id"] == tid for e in r3.json()["events"])


# ---- 异步任务队列单元 ----
def test_inline_queue_done_and_failed():
    q = InlineTaskQueue(lambda rec: {"ok": True})
    r = q.submit(TaskRecord(kind=TaskKind.REVIEW, payload={}))
    assert r.status == TaskStatus.DONE and r.result == {"ok": True}
    q2 = InlineTaskQueue(lambda rec: 1 / 0)
    r2 = q2.submit(TaskRecord(kind=TaskKind.REGRESSION, payload={}))
    assert r2.status == TaskStatus.FAILED and "division by zero" in (r2.error or "")


def test_inprocess_async_worker():
    async def scenario():
        q = InProcessTaskQueue(lambda rec: {"n": rec.payload.get("n")})
        await q.start()
        rec = q.submit(TaskRecord(kind=TaskKind.REVIEW, payload={"n": 7}))
        for _ in range(100):
            got = q.get(rec.task_id)
            if got.status in (TaskStatus.DONE, TaskStatus.FAILED):
                break
            await asyncio.sleep(0.01)
        await q.stop()
        return got

    got = asyncio.run(scenario())
    assert got.status == TaskStatus.DONE
    assert got.result == {"n": 7}


def test_json_task_store_restart_recovery(tmp_path):
    store = JsonTaskStore(tmp_path / "tasks")
    done = TaskRecord(kind=TaskKind.REVIEW, payload={})
    done.status = TaskStatus.DONE
    done.result = {"x": 1}
    pending = TaskRecord(kind=TaskKind.REGRESSION, payload={"y": 2})
    store.save(done)
    store.save(pending)

    # 重启：DONE 可查、PENDING 重投递
    q = InlineTaskQueue(lambda rec: {"replayed": rec.payload})
    resubmitted = store.resubmit_pending(q)
    assert len(resubmitted) == 1
    assert resubmitted[0].payload == {"y": 2}
    assert q.get(pending.task_id).status == TaskStatus.DONE
    loaded = store.load(done.task_id)
    assert loaded.result == {"x": 1}


def test_tasks_async_api_end_to_end(tmp_path):
    """Inline 队列 + 落盘：提交 → 202 → 轮询到 done（async worker 已单测覆盖）。"""
    from fastapi.testclient import TestClient

    from wbr.app.api.main import create_app

    app2 = create_app(data_root=tmp_path / "data2", queue=InlineTaskQueue(lambda r: None))
    from tests.wbr.phase4.conftest import contract_payload

    with TestClient(app2) as c:
        for cid, rt in [("coordinator", "coordinator"), ("expert_a", "expert"), ("verifier", "verifier")]:
            assert c.post("/api/v1/contracts", json=contract_payload(cid, rt)).status_code == 201
        r = c.post("/api/v1/reviews", json=REVIEW_BODY)
        assert r.status_code == 202
        tid = r.json()["task_id"]
        result = c.get(f"/api/v1/reviews/{tid}").json()
        assert result["status"] == "done"
