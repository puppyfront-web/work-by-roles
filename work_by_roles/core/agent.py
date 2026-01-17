"""
Agent for executing role-specific tasks.
Following Single Responsibility Principle - handles agent execution only.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import uuid

from .exceptions import WorkflowError
from .models import Role, Stage, ContextSummary, AgentContext
from .workflow_engine import WorkflowEngine
from .skill_selector import SkillSelector

class Agent:
    """
    Represents a Role in action, capable of executing tasks.
    
    IMPORTANT: This class handles the Reasoning Layer only.
    Skills MUST NOT be used in reasoning methods (prepare, make_decision, generate_prompt).
    Skills should only be invoked through AgentOrchestrator.execute_skill() in the Skill Invocation Layer.
    
    Architecture:
    - Reasoning Layer (this class): Task understanding, goal clarification, strategy, decisions
    - Skill Invocation Layer (AgentOrchestrator): Skill selection and execution
    - Execution Layer: Tool/API execution
    """
    def __init__(
        self, 
        role: Role, 
        engine: 'WorkflowEngine', 
        skill_selector: Optional[SkillSelector] = None,
        message_bus: Optional['AgentMessageBus'] = None,
        agent_id: Optional[str] = None
    ):
        self.role = role
        self.engine = engine
        self.context: Optional[AgentContext] = None
        self.agent_id = agent_id or f"{role.id}_{uuid.uuid4().hex[:8]}"
        # Note: skill_selector is stored but NOT used in reasoning methods
        # It's only available for external skill selection queries, not for reasoning
        self.skill_selector = skill_selector or SkillSelector(engine)
        self.message_bus = message_bus  # Optional message bus for inter-agent communication

    def prepare(self, goal: str, inputs: Optional[Dict[str, Any]] = None):
        """
        Prepare agent for task execution (Reasoning Layer).
        
        This is a pure reasoning method - NO skills should be invoked here.
        Skills are invoked separately through AgentOrchestrator.execute_skill().
        
        Also checks for shared contexts from other agents via message bus.
        """
        # Check for shared contexts from other agents
        shared_contexts = {}
        if self.message_bus:
            all_contexts = self.message_bus.get_all_contexts()
            for agent_id, context_data in all_contexts.items():
                if agent_id != self.agent_id:
                    # Create a simplified AgentContext from shared context
                    shared_contexts[agent_id] = AgentContext(
                        goal=context_data.get("goal", ""),
                        workspace_path=self.engine.workspace_path,
                        project_context=self.engine.context,
                        inputs=context_data.get("inputs", {}),
                        outputs=context_data.get("outputs", {}),
                        decisions=context_data.get("decisions", [])
                    )
        
        self.context = AgentContext(
            goal=goal,
            workspace_path=self.engine.workspace_path,
            project_context=self.engine.context,
            inputs=inputs or {},
            shared_contexts=shared_contexts
        )
        
        # Check for messages from other agents
        if self.message_bus:
            messages = self.message_bus.peek_messages(self.agent_id)
            if messages:
                print(f"📨 Agent {self.agent_id} has {len(messages)} unread message(s)")

    def make_decision(self, decision: str):
        """
        Record a decision made by the agent (Reasoning Layer).
        
        This is a pure reasoning method - NO skills should be invoked here.
        Decisions are made through natural language reasoning, not skill execution.
        """
        if self.context:
            self.context.decisions.append(decision)
            print(f"💭 Agent Decision: {decision}")

    def _get_output_path(self, name: str, output_type: str, stage_id: Optional[str] = None) -> Path:
        """
        Get the output path for a file based on type, workflow_id, and stage_id.
        
        Args:
            name: Output file name
            output_type: Type of output ("document", "report", "code", etc.)
            stage_id: Optional stage ID (if not provided, tries to get from engine state)
            
        Returns:
            Path object for the output file
        """
        # Get workflow_id
        workflow_id = "default"
        if self.engine.workflow:
            workflow_id = self.engine.workflow.id
        
        # Get stage_id if not provided
        if stage_id is None:
            if self.engine.executor and self.engine.executor.state:
                stage_id = self.engine.executor.state.current_stage
            if stage_id is None:
                stage_id = "default"
        
        # Determine path based on type
        if output_type in ("document", "report"):
            # All document and report types go to .workflow/outputs/{workflow_id}/{stage_id}/
            path = self.engine.workspace_path / ".workflow" / "outputs" / workflow_id / stage_id / name
        else:
            # Code, tests, and other types go to workspace root
            path = self.engine.workspace_path / name
        
        return path

    def produce_output(self, name: str, content: str, output_type: str = "code", stage_id: Optional[str] = None):
        """
        Produce an output file
        
        Args:
            name: Output file name
            content: File content
            output_type: Type of output ("document", "report", "code", etc.)
                        Documents and reports are saved to .workflow/outputs/{workflow_id}/{stage_id}/ to avoid cluttering the project
            stage_id: Optional stage ID (if not provided, tries to get from engine state)
        """
        if not self.context:
            raise ValueError("Agent not prepared")
        
        # Get output path using unified path calculation
        path = self._get_output_path(name, output_type, stage_id)
        
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        self.context.outputs[name] = str(path)
        
        if output_type in ("document", "report"):
            print(f"📄 Agent produced output: {name} -> {path.relative_to(self.engine.workspace_path)}")
        else:
            print(f"📄 Agent produced output: {name}")

    def get_context_summary(self, stage_id: Optional[str] = None) -> ContextSummary:
        """
        Get lightweight context summary for token optimization.
        
        Returns only key information, not full context history.
        This is much more token-efficient than passing full context.
        """
        return ContextSummary.from_engine(self.engine, stage_id)
    
    def generate_prompt(self, stage: Stage, use_summary: bool = True) -> str:
        """
        Generate a structured prompt for the LLM based on role and stage (Reasoning Layer).
        
        IMPORTANT: This prompt is for reasoning only - it does NOT include skill information.
        Skills are selected and executed separately in the Skill Invocation Layer.
        
        The prompt focuses on:
        - Role identity and constraints
        - Task understanding and goal clarification
        - Strategy and decision-making guidance
        - Expected outputs (but NOT how to achieve them via skills)
        
        Args:
            stage: Stage to generate prompt for
            use_summary: If True, use lightweight context summary instead of full context
        """
        if not self.context:
            raise ValueError("Agent not prepared. Call prepare() first.")
            
        # 1. Base Identity
        prompt = [f"You are acting as a {self.role.name}."]
        prompt.append(f"Description: {self.role.description}\n")
        
        # 2. Constraints
        allowed = self.role.constraints.get('allowed_actions', [])
        forbidden = self.role.constraints.get('forbidden_actions', [])
        if allowed:
            prompt.append("ALLOWED ACTIONS: " + ", ".join(allowed))
        if forbidden:
            prompt.append("FORBIDDEN ACTIONS: " + ", ".join(forbidden))
        prompt.append("")
        
        # 3. Context Summary (lightweight)
        if use_summary:
            context_summary = self.get_context_summary(stage.id)
            if context_summary.stage_summary:
                prompt.append("WORKFLOW CONTEXT:")
                prompt.append(context_summary.to_text())
                prompt.append("")
        
        # 4. Stage Goal
        prompt.append(f"CURRENT STAGE: {stage.name}")
        goal_text = stage.goal_template or self.context.goal
        prompt.append(f"GOAL: {goal_text}\n")
        
        # 5. Expected Outputs
        if stage.outputs:
            prompt.append("REQUIRED OUTPUTS:")
            for output in stage.outputs:
                prompt.append(f"- {output.name} ({output.type})")
            prompt.append("")
            
        # 6. Role-Specific Instructions
        if self.role.instruction_template:
            prompt.append("INSTRUCTIONS:")
            prompt.append(self.role.instruction_template)
        
        # 7. Reasoning Guidance (explicitly exclude skills)
        prompt.append("")
        prompt.append("REASONING GUIDANCE:")
        prompt.append("- Focus on understanding the task, clarifying goals, and making strategic decisions")
        prompt.append("- Do NOT invoke specific skills or tools during reasoning")
        prompt.append("- Skills will be selected and executed separately based on your decisions")
        prompt.append("- Use natural language reasoning and chain-of-thought")
            
        return "\n".join(prompt)
    
    # ========================================================================
    # Collaboration Methods - Agent 间协作
    # ========================================================================
    
    def review_output(self, output: Dict[str, Any], reviewer_role: Optional[str] = None) -> Dict[str, Any]:
        """
        Review output from another agent.
        
        Args:
            output: Output to review (should contain 'agent_id', 'output_type', 'content')
            reviewer_role: Optional role ID of the reviewer (defaults to self.role.id)
            
        Returns:
            Review result with feedback and approval status
        """
        if not self.message_bus:
            raise WorkflowError("Message bus not available for collaboration")
        
        reviewer_role = reviewer_role or self.role.id
        review_result = {
            "reviewer": self.agent_id,
            "reviewer_role": reviewer_role,
            "reviewed_output": output,
            "approved": True,
            "feedback": [],
            "suggestions": []
        }
        
        # Simple review logic (can be enhanced with LLM)
        if output.get("output_type") == "code":
            # Check for common code quality issues
            content = output.get("content", "")
            if "TODO" in content or "FIXME" in content:
                review_result["feedback"].append("Contains TODO/FIXME comments")
            if len(content) > 10000:
                review_result["feedback"].append("Output is very large, consider splitting")
        
        # Send review result back
        self.send_message(
            to_agent=output.get("agent_id", ""),
            message_type="response",
            content={"review": review_result}
        )
        
        return review_result
    
    def request_feedback(self, question: str, target_role: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Request feedback from other agents.
        
        Args:
            question: Question or request for feedback
            target_role: Optional target role ID (None = broadcast to all)
            
        Returns:
            List of feedback responses
        """
        if not self.message_bus:
            raise WorkflowError("Message bus not available for collaboration")
        
        # Send request
        if target_role:
            # Find agent with target role
            # For now, broadcast and filter responses
            self.message_bus.broadcast(
                from_agent=self.agent_id,
                message_type="request",
                content={
                    "question": question,
                    "requesting_role": self.role.id,
                    "target_role": target_role
                }
            )
        else:
            self.message_bus.broadcast(
                from_agent=self.agent_id,
                message_type="request",
                content={
                    "question": question,
                    "requesting_role": self.role.id
                }
            )
        
        # Wait for responses (in real implementation, this would be async)
        # For now, return empty list as responses come via messages
        return []
    
    def send_message(
        self,
        to_agent: str,
        message_type: str,
        content: Dict[str, Any]
    ) -> str:
        """
        Send a message to another agent.
        
        Args:
            to_agent: Target agent ID
            message_type: Type of message ("request", "response", "notification", "context_share")
            content: Message content
            
        Returns:
            Message ID
        """
        if not self.message_bus:
            raise WorkflowError("Message bus not available for collaboration")
        
        return self.message_bus.publish(
            from_agent=self.agent_id,
            to_agent=to_agent,
            message_type=message_type,
            content=content
        )
    
    def check_messages(self) -> List['AgentMessage']:
        """
        Check for new messages from other agents (without removing them).
        
        Returns:
            List of unread messages
        """
        if not self.message_bus:
            return []
        
        from .agent_message_bus import AgentMessage
        messages = self.message_bus.peek_messages(self.agent_id)
        return messages
    
    def get_messages(self) -> List['AgentMessage']:
        """
        Get and remove new messages from other agents.
        
        Returns:
            List of unread messages (messages are removed after reading)
        """
        if not self.message_bus:
            return []
        
        from .agent_message_bus import AgentMessage
        messages = self.message_bus.subscribe(self.agent_id)
        return messages
    
    def share_context(self, include_outputs: bool = True):
        """
        Share context with other agents via message bus.
        
        Args:
            include_outputs: Whether to include outputs in shared context
        """
        if not self.message_bus:
            raise WorkflowError("Message bus not available for collaboration")
        
        if not self.context:
            raise ValueError("Agent not prepared. Call prepare() first.")
        
        context_data = {
            "goal": self.context.goal,
            "inputs": self.context.inputs,
            "decisions": self.context.decisions
        }
        
        if include_outputs:
            context_data["outputs"] = self.context.outputs
        
        self.message_bus.share_context(self.agent_id, context_data)
        
        # Also send as notification
        self.message_bus.broadcast(
            from_agent=self.agent_id,
            message_type="notification",
            content={
                "event": "context_shared",
                "context_summary": {
                    "goal": self.context.goal,
                    "output_count": len(self.context.outputs)
                }
            }
        )


# ============================================================================
# Skill Invoker System - 可扩展的技能调用接口
# ============================================================================

