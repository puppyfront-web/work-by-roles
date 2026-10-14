"""任务基线快照：锁定契约 + 用例库 + 模型版本（SPEC-004 §1.2）。"""
from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover
    from wbr.core.contract.models import RoleContract
    from wbr.core.harness.cases import CaseSuite


class ConsistencyReport(BaseModel):
    ok: bool
    contract_mismatches: list[str] = Field(default_factory=list)
    missing_roles: list[str] = Field(default_factory=list)
    suite_matches: bool = True


class BaselineSnapshot(BaseModel):
    baseline_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = Field(default_factory=time.time)
    contract_hashes: dict[str, str] = Field(default_factory=dict)  # role_id -> sha
    suite_hash: str = ""
    model_fingerprint: str = "unknown"
    note: str = ""

    @classmethod
    def capture(
        cls,
        *,
        contracts: dict[str, RoleContract],
        suite: CaseSuite,
        model_fingerprint: str = "unknown",
        note: str = "",
    ) -> BaselineSnapshot:
        return cls(
            contract_hashes={rid: c.content_hash for rid, c in sorted(contracts.items())},
            suite_hash=suite.content_hash(),
            model_fingerprint=model_fingerprint,
            note=note,
        )

    def is_current(
        self, contracts: dict[str, RoleContract], suite: CaseSuite
    ) -> ConsistencyReport:
        """与当前契约集/用例库比对，报告不一致项（能力退化检测的前置）。"""
        mismatches: list[str] = []
        missing: list[str] = []
        for rid, locked_hash in self.contract_hashes.items():
            contract = contracts.get(rid)
            if contract is None:
                missing.append(rid)
            elif contract.content_hash != locked_hash:
                mismatches.append(f"{rid}: {locked_hash[:8]} -> {contract.content_hash[:8]}")
        return ConsistencyReport(
            ok=not (mismatches or missing) and self.suite_hash == suite.content_hash(),
            contract_mismatches=mismatches,
            missing_roles=missing,
            suite_matches=self.suite_hash == suite.content_hash(),
        )

    def save(self, path: str) -> None:
        from pathlib import Path

        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> BaselineSnapshot:
        from pathlib import Path

        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
