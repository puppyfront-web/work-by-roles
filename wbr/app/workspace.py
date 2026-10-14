"""多 Workspace 隔离（V2.0 E2 / SPEC-008 §2，R29：组合层实现）。

目录 + 存储 + 记忆三重隔离；跨域只能显式 copy（带血缘记录）。
"""
from __future__ import annotations

import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from wbr.app.store import ContractRegistry
from wbr.app.tasks.queue import JsonTaskStore
from wbr.core.exceptions import AppError
from wbr.core.memory.hub import MemoryHub

_WS_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class Workspace(BaseModel):
    name: str
    root: str
    created_at: float = Field(default_factory=time.time)


class WorkspaceRegistry:
    """企业级多租户隔离：契约/用例/任务/记忆四维按 workspace 隔离。"""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self._root = self.root / "workspaces"
        self._root.mkdir(parents=True, exist_ok=True)
        self._mem_hubs: dict[str, MemoryHub] = {}
        self._lock = threading.RLock()

    # ---- 生命周期 ----
    def _dir(self, name: str) -> Path:
        return self._root / name

    def create(self, name: str) -> Workspace:
        if not _WS_NAME.match(name):
            raise AppError(f"workspace 名称不合法: {name!r}（小写字母开头，仅 [a-z0-9_]）", code="E9022")
        ws_dir = self._dir(name)
        with self._lock:
            if ws_dir.is_dir():
                raise AppError(f"workspace 已存在: {name}", code="E9002")
            ws_dir.mkdir(parents=True)
        return Workspace(name=name, root=str(ws_dir))

    def get(self, name: str) -> Workspace:
        ws_dir = self._dir(name)
        if not ws_dir.is_dir():
            raise AppError(f"workspace 不存在: {name}", code="E9003")
        return Workspace(name=name, root=str(ws_dir))

    def list(self) -> list[Workspace]:
        return [self.get(d.name) for d in sorted(self._root.iterdir()) if d.is_dir()]

    def delete(self, name: str) -> None:
        self.get(name)  # 不存在即抛
        with self._lock:
            self._mem_hubs.pop(name, None)
            shutil.rmtree(self._dir(name))

    # ---- 四维隔离资源 ----
    def registry(self, name: str) -> ContractRegistry:
        """独立契约注册表。"""
        self.get(name)
        return ContractRegistry(self._dir(name) / "contracts")

    def suite_path(self, name: str) -> Path:
        self.get(name)
        p = self._dir(name) / "suites"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def task_store(self, name: str) -> JsonTaskStore:
        self.get(name)
        return JsonTaskStore(self._dir(name) / "tasks")

    def memory_hub(self, name: str) -> MemoryHub:
        """workspace 私有记忆门面（独立存储，跨 workspace 不可见）。"""
        self.get(name)
        with self._lock:
            hub = self._mem_hubs.get(name)
            if hub is None:
                hub = MemoryHub()
                self._mem_hubs[name] = hub
            return hub

    # ---- 跨域显式复制（带血缘） ----
    def copy_contract(self, src: str, dst: str, role_id: str) -> Any:
        src_reg, dst_reg = self.registry(src), self.registry(dst)
        contract = src_reg.get(role_id)
        if contract is None:
            raise AppError(f"源 workspace 无此契约: {src}/{role_id}", code="E9003")
        derived = contract.with_changes(
            changelog=f"copied from workspace {src!r} (hash={contract.content_hash[:12]})",
        )
        return dst_reg.create(derived)
