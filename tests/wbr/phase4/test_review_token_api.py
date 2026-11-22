"""会审 API 透传 Phase 0 的共享上下文、跳过策略和 Token 预算。"""
from __future__ import annotations

from pathlib import Path

REVIEW_BODY = {
    "question": "如何设计登录认证？",
    "coordinator": "coordinator",
    "experts": ["expert_a"],
    "verifier": "verifier",
}


def _done(client, task_id):
    result = client.get(f"/api/v1/reviews/{task_id}").json()
    assert result["status"] == "done", result
    return result["result"]


def test_review_result_includes_token_meter(seeded):
    submitted = seeded.post("/api/v1/reviews", json=REVIEW_BODY)
    assert submitted.status_code == 202, submitted.text
    result = _done(seeded, submitted.json()["task_id"])
    meter = result["token_meter"]
    assert meter["total_tokens"] == meter["prompt_tokens"] + meter["completion_tokens"]
    assert meter["cached_prompt_tokens"] >= 0
    assert isinstance(meter["by_role"], dict)


def test_shared_context_and_skip_flag_are_accepted(seeded):
    body = {
        **REVIEW_BODY,
        "shared_context": "结论必须能回溯到给定材料。",
        "skip_unassigned_experts": False,
    }
    submitted = seeded.post("/api/v1/reviews", json=body)
    assert submitted.status_code == 202, submitted.text
    result = _done(seeded, submitted.json()["task_id"])
    assert result["status"] == "completed"
    assert "token_meter" in result


def test_tiny_budget_stops_the_review_without_raising(seeded):
    body = {**REVIEW_BODY, "token_budget": {"max_total_tokens": 1, "on_exceed": "reject"}}
    submitted = seeded.post("/api/v1/reviews", json=body)
    assert submitted.status_code == 202, submitted.text
    result = _done(seeded, submitted.json()["task_id"])
    assert result["status"] == "failed"
    assert "预算" in result["error"]
    assert result["token_meter"]["total_tokens"] == 0


def test_invalid_role_budget_is_rejected(seeded):
    body = {**REVIEW_BODY, "token_budget": {"max_total_tokens": 100, "per_role": {"expert_a": 0}}}
    response = seeded.post("/api/v1/reviews", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "E9022"


def test_canvas_exposes_budget_fields():
    root = Path(__file__).resolve().parents[3]
    html = (root / "wbr/app/canvas/static/index.html").read_text(encoding="utf-8")
    script = (root / "wbr/app/canvas/static/app.js").read_text(encoding="utf-8")
    assert 'id="f-token-budget"' in html
    assert 'id="f-shared"' in html
    assert 'id="token-meter"' in html
    assert "token_budget" in script
    assert "token_meter" in script
    assert 'result.status === "failed"' in script
