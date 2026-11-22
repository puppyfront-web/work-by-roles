"""审计查询 API：按运行检索，可选 API Key，SQLite 重启后仍在。"""
from __future__ import annotations

import time

import pytest

from tests.wbr.phase4.conftest import contract_payload
from tests.wbr.phase4.test_review_harness_api import REVIEW_BODY


def _wait_review(client, task_id: str, headers: dict | None = None) -> dict:
    last: dict = {}
    for _ in range(50):
        response = client.get(f"/api/v1/reviews/{task_id}", headers=headers)
        assert response.status_code == 200, response.text
        last = response.json()
        if last["status"] in ("done", "failed"):
            return last
        time.sleep(0.05)
    return last


def _seed(client, headers: dict | None = None) -> None:
    for cid, role_type in (
        ("coordinator", "coordinator"),
        ("expert_a", "expert"),
        ("verifier", "verifier"),
    ):
        response = client.post(
            "/api/v1/contracts", json=contract_payload(cid, role_type), headers=headers
        )
        assert response.status_code == 201, response.text


def test_list_events_for_run_without_auth(seeded):
    health = seeded.get("/api/v1/healthz").json()
    assert health["components"]["audit_backend"] == "memory"
    created = seeded.post("/api/v1/reviews", json=REVIEW_BODY)
    assert created.status_code == 202
    task_id = created.json()["task_id"]
    assert _wait_review(seeded, task_id)["status"] == "done"

    listed = seeded.get(f"/api/v1/reviews/{task_id}/audits")
    assert listed.status_code == 200
    body = listed.json()
    assert body["run_id"] == task_id
    assert body["chain"]["ok"] is True
    assert body["events"]
    assert {row["run_id"] for row in body["events"]} == {task_id}
    kinds = {row["event"]["event_type"] for row in body["events"]}
    assert "session_started" in kinds
    assert "expert_skipped" in kinds or "expert_completed" in kinds or "expert_failed" in kinds

    trace_id = body["events"][0]["event"]["trace_id"]
    filtered = seeded.get("/api/v1/audits/events", params={
        "trace_id": trace_id,
        "event_type": "session_started",
        "limit": 1,
    })
    assert filtered.status_code == 200
    rows = filtered.json()["events"]
    assert len(rows) == 1
    assert rows[0]["event"]["event_type"] == "session_started"
    assert rows[0]["prev_hash"]
    assert rows[0]["event_hash"]

    missing = seeded.get("/api/v1/reviews/does-not-exist/audits")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "E9006"
    unknown = seeded.get("/api/v1/audits/events", params={"event_type": "not_a_type"})
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "E9022"
    backwards = seeded.get("/api/v1/audits/events", params={"since": 10, "until": 1})
    assert backwards.status_code == 422


def test_audit_query_requires_api_key_when_configured(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from wbr.app.api.main import create_app

    app = create_app(data_root=tmp_path / "data", api_key="s3cret")
    headers = {"X-API-Key": "s3cret"}
    with TestClient(app) as client:
        _seed(client, headers)
        created = client.post("/api/v1/reviews", json=REVIEW_BODY, headers=headers)
        assert created.status_code == 202
        task_id = created.json()["task_id"]
        assert _wait_review(client, task_id, headers)["status"] == "done"

        hidden = client.get(f"/api/v1/reviews/{task_id}/audits")
        assert hidden.status_code == 401
        query_key = client.get(
            f"/api/v1/reviews/{task_id}/audits", params={"api_key": "s3cret"}
        )
        assert query_key.status_code == 401
        allowed = client.get(
            "/api/v1/audits/events",
            params={"run_id": task_id},
            headers={"X-API-Key": "s3cret"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["chain"]["ok"] is True
        assert allowed.json()["events"]


def test_sqlite_audit_survives_new_process(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from wbr.app.api.main import create_app

    db = tmp_path / "audit.db"
    data = tmp_path / "data"
    monkeypatch.setenv("WBR_AUDIT_DB", str(db))
    with TestClient(create_app(data_root=data, api_key="")) as client:
        assert client.get("/api/v1/healthz").json()["components"]["audit_backend"] == "sqlite"
        _seed(client)
        created = client.post("/api/v1/reviews", json=REVIEW_BODY)
        task_id = created.json()["task_id"]
        assert _wait_review(client, task_id)["status"] == "done"
        before = client.get(f"/api/v1/reviews/{task_id}/audits").json()
        assert before["chain"]["ok"] is True
        count = len(before["events"])

    monkeypatch.delenv("WBR_AUDIT_DB", raising=False)
    with TestClient(create_app(data_root=data, api_key="", audit_db=db)) as client:
        after = client.get(f"/api/v1/reviews/{task_id}/audits")
        assert after.status_code == 200
        body = after.json()
        assert body["chain"]["ok"] is True
        assert len(body["events"]) == count
        assert {row["event_hash"] for row in body["events"]} == {
            row["event_hash"] for row in before["events"]
        }


def test_explicit_store_and_blank_path_ignore_env(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from wbr.app.api.main import create_app
    from wbr.core.audit.store import InMemoryAuditStore

    monkeypatch.setenv("WBR_AUDIT_DB", str(tmp_path / "from-env.db"))
    memory = InMemoryAuditStore()
    with TestClient(create_app(data_root=tmp_path / "data", api_key="", audit_store=memory)) as client:
        assert client.get("/api/v1/healthz").json()["components"]["audit_backend"] == "memory"
    assert not (tmp_path / "from-env.db").exists()

    with TestClient(create_app(data_root=tmp_path / "data2", api_key="", audit_db="")) as client:
        assert client.get("/api/v1/healthz").json()["components"]["audit_backend"] == "memory"
    assert not (tmp_path / "from-env.db").exists()
