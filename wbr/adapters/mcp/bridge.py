"""MCP 工具桥（SPEC-007 §5）：权限前置 + 二阶防护 + 可选脱敏。

Bridge 只消费 Core 的契约与安全组件（ToolPermissionGate / boundaries / Redactor），
Core 永不感知 MCP。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from wbr.adapters.langgraph.interceptors import ToolPermissionGate
from wbr.core.audit.models import AuditEvent, AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.contract.models import RoleContract
from wbr.core.security.boundaries import scan_external_content, wrap_external_content
from wbr.core.security.guard import InjectionReport
from wbr.core.security.redactor import Redactor


class MCPToolInfo(BaseModel):
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class MCPToolResult(BaseModel):
    allowed: bool
    tool: str
    content: str = ""                # 二阶包裹（及脱敏）后的最终内容
    raw_content: str = ""            # 未包裹的原始文本（仅 result.allowed 时非空）
    error: str | None = None
    injection_report: InjectionReport | None = None


class MCPToolBridge:
    """把 MCP 服务器的工具挂到契约权限体系下。"""

    def __init__(
        self,
        client: Any,                     # MCPClient 协议实现（SDK / Fake / 自定义传输）
        *,
        gate: ToolPermissionGate | None = None,
        redactor: Redactor | None = None,
        boundaries: bool = True,
    ) -> None:
        self._client = client
        self._gate = gate or ToolPermissionGate()
        self._redactor = redactor
        self._boundaries = boundaries

    # ---- 工具发现（白名单过滤） ----
    def available_tools(self, contract: RoleContract) -> list[MCPToolInfo]:
        tools = [MCPToolInfo.model_validate(t) for t in self._client.list_tools()]
        return [t for t in tools if self._gate.check(contract, t.name).allowed]

    # ---- 工具调用 ----
    def invoke(
        self,
        contract: RoleContract,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        audit: AuditTrail | None = None,
    ) -> MCPToolResult:
        # 1) 权限前置（拒绝即审计，不触达 MCP）
        decision = self._gate.check(contract, tool_name)
        self._emit(audit, contract, tool_name, allowed=decision.allowed)
        if not decision.allowed:
            return MCPToolResult(allowed=False, tool=tool_name, error=decision.reason)
        # 2) 调用 MCP
        try:
            payload = self._client.call_tool(tool_name, dict(arguments))
        except Exception as e:
            return MCPToolResult(allowed=False, tool=tool_name, error=str(e))
        import json as _json

        raw = payload if isinstance(payload, str) else _json.dumps(payload, ensure_ascii=False)
        # 3) 二阶注入扫描
        report = scan_external_content(raw)
        # 4) 可选脱敏
        if self._redactor is not None:
            raw = self._redactor.redact(raw).redacted_text
        # 5) 边界包裹
        content = wrap_external_content(raw, source=f"mcp:{tool_name}") if self._boundaries else raw
        return MCPToolResult(allowed=True, tool=tool_name, content=content,
                             raw_content=raw, injection_report=report)

    def _emit(self, audit: AuditTrail | None, contract: RoleContract,
              tool: str, *, allowed: bool) -> None:
        if audit is not None:
            audit.append(
                AuditEvent(event_type=AuditEventType.TOOL_CALL, trace_id="no-trace",
                           role_id=contract.role_id, payload={"tool": tool, "allowed": allowed,
                                                              "source": "mcp"})
            )
