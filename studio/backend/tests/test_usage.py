import json

import pytest

from wbr.core.contract.models import RoleType
from wbr.core.orchestration.invoker import ModelRequest, ModelResponse, TokenUsage
from wbr_studio.runner import set_invoker_builder

USAGE = TokenUsage(prompt_tokens=200, completion_tokens=40, cached_prompt_tokens=150, cache_scope="included")


class RecordingInvoker:
    def __init__(self, experts: list[str]) -> None:
        self.experts = experts
        self.calls = 0

    def invoke(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
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
                "comments": "复核通过",
                "final_answer": "结论保留。",
            }
        else:
            body = {"conclusion": "保持前缀稳定。", "confidence": 0.8, "citations": [], "risks": []}
        return ModelResponse(text=json.dumps(body, ensure_ascii=False), usage=USAGE)


def test_usage_groups_tokens_cost_and_cache_hit_rate(client, account):
    team = client.post(
        f"/api/workspaces/{account['workspace_id']}/teams",
        headers=account["headers"],
        json={"name": "架构组", "template": "arch_review_team"},
    )
    assert team.status_code == 201, team.text
    experts = [role["role_id"] for role in team.json()["roles"] if role["role_type"] == "expert"]
    client.post(
        f"/api/workspaces/{account['workspace_id']}/provider-keys",
        headers=account["headers"],
        json={
            "name": "openai",
            "base_url": "https://api.example.invalid/v1",
            "model": "gpt-test",
            "api_key": "sk-test-value",
        },
    )
    invoker = RecordingInvoker(experts)
    set_invoker_builder(lambda _base, _key, _model: invoker)
    created = client.post(
        f"/api/workspaces/{account['workspace_id']}/runs",
        headers=account["headers"],
        json={
            "team_id": team.json()["id"],
            "question": "统计这一轮",
            "input_price": 0.000002,
            "output_price": 0.000008,
            "cached_input_price": 0.0000005,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    report = client.get(
        f"/api/workspaces/{account['workspace_id']}/usage?days=7",
        headers=account["headers"],
    )
    assert report.status_code == 200, report.text
    payload = report.json()
    assert payload["totals"]["prompt_tokens"] == body["prompt_tokens"]
    assert payload["totals"]["completion_tokens"] == body["completion_tokens"]
    assert payload["totals"]["cached_prompt_tokens"] == body["cached_prompt_tokens"]
    assert payload["totals"]["cache_hit_rate"] == 0.75
    assert payload["totals"]["cost_total"] == body["cost_total"]
    assert payload["totals"]["runs"] == 1
    assert payload["totals"]["saved_tokens"] == body["savings"]["saved_tokens"] == 0
    assert payload["totals"]["saved_cost"] == pytest.approx(body["savings"]["saved_cost"])
    assert payload["by_day"][0]["saved_tokens"] == 0
    assert "saved_tokens" not in payload["by_model"][0]
    assert "saved_cost" not in payload["by_role"][0]
    assert payload["by_model"][0]["model"] == "gpt-test"
    assert payload["by_model"][0]["cache_hit_rate"] == 0.75
    assert payload["by_day"][0]["prompt_tokens"] == body["prompt_tokens"]
    role_ids = {item["role_id"] for item in payload["by_role"]}
    assert set(experts) <= role_ids
    assert sum(item["prompt_tokens"] for item in payload["by_role"]) == body["prompt_tokens"]
    assert "runs" not in payload["by_role"][0]


def test_usage_is_empty_without_runs(client, account):
    report = client.get(f"/api/workspaces/{account['workspace_id']}/usage", headers=account["headers"])
    assert report.status_code == 200
    assert report.json()["totals"]["runs"] == 0
    assert report.json()["totals"]["saved_tokens"] == 0
    assert report.json()["totals"]["saved_cost"] == 0
    assert report.json()["by_day"] == []


def test_usage_sums_receipt_savings_across_runs(client, account):
    team = client.post(
        f"/api/workspaces/{account['workspace_id']}/teams",
        headers=account["headers"],
        json={"name": "架构组", "template": "arch_review_team"},
    )
    experts = [role["role_id"] for role in team.json()["roles"] if role["role_type"] == "expert"]
    client.post(
        f"/api/workspaces/{account['workspace_id']}/provider-keys",
        headers=account["headers"],
        json={
            "name": "openai",
            "base_url": "https://api.example.invalid/v1",
            "model": "gpt-test",
            "api_key": "sk-test-value",
        },
    )
    prices = {
        "input_price": 0.000002,
        "output_price": 0.000008,
        "cached_input_price": 0.0000005,
    }
    saved_tokens = 0
    saved_cost = 0.0
    for assigned in (experts, experts[:1]):
        set_invoker_builder(lambda _base, _key, _model, names=assigned: RecordingInvoker(names))
        created = client.post(
            f"/api/workspaces/{account['workspace_id']}/runs",
            headers=account["headers"],
            json={"team_id": team.json()["id"], "question": " ".join(assigned), **prices},
        )
        assert created.status_code == 201, created.text
        receipt = created.json()["savings"]
        saved_tokens += receipt["saved_tokens"]
        saved_cost += receipt["saved_cost"]
    report = client.get(
        f"/api/workspaces/{account['workspace_id']}/usage?days=7",
        headers=account["headers"],
    )
    totals = report.json()["totals"]
    assert totals["runs"] == 2
    assert totals["saved_tokens"] == saved_tokens
    assert totals["saved_tokens"] > 0
    assert totals["saved_cost"] == pytest.approx(saved_cost)
    assert report.json()["by_day"][0]["saved_tokens"] == saved_tokens
