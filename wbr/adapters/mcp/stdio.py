"""基于 mcp SDK 的 stdio 客户端（可选依赖，R15：缺失给安装指引）。"""
from __future__ import annotations

import asyncio
from typing import Any

from wbr.adapters.mcp.bridge import MCPToolInfo

_INSTALL_HINT = "StdioMCPClient 需要 MCP SDK: pip install mcp"


class StdioMCPClient:
    """通过 stdio 连接一个 MCP 服务器（子进程）。"""

    def __init__(self, *, command: list[str], env: dict[str, str] | None = None) -> None:
        try:
            import mcp  # noqa: F401
        except ImportError as e:
            from wbr.core.exceptions import AdapterError

            raise AdapterError(_INSTALL_HINT) from e
        self._command = command
        self._env = env
        self._session: Any = None
        self._ctx: Any = None

    # ---- 生命周期 ----
    async def connect(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(command=self._command[0], args=self._command[1:], env=self._env)
        self._ctx = stdio_client(params)
        read, write = await self._ctx.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None
        if self._ctx is not None:
            await self._ctx.__aexit__(None, None, None)
            self._ctx = None

    # ---- MCPClient 协议（同步外观，内部驱动事件循环） ----
    def list_tools(self) -> list[MCPToolInfo]:
        async def _run():
            resp = await self._session.list_tools()
            return [
                MCPToolInfo(name=t.name, description=t.description or "",
                            input_schema=getattr(t, "inputSchema", {}) or {})
                for t in resp.tools
            ]

        return asyncio.run(_run())

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async def _run():
            resp = await self._session.call_tool(name, arguments)
            content = getattr(resp, "content", []) or []
            texts = [getattr(c, "text", "") for c in content]
            return {"texts": texts, "is_error": bool(getattr(resp, "isError", False))}

        return asyncio.run(_run())
