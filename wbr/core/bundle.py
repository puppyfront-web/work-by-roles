"""基线 Bundle 版本打包（V2.0 E4 / SPEC-008 §4）：契约+用例+基线三位一体快照。

完整性算法与 D-09 一致：canonical JSON + sha256；manifest 逐文件 digest + 总 digest。
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from wbr.core.canonical import canonical_json, sha256_hex
from wbr.core.contract.models import RoleContract
from wbr.core.exceptions import HarnessError
from wbr.core.harness.baseline import BaselineSnapshot
from wbr.core.harness.cases import CaseSuite

FORMAT_VERSION = "2.0"


class _ManifestEntry(BaseModel):
    file: str
    digest: str


class BundleVerification(BaseModel):
    ok: bool
    broken_file: str | None = None
    checked: int = 0


class BaselineBundle(BaseModel):
    """可迁移的基线快照包：契约集 + 黄金用例库 + 基线，附完整性 manifest。"""

    format_version: str = FORMAT_VERSION
    bundle_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = Field(default_factory=time.time)
    note: str = ""
    contracts: list[dict[str, Any]] = Field(default_factory=list)   # 契约 JSON（by_alias）
    suite: dict[str, Any] = Field(default_factory=dict)
    baseline: dict[str, Any] = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)

    # ---- 打包 ----
    @classmethod
    def pack(
        cls,
        *,
        contracts: dict[str, RoleContract],
        suite: CaseSuite,
        baseline: BaselineSnapshot,
        note: str = "",
    ) -> "BaselineBundle":
        if not contracts:
            raise HarnessError("Bundle 至少包含一个契约", code="E7001")
        contract_payloads = [
            json_loads(contract.to_json()) for _, contract in sorted(contracts.items())
        ]
        files = {
            "contracts": contract_payloads,
            "suite": suite.model_dump(mode="json"),
            "baseline": baseline.model_dump(mode="json"),
        }
        digests = {name: sha256_hex(canonical_json(payload)) for name, payload in files.items()}
        manifest = {
            "files": [{"file": name, "digest": digest} for name, digest in sorted(digests.items())],
            "bundle_digest": sha256_hex(canonical_json(digests)),
        }
        return cls(
            note=note,
            contracts=contract_payloads,
            suite=files["suite"],
            baseline=files["baseline"],
            manifest=manifest,
        )

    # ---- 校验 ----
    def verify(self) -> BundleVerification:
        files = {
            "contracts": self.contracts,
            "suite": self.suite,
            "baseline": self.baseline,
        }
        expected = {e["file"]: e["digest"] for e in self.manifest.get("files", [])}
        checked = 0
        for name, payload in files.items():
            digest = sha256_hex(canonical_json(payload))
            checked += 1
            if name not in expected or expected[name] != digest:
                return BundleVerification(ok=False, broken_file=name, checked=checked)
        bundle_digest = sha256_hex(canonical_json(
            {name: sha256_hex(canonical_json(payload)) for name, payload in files.items()}
        ))
        checked += 1
        if self.manifest.get("bundle_digest") != bundle_digest:
            return BundleVerification(ok=False, broken_file="manifest", checked=checked)
        return BundleVerification(ok=True, checked=checked)

    # ---- 还原 ----
    def to_registry(self, registry) -> list[RoleContract]:
        """把包内契约落回注册表（按包内版本原样定版）。"""
        restored = []
        for payload in self.contracts:
            contract = RoleContract.model_validate(payload)
            contract.meta.content_hash = RoleContract.compute_hash(contract)
            restored.append(registry.create(contract))
        return restored

    def get_suite(self) -> CaseSuite:
        return CaseSuite.model_validate(self.suite)

    def get_baseline(self) -> BaselineSnapshot:
        return BaselineSnapshot.model_validate(self.baseline)

    # ---- 序列化 ----
    def to_json(self) -> str:
        import json

        return json.dumps(self.model_dump(), ensure_ascii=False, indent=2)

    def save(self, path: str) -> None:
        from pathlib import Path

        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "BaselineBundle":
        import json
        from pathlib import Path

        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def json_loads(raw: str) -> dict:
    import json

    return json.loads(raw)
