"""可选 API Key：未配置时保持开放；配置后保护变更与敏感接口。"""
from __future__ import annotations

import asyncio
import logging

import pytest

from tests.wbr.phase4.conftest import contract_payload
from wbr.app.api.auth import (
    ApiKeyMiddleware,
    is_non_local_bind,
    is_public_path,
    normalize_path,
    resolve_api_key,
)
from wbr.app.api.main import create_app

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

_PROTECTED = (
    ("get", "/api/v1/contracts"),
    ("post", "/api/v1/contracts"),
    ("post", "/api/v1/reviews"),
    ("post", "/api/v1/harness/regressions"),
    ("get", "/api/v1/audits/export"),
    ("get", "/api/v1/templates"),
    ("post", "/api/v1/templates/arch_review_team/import"),
    ("get", "/canvas/api-bootstrap"),
)


def test_path_rules_keep_health_and_canvas_shell_open():
    assert is_public_path("/api/v1/healthz")
    assert is_public_path("/canvas")
    assert is_public_path("/canvas/static/app.js")
    assert is_public_path("/docs")
    assert not is_public_path("/api/v1/contracts")
    assert not is_public_path("/canvas/api-bootstrap")
    assert normalize_path("/canvas/static/../api-bootstrap") == "/canvas/api-bootstrap"
    assert not is_public_path("/canvas/static/../api-bootstrap")


def test_bind_host_classification():
    assert not is_non_local_bind("127.0.0.1")
    assert not is_non_local_bind("::1")
    assert not is_non_local_bind("localhost")
    assert not is_non_local_bind("testserver")
    assert is_non_local_bind("0.0.0.0")
    assert is_non_local_bind("::")
    assert is_non_local_bind("192.168.1.10")
    assert not is_non_local_bind(None)


def test_resolve_api_key_prefers_explicit_value(monkeypatch):
    monkeypatch.setenv("WBR_API_KEY", "from-env")
    assert resolve_api_key(None) == "from-env"
    assert resolve_api_key("  explicit  ") == "explicit"
    assert resolve_api_key("   ") == ""


def test_blank_key_leaves_local_api_open(tmp_path):
    app = create_app(data_root=tmp_path, api_key="   ")
    with TestClient(app) as client:
        health = client.get("/api/v1/healthz")
        assert health.status_code == 200
        assert health.json()["auth_required"] is False
        assert client.get("/api/v1/contracts").status_code == 200


def test_configured_key_protects_sensitive_routes_and_accepts_headers(tmp_path):
    app = create_app(data_root=tmp_path, api_key="s3cret")
    with TestClient(app) as client:
        health = client.get("/api/v1/healthz")
        assert health.status_code == 200
        assert health.json()["auth_required"] is True
        assert client.get("/canvas").status_code == 200
        assert client.get("/canvas/static/app.js").status_code == 200
        assert 'id="api-key"' in client.get("/canvas").text
        assert "X-API-Key" in client.get("/canvas/static/app.js").text

        for method, path in _PROTECTED:
            response = getattr(client, method)(path)
            assert response.status_code == 401, path
            assert response.json()["error"]["code"] == "E9008"

        leaked = client.get("/api/v1/contracts", params={"api_key": "s3cret"})
        assert leaked.status_code == 401

        created = client.post(
            "/api/v1/contracts",
            json=contract_payload("expert_a", "expert"),
            headers={"X-API-Key": "s3cret"},
        )
        assert created.status_code == 201, created.text
        listed = client.get("/api/v1/contracts", headers={"Authorization": "Bearer s3cret"})
        assert listed.status_code == 200
        assert listed.json()[0]["identity"]["role_id"] == "expert_a"
        wrong = client.get("/api/v1/contracts", headers={"X-API-Key": "nope"})
        assert wrong.status_code == 401

        boot = client.get("/canvas/api-bootstrap", headers={"X-API-Key": "s3cret"})
        assert boot.status_code == 200
        assert boot.json()["contracts"]

        schema = client.get("/openapi.json").json()
        assert "ApiKeyHeader" in schema["components"]["securitySchemes"]
        assert "security" not in schema["paths"]["/api/v1/healthz"]["get"]
        assert schema["paths"]["/api/v1/contracts"]["get"]["security"]


def test_env_var_enables_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("WBR_API_KEY", "from-env")
    app = create_app(data_root=tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/v1/audits/export").status_code == 401
        ok = client.get("/api/v1/audits/export", headers={"X-API-Key": "from-env"})
        assert ok.status_code == 200


def test_explicit_empty_key_overrides_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WBR_API_KEY", "from-env")
    app = create_app(data_root=tmp_path, api_key="")
    with TestClient(app) as client:
        assert client.get("/api/v1/contracts").status_code == 200


def _invoke(middleware: ApiKeyMiddleware, host: str) -> None:
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(_message):
        return None

    scope = {
        "type": "http",
        "path": "/api/v1/healthz",
        "headers": [],
        "server": (host, 8000),
    }

    async def once():
        await middleware(scope, receive, send)

    asyncio.run(once())


def test_public_bind_without_key_warns_once(caplog):
    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = ApiKeyMiddleware(downstream, api_key="")
    with caplog.at_level(logging.WARNING, logger="wbr.app.api.auth"):
        _invoke(middleware, "0.0.0.0")
        _invoke(middleware, "0.0.0.0")
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.WARNING
    ]
    assert len(messages) == 1
    assert "0.0.0.0" in messages[0]
    assert "WBR_API_KEY" in messages[0]


def test_localhost_or_configured_key_does_not_warn(caplog):
    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    with caplog.at_level(logging.WARNING, logger="wbr.app.api.auth"):
        _invoke(ApiKeyMiddleware(downstream, api_key=""), "127.0.0.1")
        _invoke(ApiKeyMiddleware(downstream, api_key="s3cret"), "0.0.0.0")
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]
