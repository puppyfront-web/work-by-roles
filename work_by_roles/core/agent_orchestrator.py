"""
Agent orchestrator for coordinating multiple agents.
Following Single Responsibility Principle - handles agent orchestration only.
"""

from typing import Dict, List, Optional, Any, cast, TYPE_CHECKING
from pathlib import Path
import asyncio
import time
import warnings
import json

if TYPE_CHECKING:
    from .models import Output

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    warnings.warn("jsonschema not available. Schema validation will be skipped.")

from .exceptions import WorkflowError
from .models import Role, Stage, AgentContext, ContextSummary, Skill, SkillWorkflow, SkillWorkflowExecution, SkillExecution
from .enums import SkillErrorType
from .workflow_engine import WorkflowEngine
from .agent import Agent
from .skill_selector import SkillSelector, RetryHandler
from .skill_invoker import SkillInvoker, PlaceholderSkillInvoker, LLMSkillInvoker
from .skill_workflow_executor import SkillWorkflowExecutor
from .execution_tracker import ExecutionTracker
from .task_decomposer import TaskDecomposer

class AgentOrchestrator:
    """
    Orchestrates Agents to execute a workflow automatically (Sequential and Parallel multi-agent).
    
    This class manages the Skill Invocation Layer, which is separate from the Reasoning Layer.
    
    Architecture:
    - Reasoning Layer (Agent): Task understanding, decisions, strategy (NO skills)
    - Skill Invocation Layer (this class): Skill selection and execution
    - Execution Layer: Tool/API execution
    
    Skills are ONLY invoked through execute_skill(), never during agent reasoning.
    
    LLM Integration:
    - LLM is completely optional - core functionality works without LLM
    - Set llm_client to enable LLM features
    - Use use_llm=True in execute_stage() to explicitly enable LLM
    - Default behavior is constraint checking only (no LLM calls)
    """
    def __init__(
        self, 
        engine: 'WorkflowEngine', 
        llm_client: Optional[Any] = None,
        skill_invoker: Optional[SkillInvoker] = None,
        message_bus: Optional['AgentMessageBus'] = None,
        immersive_display: Optional[Any] = None
    ):
        """
        Initialize AgentOrchestrator.
        
        Args:
            engine: WorkflowEngine instance
            llm_client: Optional LLM client. If None, LLM features are disabled.
            skill_invoker: Optional custom skill invoker (defaults to PlaceholderSkillInvoker)
            message_bus: Optional message bus for inter-agent communication
            immersive_display: Optional immersive workflow display for Cursor IDE conversations
        """
        self.engine = engine
        self.llm_client = llm_client
        self.llm_enabled = llm_client is not None
        self.execution_log: List[Dict[str, Any]] = []
        self.execution_tracker: ExecutionTracker = ExecutionTracker()
        self.skill_selector: SkillSelector = SkillSelector(engine, self.execution_tracker)
        self.retry_handler: RetryHandler = RetryHandler(self.execution_tracker)
        
        # Message bus for inter-agent communication
        if message_bus is None:
            from .agent_message_bus import AgentMessageBus
            messages_dir = engine.workspace_path / ".workflow" / "messages"
            self.message_bus = AgentMessageBus(persist_messages=True, messages_dir=messages_dir)
        else:
            self.message_bus = message_bus
        
        # Task decomposer for breaking down goals
        self.task_decomposer = TaskDecomposer(engine, llm_client)
        
        # Skill invoker for actual skill execution
        if skill_invoker:
            self.skill_invoker = skill_invoker
        elif llm_client:
            # Create stream handler if immersive display available
            stream_handler = None
            if immersive_display and hasattr(immersive_display, 'use_streaming') and immersive_display.use_streaming:
                try:
                    from .llm_stream_handler import LLMStreamHandler
                    if immersive_display.stream_writer:
                        stream_handler = LLMStreamHandler(immersive_display.stream_writer)
                except Exception:
                    pass
            self.skill_invoker = LLMSkillInvoker(llm_client, stream_handler=stream_handler)
        else:
            self.skill_invoker = PlaceholderSkillInvoker()
        
        # Skill workflow executor for multi-skill workflows
        self.workflow_executor = SkillWorkflowExecutor(
            engine=engine,
            skill_invoker=self.skill_invoker,
            execution_tracker=self.execution_tracker
        )
        
        # Immersive workflow display for Cursor IDE conversations
        if immersive_display is None:
            try:
                from .immersive_workflow_display import ImmersiveWorkflowDisplay
                self.immersive_display = ImmersiveWorkflowDisplay(engine.workspace_path)
            except ImportError:
                self.immersive_display = None
        else:
            self.immersive_display = immersive_display

    def execute_stage(self, stage_id: str, inputs: Optional[Dict[str, Any]] = None, use_llm: bool = False) -> Dict[str, Any]:
        """
        Execute a single stage using the assigned agent.
        
        This method handles the Reasoning Layer:
        1. Creates an Agent for reasoning (task understanding, decisions)
        2. Generates prompt for LLM reasoning (NO skills involved) - only if use_llm=True
        3. Returns context for skill invocation
        
        Skills are NOT invoked here - they are invoked separately via execute_skill()
        after the agent has made decisions about what needs to be done.
        
        Args:
            stage_id: Stage ID to execute
            inputs: Optional input data
            use_llm: If True and llm_client is set, will generate LLM prompt. Default False.
        
        Returns:
            Dict with stage execution result
        """
        if use_llm and self.llm_enabled:
            return self._execute_with_llm(stage_id, inputs)
        else:
            return self.check_constraints_only(stage_id, inputs)
    
    def check_constraints_only(self, stage_id: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Check constraints and validate stage without LLM execution.
        
        This is the lightweight mode - no LLM calls, just constraint checking.
        Perfect for offline use or when you want to avoid token costs.
        
        Args:
            stage_id: Stage ID to check
            inputs: Optional input data
        
        Returns:
            Dict with constraint check result
        """
        stage = self.engine.executor._get_stage_by_id(stage_id) if self.engine.executor else None
        if not stage:
            raise WorkflowError(f"Stage '{stage_id}' not found")
            
        role = self.engine.role_manager.get_role(stage.role)
        if not role:
            raise WorkflowError(f"Role '{stage.role}' for stage '{stage_id}' not found")
        
        # Check if stage can be started
        can_start = True
        errors: List[str] = []
        if self.engine.executor:
            can_start, errors = self.engine.executor.can_transition_to(stage_id)
        
        # Create minimal agent context (no LLM prompt generation)
        agent = Agent(role, self.engine, self.skill_selector, self.message_bus)
        goal = "Implement requirements"
        # Priority: inputs > engine.context.specs > default
        if inputs and ("goal" in inputs or "user_intent" in inputs):
            goal = inputs.get("goal") or inputs.get("user_intent", goal)
        elif self.engine.context and self.engine.context.specs:
            goal = self.engine.context.specs.get("global_goal", goal)
        agent.prepare(goal, inputs)
        
        result = {
            "stage": stage_id,
            "agent": agent,
            "context": agent.context,
            "status": "constraints_checked",
            "can_start": can_start,
            "errors": errors,
            "llm_used": False
        }
        
        self.execution_log.append(result)
        return result
    
    def _execute_with_llm(self, stage_id: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute stage with LLM support (requires llm_client to be set).
        
        This method generates LLM prompts and can call the LLM if needed.
        Only called when use_llm=True and llm_client is available.
        
        Args:
            stage_id: Stage ID to execute
            inputs: Optional input data
        
        Returns:
            Dict with LLM execution result
        """
        if not self.llm_enabled:
            raise WorkflowError("LLM client not available. Set llm_client in __init__ or use check_constraints_only()")
        
        stage = self.engine.executor._get_stage_by_id(stage_id) if self.engine.executor else None
        if not stage:
            raise WorkflowError(f"Stage '{stage_id}' not found")
            
        role = self.engine.role_manager.get_role(stage.role)
        if not role:
            raise WorkflowError(f"Role '{stage.role}' for stage '{stage_id}' not found")
            
        # Create agent for reasoning (Reasoning Layer - NO skills)
        agent = Agent(role, self.engine, self.skill_selector, self.message_bus)
        goal = "Implement requirements"
        # Priority: inputs > engine.context.specs > default
        if inputs and ("goal" in inputs or "user_intent" in inputs):
            goal = inputs.get("goal") or inputs.get("user_intent", goal)
        elif self.engine.context and self.engine.context.specs:
            goal = self.engine.context.specs.get("global_goal", goal)
        agent.prepare(goal, inputs)
        
        # Generate prompt for reasoning (Reasoning Layer - NO skills)
        # Here we would normally call an LLM for reasoning.
        prompt = agent.generate_prompt(stage)
        
        # Note: Actual LLM call would happen here if needed
        # For now, we just return the prompt and context
        
        result = {
            "stage": stage_id,
            "agent": agent,
            "prompt": prompt,
            "context": agent.context,
            "status": "ready_for_execution",
            "llm_used": True
            # Note: Skills are invoked separately via execute_skill() after reasoning
        }
        
        self.execution_log.append(result)
        return result
    
    def execute_skill(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        stage_id: Optional[str] = None,
        role_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a skill with retry logic and tracking (Skill Invocation Layer).
        
        This is the ONLY place where skills should be invoked.
        Skills are NEVER invoked during agent reasoning (prepare, make_decision, generate_prompt).
        
        Execution flow:
        1. Agent reasoning (Reasoning Layer) - decides WHAT needs to be done
        2. Skill selection (this layer) - decides WHICH skill to use
        3. Skill execution (this layer) - executes the skill
        4. Result validation and tracking
        
        Args:
            skill_id: ID of the skill to execute
            input_data: Input data for the skill
            stage_id: Optional stage ID for tracking
            role_id: Optional role ID for tracking
            
        Returns:
            Dict with execution result
        """
        if not self.engine.role_manager.skill_library:
            raise WorkflowError("Skill library not loaded")
        
        skill = self.engine.role_manager.skill_library.get(skill_id)
        if not skill:
            raise WorkflowError(f"Skill '{skill_id}' not found")
        execution: Optional[SkillExecution] = None
        
        # Validate input schema if available
        if skill.input_schema and JSONSCHEMA_AVAILABLE:
            try:
                jsonschema.validate(input_data, skill.input_schema)
            except jsonschema.ValidationError as e:
                error_response = self.retry_handler.format_error_response(
                    e, skill, retryable=False
                )
                execution = SkillExecution(
                    skill_id=skill_id,
                    input=input_data,
                    output=None,
                    status="failed",
                    error_type=SkillErrorType.VALIDATION_ERROR.value,
                    error_message=str(e),
                    execution_time=0.0,
                    stage_id=stage_id,
                    role_id=role_id
                )
                self.execution_tracker.record_execution(execution)
                return error_response
        
        # 如果有角色ID，更新流式处理器的角色名称
        original_role_name = None
        if role_id and self.skill_invoker and hasattr(self.skill_invoker, 'stream_handler'):
            if self.skill_invoker.stream_handler:
                original_role_name = getattr(self.skill_invoker.stream_handler, 'role_name', None)
                # 获取角色名称
                role = self.engine.role_manager.get_role(role_id) if role_id else None
                if role:
                    self.skill_invoker.stream_handler.role_name = role.name
        
        # Execute skill with retry logic
        start_time = time.time()
        last_error: Optional[Exception] = None
        
        try:
            for attempt in range(10):  # Max 10 attempts
                try:
                    # Here we would normally invoke the actual skill execution
                    # For now, this is a placeholder that would call LLM or tool
                    result = self._invoke_skill(skill, input_data)
                    
                    execution_time = time.time() - start_time
                    execution = SkillExecution(
                        skill_id=skill_id,
                        input=input_data,
                        output=result,
                        status="success",
                        execution_time=execution_time,
                        retry_count=attempt,
                        stage_id=stage_id,
                        role_id=role_id
                    )
                    self.execution_tracker.record_execution(execution)
                    
                    # 恢复原始角色名称
                    if original_role_name is not None and self.skill_invoker and hasattr(self.skill_invoker, 'stream_handler'):
                        if self.skill_invoker.stream_handler:
                            self.skill_invoker.stream_handler.role_name = original_role_name
                    
                    return {
                        "success": True,
                        "output": result,
                        "execution_time": execution_time,
                        "retry_count": attempt
                    }
                    
                except Exception as e:
                    last_error = e
                execution_time = time.time() - start_time
                
                # Create execution record for this attempt
                execution = SkillExecution(
                    skill_id=skill_id,
                    input=input_data,
                    output=None,
                    status="failed" if attempt == 0 else "retried",
                    error_type=self.retry_handler._classify_error(e).value,
                    error_message=str(e),
                    execution_time=execution_time,
                    retry_count=attempt,
                    stage_id=stage_id,
                    role_id=role_id
                )
                self.execution_tracker.record_execution(execution)
                
                # Check if should retry
                if not self.retry_handler.should_retry(e, skill, execution):
                    break
                
                # Get retry delay and wait
                retry_config = self.retry_handler.handle_retry(skill_id, input_data, e, skill)
                time.sleep(retry_config['delay'])
        finally:
            # 恢复原始角色名称
            if original_role_name is not None and self.skill_invoker and hasattr(self.skill_invoker, 'stream_handler'):
                if self.skill_invoker.stream_handler:
                    self.skill_invoker.stream_handler.role_name = original_role_name
        
        # All retries exhausted
        error_obj: Exception = last_error if last_error else Exception("Unknown error")
        error_response = self.retry_handler.format_error_response(
            error_obj, skill, retryable=False
        )
        return error_response
    
    def _invoke_skill(self, skill: Skill, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke skill using the configured skill invoker.
        
        Uses the skill_invoker set during initialization:
        - LLMSkillInvoker if llm_client was provided
        - PlaceholderSkillInvoker by default
        - Custom invoker if provided
        
        Args:
            skill: Skill definition to execute
            input_data: Input data for the skill
            
        Returns:
            Dict with execution result
        """
        result = cast(Dict[str, Any], self.skill_invoker.invoke(skill, input_data))
        
        if result.get("success"):
            output = result.get("output", {}) or {}
            if isinstance(output, dict):
                return cast(Dict[str, Any], output)
            return {"output": output}
        else:
            raise WorkflowError(
                f"Skill execution failed: {result.get('error', 'Unknown error')}",
                context={"skill_id": skill.id, "input": input_data}
            )

    def complete_stage(self, stage_id: str) -> Dict[str, Any]:
        """Validate and complete a stage"""
        passed, errors = self.engine.complete_stage(stage_id)
        return {
            "stage": stage_id,
            "quality_gates_passed": passed,
            "errors": errors,
            "result": self.execution_log[-1] if self.execution_log else None
        }

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of automated execution"""
        return {
            "total_stages_executed": len(self.execution_log),
            "agents_used": list(set(log["agent"].role.id for log in self.execution_log)),
            "log": self.execution_log
        }
    
    # ========================================================================
    # Skill Workflow Methods - 多技能工作流执行
    # ========================================================================
    
    def execute_skill_workflow(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        stage_id: Optional[str] = None,
        role_id: Optional[str] = None
    ) -> SkillWorkflowExecution:
        """
        Execute a skill workflow (multi-skill pipeline).
        
        This is the main entry point for executing skill workflows that combine
        multiple skills in a dependency-based execution graph.
        
        Args:
            workflow_id: ID of the skill workflow to execute
            inputs: Initial inputs for the workflow
            stage_id: Optional stage context for tracking
            role_id: Optional role context for tracking
            
        Returns:
            SkillWorkflowExecution with complete execution details
            
        Example:
            >>> result = orchestrator.execute_skill_workflow(
            ...     "feature_delivery",
            ...     {"goal": "Build user auth", "context": {"framework": "FastAPI"}}
            ... )
            >>> print(result.status)  # "completed" or "failed"
            >>> print(result.outputs)  # Final workflow outputs
        """
        return self.workflow_executor.execute_workflow(
            workflow_id=workflow_id,
            inputs=inputs,
            stage_id=stage_id,
            role_id=role_id
        )
    
    def list_skill_workflows(self) -> List[Dict[str, Any]]:
        """
        List all available skill workflows.
        
        Returns:
            List of workflow summaries with id, name, description, and step count
        """
        workflows = []
        for wf_id, wf in self.engine.role_manager.skill_workflows.items():
            workflows.append({
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "steps": len(wf.steps),
                "trigger": {
                    "stage_id": wf.trigger.stage_id,
                    "condition": wf.trigger.condition
                }
            })
        return workflows
    
    def get_skill_workflow(self, workflow_id: str) -> Optional[SkillWorkflow]:
        """
        Get a skill workflow by ID.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            SkillWorkflow or None if not found
        """
        return self.engine.role_manager.skill_workflows.get(workflow_id)
    
    def get_workflow_details(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a skill workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Dict with workflow details including steps, dependencies, and config
        """
        workflow = self.get_skill_workflow(workflow_id)
        if not workflow:
            return None
        
        return {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "trigger": {
                "stage_id": workflow.trigger.stage_id,
                "condition": workflow.trigger.condition,
                "event_type": workflow.trigger.event_type
            },
            "config": {
                "max_parallel": workflow.config.max_parallel,
                "fail_fast": workflow.config.fail_fast,
                "retry_failed_steps": workflow.config.retry_failed_steps,
                "timeout": workflow.config.timeout
            },
            "steps": [
                {
                    "step_id": s.step_id,
                    "skill_id": s.skill_id,
                    "name": s.name,
                    "order": s.order,
                    "depends_on": s.depends_on,
                    "inputs": s.inputs,
                    "outputs": s.outputs
                }
                for s in workflow.steps
            ],
            "outputs": workflow.outputs,
            "execution_order": [s.step_id for s in workflow.topological_sort()]
        }
    
    def execute_stage_with_workflows(
        self,
        stage_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        auto_execute_workflows: bool = True,
        immersive: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a stage and optionally auto-trigger associated skill workflows.
        
        This combines stage execution with automatic skill workflow execution
        for workflows that have auto-trigger configured for this stage.
        
        Args:
            stage_id: Stage ID to execute
            inputs: Optional input data
            auto_execute_workflows: If True, execute workflows with auto-trigger
            immersive: Whether to use immersive display mode
            
        Returns:
            Dict with stage and workflow execution results
        """
        # Get stage object first for display
        stage = self.engine.executor._get_stage_by_id(stage_id) if self.engine.executor else None
        
        # Display stage start if immersive mode enabled
        if immersive and self.immersive_display and stage:
            self.immersive_display.display_stage_start(stage_id, stage.name)
        
        # Execute stage
        stage_result = self.execute_stage(stage_id, inputs)
        
        # Get agent object
        agent = stage_result.get("agent")
        
        workflow_results = []
        stage_summary = []  # Collect stage conclusions
        
        # Create checkpoint before stage execution (optional)
        checkpoint_before = None
        if self.engine.auto_checkpoint and self.engine.workflow:
            try:
                checkpoint_before = self.engine.create_checkpoint(
                    name=f"Before {stage_id}",
                    description=f"Checkpoint before executing stage {stage_id}",
                    stage_id=stage_id,
                    progress_manager=self.immersive_display.progress_manager if self.immersive_display else None
                )
            except Exception as e:
                import warnings
                warnings.warn(f"Failed to create checkpoint: {e}")
        
        if auto_execute_workflows:
            # Find workflows that auto-trigger on this stage
            auto_workflows = self.engine.role_manager.get_workflows_for_stage(stage_id)
            
            # Display progress if immersive mode enabled
            if immersive and self.immersive_display and auto_workflows:
                progress_msg = self.immersive_display.display_stage_progress(
                    stage_id,
                    "执行技能工作流",
                    {"workflows": len(auto_workflows)}
                )
                # display_stage_progress already streams output, no need to print again
            
            for workflow in auto_workflows:
                try:
                    wf_result = self.workflow_executor.execute_workflow(
                        workflow_id=workflow.id,
                        inputs=inputs or {},
                        stage_id=stage_id,
                        role_id=stage_result.get("agent", {}).role.id if stage_result.get("agent") else None
                    )
                    workflow_results.append({
                        "workflow_id": workflow.id,
                        "status": wf_result.status,
                        "outputs": wf_result.outputs,
                        "errors": wf_result.errors
                    })
                    
                    # Collect workflow execution results and format as readable text
                    if wf_result.outputs:
                        summary = self._format_workflow_summary(
                            workflow_id=workflow.id,
                            outputs=wf_result.outputs,
                            stage=stage
                        )
                        if summary:
                            stage_summary.append(summary)
                            
                except Exception as e:
                    workflow_results.append({
                        "workflow_id": workflow.id,
                        "status": "error",
                        "error": str(e)
                    })
        
        # Generate stage output files
        if agent and stage:
            try:
                self._generate_stage_output_files(
                    stage=stage,
                    agent=agent,
                    workflow_results=workflow_results,
                    immersive=immersive
                )
            except Exception as e:
                # Don't fail the entire workflow if file generation fails
                warnings.warn(f"Failed to generate stage output files: {e}")
        
        # Generate conversation summary
        conversation_summary = self._generate_conversation_summary(
            stage=stage,
            agent=agent,
            workflow_results=workflow_results,
            stage_summary=stage_summary
        )
        
        # Display stage completion if immersive mode enabled
        if immersive and self.immersive_display and stage:
            # display_stage_complete already streams output, no need to print again
            self.immersive_display.display_stage_complete(
                stage_id,
                conversation_summary
            )
        
        # Create checkpoint after stage execution (optional)
        if self.engine.auto_checkpoint and self.engine.workflow:
            try:
                self.engine.create_checkpoint(
                    name=f"After {stage_id}",
                    description=f"Checkpoint after executing stage {stage_id}",
                    stage_id=stage_id,
                    progress_manager=self.immersive_display.progress_manager if self.immersive_display else None
                )
            except Exception as e:
                import warnings
                warnings.warn(f"Failed to create checkpoint: {e}")
        
        return {
            **stage_result,
            "skill_workflows": workflow_results,
            "conversation_summary": conversation_summary,
            "stage_summary": stage_summary,
            "checkpoint_before": checkpoint_before.checkpoint_id if checkpoint_before else None
        }
    
    def _generate_stage_output_files(
        self,
        stage: Stage,
        agent: Agent,
        workflow_results: List[Dict[str, Any]],
        immersive: bool = True
    ) -> None:
        """
        Generate output files based on stage.outputs configuration.
        
        Args:
            stage: Stage definition with outputs configuration
            agent: Agent instance for producing outputs
            workflow_results: List of workflow execution results
            immersive: If True, display immersive progress for generated files
        """
        if not stage.outputs:
            return
        
        for output in stage.outputs:
            # Get output path using agent's unified path calculation
            output_path = agent._get_output_path(output.name, output.type, stage.id)
            
            # Check if file already exists (skip if optional and exists)
            if output_path.exists() and not output.required:
                continue  # Optional output already exists, skip
            
            # Extract or generate content
            content = self._extract_or_generate_content(
                output=output,
                workflow_results=workflow_results,
                agent=agent,
                stage=stage
            )
            
            # For required outputs, ensure content is always generated (Lovable workflow pattern)
            if output.required and not content:
                if output.type in ("code", "tests"):
                    # For code outputs, generate a basic template
                    content = self._generate_code_template(output, stage, agent)
                else:
                    # Generate basic template for document/report outputs
                    content = self._generate_basic_template(output, stage)
                
                if not content:
                    # Fallback: create minimal content based on type
                    if output.type in ("code", "tests"):
                        content = f"# {output.name}\n# Generated by workflow system\n# TODO: Implement functionality\n"
                    else:
                        content = f"# {stage.name}\n\n*此文档由工作流系统自动生成，待完善*\n"
            
            # Call agent.produce_output() to save file
            if content:
                try:
                    agent.produce_output(
                        name=output.name,
                        content=content,
                        output_type=output.type,
                        stage_id=stage.id
                    )
                    
                    # Use immersive display if available
                    if immersive and self.immersive_display:
                        output_path = agent._get_output_path(output.name, output.type, stage.id)
                        if output.type in ("code", "tests"):
                            # Display code writing with immersive display (already streams output)
                            self.immersive_display.display_code_written(
                                file_path=str(output_path.relative_to(self.engine.workspace_path)),
                                content=content,
                                stage_id=stage.id
                            )
                        elif output.type in ("document", "report"):
                            # Display document generation with immersive display (already streams output)
                            self.immersive_display.display_document_generated(output.name)
                    
                except Exception as e:
                    if output.required:
                        # For required outputs, raise error instead of warning
                        raise WorkflowError(
                            f"Failed to produce required output file {output.name}: {e}",
                            context={"output": output.name, "stage": stage.id}
                        )
                    else:
                        warnings.warn(f"Failed to produce output file {output.name}: {e}")
    
    def _extract_or_generate_content(
        self,
        output: "Output",
        workflow_results: List[Dict[str, Any]],
        agent: Agent,
        stage: Stage
    ) -> Optional[str]:
        """
        Extract content from skill execution results or generate content.
        
        Args:
            output: Output definition
            workflow_results: List of workflow execution results
            agent: Agent instance
            stage: Stage definition
            
        Returns:
            Content string or None if not found
        """
        # Priority 1: Extract from workflow results
        for wf_result in workflow_results:
            if wf_result.get("outputs"):
                outputs = wf_result["outputs"]
                # Try common content keys
                for key in ["content", "document", "summary", "markdown", "text", output.name, f"{output.name}_content", "code", "file_content"]:
                    if key in outputs:
                        value = outputs[key]
                        if isinstance(value, str):
                            # Check if it's a file path
                            if value.startswith("/") or value.startswith("./") or "/" in value:
                                path = Path(value)
                                if path.exists():
                                    return path.read_text(encoding='utf-8')
                            return value
                        elif isinstance(value, dict):
                            # Try nested content keys
                            for nested_key in ["content", "document", "summary", "text", "body", "code", "file_content"]:
                                if nested_key in value:
                                    nested_value = value[nested_key]
                                    if isinstance(nested_value, str):
                                        # Check if it's a file path
                                        if nested_value.startswith("/") or nested_value.startswith("./") or "/" in nested_value:
                                            path = Path(nested_value)
                                            if path.exists():
                                                return path.read_text(encoding='utf-8')
                                        return nested_value
                            # If dict has string values, format as markdown
                            return f"```json\n{json.dumps(value, indent=2, ensure_ascii=False)}\n```"
                # Try to find file paths in outputs
                for key, value in outputs.items():
                    if isinstance(value, str) and ("/" in value or value.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".yaml", ".yml"))):
                        path = Path(value)
                        if path.exists():
                            return path.read_text(encoding='utf-8')
        
        # Priority 2: Check agent context outputs
        if agent and agent.context and agent.context.outputs:
            if output.name in agent.context.outputs:
                output_path = Path(agent.context.outputs[output.name])
                if output_path.exists():
                    return output_path.read_text(encoding='utf-8')
        
        # Priority 3: Generate basic template if required
        if output.required:
            # Generate a basic template based on stage and output type
            if output.type in ("code", "tests"):
                template = self._generate_code_template(output, stage, agent)
            else:
                template = self._generate_basic_template(output, stage)
            return template
        
        return None
    
    def _generate_basic_template(
        self,
        output: "Output",
        stage: Optional[Stage]
    ) -> str:
        """
        Generate a basic template for required outputs.
        
        Args:
            output: Output definition
            stage: Optional stage definition
            
        Returns:
            Basic template content
        """
        stage_name = stage.name if stage else "Unknown Stage"
        stage_goal = stage.goal_template if stage and stage.goal_template else None
        
        lines = [f"# {stage_name}"]
        lines.append("")
        lines.append(f"**阶段**: {stage_name}")
        if stage_goal:
            lines.append(f"**目标**: {stage_goal}")
        lines.append("")
        lines.append("## 概述")
        lines.append("")
        lines.append("（待完善）")
        lines.append("")
        lines.append("---")
        lines.append(f"*此文档由工作流系统自动生成*")
        return "\n".join(lines)
    
    def _generate_code_template(
        self,
        output: "Output",
        stage: Optional[Stage],
        agent: Optional[Agent] = None
    ) -> str:
        """
        Generate a basic code template for code/test outputs.
        Tries to generate content based on user intent if available.
        
        Args:
            output: Output definition
            stage: Optional stage definition
            agent: Optional agent instance to get user intent
            
        Returns:
            Basic code template content
        """
        file_ext = output.name.split('.')[-1] if '.' in output.name else 'py'
        stage_name = stage.name if stage else "unknown"
        
        # Try to get user intent from engine context
        user_intent = None
        if agent and agent.engine and agent.engine.context:
            user_intent = agent.engine.context.specs.get("user_intent") or agent.engine.context.specs.get("global_goal")
        
        # If we have user intent and it mentions a component/file, try to generate appropriate code
        if user_intent and output.type == "code":
            # Check if user intent mentions the output file name or component name
            output_base = output.name.replace('.py', '').replace('.ts', '').replace('.tsx', '').replace('.js', '').replace('.jsx', '')
            intent_lower = user_intent.lower()
            output_base_lower = output_base.lower()
            
            # If intent mentions the component/file, generate more specific template
            if output_base_lower in intent_lower or any(keyword in intent_lower for keyword in [output_base_lower.replace('_', ''), output_base_lower.replace('-', '')]):
                # Generate component-specific code based on file extension
                if file_ext in ['tsx', 'jsx']:
                    # React component
                    component_name = output_base.replace('-', '').replace('_', '')
                    component_name = ''.join(word.capitalize() for word in component_name.split('-') if word)
                    if not component_name[0].isupper():
                        component_name = component_name[0].upper() + component_name[1:]
                    
                    lines = [
                        f"import React, {{ useState }} from 'react';",
                        "",
                        f"interface {component_name}Props {{",
                        "  // Add props here",
                        "}}",
                        "",
                        f"export const {component_name}: React.FC<{component_name}Props> = ({{}}) => {{",
                        "  // Component implementation",
                        "  return (",
                        "    <div>",
                        f"      <h1>{component_name}</h1>",
                        "      {/* Add component content here */}",
                        "    </div>",
                        "  );",
                        "};",
                        "",
                        f"export default {component_name};",
                        ""
                    ]
                    return "\n".join(lines)
                elif file_ext in ['ts', 'js']:
                    # TypeScript/JavaScript module
                    lines = [
                        f"// {output.name}",
                        f"// Generated based on user intent: {user_intent}",
                        "",
                        "// TODO: Implement functionality based on requirements",
                        "",
                        "export function main() {{",
                        "  // Implementation here",
                        "}}",
                        ""
                    ]
                    return "\n".join(lines)
        
        # Default template based on file type
        if output.type == "tests":
            # Test file template
            lines = [
                f"# Test file: {output.name}",
                f"# Generated by workflow system for stage: {stage_name}",
                "",
                "import pytest",
                "",
                "",
                "def test_example():",
                "    \"\"\"Example test case\"\"\"",
                "    # TODO: Implement test cases",
                "    pass",
                ""
            ]
        else:
            # Code file template
            if file_ext in ['tsx', 'jsx']:
                # React component default
                component_name = output.name.replace('.tsx', '').replace('.jsx', '')
                component_name = ''.join(word.capitalize() for word in component_name.split('-') if word)
                lines = [
                    f"import React from 'react';",
                    "",
                    f"export const {component_name} = () => {{",
                    "  return <div>{component_name}</div>;",
                    "}};",
                    ""
                ]
            elif file_ext in ['ts', 'js']:
                lines = [
                    f"// {output.name}",
                    f"// Generated by workflow system for stage: {stage_name}",
                    "",
                    "// TODO: Implement functionality",
                    "",
                    "export function main() {{",
                    "  // Implementation here",
                    "}}",
                    ""
                ]
            else:
                # Python default
                lines = [
                    f"# {output.name}",
                    f"# Generated by workflow system for stage: {stage_name}",
                    "",
                    "from typing import Any, Dict, List, Optional",
                    "",
                    "",
                    "def main():",
                    "    \"\"\"Main entry point\"\"\"",
                    "    # TODO: Implement functionality",
                    "    pass",
                    "",
                    "",
                    "if __name__ == '__main__':",
                    "    main()",
                    ""
                ]
        return "\n".join(lines)
    
    def _format_workflow_summary(
        self,
        workflow_id: str,
        outputs: Dict[str, Any],
        stage: Optional[Stage]
    ) -> Optional[str]:
        """
        Format workflow outputs as readable markdown text.
        
        Args:
            workflow_id: Workflow ID
            outputs: Workflow outputs dictionary
            stage: Optional stage definition
            
        Returns:
            Formatted markdown text or None
        """
        if not outputs:
            return None
        
        parts = []
        
        # Try to extract key information
        for key, value in outputs.items():
            if isinstance(value, dict):
                # If dict, try to extract document content
                if "content" in value:
                    parts.append(f"### {key}\n{value['content']}")
                elif "document" in value:
                    parts.append(f"### {key}\n{value['document']}")
                elif "summary" in value:
                    parts.append(f"### {key}\n{value['summary']}")
                elif "markdown" in value:
                    parts.append(f"### {key}\n{value['markdown']}")
                else:
                    # Format entire dict
                    parts.append(f"### {key}\n```json\n{json.dumps(value, indent=2, ensure_ascii=False)}\n```")
            elif isinstance(value, str):
                parts.append(f"### {key}\n{value}")
            else:
                parts.append(f"### {key}\n{str(value)}")
        
        return "\n\n".join(parts) if parts else None
    
    def _generate_conversation_summary(
        self,
        stage: Optional[Stage],
        agent: Optional[Agent],
        workflow_results: List[Dict[str, Any]],
        stage_summary: List[str]
    ) -> str:
        """
        Generate conversation summary for stage execution.
        
        Args:
            stage: Optional stage definition
            agent: Optional agent instance
            workflow_results: List of workflow execution results
            stage_summary: List of formatted workflow summaries
            
        Returns:
            Formatted markdown summary
        """
        if not stage:
            return ""
        
        parts = []
        
        # Stage title
        parts.append(f"## {stage.name}")
        
        # Stage goal
        if stage.goal_template:
            parts.append(f"\n**目标**: {stage.goal_template}")
        
        # Skill execution results summary
        if stage_summary:
            parts.append("\n### 执行结果\n")
            parts.extend(stage_summary)
        
        # If no documents generated, create an execution summary
        if not stage_summary and workflow_results:
            parts.append("\n### 执行摘要\n")
            for wf_result in workflow_results:
                if wf_result.get("status") == "completed":
                    parts.append(f"- ✅ 工作流 `{wf_result.get('workflow_id')}` 执行成功")
                    if wf_result.get("outputs"):
                        parts.append(f"  输出: {len(wf_result['outputs'])} 项")
                elif wf_result.get("status") == "failed":
                    parts.append(f"- ❌ 工作流 `{wf_result.get('workflow_id')}` 执行失败")
                    if wf_result.get("error"):
                        parts.append(f"  错误: {wf_result['error']}")
                elif wf_result.get("status") == "error":
                    parts.append(f"- ❌ 工作流 `{wf_result.get('workflow_id')}` 执行出错")
                    if wf_result.get("error"):
                        parts.append(f"  错误: {wf_result['error']}")
        
        # Agent decisions (if any)
        if agent and agent.context and agent.context.decisions:
            parts.append("\n### 关键决策\n")
            for decision in agent.context.decisions:
                parts.append(f"- {decision}")
        
        return "\n".join(parts)
    
    # ========================================================================
    # Parallel Execution Methods - 并行执行
    # ========================================================================
    
    async def execute_parallel_stages(
        self,
        stage_ids: List[str],
        inputs: Optional[Dict[str, Any]] = None,
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        Execute multiple stages in parallel (asynchronous).
        
        Stages without dependencies can run in parallel.
        Stages with dependencies will wait for their dependencies to complete.
        
        Args:
            stage_ids: List of stage IDs to execute
            inputs: Optional input data
            use_llm: If True and llm_client is set, will generate LLM prompt
            
        Returns:
            Dict mapping stage_id to execution result
        """
        if not self.engine.executor:
            raise WorkflowError("Workflow executor not initialized")
        
        # Build dependency graph
        stage_deps: Dict[str, List[str]] = {}
        stage_map: Dict[str, Stage] = {}
        
        for stage_id in stage_ids:
            stage = self.engine.executor._get_stage_by_id(stage_id)
            if not stage:
                raise WorkflowError(f"Stage '{stage_id}' not found")
            stage_map[stage_id] = stage
            # Get dependencies from prerequisites
            deps = []
            for prereq in stage.prerequisites:
                if prereq in stage_ids:
                    deps.append(prereq)
            stage_deps[stage_id] = deps
        
        # Track execution results
        results: Dict[str, Any] = {}
        completed: set = set()
        
        async def execute_stage_async(stage_id: str):
            """Execute a single stage asynchronously"""
            # Wait for dependencies
            deps = stage_deps.get(stage_id, [])
            while not all(dep in completed for dep in deps):
                await asyncio.sleep(0.1)  # Small delay to avoid busy waiting
            
            # Execute stage
            try:
                result = self.execute_stage(stage_id, inputs, use_llm)
                results[stage_id] = result
                completed.add(stage_id)
            except Exception as e:
                results[stage_id] = {
                    "stage": stage_id,
                    "status": "failed",
                    "error": str(e)
                }
                completed.add(stage_id)
        
        # Create tasks for all stages
        tasks = [execute_stage_async(stage_id) for stage_id in stage_ids]
        
        # Execute all tasks concurrently
        await asyncio.gather(*tasks)
        
        return results
    
    def execute_parallel_stages_sync(
        self,
        stage_ids: List[str],
        inputs: Optional[Dict[str, Any]] = None,
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        Execute multiple stages in parallel (synchronous wrapper).
        
        This is a synchronous wrapper around execute_parallel_stages().
        
        Args:
            stage_ids: List of stage IDs to execute
            inputs: Optional input data
            use_llm: If True and llm_client is set, will generate LLM prompt
            
        Returns:
            Dict mapping stage_id to execution result
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.execute_parallel_stages(stage_ids, inputs, use_llm)
        )
    
    def execute_with_collaboration(
        self,
        goal: str,
        role_ids: Optional[List[str]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a goal with multiple agents collaborating.
        
        This method:
        1. Decomposes the goal into tasks
        2. Assigns tasks to appropriate agents
        3. Coordinates execution through message bus
        4. Supports agent-to-agent feedback and review
        
        Args:
            goal: High-level goal to achieve
            role_ids: Optional list of role IDs to use (defaults to all available)
            inputs: Optional input data
            use_llm: If True and llm_client is set, will use LLM for decomposition
            
        Returns:
            Dict with execution results and collaboration summary
        """
        # Get available roles
        if role_ids:
            available_roles = [
                self.engine.role_manager.get_role(role_id)
                for role_id in role_ids
                if self.engine.role_manager.get_role(role_id)
            ]
        else:
            available_roles = list(self.engine.role_manager.roles.values())
        
        if not available_roles:
            raise WorkflowError("No available roles for collaboration")
        
        # Decompose goal into tasks
        decomposition = self.task_decomposer.decompose(goal, available_roles, inputs)
        
        # Create agents for each task
        agents: Dict[str, Agent] = {}
        agent_tasks: Dict[str, str] = {}  # Map agent_id to task_id
        
        for task in decomposition.tasks:
            role = self.engine.role_manager.get_role(task.assigned_role)
            if not role:
                continue
            
            agent = Agent(role, self.engine, self.skill_selector, self.message_bus)
            agents[agent.agent_id] = agent
            agent_tasks[agent.agent_id] = task.id
        
        # Update execution state with active agents
        if self.engine.executor:
            self.engine.executor.state.active_agents = list(agents.keys())
        
        # Execute tasks in order
        execution_results: Dict[str, Any] = {}
        task_results: Dict[str, Any] = {}
        
        for task_id in decomposition.execution_order:
            task = decomposition.get_task(task_id)
            if not task:
                continue
            
            # Find agent for this task
            agent_id = None
            for aid, tid in agent_tasks.items():
                if tid == task_id:
                    agent_id = aid
                    break
            
            if not agent_id or agent_id not in agents:
                continue
            
            agent = agents[agent_id]
            
            # Prepare agent
            combined_inputs = dict(inputs or {})
            combined_inputs.update(task.inputs)
            agent.prepare(task.description, combined_inputs)
            
            # Check for messages from other agents
            messages = agent.check_messages()
            if messages:
                print(f"📨 Agent {agent.agent_id} received {len(messages)} message(s) before execution")
            
            # Execute task (simplified - in real implementation would execute skills)
            try:
                # Mark task as in progress
                task.status = "in_progress"
                
                # Share context with other agents
                agent.share_context()
                
                # Simulate task execution
                # In real implementation, this would select and execute skills
                result = {
                    "task_id": task_id,
                    "agent_id": agent_id,
                    "status": "completed",
                    "outputs": {}
                }
                
                task.status = "completed"
                task_results[task_id] = result
                execution_results[agent_id] = result
                
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                result = {
                    "task_id": task_id,
                    "agent_id": agent_id,
                    "status": "failed",
                    "error": str(e)
                }
                task_results[task_id] = result
                execution_results[agent_id] = result
        
        return {
            "goal": goal,
            "decomposition": decomposition,
            "agents": {aid: {"role": agent.role.id, "agent_id": aid} for aid, agent in agents.items()},
            "task_results": task_results,
            "execution_results": execution_results,
            "collaboration_summary": {
                "total_tasks": len(decomposition.tasks),
                "completed_tasks": len([t for t in decomposition.tasks if t.status == "completed"]),
                "failed_tasks": len([t for t in decomposition.tasks if t.status == "failed"]),
                "active_agents": list(agents.keys())
            }
        }
    
    def _create_agent_pool(self, roles: List[Role]) -> Dict[str, Agent]:
        """
        Create a pool of agents for parallel execution.
        
        Args:
            roles: List of roles to create agents for
            
        Returns:
            Dictionary mapping agent_id to Agent instance
        """
        agents = {}
        for role in roles:
            agent = Agent(role, self.engine, self.skill_selector, self.message_bus)
            agents[agent.agent_id] = agent
        return agents
    
    async def _wait_for_dependencies(
        self,
        task_id: str,
        dependencies: List[str],
        completed: set
    ):
        """
        Wait for task dependencies to complete.
        
        Args:
            task_id: Task ID waiting for dependencies
            dependencies: List of dependency task IDs
            completed: Set of completed task IDs
        """
        while not all(dep in completed for dep in dependencies):
            await asyncio.sleep(0.1)


