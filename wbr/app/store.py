"""App 层存储：JSON 文件契约注册表（CRUD + 版本管理 + Diff）。"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from wbr.core.contract.diff import ContractDiffEngine, DiffReport
from wbr.core.contract.models import RoleContract
from wbr.core.exceptions import AppError


class ContractRegistry:
    """契约库：每契约一目录，版本快照按序存储，最新版本为当前版本。"""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._cache: dict[str, list[RoleContract]] = {}

    def _dir(self, cid: str) -> Path:
        safe = cid.replace("/", "_").replace("..", "_")
        return self.root / "contracts" / safe

    def _versions_file(self, cid: str) -> Path:
        return self._dir(cid) / "versions.json"

    def _load(self, cid: str) -> list[RoleContract]:
        if cid in self._cache:
            return self._cache[cid]
        f = self._versions_file(cid)
        if not f.is_file():
            return []
        data = json.loads(f.read_text(encoding="utf-8"))
        versions = [RoleContract.model_validate(d) for d in data]
        self._cache[cid] = versions
        return versions

    def _save(self, cid: str, versions: list[RoleContract]) -> None:
        self._dir(cid).mkdir(parents=True, exist_ok=True)
        payload = [json.loads(v.to_json()) for v in versions]
        self._versions_file(cid).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---- CRUD ----
    def create(self, contract: RoleContract) -> RoleContract:
        with self._lock:
            if self._versions_file(contract.role_id).is_file() or contract.role_id in self._cache:
                raise AppError(f"契约已存在: {contract.role_id}", code="E9002",
                               details={"role_id": contract.role_id})
            versions = [contract]
            self._save(contract.role_id, versions)
            self._cache[contract.role_id] = versions
            return contract

    def get(self, cid: str) -> RoleContract | None:
        with self._lock:
            versions = self._load(cid)
            return versions[-1] if versions else None

    def list(self) -> list[RoleContract]:
        with self._lock:
            out = []
            if (self.root / "contracts").is_dir():
                for d in sorted((self.root / "contracts").iterdir()):
                    versions = self._load(d.name)
                    if versions:
                        out.append(versions[-1])
            return out

    def update(self, cid: str, new_contract: RoleContract) -> tuple[RoleContract, DiffReport | None]:
        """更新为新版本：自动 Diff 上一版本；返回 (新当前版本, diff)。"""
        with self._lock:
            versions = self._load(cid)
            if not versions:
                raise AppError(f"契约不存在: {cid}", code="E9003")
            latest = versions[-1]
            if new_contract.role_id != cid:
                raise AppError("role_id 不可变更", code="E9004")
            diff = None
            if new_contract.content_hash != latest.content_hash:
                diff = ContractDiffEngine().diff(latest, new_contract)
            elif new_contract.meta.version == latest.meta.version:
                raise AppError("内容无变化且版本号未推进", code="E9005")
            versions.append(new_contract)
            self._save(cid, versions)
            self._cache[cid] = versions
            return new_contract, diff

    def delete(self, cid: str) -> bool:
        with self._lock:
            versions = self._load(cid)
            if not versions:
                return False
            import shutil

            shutil.rmtree(self._dir(cid), ignore_errors=True)
            self._cache.pop(cid, None)
            return True

    # ---- 版本管理 ----
    def versions(self, cid: str) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"version": v.meta.version, "content_hash": v.meta.content_hash,
                 "created_at": v.meta.created_at.isoformat(), "changelog": v.meta.changelog}
                for v in self._load(cid)
            ]

    def get_version(self, cid: str, version: str) -> RoleContract | None:
        with self._lock:
            for v in self._load(cid):
                if v.meta.version == version:
                    return v
            return None

    def diff_versions(self, cid: str, from_version: str, to_version: str) -> DiffReport | None:
        old = self.get_version(cid, from_version)
        new = self.get_version(cid, to_version)
        if old is None or new is None:
            return None
        return ContractDiffEngine().diff(old, new)
