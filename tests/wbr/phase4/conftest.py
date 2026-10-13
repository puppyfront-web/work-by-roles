"""阶段4 测试夹具：ASGI 客户端 + 临时数据目录。"""
from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from tests.wbr.factories import (  # noqa: E402
    coordinator_contract,
    expert_contract,
    verifier_contract,
)
from wbr.app.api.main import create_app  # noqa: E402


def contract_payload(cid="expert_a", role_type="expert"):
    c = {"expert": expert_contract, "coordinator": coordinator_contract, "verifier": verifier_contract}[role_type](cid)
    return {"contract": __import__("json").loads(c.to_json())}


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient

    app = create_app(data_root=tmp_path / "data")
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def seeded(client):
    """预置三角色契约。"""
    for cid, rt in [("coordinator", "coordinator"), ("expert_a", "expert"), ("verifier", "verifier")]:
        r = client.post("/api/v1/contracts", json=contract_payload(cid, rt))
        assert r.status_code == 201, r.text
    return client
