"""
Skill invoker implementations for executing skills.
Following Single Responsibility Principle - handles skill invocation only.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
import warnings

from .exceptions import ValidationError
from .models import Skill

class SkillInvoker(ABC):
    """
    Abstract base class for skill invocation.
    
    Provides a pluggable interface for different skill execution backends:
    - LLM-based execution
    - Tool/Function execution
    - External API calls
    - Custom implementations
    """
    
    @abstractmethod
    def invoke(
        self,
        skill: Skill,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Invoke a skill with the given input data.
        
        Args:
            skill: The skill definition to execute
            input_data: Input data for the skill
            context: Optional execution context
            
        Returns:
            Dict containing execution result with at least:
            - success: bool
            - output: Dict[str, Any] (if successful)
            - error: str (if failed)
        """
        pass
    
    @abstractmethod
    def supports_skill(self, skill: Skill) -> bool:
        """Check if this invoker can handle the given skill"""
        pass


class PlaceholderSkillInvoker(SkillInvoker):
    """
    Default placeholder implementation for skill invocation.
    
    Returns mock results - useful for testing workflow structure.
    """
    
    def invoke(
        self,
        skill: Skill,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Placeholder implementation that returns mock success"""
        # Generate mock output based on skill's output_schema
        output = {}
        if skill.output_schema and 'properties' in skill.output_schema:
            for prop_name, prop_def in skill.output_schema['properties'].items():
                output[prop_name] = f"[mock_{prop_name}]"
        else:
            output = {"result": f"Skill {skill.id} executed successfully"}
        
        return {
            "success": True,
            "output": output,
            "message": f"Placeholder execution of skill '{skill.name}'"
        }
    
    def supports_skill(self, skill: Skill) -> bool:
        """Placeholder supports all skills"""
        return True


class LLMSkillInvoker(SkillInvoker):
    """
    LLM-based skill invoker.
    
    Uses an LLM client to execute skills by generating appropriate prompts
    and parsing the responses according to skill schemas.
    """
    
    def __init__(self, llm_client: Any, max_tokens: int = 4096, stream_handler: Optional[Any] = None):
        """
        Initialize LLM skill invoker.
        
        Args:
            llm_client: LLM client with a 'complete' or 'chat' method
            max_tokens: Maximum tokens for LLM response
            stream_handler: Optional LLM stream handler for streaming responses
        """
        self.llm_client = llm_client
        self.max_tokens = max_tokens
        self.stream_handler = stream_handler
    
    def invoke(
        self,
        skill: Skill,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute skill using LLM"""
        prompt = self._generate_prompt(skill, input_data, context)
        
        try:
            # Try streaming if stream handler available and LLM supports it
            if self.stream_handler and hasattr(self.llm_client, 'stream'):
                try:
                    stream = self.llm_client.stream(prompt)
                    response = self.stream_handler.handle_stream(stream)
                    # Parse response
                    output = self._parse_response(response, skill)
                    return {
                        "success": True,
                        "output": output,
                        "raw_response": response
                    }
                except Exception:
                    # Fall back to non-streaming if streaming fails
                    pass
            
            # Try different LLM client interfaces (non-streaming)
            if hasattr(self.llm_client, 'complete'):
                response = self.llm_client.complete(prompt, max_tokens=self.max_tokens)
            elif hasattr(self.llm_client, 'chat'):
                response = self.llm_client.chat([{"role": "user", "content": prompt}])
            elif callable(self.llm_client):
                response = self.llm_client(prompt)
            else:
                raise ValueError("LLM client must have 'complete', 'chat' method or be callable")
            
            # Parse response
            output = self._parse_response(response, skill)
            
            return {
                "success": True,
                "output": output,
                "raw_response": response
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "llm_execution_error"
            }
    
    def _generate_prompt(
        self,
        skill: Skill,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate LLM prompt for skill execution"""
        parts = []
        
        # Skill description
        parts.append(f"# Task: Execute Skill '{skill.name}'")
        parts.append(f"\n## Description\n{skill.description}")
        
        # Dimensions
        if skill.dimensions:
            parts.append(f"\n## Skill Dimensions\n- " + "\n- ".join(skill.dimensions))
        
        # Constraints
        if skill.constraints:
            parts.append(f"\n## Constraints\n- " + "\n- ".join(skill.constraints))
        
        # Input data
        parts.append(f"\n## Input Data\n```json\n{json.dumps(input_data, indent=2)}\n```")
        
        # Expected output schema
        if skill.output_schema:
            parts.append(f"\n## Expected Output Format\n```json\n{json.dumps(skill.output_schema, indent=2)}\n```")
        
        # Context
        if context:
            parts.append(f"\n## Context\n```json\n{json.dumps(context, indent=2)}\n```")
        
        parts.append("\n## Instructions")
        parts.append("Execute the task described above and provide output in the expected format.")
        parts.append("Return your response as valid JSON matching the output schema.")
        
        return "\n".join(parts)
    
    def _parse_response(self, response: Any, skill: Skill) -> Dict[str, Any]:
        """Parse LLM response into structured output"""
        # Handle different response types
        if isinstance(response, dict):
            return cast(Dict[str, Any], response)
        
        response_str = str(response)
        
        # Try to extract JSON from response
        try:
            # Look for JSON block
            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response_str)
            if json_match:
                return cast(Dict[str, Any], json.loads(json_match.group(1)))
            
            # Try parsing entire response as JSON
            return cast(Dict[str, Any], json.loads(response_str))
        except json.JSONDecodeError:
            # Return as text if not valid JSON
            return {"text": response_str}
    
    def supports_skill(self, skill: Skill) -> bool:
        """LLM invoker supports all skills"""
        return True


class CompositeSkillInvoker(SkillInvoker):
    """
    Composite invoker that delegates to specialized invokers.
    
    Allows registering different invokers for different skill types.
    """
    
    def __init__(self, default_invoker: Optional[SkillInvoker] = None):
        """
        Initialize composite invoker.
        
        Args:
            default_invoker: Default invoker for unmatched skills
        """
        self.invokers: List[Tuple[Callable[[Skill], bool], SkillInvoker]] = []
        self.default_invoker = default_invoker or PlaceholderSkillInvoker()
    
    def register(
        self,
        matcher: Callable[[Skill], bool],
        invoker: SkillInvoker
    ) -> None:
        """
        Register an invoker for skills matching the condition.
        
        Args:
            matcher: Function that returns True if skill should use this invoker
            invoker: The invoker to use for matched skills
        """
        self.invokers.append((matcher, invoker))
    
    def register_for_skill_ids(
        self,
        skill_ids: List[str],
        invoker: SkillInvoker
    ) -> None:
        """Register an invoker for specific skill IDs"""
        self.register(lambda s: s.id in skill_ids, invoker)
    
    def register_for_dimensions(
        self,
        dimensions: List[str],
        invoker: SkillInvoker
    ) -> None:
        """Register an invoker for skills with specific dimensions"""
        self.register(
            lambda s: any(d in s.dimensions for d in dimensions),
            invoker
        )
    
    def invoke(
        self,
        skill: Skill,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Invoke skill using the appropriate registered invoker"""
        for matcher, invoker in self.invokers:
            if matcher(skill):
                return invoker.invoke(skill, input_data, context)
        
        return self.default_invoker.invoke(skill, input_data, context)
    
    def supports_skill(self, skill: Skill) -> bool:
        """Check if any registered invoker supports the skill"""
        for matcher, invoker in self.invokers:
            if matcher(skill) and invoker.supports_skill(skill):
                return True
        return self.default_invoker.supports_skill(skill)


# ============================================================================
# Condition Evaluator - 条件表达式评估器
# ConditionEvaluator has been moved to condition_evaluator.py
# It is imported above and re-exported for backward compatibility.

# ============================================================================
# Skill Workflow Executor - 多技能工作流执行器
# ============================================================================

