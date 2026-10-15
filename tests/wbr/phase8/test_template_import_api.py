"""模板导入 API：列表 / 导入 / 幂等重导 / 未知模板错误体。"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from wbr.app.api.main import create_app


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(data_root=tmp_path / "data")) as c:
        yield c


def test_list_templates(client):
    teams = client.get("/api/v1/templates").json()
    names = [t["name"] for t in teams]
    assert "arch_review_team" in names
    assert "security_audit_team" in names
    arch = next(t for t in teams if t["name"] == "arch_review_team")
    assert len(arch["roles"]) == 5


def test_import_template_then_idempotent(client):
    r = client.post("/api/v1/templates/arch_review_team/import")
    assert r.status_code == 201
    body = r.json()
    assert sorted(body["imported"]) == [
        "api_design_expert", "coordinator", "data_architect", "infra_expert", "verifier",
    ]
    assert body["skipped"] == []
    # 画布可见
    boot = client.get("/canvas/api-bootstrap").json()
    assert len(boot["contracts"]) == 5
    # 重复导入幂等：全部跳过
    r2 = client.post("/api/v1/templates/arch_review_team/import")
    assert r2.json()["imported"] == []
    assert len(r2.json()["skipped"]) == 5


def test_import_unknown_team_error_body(client):
    r = client.post("/api/v1/templates/no_such_team/import")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "E9003"


def test_bootstrap_reports_demo_mode(client):
    boot = client.get("/canvas/api-bootstrap").json()
    assert boot["live"] is False
