"""
Variable resolver for resolving placeholders in text.
Following Single Responsibility Principle - handles variable resolution only.
"""

import os
import re
from typing import Optional, Any, Dict, List
from pathlib import Path

from .models import ProjectContext
from .exceptions import ValidationError


class VariableResolver:
    """
    Resolves variable placeholders in text.
    
    Supports multiple variable sources:
    - {{project.xxx}} - Project context variables
    - {{env.VAR_NAME}} - Environment variables
    - {{config.key}} - Configuration variables (future extension)
    
    Also supports default values: {{key or 'default'}}
    """
    
    def __init__(self, context: Optional[ProjectContext] = None, 
                 config: Optional[Dict[str, Any]] = None,
                 raise_on_missing: bool = False):
        """
        Initialize variable resolver.
        
        Args:
            context: Project context for project.* variables
            config: Configuration dict for config.* variables
            raise_on_missing: If True, raise exception on missing variables instead of returning placeholder
        """
        self.context = context
        self.config = config or {}
        self.raise_on_missing = raise_on_missing
    
    @staticmethod
    def resolve(text: Any, context: Optional[ProjectContext] = None,
                config: Optional[Dict[str, Any]] = None,
                raise_on_missing: bool = False) -> Any:
        """
        Static method for backward compatibility.
        
        Args:
            text: Text to resolve variables in
            context: Project context
            config: Configuration dict
            raise_on_missing: Whether to raise on missing variables
        """
        resolver = VariableResolver(context, config, raise_on_missing)
        return resolver.resolve_text(text)
    
    def resolve_text(self, text: Any) -> Any:
        """Resolve variables in text"""
        if not isinstance(text, str):
            return text
        
        def replacement(match):
            full_key = match.group(1).strip()
            
            # Handle simple 'or' fallback: {{key or 'default'}}
            default_val = None
            if ' or ' in full_key:
                parts = full_key.split(' or ', 1)
                key = parts[0].strip()
                default_val = parts[1].strip().strip("'").strip('"')
            else:
                key = full_key

            parts = key.split('.')
            if len(parts) < 2:
                # Not a valid variable reference
                if self.raise_on_missing:
                    raise ValidationError(f"Invalid variable reference: {key}")
                return match.group(0) if default_val is None else default_val
            
            prefix = parts[0]
            res = None
            
            # Handle project.* variables
            if prefix == 'project':
                res = self._resolve_project_var(parts[1:])
            
            # Handle env.* variables
            elif prefix == 'env':
                if len(parts) > 1:
                    env_var = parts[1]
                    res = os.environ.get(env_var)
            
            # Handle config.* variables
            elif prefix == 'config':
                res = self._resolve_config_var(parts[1:])
            
            # Unknown prefix
            else:
                if self.raise_on_missing:
                    raise ValidationError(
                        f"Unknown variable prefix: {prefix}",
                        field="variable",
                        value=key,
                        context={"available_prefixes": ["project", "env", "config"]}
                    )
            res = None
            
            if res:
                return res
            if default_val is not None:
                return default_val
                
            # Variable not found
            if self.raise_on_missing:
                raise ValidationError(
                    f"Variable not found: {key}",
                    field="variable",
                    value=key,
                    context={"prefix": prefix}
                )
            return f"[{key} NOT FOUND]"

        return re.sub(r'\{\{([^}]+)\}\}', replacement, text)
    
    def _resolve_project_var(self, parts: List[str]) -> Optional[str]:
        """Resolve project.* variable"""
        if not self.context:
            return None
        
        if len(parts) == 0:
            return None
        
        category = parts[0]
        sub_key = '.'.join(parts[1:]) if len(parts) > 1 else None
        
        if category == 'paths' and sub_key and sub_key in self.context.paths:
            return self.context.paths[sub_key]
        elif category == 'specs' and sub_key and sub_key in self.context.specs:
            return self.context.specs[sub_key]
        elif category == 'standards' and sub_key and sub_key in self.context.standards:
            val = self.context.standards[sub_key]
            return str(val) if val is not None else None
        elif category == 'root':
            return str(self.context.root_path)
        
        return None
    
    def _resolve_config_var(self, parts: List[str]) -> Any:
        """Resolve config.* variable"""
        if not parts:
            return None
        
        current = self.config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current

