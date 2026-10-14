"""MCP 接入层公共导出（V1.x F5）。"""
from wbr.adapters.mcp.bridge import MCPToolBridge, MCPToolInfo, MCPToolResult
from wbr.adapters.mcp.protocol import MCPClient

__all__ = ["MCPClient", "MCPToolBridge", "MCPToolInfo", "MCPToolResult"]


def __getattr__(name: str):
    if name == "StdioMCPClient":
        from wbr.adapters.mcp.stdio import StdioMCPClient

        return StdioMCPClient
    raise AttributeError(name)
