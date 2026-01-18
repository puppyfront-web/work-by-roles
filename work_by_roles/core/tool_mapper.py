"""
Tool mapper for mapping generic tools to environment-specific tools.
Following Single Responsibility Principle - handles tool mapping only.
"""

from typing import List, Dict, Optional


class ToolMapper:
    """Maps generic tools to environment-specific tools"""
    
    # Tool mappings for different environments
    CURSOR_MAPPING = {
        'file_write': 'write',
        'file_modify': 'search_replace',
        'file_read': 'read_file',
        'code_search': 'codebase_search',
        'command_execute': 'run_terminal_cmd',
    }
    
    # Default mapping (no transformation)
    DEFAULT_MAPPING: Dict[str, str] = {}
    
    @classmethod
    def map_tools(
        cls,
        generic_tools: List[str],
        environment: str = "cursor"
    ) -> List[str]:
        """
        Map generic tools to environment-specific tools.
        
        Args:
            generic_tools: List of generic tool names
            environment: Target environment ("cursor", "default", etc.)
            
        Returns:
            List of environment-specific tool names
        """
        if not generic_tools:
            return []
        
        # Select mapping based on environment
        if environment == "cursor":
            mapping = cls.CURSOR_MAPPING
        else:
            mapping = cls.DEFAULT_MAPPING
        
        # Map tools
        mapped_tools = []
        for tool in generic_tools:
            mapped_tool = mapping.get(tool, tool)
            mapped_tools.append(mapped_tool)
        
        return mapped_tools
    
    @classmethod
    def get_mapping_info(cls, environment: str = "cursor") -> Dict[str, str]:
        """
        Get tool mapping information for an environment.
        
        Args:
            environment: Target environment
            
        Returns:
            Dictionary mapping generic tools to environment-specific tools
        """
        if environment == "cursor":
            return cls.CURSOR_MAPPING.copy()
        else:
            return cls.DEFAULT_MAPPING.copy()

