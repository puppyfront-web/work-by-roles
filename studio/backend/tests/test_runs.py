import json

import pytest

from wbr.core.contract.models import RoleType
from wbr.core.orchestration.invoker import ModelRequest, ModelResponse, TokenUsage
from wbr_studio.runner import set_invoker_builder

SECRET = "sk-live-DO-NOT-LEAK-8f3a2c91"

USAGE = TokenUsage(
    prompt_tokens=200,
    completion_tokens=40,
    cached_prompt_tokens=150,
    cache_scope="included",
)


class RecordingInvoker:
    def __init__(self, experts: list[str]) -> None:
        self.experts = experts
        self.calls: list[str] = []

    def invoke(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request.role_contract.role_id)
        role = request.role_contract
        if role.role_type == RoleType.COORDINATOR:
            body = {
                "assignments": [
                    {"expert_role_id": expert_id, "sub_question": "请给出可复核的结论"}
                    for expert_id in self.experts
                ],
                "strategy": "parallel",
            }
        elif role.role_type == RoleType.VERIFIER:
            names = [item.name for item in role.review_criteria.dimensions] if role.review_criteria else []
            body = {
                "passed": True,
                "scores": {name: 0.85 for name in names} or {"quality": 0.85},
                "comments": "复核通过，证据与结论一致",
                "final_answer": "按专家结论推进，并保留审计。",
            }
        else:
            body = {
                "conclusion": "建议保持契约前缀稳定以命中提示缓存。",
                "confidence": 0.82,
                "citations": ["[^1]"],
                "risks": ["缓存键漂移"],
            }
        return ModelResponse(text=json.dumps(body, ensure_ascii=False), usage=USAGE)


def _team_and_key(client, account):
    headers = account["headers"]
    workspace_id = account["workspace_id"]
    team = client.post(
        f"/api/workspaces/{workspace_id}/teams",
        headers=headers,
        json={"name": "架构组", "template": "arch_review_team"},
    )
    assert team.status_code == 201, team.text
    key = client.post(
        f"/api/workspaces/{workspace_id}/provider-keys",
        headers=headers,
        json={
            "name": "openai",
            "base_url": "https://api.example.invalid/v1",
            "model": "gpt-test",
            "api_key": SECRET,
        },
    )
    assert key.status_code == 201, key.text
    experts = [role["role_id"] for role in team.json()["roles"] if role["role_type"] == "expert"]
    return team.json()["id"], experts


def test_run_uses_fake_invoker_and_records_cached_tokens(client, account):
    team_id, experts = _team_and_key(client, account)
    seen: dict[str, str] = {}
    invoker = RecordingInvoker(experts)

    def builder(base_url: str, api_key: str, model: str):
        seen["base_url"] = base_url
        seen["api_key"] = api_key
        seen["model"] = model
        return invoker

    set_invoker_builder(builder)
    created = client.post(
        f"/api/workspaces/{account['workspace_id']}/runs",
        headers=account["headers"],
        json={
            "team_id": team_id,
            "question": "订单服务要不要拆成三个部署单元？",
            "token_budget": 100000,
            "input_price": 0.000002,
            "output_price": 0.000008,
            "cached_input_price": 0.0000005,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert SECRET not in created.text
    assert seen["api_key"] == SECRET
    assert seen["model"] == "gpt-test"
    assert seen["base_url"] == "https://api.example.invalid/v1"
    assert body["status"] == "completed"
    assert body["prompt_tokens"] == 200 * len(invoker.calls)
    assert body["completion_tokens"] == 40 * len(invoker.calls)
    assert body["cached_prompt_tokens"] == 150 * len(invoker.calls)
    assert len(invoker.calls) == 1 + len(experts) + 1
    one = USAGE.estimate_cost(
        input_price=0.000002, output_price=0.000008, cached_input_price=0.0000005
    )
    assert one["savings"] > 0
    assert body["cost_total"] == pytest.approx(one["total"] * len(invoker.calls))
    assert body["cost_savings"] == pytest.approx(one["savings"] * len(invoker.calls))
    verdict = body["result"]["verifier_verdict"]
    assert verdict["passed"] is True
    completed = [
        item for item in body["result"]["expert_outcomes"] if item["status"] == "completed"
    ]
    assert len(completed) == len(experts)
    assert completed[0]["output"]["conclusion"]

    audit = client.get(
        f"/api/workspaces/{account['workspace_id']}/runs/{body['id']}/audit",
        headers=account["headers"],
    )
    assert audit.status_code == 200, audit.text
    assert SECRET not in audit.text
    payload = audit.json()
    assert payload["chain"]["ok"] is True
    assert payload["chain"]["checked"] == len(payload["events"])
    kinds = {event["event_type"] for event in payload["events"]}
    assert {"session_started", "verifier_verdict", "token_record", "review_completed"} <= kinds
    assert all(event["run_id"] == body["id"] for event in payload["events"])

    chain = client.get(
        f"/api/workspaces/{account['workspace_id']}/audit/verify",
        headers=account["headers"],
    )
    assert chain.json()["ok"] is True


def test_run_requires_a_provider_key(client, account):
    team = client.post(
        f"/api/workspaces/{account['workspace_id']}/teams",
        headers=account["headers"],
        json={"name": "架构组", "template": "arch_review_team"},
    )
    response = client.post(
        f"/api/workspaces/{account['workspace_id']}/runs",
        headers=account["headers"],
        json={"team_id": team.json()["id"], "question": "还有密钥吗？"},
    )
    assert response.status_code == 400


def test_team_with_runs_cannot_be_deleted(client, account):
    team_id, _experts = _team_and_key(client, account)
    set_invoker_builder(lambda _base, _key, _model: RecordingInvoker(["api_design_expert", "data_architect", "infra_expert"]))
    created = client.post(
        f"/api/workspaces/{account['workspace_id']}/runs",
        headers=account["headers"],
        json={"team_id": team_id, "question": "保留这支团队"},
    )
    assert created.status_code == 201, created.text
    removed = client.delete(
        f"/api/workspaces/{account['workspace_id']}/teams/{team_id}",
        headers=account["headers"],
    )
    assert removed.status_code == 409
