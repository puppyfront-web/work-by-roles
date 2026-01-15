"""
Condition evaluator for workflow step conditions.
Following Single Responsibility Principle - handles condition evaluation only.
"""

import re
import warnings
from typing import Dict, Any


class ConditionEvaluator:
    """
    Evaluates condition expressions in workflow steps.
    
    Supports:
    - Step result access: step_1.result.status
    - Step output access: step_1.outputs.key
    - Workflow input access: inputs.key
    - Comparison operators: ==, !=, <, >, <=, >=
    - Logical operators: and, or, not
    - String and numeric comparisons
    """
    
    def __init__(self, step_outputs: Dict[str, Dict[str, Any]], workflow_inputs: Dict[str, Any]):
        """
        Initialize condition evaluator.
        
        Args:
            step_outputs: Dictionary mapping step_id to step outputs
            workflow_inputs: Workflow input variables
        """
        self.step_outputs = step_outputs
        self.workflow_inputs = workflow_inputs
    
    def evaluate(self, condition: str) -> bool:
        """
        Evaluate a condition expression.
        
        Args:
            condition: Condition expression string
            
        Returns:
            Boolean result of evaluation
        """
        if not condition:
            return True
        
        try:
            # Resolve variable references
            resolved_condition = self._resolve_variables(condition)
            
            # Evaluate the expression safely
            # Using eval with restricted globals for safety
            safe_dict = {
                '__builtins__': {
                    'True': True,
                    'False': False,
                    'None': None,
                    'bool': bool,
                    'int': int,
                    'float': float,
                    'str': str,
                    'len': len,
                }
            }
            
            # Replace common operators with Python equivalents
            resolved_condition = resolved_condition.replace(' and ', ' and ')
            resolved_condition = resolved_condition.replace(' or ', ' or ')
            resolved_condition = resolved_condition.replace(' not ', ' not ')
            
            result = eval(resolved_condition, safe_dict)
            return bool(result)
        except Exception as e:
            # If evaluation fails, log and return False
            warnings.warn(f"Condition evaluation failed: {condition}, error: {e}")
            return False
    
    def _resolve_variables(self, condition: str) -> str:
        """Resolve variable references in condition"""
        def resolve_step_ref(match):
            """Resolve step reference like step_1.result.status"""
            ref = match.group(1)
            parts = ref.split('.')
            
            if len(parts) < 2:
                return 'None'
            
            step_id = parts[0]
            if step_id not in self.step_outputs:
                return 'None'
            
            step_data = self.step_outputs[step_id]
            
            # Navigate through the data structure
            current = step_data
            for part in parts[1:]:
                if isinstance(current, dict):
                    current = current.get(part)
                elif hasattr(current, part):
                    current = getattr(current, part)
                else:
                    return 'None'
                if current is None:
                    return 'None'
            
            # Convert to Python literal
            if isinstance(current, bool):
                return str(current)
            elif isinstance(current, (int, float)):
                return str(current)
            elif isinstance(current, str):
                return repr(current)
            else:
                return repr(current)
        
        def resolve_input_ref(match):
            """Resolve input reference like inputs.key"""
            key = match.group(1)
            value = self.workflow_inputs.get(key)
            if value is None:
                return 'None'
            if isinstance(value, bool):
                return str(value)
            elif isinstance(value, (int, float)):
                return str(value)
            elif isinstance(value, str):
                return repr(value)
            else:
                return repr(value)
        
        # Resolve step references: {{step.step_id.result.field}}
        condition = re.sub(r'\{\{step\.(\w+(?:\.[\w.]+)*)\}\}', resolve_step_ref, condition)
        
        # Resolve input references: {{inputs.key}}
        condition = re.sub(r'\{\{inputs\.(\w+)\}\}', resolve_input_ref, condition)
        
        return condition

