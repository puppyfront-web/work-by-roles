"""官方团队模板注册表（SPEC-006 §1.3）：list_teams / load_team。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from wbr.core.contract.models import RoleContract
from wbr.core.exceptions import AppError

TEAMS_DIR = Path(__file__).resolve().parent / "teams"


def templates_root() -> Path:
    return TEAMS_DIR


def list_teams() -> list[dict[str, Any]]:
    """列出全部官方团队模板（含角色摘要）。"""
    out = []
    if not TEAMS_DIR.is_dir():  # pragma: no cover - 打包异常保护
        return out
    for team_dir in sorted(TEAMS_DIR.iterdir()):
        meta = team_dir / "team.json"
        if not meta.is_file():
            continue
        data = yaml.safe_load(meta.read_text(encoding="utf-8"))
        out.append({
            "name": data.get("team", team_dir.name),
            "version": data.get("version", "1.0.0"),
            "roles": data.get("roles", []),
            "path": str(team_dir),
        })
    return out


@lru_cache(maxsize=8)
def _load_cached(team_dir: str, mtime: float) -> dict[str, RoleContract]:
    del mtime  # 仅作缓存键
    return _load_uncached(Path(team_dir))


def _load_uncached(team_dir: Path) -> dict[str, RoleContract]:
    meta = team_dir / "team.json"
    if not meta.is_file():
        raise AppError(f"团队模板不存在: {team_dir.name}", code="E9003")
    data = yaml.safe_load(meta.read_text(encoding="utf-8"))
    contracts: dict[str, RoleContract] = {}
    for role_meta in data.get("roles", []):
        yml = team_dir / role_meta["file"]
        raw = yaml.safe_load(yml.read_text(encoding="utf-8"))
        contract = RoleContract.model_validate(raw)
        contract.meta.content_hash = RoleContract.compute_hash(contract)  # 加载时定版
        contracts[contract.role_id] = contract
    if not contracts:
        raise AppError(f"团队模板为空: {team_dir.name}", code="E9003")
    return contracts


def load_team(name: str) -> dict[str, RoleContract]:
    """加载官方团队模板：role_id → 已定版 RoleContract。"""
    team_dir = TEAMS_DIR / name
    if not (team_dir / "team.json").is_file():
        raise AppError(
            f"团队模板不存在: {name}（可用: {[t['name'] for t in list_teams()]}）",
            code="E9003",
        )
    return dict(_load_cached(str(team_dir), (team_dir / "team.json").stat().st_mtime))


class TeamSpec:
    """团队模板规格：契约集 + 元信息。"""

    def __init__(self, name: str, contracts: dict[str, RoleContract]) -> None:
        self.name = name
        self.contracts = contracts

    @property
    def coordinator(self) -> RoleContract:
        return self._find_role_type("coordinator")

    @property
    def verifier(self) -> RoleContract:
        return self._find_role_type("verifier")

    @property
    def experts(self) -> list[RoleContract]:
        from wbr.core.contract.models import RoleType

        return sorted(
            (c for c in self.contracts.values() if c.role_type == RoleType.EXPERT),
            key=lambda c: c.role_id,
        )

    def _find_role_type(self, type_value: str) -> RoleContract:
        from wbr.core.contract.models import RoleType

        for c in self.contracts.values():
            if c.role_type == RoleType(type_value):
                return c
        raise AppError(f"模板 {self.name} 缺少 {type_value} 角色", code="E9003")


def load_team_spec(name: str) -> TeamSpec:
    return TeamSpec(name, load_team(name))
