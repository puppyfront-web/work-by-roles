"""把表行收成响应。这里不读 ciphertext，也不解密。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from wbr_studio.models import ProviderKey, Run, Team, User, Workspace


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def user_out(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "email_verified": user.email_verified,
        "created_at": iso(user.created_at),
    }


def workspace_out(workspace: Workspace, role: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": str(workspace.id),
        "name": workspace.name,
        "created_at": iso(workspace.created_at),
    }
    if role is not None:
        body["role"] = role
    return body


def member_out(member, email: str) -> dict[str, Any]:
    return {
        "user_id": str(member.user_id),
        "email": email,
        "role": member.role,
        "created_at": iso(member.created_at),
    }


def invite_out(invite, token: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": str(invite.id),
        "email": invite.email,
        "role": invite.role,
        "expires_at": iso(invite.expires_at),
        "accepted_at": iso(invite.accepted_at),
        "revoked_at": iso(invite.revoked_at),
        "created_at": iso(invite.created_at),
    }
    if token is not None:
        body["token"] = token
        body["invite_path"] = f"/invite/{token}"
    return body


def key_out(row: ProviderKey) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "name": row.name,
        "base_url": row.base_url,
        "model": row.model,
        "key_hint": row.key_hint,
        "created_at": iso(row.created_at),
    }


def role_summaries(contracts: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    summaries = []
    for raw in contracts:
        identity = raw.get("identity") if isinstance(raw.get("identity"), dict) else {}
        summaries.append({
            "role_id": identity.get("role_id"),
            "name": identity.get("name"),
            "role_type": identity.get("role_type"),
        })
    return summaries


def team_out(team: Team, *, with_contracts: bool) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": str(team.id),
        "name": team.name,
        "template_name": team.template_name,
        "roles": role_summaries(team.contracts),
        "current_version": team.current_version,
        "created_at": iso(team.created_at),
        "updated_at": iso(team.updated_at),
    }
    if with_contracts:
        body["contracts"] = team.contracts
    return body


def run_out(run: Run) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "workspace_id": str(run.workspace_id),
        "team_id": str(run.team_id),
        "provider_key_id": str(run.provider_key_id) if run.provider_key_id else None,
        "status": run.status,
        "cancel_requested": run.cancel_requested,
        "model": run.model,
        "contract_version": run.contract_version,
        "question": run.question,
        "token_budget": run.token_budget,
        "trace_id": run.trace_id,
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "cached_prompt_tokens": run.cached_prompt_tokens,
        "input_price": run.input_price,
        "output_price": run.output_price,
        "cached_input_price": run.cached_input_price,
        "cost_total": run.cost_total,
        "cost_baseline": run.cost_baseline,
        "cost_savings": run.cost_savings,
        "savings": run.savings_receipt,
        "error": run.error,
        "result": run.result_json,
        "created_at": iso(run.created_at),
        "started_at": iso(run.started_at),
        "finished_at": iso(run.finished_at),
    }
