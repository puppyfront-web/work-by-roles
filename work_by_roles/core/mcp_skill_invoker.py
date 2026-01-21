"""
MCP (Model Context Protocol) Skill Invoker.

Supports calling external MCP servers during workflow execution.
This allows roles and workflows to integrate with external services via MCP.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import json
import warnings

from .exceptions import WorkflowError
from .models import Skill


class MCPSkillInvoker:
    """
    MCP-based skill invoker for calling external MCP servers.
    
    Supports:
    - Listing MCP resources
    - Fetching MCP resources
    - Calling MCP tools (if available)
    - Integrating MCP calls into skill execution
    """
    
    def __init__(self, mcp_client: Optional[Any] = None):
        """
        Initialize MCP skill invoker.
        
        Args:
            mcp_client: Optional MCP client instance. If None, will try to use
                       available MCP resources from the environment.
        """
        self.mcp_client = mcp_client
        self._available_resources: Optional[List[Dict[str, Any]]] = None
    
    def invoke(
        self,
        skill: Skill,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Invoke a skill using MCP resources.
        
        The skill metadata should specify:
        - mcp_server: MCP server identifier
        - mcp_resource_uri: Resource URI to fetch (optional)
        - mcp_tool: Tool name to call (optional)
        - mcp_action: Action to perform (list_resources, fetch_resource, call_tool)
        
        Args:
            skill: The skill definition to execute
            input_data: Input data for the skill
            context: Optional execution context
            
        Returns:
            Dict containing execution result
        """
        # Extract MCP configuration from skill metadata
        metadata = skill.metadata or {}
        mcp_config = metadata.get("mcp", {})
        
        if not mcp_config:
            return {
                "success": False,
                "error": "Skill does not have MCP configuration",
                "error_type": "mcp_config_missing"
            }
        
        action = mcp_config.get("action", "fetch_resource")
        server = mcp_config.get("server")
        resource_uri = mcp_config.get("resource_uri")
        tool_name = mcp_config.get("tool")
        
        try:
            if action == "list_resources":
                result = self._list_resources(server)
            elif action == "fetch_resource":
                if not resource_uri:
                    return {
                        "success": False,
                        "error": "resource_uri required for fetch_resource action",
                        "error_type": "mcp_config_error"
                    }
                result = self._fetch_resource(server, resource_uri, input_data)
            elif action == "call_tool":
                if not tool_name:
                    return {
                        "success": False,
                        "error": "tool required for call_tool action",
                        "error_type": "mcp_config_error"
                    }
                result = self._call_tool(server, tool_name, input_data)
            else:
                return {
                    "success": False,
                    "error": f"Unknown MCP action: {action}",
                    "error_type": "mcp_action_error"
                }
            
            # Process result according to skill output schema
            output = self._process_result(result, skill, input_data)
            
            return {
                "success": True,
                "output": output,
                "mcp_result": result,
                "mcp_action": action
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "mcp_execution_error"
            }
    
    def supports_skill(self, skill: Skill) -> bool:
        """Check if skill has MCP configuration"""
        if not skill.metadata:
            return False
        return "mcp" in skill.metadata
    
    def _list_resources(self, server: Optional[str] = None) -> Dict[str, Any]:
        """
        List available MCP resources.
        
        Args:
            server: Optional server identifier to filter by
            
        Returns:
            Dict with list of resources
        """
        # Try to use MCP client if available
        if self.mcp_client and hasattr(self.mcp_client, 'list_resources'):
            resources = self.mcp_client.list_resources(server=server)
            return {"resources": resources}
        
        # Fallback: Try to use MCP resources from environment
        # This would require integration with MCP SDK
        warnings.warn(
            "MCP client not available. MCP integration requires MCP SDK. "
            "Install mcp package or provide MCP client.",
            UserWarning
        )
        
        return {
            "resources": [],
            "message": "MCP client not configured"
        }
    
    def _fetch_resource(
        self,
        server: str,
        resource_uri: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fetch a resource from MCP server.
        
        Args:
            server: MCP server identifier
            resource_uri: Resource URI to fetch
            input_data: Input data (may contain download_path, etc.)
            
        Returns:
            Dict with resource data
        """
        # Try to use MCP client if available
        if self.mcp_client and hasattr(self.mcp_client, 'fetch_resource'):
            download_path = input_data.get("download_path")
            result = self.mcp_client.fetch_resource(
                server=server,
                uri=resource_uri,
                downloadPath=download_path
            )
            return {"resource": result}
        
        # Fallback: Return placeholder
        warnings.warn(
            f"MCP client not available. Cannot fetch resource {resource_uri} from {server}",
            UserWarning
        )
        
        return {
            "resource_uri": resource_uri,
            "server": server,
            "message": "MCP client not configured",
            "placeholder": True
        }
    
    def _call_tool(
        self,
        server: str,
        tool_name: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call an MCP tool.
        
        Args:
            server: MCP server identifier
            tool_name: Tool name to call
            input_data: Tool input parameters
            
        Returns:
            Dict with tool execution result
        """
        # Try to use MCP client if available
        if self.mcp_client and hasattr(self.mcp_client, 'call_tool'):
            result = self.mcp_client.call_tool(
                server=server,
                tool=tool_name,
                arguments=input_data
            )
            return {"tool_result": result}
        
        # Fallback: Return placeholder
        warnings.warn(
            f"MCP client not available. Cannot call tool {tool_name} on {server}",
            UserWarning
        )
        
        return {
            "tool": tool_name,
            "server": server,
            "arguments": input_data,
            "message": "MCP client not configured",
            "placeholder": True
        }
    
    def _process_result(
        self,
        result: Dict[str, Any],
        skill: Skill,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process MCP result according to skill output schema.
        
        Args:
            result: Raw MCP result
            skill: Skill definition
            input_data: Original input data
            
        Returns:
            Processed output matching skill output schema
        """
        # If skill has output schema, validate and transform result
        if skill.output_schema and "properties" in skill.output_schema:
            output = {}
            for prop_name, prop_def in skill.output_schema["properties"].items():
                # Try to extract from result
                if prop_name in result:
                    output[prop_name] = result[prop_name]
                elif "resource" in result:
                    # If result has resource, try to extract from it
                    output[prop_name] = result.get("resource", {}).get(prop_name)
                else:
                    # Use default or None
                    output[prop_name] = prop_def.get("default")
            
            return output
        
        # No output schema, return result as-is
        return result


class MCPSkillInvokerFactory:
    """Factory for creating MCP skill invokers"""
    
    @staticmethod
    def create(mcp_client: Optional[Any] = None) -> MCPSkillInvoker:
        """
        Create an MCP skill invoker.
        
        Args:
            mcp_client: Optional MCP client. If None, will try to auto-detect.
            
        Returns:
            MCPSkillInvoker instance
        """
        # Try to auto-detect MCP client if not provided
        if mcp_client is None:
            mcp_client = MCPSkillInvokerFactory._auto_detect_mcp_client()
        
        return MCPSkillInvoker(mcp_client=mcp_client)
    
    @staticmethod
    def _auto_detect_mcp_client() -> Optional[Any]:
        """
        Try to auto-detect MCP client from environment.
        
        Returns:
            MCP client instance or None
        """
        # Try to import MCP SDK
        try:
            # This would require the actual MCP SDK
            # import mcp
            # return mcp.Client()
            pass
        except ImportError:
            pass
        
        return None
