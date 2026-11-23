import json
import uuid
from datetime import timedelta

from sqlalchemy import select

from wbr.core.contract.models import RoleType
from wbr.core.orchestration.invoker import ModelRequest, ModelResponse, TokenUsage
from wbr_studio.db import get_sessionmaker
from wbr_studio.models import Run, utcnow
from wbr_studio.reaper import STUCK_REASON, reap_stuck_runs
from wbr_studio.runner import execute_run, set_invoker_builder
from wbr_studio.settings import reset_settings

USAGE = TokenUsage(prompt_tokens=10, completion_tokens=4, cached_prompt_tokens=3, cache_scope="included")


class RecordingInvoker:
    def __init__(self, experts: list[str]) -> None:
        self.experts = experts
        self.calls = 0
        self.names: list[str] = []

    def invoke(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        self.names.append(request.role_contract.identity.name)
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


def _team(client, account):
    team = client.post(
        f"/api/workspaces/{account['workspace_id']}/teams",
        headers=account["headers"],
        json={"name": "架构组", "template": "arch_review_team"},
    )
    assert team.status_code == 201, team.text
    key = client.post(
        f"/api/workspaces/{account['workspace_id']}/provider-keys",
        headers=account["headers"],
        json={
            "name": "openai",
            "base_url": "https://api.example.invalid/v1",
            "model": "gpt-test",
            "api_key": "sk-test-value",
        },
    )
    assert key.status_code == 201, key.text
    experts = [role["role_id"] for role in team.json()["roles"] if role["role_type"] == "expert"]
    return team.json(), experts


def test_cancel_queued_run_is_idempotent(client, account, monkeypatch):
    team, _experts = _team(client, account)

    async def hold(_run_id: str) -> None:
        return None

    monkeypatch.setattr("wbr_studio.api.runs.enqueue_run", hold)
    created = client.post(
        f"/api/workspaces/{account['workspace_id']}/runs",
        headers=account["headers"],
        json={"team_id": team["id"], "question": "先别跑"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "queued"
    assert created.json()["model"] == "gpt-test"
    assert created.json()["contract_version"] == 1

    cancelled = client.post(
        f"/api/workspaces/{account['workspace_id']}/runs/{created.json()['id']}/cancel",
        headers=account["headers"],
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    again = client.post(
        f"/api/workspaces/{account['workspace_id']}/runs/{created.json()['id']}/cancel",
        headers=account["headers"],
    )
    assert again.status_code == 200
    assert again.json()["status"] == "cancelled"
    execute_run(created.json()["id"])
    stored = client.get(
        f"/api/workspaces/{account['workspace_id']}/runs/{created.json()['id']}",
        headers=account["headers"],
    )
    assert stored.json()["status"] == "cancelled"
    assert stored.json()["prompt_tokens"] == 0


def test_cancel_running_run_stops_before_the_next_role(client, account):
    team, experts = _team(client, account)
    invoker = RecordingInvoker(experts)

    def builder(_base: str, _key: str, _model: str):
        original = invoker.invoke

        def invoke(request: ModelRequest) -> ModelResponse:
            if invoker.calls == 0:
                db = get_sessionmaker()()
                try:
                    run = db.scalars(select(Run).where(Run.question == "请在第一轮后停下")).one()
                    run.cancel_requested = True
                    db.commit()
                finally:
                    db.close()
            return original(request)

        invoker.invoke = invoke
        return invoker

    set_invoker_builder(builder)
    created = client.post(
        f"/api/workspaces/{account['workspace_id']}/runs",
        headers=account["headers"],
        json={"team_id": team["id"], "question": "请在第一轮后停下"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "cancelled"
    assert invoker.calls == 1


def test_cancel_completed_run_conflicts(client, account):
    team, experts = _team(client, account)
    set_invoker_builder(lambda _base, _key, _model: RecordingInvoker(experts))
    created = client.post(
        f"/api/workspaces/{account['workspace_id']}/runs",
        headers=account["headers"],
        json={"team_id": team["id"], "question": "已经结束"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "completed"
    tokens = created.json()["prompt_tokens"]
    denied = client.post(
        f"/api/workspaces/{account['workspace_id']}/runs/{created.json()['id']}/cancel",
        headers=account["headers"],
    )
    assert denied.status_code == 409
    execute_run(created.json()["id"])
    again = client.get(
        f"/api/workspaces/{account['workspace_id']}/runs/{created.json()['id']}",
        headers=account["headers"],
    )
    assert again.json()["status"] == "completed"
    assert again.json()["prompt_tokens"] == tokens


def test_worker_retries_and_reaps_on_a_schedule():
    from wbr_studio.worker import WorkerSettings

    assert WorkerSettings.max_tries == 1
    assert WorkerSettings.on_startup is not None
    assert WorkerSettings.cron_jobs


def test_reaper_fails_only_stuck_running_runs(client, account, monkeypatch):
    team, _experts = _team(client, account)
    db = get_sessionmaker()()
    try:
        stuck = Run(
            workspace_id=uuid.UUID(account["workspace_id"]),
            team_id=uuid.UUID(team["id"]),
            created_by=uuid.UUID(client.get("/api/auth/me", headers=account["headers"]).json()["id"]),
            status="running",
            question="卡住了",
            started_at=utcnow() - timedelta(hours=2),
        )
        fresh = Run(
            workspace_id=stuck.workspace_id,
            team_id=stuck.team_id,
            created_by=stuck.created_by,
            status="running",
            question="刚开始",
            started_at=utcnow(),
        )
        done = Run(
            workspace_id=stuck.workspace_id,
            team_id=stuck.team_id,
            created_by=stuck.created_by,
            status="completed",
            question="早结束了",
            started_at=utcnow() - timedelta(hours=3),
            finished_at=utcnow() - timedelta(hours=3),
        )
        db.add_all([stuck, fresh, done])
        db.commit()
        stuck_id, fresh_id, done_id = stuck.id, fresh.id, done.id
    finally:
        db.close()

    monkeypatch.setenv("STUDIO_RUN_TIMEOUT_SECONDS", "60")
    reset_settings()
    try:
        assert reap_stuck_runs() == 1
        assert reap_stuck_runs() == 0
    finally:
        monkeypatch.setenv("STUDIO_RUN_TIMEOUT_SECONDS", "900")
        reset_settings()

    db = get_sessionmaker()()
    try:
        assert db.get(Run, stuck_id).status == "failed"
        assert db.get(Run, stuck_id).error == STUCK_REASON
        assert db.get(Run, fresh_id).status == "running"
        assert db.get(Run, done_id).status == "completed"
    finally:
        db.close()


def test_run_keeps_the_contract_version_it_started_with(client, account, monkeypatch):
    team, experts = _team(client, account)

    async def hold(_run_id: str) -> None:
        return None

    monkeypatch.setattr("wbr_studio.api.runs.enqueue_run", hold)
    created = client.post(
        f"/api/workspaces/{account['workspace_id']}/runs",
        headers=account["headers"],
        json={"team_id": team["id"], "question": "用当时的契约"},
    )
    assert created.status_code == 201, created.text
    detail = client.get(
        f"/api/workspaces/{account['workspace_id']}/teams/{team['id']}",
        headers=account["headers"],
    )
    contracts = detail.json()["contracts"]
    old_name = next(item["identity"]["name"] for item in contracts if item["identity"]["role_type"] == "expert")
    for item in contracts:
        if item["identity"]["role_type"] == "expert":
            item["identity"]["name"] = "改名后的专家"
            break
    updated = client.patch(
        f"/api/workspaces/{account['workspace_id']}/teams/{team['id']}",
        headers=account["headers"],
        json={"contracts": contracts},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["current_version"] == 2

    seen = RecordingInvoker(experts)
    set_invoker_builder(lambda _base, _key, _model: seen)
    execute_run(created.json()["id"])
    finished = client.get(
        f"/api/workspaces/{account['workspace_id']}/runs/{created.json()['id']}",
        headers=account["headers"],
    )
    assert finished.json()["status"] == "completed"
    assert finished.json()["contract_version"] == 1
    assert old_name in seen.names
    assert "改名后的专家" not in seen.names
