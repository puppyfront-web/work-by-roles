"""用内核 RoleContract 校验团队契约，并只接受内置模板名。"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from wbr.core.contract.models import RoleContract, RoleType
from wbr.core.exceptions import AppError
from wbr.templates.registry import list_teams, load_team


class TeamContractError(Exception):
    pass


def public_templates() -> list[dict[str, Any]]:
    published = []
    for team in list_teams():
        published.append({
            "name": team["name"],
            "version": team["version"],
            "roles": [
                {"role_id": role.get("role_id"), "role_type": role.get("role_type")}
                for role in team.get("roles", [])
            ],
        })
    return published


def contracts_from_template(name: str) -> list[dict[str, Any]]:
    known = {item["name"] for item in list_teams()}
    if name not in known:
        raise TeamContractError(f"未知模板: {name}")
    try:
        loaded = load_team(name)
    except AppError as exc:
        raise TeamContractError(exc.message) from exc
    return dump_contracts(list(loaded.values()))


def dump_contracts(contracts: list[RoleContract]) -> list[dict[str, Any]]:
    _require_shape(contracts)
    for contract in contracts:
        contract.refresh_hash()
    return [contract.model_dump(mode="json", by_alias=True) for contract in contracts]


def parse_stored_contracts(
    raw_contracts: list[dict[str, Any]],
) -> tuple[RoleContract, list[RoleContract], RoleContract]:
    parsed: list[RoleContract] = []
    for index, raw in enumerate(raw_contracts):
        try:
            parsed.append(RoleContract.model_validate(raw))
        except ValidationError as exc:
            message = exc.errors()[0]["msg"] if exc.errors() else "无法解析"
            raise TeamContractError(f"契约 #{index + 1} 不合法: {message}") from exc
    _require_shape(parsed)
    coordinator = next(item for item in parsed if item.role_type == RoleType.COORDINATOR)
    verifier = next(item for item in parsed if item.role_type == RoleType.VERIFIER)
    experts = [item for item in parsed if item.role_type == RoleType.EXPERT]
    return coordinator, experts, verifier


def normalize_contract_payload(raw_contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coordinator, experts, verifier = parse_stored_contracts(raw_contracts)
    ordered = [coordinator, *experts, verifier]
    return dump_contracts(ordered)


def _require_shape(contracts: list[RoleContract]) -> None:
    if not contracts:
        raise TeamContractError("团队至少需要一个角色契约")
    ids = [contract.role_id for contract in contracts]
    if len(ids) != len(set(ids)):
        raise TeamContractError("role_id 不能重复")
    counts = {kind: 0 for kind in RoleType}
    for contract in contracts:
        counts[contract.role_type] += 1
    if counts[RoleType.COORDINATOR] != 1 or counts[RoleType.VERIFIER] != 1:
        raise TeamContractError("团队需要恰好一个 coordinator 和一个 verifier")
    if counts[RoleType.EXPERT] < 1:
        raise TeamContractError("团队至少需要一个 expert")
