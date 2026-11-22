"""API 上的 Workspace：默认目录保持兼容，带头后契约与任务互相不可见。"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.wbr.phase4.conftest import contract_payload
from wbr.app.api.main import create_app

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

HEADER_A = {"X-WBR-Workspace": "team_a"}
HEADER_B = {"X-WBR-Workspace": "team_b"}

REVIEW_BODY = {
    "question": "如何设计登录认证？",
    "coordinator": "coordinator",
    "experts": ["expert_a"],
    "verifier": "verifier",
}


def _create_pair(client):
    assert client.post("/api/v1/workspaces", json={"name": "team_a"}).status_code == 201
    assert client.post("/api/v1/workspaces", json={"name": "team_b"}).status_code == 201


def _seed(client, headers):
    for cid, role in (
        ("coordinator", "coordinator"),
        ("expert_a", "expert"),
        ("verifier", "verifier"),
    ):
        response = client.post(
            "/api/v1/contracts", json=contract_payload(cid, role), headers=headers,
        )
        assert response.status_code == 201, response.text


def test_default_directory_ignores_other_workspaces(client):
    _create_pair(client)
    created = client.post("/api/v1/contracts", json=contract_payload("expert_a"), headers=HEADER_A)
    assert created.status_code == 201, created.text

    assert client.get("/api/v1/contracts", headers=HEADER_B).json() == []
    assert client.get("/api/v1/contracts").json() == []
    assert client.get("/api/v1/contracts/expert_a").status_code == 404
    assert client.get("/api/v1/contracts/expert_a", headers=HEADER_A).status_code == 200
    missing = client.get("/api/v1/contracts", headers={"X-WBR-Workspace": "no_such"})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "E9003"


def test_workspace_names_and_listing(client):
    _create_pair(client)
    names = {item["name"] for item in client.get("/api/v1/workspaces").json()}
    assert names == {"team_a", "team_b"}
    again = client.post("/api/v1/workspaces", json={"name": "team_a"})
    assert again.status_code == 409
    bad = client.post("/api/v1/workspaces", json={"name": "Bad-Name"})
    assert bad.status_code == 422
    assert client.delete("/api/v1/workspaces/team_b").status_code == 204
    assert client.get("/api/v1/contracts", headers=HEADER_B).status_code == 404


def test_copy_contract_keeps_lineage_and_stays_isolated(client):
    _create_pair(client)
    assert client.post(
        "/api/v1/contracts", json=contract_payload("expert_a"), headers=HEADER_A
    ).status_code == 201
    copied = client.post(
        "/api/v1/workspaces/team_b/contracts/expert_a/copy",
        json={"source": "team_a"},
    )
    assert copied.status_code == 201, copied.text
    body = client.get("/api/v1/contracts/expert_a", headers=HEADER_B).json()
    assert "team_a" in body["meta"]["changelog"][-1]
    assert client.get("/api/v1/contracts/expert_a").status_code == 404


def test_review_tasks_do_not_cross_workspaces(client):
    _create_pair(client)
    _seed(client, HEADER_A)
    submitted = client.post("/api/v1/reviews", json=REVIEW_BODY, headers=HEADER_A)
    assert submitted.status_code == 202, submitted.text
    task_id = submitted.json()["task_id"]
    assert client.get(f"/api/v1/reviews/{task_id}").status_code == 404
    assert client.get(f"/api/v1/reviews/{task_id}", headers=HEADER_B).status_code == 404
    owned = client.get(f"/api/v1/reviews/{task_id}", headers=HEADER_A)
    assert owned.status_code == 200
    assert owned.json()["status"] in {"pending", "running", "done"}
    listed = client.get("/api/v1/reviews", headers=HEADER_A).json()
    assert task_id in {item["task_id"] for item in listed}
    assert client.get("/api/v1/reviews", headers=HEADER_B).json() == []


def test_suite_files_stay_in_the_workspace(client):
    _create_pair(client)
    suite = {"suite_id": "suite_ws", "cases": []}
    assert client.post("/api/v1/harness/suites", json=suite, headers=HEADER_A).status_code == 201
    assert client.get("/api/v1/harness/suites/suite_ws").status_code == 404
    assert client.get("/api/v1/harness/suites/suite_ws", headers=HEADER_A).status_code == 200


def test_workspace_header_cannot_escape_the_root(client):
    escaped = client.get("/api/v1/contracts", headers={"X-WBR-Workspace": ".."})
    assert escaped.status_code == 422
    assert escaped.json()["error"]["code"] == "E9022"


def test_workspace_routes_require_api_key_when_configured(tmp_path):
    app = create_app(data_root=tmp_path, api_key="s3cret")
    with TestClient(app) as client:
        denied = client.post("/api/v1/workspaces", json={"name": "team_a"})
        assert denied.status_code == 401
        ok = client.post(
            "/api/v1/workspaces",
            json={"name": "team_a"},
            headers={"X-API-Key": "s3cret"},
        )
        assert ok.status_code == 201


def test_canvas_sends_workspace_header():
    root = Path(__file__).resolve().parents[3]
    html = (root / "wbr/app/canvas/static/index.html").read_text(encoding="utf-8")
    script = (root / "wbr/app/canvas/static/app.js").read_text(encoding="utf-8")
    assert 'id="ws-name"' in html
    assert "X-WBR-Workspace" in script
