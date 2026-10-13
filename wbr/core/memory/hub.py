"""MemoryHub：按契约权限管控的四层记忆访问门面。"""
from __future__ import annotations

import time
from typing import Any

from wbr.core.audit.models import AuditEvent, AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.constants import MemoryLayer
from wbr.core.contract.models import RoleContract
from wbr.core.exceptions import MemoryPermissionDeniedError
from wbr.core.memory.base import InMemoryMemoryStore, MemoryRecord, MemoryStore


class MemoryHub:
    """记忆门面：每次读写先校验 contract.memory_permissions，越权拒绝并审计。"""

    def __init__(
        self,
        store: MemoryStore | None = None,
        *,
        audit: AuditTrail | None = None,
        trace_id: str | None = None,
    ) -> None:
        self._store: MemoryStore = store if store is not None else InMemoryMemoryStore()
        self._audit = audit
        self._trace_id = trace_id

    @property
    def store(self) -> MemoryStore:
        return self._store

    # ---- 作用域规则 ----
    @staticmethod
    def scope(layer: MemoryLayer, *, role_id: str | None, session_id: str | None) -> str:
        if layer == MemoryLayer.ROLE_STATIC:
            return f"{layer.value}:{role_id or 'unknown'}"
        if layer == MemoryLayer.ROLE_SESSION:
            return f"{layer.value}:{role_id or 'unknown'}:{session_id or 'unknown'}"
        if layer == MemoryLayer.TASK_SCRATCH:
            return f"{layer.value}:task:{session_id or 'unknown'}"
        return f"{layer.value}:__global__"

    def _namespace(self, layer: MemoryLayer, *, role_id: str | None, session_id: str | None):
        return (layer.value, self.scope(layer, role_id=role_id, session_id=session_id))

    # ---- 权限 ----
    def _check(
        self,
        mode: str,
        layer: MemoryLayer,
        contract: RoleContract,
        *,
        key: str,
        session_id: str | None,
    ) -> None:
        perms = contract.memory_permissions
        allowed_layers = perms.read_layers if mode == "read" else perms.write_layers
        allowed = layer in allowed_layers
        if allowed and mode == "write" and layer == MemoryLayer.GLOBAL_SHARED:
            allowed = bool(perms.allow_global_write)  # 全局写第二道授权
        self._audit_access(mode, layer, contract, key=key, allowed=allowed, session_id=session_id)
        if not allowed:
            raise MemoryPermissionDeniedError(
                f"角色 {contract.role_id} 无 {mode} 权限: layer={layer.value}, key={key}",
                details={
                    "role_id": contract.role_id,
                    "layer": layer.value,
                    "mode": mode,
                    "key": key,
                },
            )

    def _audit_access(
        self,
        mode: str,
        layer: MemoryLayer,
        contract: RoleContract,
        *,
        key: str,
        allowed: bool,
        session_id: str | None,
    ) -> None:
        if self._audit is None:
            return
        self._audit.append(
            AuditEvent(
                event_type=AuditEventType.MEMORY_ACCESS,
                trace_id=self._trace_id or "no-trace",
                role_id=contract.role_id,
                payload={
                    "mode": mode,
                    "layer": layer.value,
                    "key": key,
                    "allowed": allowed,
                    "session_id": session_id,
                    "ts": time.time(),
                },
            )
        )

    # ---- 读写 API ----
    def read(
        self,
        layer: MemoryLayer,
        key: str,
        *,
        contract: RoleContract,
        role_id: str | None = None,
        session_id: str | None = None,
    ) -> Any:
        self._check("read", layer, contract, key=key, session_id=session_id)
        ns = self._namespace(layer, role_id=role_id or contract.role_id, session_id=session_id)
        record = self._store.get(ns, key)
        return record.value if record else None

    def write(
        self,
        layer: MemoryLayer,
        key: str,
        value: Any,
        *,
        contract: RoleContract,
        role_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self._check("write", layer, contract, key=key, session_id=session_id)
        ns = self._namespace(layer, role_id=role_id or contract.role_id, session_id=session_id)
        self._store.set(
            ns,
            key,
            MemoryRecord(
                key=key,
                value=value,
                layer=layer,
                role_id=role_id or contract.role_id,
                session_id=session_id,
            ),
        )

    def append(
        self,
        layer: MemoryLayer,
        key: str,
        value: Any,
        *,
        contract: RoleContract,
        role_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self._check("write", layer, contract, key=key, session_id=session_id)
        ns = self._namespace(layer, role_id=role_id or contract.role_id, session_id=session_id)
        self._store.append(ns, key, value)

    def keys_of(
        self,
        layer: MemoryLayer,
        *,
        contract: RoleContract,
        role_id: str | None = None,
        session_id: str | None = None,
    ) -> list[str]:
        self._check("read", layer, contract, key="*", session_id=session_id)
        ns = self._namespace(layer, role_id=role_id or contract.role_id, session_id=session_id)
        return self._store.keys(ns)
