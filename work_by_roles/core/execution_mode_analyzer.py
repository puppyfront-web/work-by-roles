"""
Execution mode analyzer for determining role execution modes from skills.
Following Single Responsibility Principle - handles execution mode analysis only.
"""

from typing import Dict, List, Optional, Set, Any
from .models import Role, Skill
from .tool_mapper import ToolMapper


class ExecutionModeAnalyzer:
    """Analyzes execution modes and capabilities from role skills"""
    
    @staticmethod
    def analyze_role_execution_mode(
        role: Role,
        skill_library: Dict[str, Skill]
    ) -> Dict[str, Any]:
        """
        Analyze the primary execution mode for a role based on its skills.
        
        Args:
            role: Role to analyze
            skill_library: Dictionary of available skills
            
        Returns:
            Dictionary with execution mode information:
            - mode: Primary execution mode ("analysis", "implementation", "validation")
            - modes: Set of all execution modes found
            - generic_tools: Set of generic tools from skills
            - capabilities: List of capabilities from skills
        """
        execution_modes: Set[str] = set()
        generic_tools: Set[str] = set()
        execution_capabilities: List[str] = []
        
        # Check all skills for the role (new format: role.skills is a list of skill IDs)
        if role.skills and skill_library:
            for skill_id in role.skills:
                if skill_id and skill_id in skill_library:
                    skill = skill_library[skill_id]
                    if skill.metadata:
                        # Get execution mode (backward compatible with cursor_execution_mode)
                        mode = (
                            skill.metadata.get('execution_mode') 
                            or skill.metadata.get('cursor_execution_mode', 'analysis')
                        )
                        execution_modes.add(mode)
                        
                        # Get execution tools (backward compatible with cursor_tools)
                        tools = (
                            skill.metadata.get('execution_tools') 
                            or skill.metadata.get('cursor_tools', [])
                        )
                        if tools:
                            generic_tools.update(tools)
                        
                        # Get capabilities
                        capabilities = skill.metadata.get('execution_capabilities', [])
                        if capabilities:
                            execution_capabilities.extend(capabilities)
        
        # Determine primary execution mode (priority: implementation > validation > analysis)
        primary_mode = 'analysis'  # default
        if 'implementation' in execution_modes:
            primary_mode = 'implementation'
        elif 'validation' in execution_modes:
            primary_mode = 'validation'
        elif execution_modes:
            primary_mode = list(execution_modes)[0]
        
        return {
            'mode': primary_mode,
            'modes': execution_modes,
            'generic_tools': generic_tools,
            'capabilities': execution_capabilities
        }
    
    @staticmethod
    def get_available_tools(
        role: Role,
        skill_library: Dict[str, Skill],
        environment: str = "cursor"
    ) -> List[str]:
        """
        Get list of available tools for a role in the specified environment.
        
        Args:
            role: Role to analyze
            skill_library: Dictionary of available skills
            environment: Target environment ("cursor", "default", etc.)
            
        Returns:
            List of environment-specific tool names
        """
        analysis = ExecutionModeAnalyzer.analyze_role_execution_mode(role, skill_library)
        generic_tools = list(analysis['generic_tools'])
        
        if not generic_tools:
            return []
        
        # Map generic tools to environment-specific tools
        return ToolMapper.map_tools(generic_tools, environment)
    
    @staticmethod
    def get_capabilities(
        role: Role,
        skill_library: Dict[str, Skill]
    ) -> List[str]:
        """
        Get list of capabilities for a role.
        
        Args:
            role: Role to analyze
            skill_library: Dictionary of available skills
            
        Returns:
            List of unique capability names
        """
        analysis = ExecutionModeAnalyzer.analyze_role_execution_mode(role, skill_library)
        capabilities = analysis['capabilities']
        
        # Return unique capabilities
        return list(set(capabilities))
    
    @staticmethod
    def get_execution_mode_info(
        role: Role,
        skill_library: Dict[str, Skill],
        environment: str = "cursor"
    ) -> Dict[str, Any]:
        """
        Get complete execution mode information for a role.
        
        Args:
            role: Role to analyze
            skill_library: Dictionary of available skills
            environment: Target environment
            
        Returns:
            Dictionary with complete execution mode information:
            - mode: Primary execution mode
            - modes: All execution modes
            - tools: Environment-specific tools
            - generic_tools: Generic tool names
            - capabilities: Role capabilities
        """
        analysis = ExecutionModeAnalyzer.analyze_role_execution_mode(role, skill_library)
        
        generic_tools = list(analysis['generic_tools'])
        tools = ToolMapper.map_tools(generic_tools, environment) if generic_tools else []
        
        return {
            'mode': analysis['mode'],
            'modes': list(analysis['modes']),
            'tools': tools,
            'generic_tools': generic_tools,
            'capabilities': list(set(analysis['capabilities']))
        }

