"""TC-4-API-C-1/2 + TC-4-STORE-1：契约 CRUD / 版本 / Diff API 与错误规范。"""
from __future__ import annotations

import copy

import pytest

from tests.wbr.factories import expert_contract
from wbr.app.store import ContractRegistry


# ---- 单元层：注册表 ----
def test_registry_crud_and_versions(tmp_path):
    reg = ContractRegistry(tmp_path)
    c1 = expert_contract("expert_a")
    reg.create(c1)
    with pytest.raises(Exception, match="已存在"):
        reg.create(expert_contract("expert_a"))
    c2 = c1.with_changes(**{"identity.description": "v2"}, bump="minor", changelog="升级")
    updated, diff = reg.update("expert_a", c2)
    assert updated.meta.version == "1.1.0"
    assert diff is not None and diff.from_version == "1.0.0"
    assert [v["version"] for v in reg.versions("expert_a")] == ["1.0.0", "1.1.0"]
    assert reg.get_version("expert_a", "1.0.0").meta.version == "1.0.0"
    assert reg.get("expert_a").meta.version == "1.1.0"
    d = reg.diff_versions("expert_a", "1.0.0", "1.1.0")
    assert d.has_breaking is False
    assert reg.delete("expert_a") is True
    assert reg.get("expert_a") is None
    assert reg.delete("expert_a") is False


def test_registry_persistence_across_instances(tmp_path):
    reg = ContractRegistry(tmp_path)
    reg.create(expert_contract("expert_a"))
    reg2 = ContractRegistry(tmp_path)
    assert reg2.get("expert_a") is not None  # 落盘恢复


# ---- API 层 ----
def test_contract_crud_api(seeded):
    r = seeded.get("/api/v1/contracts")
    assert r.status_code == 200
    ids = {c["identity"]["role_id"] for c in r.json()}
    assert {"coordinator", "expert_a", "verifier"} <= ids

    r = seeded.get("/api/v1/contracts/expert_a")
    assert r.status_code == 200
    assert r.json()["meta"]["content_hash"]

    # PUT 新版本（改动业务字段）
    payload = r.json()
    new_contract = copy.deepcopy(payload)
    new_contract["identity"]["description"] = "API 更新描述"
    new_contract["meta"]["version"] = "1.1.0"
    r = seeded.put("/api/v1/contracts/expert_a", json={"contract": new_contract})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["contract"]["meta"]["version"] == "1.1.0"
    assert body["diff"] is not None

    # 版本与 Diff API
    assert {v["version"] for v in seeded.get("/api/v1/contracts/expert_a/versions").json()} == {"1.0.0", "1.1.0"}
    d = seeded.get("/api/v1/contracts/expert_a/diff?from=1.0.0&to=1.1.0")
    assert d.status_code == 200 and d.json()["from_version"] == "1.0.0"
    v1 = seeded.get("/api/v1/contracts/expert_a/versions/1.0.0")
    assert v1.json()["meta"]["version"] == "1.0.0"

    # DELETE
    r = seeded.delete("/api/v1/contracts/expert_a")
    assert r.status_code == 204
    assert seeded.get("/api/v1/contracts/expert_a").status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "expect"),
    [
        ("get", "/api/v1/contracts/ghost", 404),
        ("get", "/api/v1/contracts/ghost/versions", 404),
        ("get", "/api/v1/contracts/expert_a/versions/9.9.9", 404),
        ("get", "/api/v1/contracts/expert_a/diff?from=1.0.0&to=9.9.9", 404),
        ("delete", "/api/v1/contracts/ghost", 404),
        ("get", "/api/v1/reviews/nonexistent", 404),
        ("get", "/api/v1/harness/regressions/nonexistent", 404),
        ("get", "/api/v1/harness/suites/nope", 404),
    ],
)
def test_unified_error_envelope(seeded, method, path, expect):
    r = getattr(seeded, method)(path)
    assert r.status_code == expect
    body = r.json()
    assert "error" in body and "code" in body["error"] and "message" in body["error"]


def test_409_and_422_errors(seeded):
    # 409 重复创建
    from tests.wbr.phase4.conftest import contract_payload

    r = seeded.post("/api/v1/contracts", json=contract_payload("expert_a", "expert"))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "E9002"
    # 422 非法契约结构（缺 identity）
    r = seeded.post("/api/v1/contracts", json={"contract": {"sop": {"steps": []}}})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "E9022"
    # 422 请求体缺失字段
    r = seeded.post("/api/v1/reviews", json={"question": "q"})
    assert r.status_code == 422


def test_healthz(client):
    r = client.get("/api/v1/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["components"]["registry"] is True
