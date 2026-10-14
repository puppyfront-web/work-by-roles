"""MCP 客户端协议（Core 不感知 MCP，D-01/R20）：任意传输实现此协议即可接入。"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from wbr.adapters.mcp.bridge import MCPToolInfo


@runtime_checkable
class MCPClient(Protocol):
    """MCP 服务器连接的最小协议：工具发现 + 工具调用。"""

    def list_tools(self) -> list[MCPToolInfo]: ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...
