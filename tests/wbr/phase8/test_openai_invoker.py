"""OpenAICompatInvoker：环境变量解析 / 消息映射 / 重试 / 错误路径 / create_app 自动接线。"""
from __future__ import annotations

import json

import httpx
import pytest

from tests.wbr.factories import expert_contract
from wbr.adapters.llm import OpenAICompatInvoker
from wbr.core.contract.compiler import CompiledPrompt
from wbr.core.exceptions import AdapterError
from wbr.core.orchestration.invoker import ModelRequest


def make_request(role_id: str = "expert_a") -> ModelRequest:
    return ModelRequest(
        role_contract=expert_contract(role_id),
        compiled_prompt=CompiledPrompt(system_prompt="SYS-PROMPT", user_block="USER-BLOCK"),
        trace_id="t-1",
    )


def mock_client(handler, invoker: OpenAICompatInvoker) -> None:
    invoker._client = httpx.Client(
        base_url="https://mock.local",
        transport=httpx.MockTransport(handler),
        headers=invoker._default_headers(),
    )


def completion(content: str, prompt_tokens: int = 100, completion_tokens: int = 50) -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }


# ---- 环境变量 ----
def test_from_env_missing_returns_none(monkeypatch):
    monkeypatch.delenv("WBR_LLM_API_KEY", raising=False)
    monkeypatch.delenv("WBR_LLM_MODEL", raising=False)
    assert OpenAICompatInvoker.from_env() is None


def test_from_env_present(monkeypatch):
    monkeypatch.setenv("WBR_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("WBR_LLM_MODEL", "deepseek-chat")
    inv = OpenAICompatInvoker.from_env()
    assert inv is not None
    assert inv.model == "deepseek-chat"
    assert inv.base_url == "https://api.openai.com/v1"


def test_missing_api_key_raises():
    with pytest.raises(AdapterError, match="WBR_LLM_API_KEY"):
        OpenAICompatInvoker(api_key="", model="m")


def test_missing_model_raises():
    with pytest.raises(AdapterError, match="WBR_LLM_MODEL"):
        OpenAICompatInvoker(api_key="sk", model="")


# ---- 调用与消息映射 ----
def test_invoke_maps_contract_prompt_to_messages():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx_response(completion("结论文本"))

    inv = OpenAICompatInvoker(api_key="sk", model="glm-4-flash")
    mock_client(handler, inv)
    resp = inv.invoke(make_request())
    assert seen["model"] == "glm-4-flash"
    assert seen["messages"][0] == {"role": "system", "content": "SYS-PROMPT"}
    assert seen["messages"][1] == {"role": "user", "content": "USER-BLOCK"}
    assert resp.text == "结论文本"
    assert resp.usage.prompt_tokens == 100
    assert resp.usage.total == 150


def test_model_by_role_override():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx_response(completion("ok"))

    inv = OpenAICompatInvoker(
        api_key="sk", model="cheap-model", model_by_role={"expert_a": "strong-model"}
    )
    mock_client(handler, inv)
    inv.invoke(make_request("expert_a"))
    assert seen["model"] == "strong-model"


def test_authorization_header_sent():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("Authorization")
        return httpx_response(completion("ok"))

    inv = OpenAICompatInvoker(api_key="sk-secret", model="m")
    mock_client(handler, inv)
    inv.invoke(make_request())
    assert captured["auth"] == "Bearer sk-secret"


# ---- 重试与错误 ----
def test_retry_on_500_then_success():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(500, text="boom")
        return httpx_response(completion("recovered"))

    inv = OpenAICompatInvoker(api_key="sk", model="m", max_retries=2)
    mock_client(handler, inv)
    resp = inv.invoke(make_request())
    assert resp.text == "recovered"
    assert attempts["n"] == 2


def test_persistent_500_raises_adapter_error():
    def handler(request):
        return httpx.Response(500, text="server down")

    inv = OpenAICompatInvoker(api_key="sk", model="m", max_retries=1)
    mock_client(handler, inv)
    with pytest.raises(AdapterError, match="HTTP 500"):
        inv.invoke(make_request())


def test_401_not_retried():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        return httpx.Response(401, text="unauthorized")

    inv = OpenAICompatInvoker(api_key="sk", model="m", max_retries=3)
    mock_client(handler, inv)
    with pytest.raises(AdapterError, match="HTTP 401"):
        inv.invoke(make_request())
    assert attempts["n"] == 1


def test_malformed_response_raises():
    def handler(request):
        return httpx_response({"unexpected": True})

    inv = OpenAICompatInvoker(api_key="sk", model="m")
    mock_client(handler, inv)
    with pytest.raises(AdapterError, match="响应结构异常"):
        inv.invoke(make_request())


# ---- create_app 自动接线 ----
def test_create_app_picks_live_invoker_from_env(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("WBR_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("WBR_LLM_MODEL", "test-model")
    from fastapi.testclient import TestClient

    from wbr.app.api.main import create_app

    app = create_app(data_root=tmp_path / "data")
    client = TestClient(app)
    data = client.get("/api/v1/healthz").json()
    assert data["components"]["invoker"] == "OpenAICompatInvoker"


def test_create_app_falls_back_to_demo(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from wbr.app.api.main import _DemoInvoker, create_app

    app = create_app(data_root=tmp_path / "data")
    client = TestClient(app)
    data = client.get("/api/v1/healthz").json()
    assert data["components"]["invoker"] == type(_DemoInvoker()).__name__


def httpx_response(payload):
    import httpx

    return httpx.Response(200, json=payload)
