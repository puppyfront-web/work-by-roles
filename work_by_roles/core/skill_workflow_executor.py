"""
Skill workflow executor for orchestrating multiple skills.
Following Single Responsibility Principle - handles skill workflow execution only.
"""

from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import time

from .exceptions import WorkflowError
from .enums import SkillWorkflowStepStatus
from .models import (
    Skill, SkillExecution, SkillStep, SkillWorkflow, SkillWorkflowExecution
)
from .execution_tracker import ExecutionTracker
from .skill_selector import SkillSelector
from .condition_evaluator import ConditionEvaluator
from .workflow_engine import WorkflowEngine
from .skill_invoker import SkillInvoker, PlaceholderSkillInvoker

class SkillWorkflowExecutor:
    """
    Executes skill workflows by orchestrating multiple skills according to their dependencies.
    
    Features:
    - DAG-based execution respecting dependencies
    - Parallel execution of independent steps
    - Variable resolution for input/output chaining
    - Retry handling for failed steps
    - Execution tracking and reporting
    """
    
    def __init__(
        self,
        engine: 'WorkflowEngine',
        skill_invoker: Optional[SkillInvoker] = None,
        execution_tracker: Optional[ExecutionTracker] = None,
        max_parallel: int = 2
    ):
        """
        Initialize workflow executor.
        
        Args:
            engine: WorkflowEngine instance
            skill_invoker: Skill invoker to use (defaults to PlaceholderSkillInvoker)
            execution_tracker: Optional execution tracker
            max_parallel: Maximum parallel step executions
        """
        self.engine = engine
        self.skill_invoker = skill_invoker or PlaceholderSkillInvoker()
        self.execution_tracker = execution_tracker or ExecutionTracker()
        self.max_parallel = max_parallel
        
        # Execution state
        self._step_outputs: Dict[str, Dict[str, Any]] = {}
        self._current_execution: Optional[SkillWorkflowExecution] = None
    
    def execute_workflow(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        stage_id: Optional[str] = None,
        role_id: Optional[str] = None
    ) -> SkillWorkflowExecution:
        """
        Execute a skill workflow.
        
        Args:
            workflow_id: ID of the workflow to execute
            inputs: Initial inputs for the workflow
            stage_id: Optional stage context
            role_id: Optional role context
            
        Returns:
            SkillWorkflowExecution record
        """
        # Get workflow definition
        workflow = self.engine.role_manager.skill_workflows.get(workflow_id)
        if not workflow:
            raise WorkflowError(f"Skill workflow '{workflow_id}' not found")
        
        # Initialize execution
        execution = SkillWorkflowExecution(
            workflow_id=workflow_id,
            status="running",
            inputs=inputs.copy()
        )
        self._current_execution = execution
        self._step_outputs = {}
        
        start_time = time.time()
        
        try:
            # Reset step states
            for step in workflow.steps:
                step.status = SkillWorkflowStepStatus.PENDING
                step.result = None
                step.error = None
            
            # Create condition evaluator
            evaluator = ConditionEvaluator(self._step_outputs, inputs)
            
            # Execute steps with support for conditions and loops
            executed_steps = set()
            step_queue = workflow.topological_sort()
            
            while step_queue:
                step = step_queue.pop(0)
                
                # Skip if already executed
                if step.step_id in executed_steps:
                    continue
                
                # Check if dependencies are met
                if not self._check_dependencies_met(step, workflow, executed_steps):
                    # Re-add to queue for later processing
                    step_queue.append(step)
                    continue
                
                # Check for early termination
                if workflow.config.fail_fast and execution.errors:
                    step.status = SkillWorkflowStepStatus.SKIPPED
                    executed_steps.add(step.step_id)
                    continue
                
                # Check step condition
                if step.condition:
                    if not evaluator.evaluate(step.condition):
                        step.status = SkillWorkflowStepStatus.SKIPPED
                        executed_steps.add(step.step_id)
                        continue
                
                # Handle loops
                if step.loop_config:
                    self._execute_loop_step(step, workflow, inputs, stage_id, role_id, evaluator)
                else:
                    # Execute step normally
                    self._execute_step(step, workflow, inputs, stage_id, role_id)
                
                # Store results
                execution.step_results[step.step_id] = {
                    "status": step.status.value,
                    "result": step.result,
                    "error": step.error,
                    "execution_time": step.execution_time,
                    "iteration_count": getattr(step, 'iteration_count', 0)
                }
                
                if step.status == SkillWorkflowStepStatus.FAILED:
                    execution.errors.append(f"Step '{step.step_id}' failed: {step.error}")
                
                # Mark as executed
                executed_steps.add(step.step_id)
                
                # Handle conditional branches
                if step.branches:
                    next_step_id = self._evaluate_branches(step, workflow, evaluator)
                    if next_step_id:
                        next_step = workflow.get_step(next_step_id)
                        if next_step and next_step_id not in executed_steps:
                            # Insert next step at the beginning of queue
                            step_queue.insert(0, next_step)
            
            # Resolve final outputs
            execution.outputs = self._resolve_workflow_outputs(workflow)
            
            # Determine final status
            failed_required = any(
                s.status == SkillWorkflowStepStatus.FAILED and s.config.required
                for s in workflow.steps
            )
            all_completed = all(
                s.status in (SkillWorkflowStepStatus.COMPLETED, SkillWorkflowStepStatus.SKIPPED)
                for s in workflow.steps
            )
            
            if failed_required:
                execution.status = "failed"
            elif all_completed:
                execution.status = "completed"
            else:
                execution.status = "partial"
            
        except Exception as e:
            execution.status = "failed"
            execution.errors.append(str(e))
        
        execution.completed_at = datetime.now()
        execution.execution_time = time.time() - start_time
        self._current_execution = None
        
        return execution
    
    def _check_dependencies_met(
        self,
        step: SkillStep,
        workflow: SkillWorkflow,
        executed_steps: Set[str]
    ) -> bool:
        """Check if all step dependencies are met"""
        for dep_id in step.depends_on:
            if dep_id not in executed_steps:
                return False
            dep_step = workflow.get_step(dep_id)
            if dep_step and dep_step.status == SkillWorkflowStepStatus.FAILED:
                # If dependency failed and step is required, mark as failed
                if step.config.required:
                    step.status = SkillWorkflowStepStatus.FAILED
                    step.error = f"Dependency '{dep_id}' failed"
                    return True
        return True
    
    def _wait_for_dependencies(
        self,
        step: SkillStep,
        workflow: SkillWorkflow
    ) -> None:
        """Wait for step dependencies to complete (legacy method)"""
        for dep_id in step.depends_on:
            dep_step = workflow.get_step(dep_id)
            if dep_step and dep_step.status not in (
                SkillWorkflowStepStatus.COMPLETED,
                SkillWorkflowStepStatus.FAILED,
                SkillWorkflowStepStatus.SKIPPED
            ):
                # In a real async implementation, we would wait here
                # For now, topological sort ensures this won't happen
                pass
    
    def _evaluate_branches(
        self,
        step: SkillStep,
        workflow: SkillWorkflow,
        evaluator: ConditionEvaluator
    ) -> Optional[str]:
        """Evaluate conditional branches and return next step ID"""
        for branch in step.branches:
            if evaluator.evaluate(branch.condition):
                return branch.target_step_id
            elif branch.else_step_id:
                return branch.else_step_id
        return None
    
    def _execute_loop_step(
        self,
        step: SkillStep,
        workflow: SkillWorkflow,
        inputs: Dict[str, Any],
        stage_id: Optional[str],
        role_id: Optional[str],
        evaluator: ConditionEvaluator
    ) -> None:
        """Execute a step with loop configuration"""
        if not step.loop_config:
            return
        
        loop_config = step.loop_config
        step.iteration_count = 0
        total_time = 0.0
        
        if loop_config.type == "while":
            # While loop: execute until condition is false
            while step.iteration_count < loop_config.max_iterations:
                condition_result = evaluator.evaluate(loop_config.condition) if loop_config.condition else True
                if not condition_result:
                    break
                
                # Execute step
                step.status = SkillWorkflowStepStatus.RUNNING
                step_start = time.time()
                self._execute_step(step, workflow, inputs, stage_id, role_id)
                step_execution_time = time.time() - step_start
                total_time += step_execution_time
                
                step.iteration_count += 1
                
                # Check if we should break on failure
                if step.status == SkillWorkflowStepStatus.FAILED and loop_config.break_on_failure:
                    break
                
                # Update step outputs for next iteration
                if step.result:
                    self._step_outputs[step.step_id] = step.result
        
        elif loop_config.type == "for_each":
            # For each loop: iterate over items
            items = self._get_loop_items(loop_config.items_source, evaluator)
            
            if not isinstance(items, list):
                step.status = SkillWorkflowStepStatus.FAILED
                step.error = f"Items source '{loop_config.items_source}' is not a list"
                return
            
            for item in items:
                if step.iteration_count >= loop_config.max_iterations:
                    break
                
                # Add current item to inputs
                loop_inputs = inputs.copy()
                loop_inputs["_loop_item"] = item
                loop_inputs["_loop_index"] = step.iteration_count
                
                # Execute step
                step.status = SkillWorkflowStepStatus.RUNNING
                step_start = time.time()
                self._execute_step(step, workflow, loop_inputs, stage_id, role_id)
                step_execution_time = time.time() - step_start
                total_time += step_execution_time
                
                step.iteration_count += 1
                
                # Check if we should break on failure
                if step.status == SkillWorkflowStepStatus.FAILED and loop_config.break_on_failure:
                    break
        
        # Mark as completed if not failed
        if step.status == SkillWorkflowStepStatus.RUNNING:
            step.status = SkillWorkflowStepStatus.COMPLETED
        step.execution_time = total_time
    
    def _get_loop_items(self, items_source: Optional[str], evaluator: ConditionEvaluator) -> Any:
        """Get items for for_each loop"""
        if not items_source:
            return []
        
        # Resolve variable reference
        import re
        step_match = re.match(r'step\.(\w+)\.(.*)', items_source)
        if step_match:
            step_id = step_match.group(1)
            path = step_match.group(2)
            
            if step_id in self._step_outputs:
                step_data = self._step_outputs[step_id]
                # Navigate through path
                parts = path.split('.')
                current = step_data
                for part in parts:
                    if isinstance(current, dict):
                        current = current.get(part)
                    elif hasattr(current, part):
                        current = getattr(current, part)
                    else:
                        return []
                    if current is None:
                        return []
                return current if isinstance(current, list) else []
        
        return []
    
    def _select_dynamic_skill(
        self,
        step: SkillStep,
        workflow: SkillWorkflow,
        workflow_inputs: Dict[str, Any],
        role_id: Optional[str]
    ) -> Optional[Skill]:
        """Select a skill dynamically based on context"""
        if not step.skill_selector_config:
            return None
        
        # Get role for skill selection
        role = None
        if role_id:
            role = self.engine.role_manager.get_role(role_id)
        if not role:
            # Try to get role from workflow context or use a default
            return None
        
        # Build task description from config
        task_description = step.skill_selector_config.get("task", "")
        if not task_description:
            # Try to resolve from step inputs or workflow inputs
            task_description = step.skill_selector_config.get("task_template", "")
            if task_description:
                # Resolve variables in task description
                evaluator = ConditionEvaluator(self._step_outputs, workflow_inputs)
                task_description = evaluator._resolve_variables(task_description)
        
        # Build context for skill selection
        context = step.skill_selector_config.get("context", {})
        if isinstance(context, dict):
            # Resolve context variables
            evaluator = ConditionEvaluator(self._step_outputs, workflow_inputs)
            resolved_context = {}
            for key, value in context.items():
                if isinstance(value, str):
                    resolved_context[key] = evaluator._resolve_variables(value)
                else:
                    resolved_context[key] = value
            context = resolved_context
        
        # Add workflow context
        context["workflow_id"] = workflow.id
        context["step_id"] = step.step_id
        if self.engine.context:
            context["project_context"] = self.engine.context
        
        # Use SkillSelector to select skill
        skill_selector = SkillSelector(self.engine, self.execution_tracker)
        selected_skill = skill_selector.select_skill(
            task_description=task_description,
            role=role,
            context=context
        )
        
        return selected_skill
    
    def _execute_step(
        self,
        step: SkillStep,
        workflow: SkillWorkflow,
        workflow_inputs: Dict[str, Any],
        stage_id: Optional[str],
        role_id: Optional[str]
    ) -> None:
        """Execute a single step"""
        step.status = SkillWorkflowStepStatus.RUNNING
        start_time = time.time()
        
        try:
            # Handle dynamic skill selection
            if step.dynamic_skill:
                skill = self._select_dynamic_skill(step, workflow, workflow_inputs, role_id)
                if skill:
                    step.selected_skill_id = skill.id
                else:
                    # Try fallback skill
                    if step.fallback_skill_id:
                        skill = self.engine.role_manager.skill_library.get(step.fallback_skill_id)
                        if skill:
                            step.selected_skill_id = step.fallback_skill_id
                        else:
                            raise WorkflowError(f"Dynamic skill selection failed and fallback skill '{step.fallback_skill_id}' not found")
                    else:
                        raise WorkflowError("Dynamic skill selection failed and no fallback skill specified")
            else:
                # Use static skill_id
                if not self.engine.role_manager.skill_library:
                    raise WorkflowError("Skill library not loaded")
                
                skill = self.engine.role_manager.skill_library.get(step.skill_id)
                if not skill:
                    raise WorkflowError(f"Skill '{step.skill_id}' not found")
            
            # Resolve inputs
            resolved_inputs = self._resolve_step_inputs(step, workflow_inputs)
            
            # Execute with retry
            max_retries = step.config.max_retries if step.config.retry_on_failure else 0
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    result = self.skill_invoker.invoke(skill, resolved_inputs)
                    
                    if result.get("success"):
                        step.result = result.get("output", {}) or {}
                        step.status = SkillWorkflowStepStatus.COMPLETED
                        
                        # Store outputs for downstream steps
                        self._step_outputs[step.step_id] = step.result
                        
                        # Record execution
                        executed_skill_id = step.selected_skill_id if step.dynamic_skill else step.skill_id
                        execution = SkillExecution(
                            skill_id=executed_skill_id,
                            input=resolved_inputs,
                            output=step.result,
                            status="success",
                            execution_time=time.time() - start_time,
                            stage_id=stage_id,
                            role_id=role_id,
                            retry_count=attempt
                        )
                        self.execution_tracker.record_execution(execution)
                        return
                    else:
                        last_error = result.get("error", "Unknown error")
                        if attempt < max_retries:
                            time.sleep(2 ** attempt)  # Exponential backoff
                        
                except Exception as e:
                    last_error = str(e)
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
            
            # All retries exhausted
            step.status = SkillWorkflowStepStatus.FAILED
            step.error = last_error
            
        except Exception as e:
            step.status = SkillWorkflowStepStatus.FAILED
            step.error = str(e)
        
        step.execution_time = time.time() - start_time
    
    def _resolve_step_inputs(
        self,
        step: SkillStep,
        workflow_inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve input variable references for a step"""
        resolved = {}
        
        for key, value in step.inputs.items():
            if isinstance(value, str):
                resolved[key] = self._resolve_variable(value, workflow_inputs)
            else:
                resolved[key] = value
        
        return resolved
    
    def _resolve_variable(
        self,
        var_ref: str,
        workflow_inputs: Dict[str, Any]
    ) -> Any:
        """
        Resolve a variable reference.
        
        Supports:
        - {{workflow.inputs.xxx}} - Workflow input
        - {{steps.step_id.outputs.xxx}} - Step output
        """
        import re
        
        # Check for workflow inputs
        workflow_match = re.match(r'\{\{workflow\.inputs\.(\w+)\}\}', var_ref)
        if workflow_match:
            key = workflow_match.group(1)
            return workflow_inputs.get(key, var_ref)
        
        # Check for step outputs
        step_match = re.match(r'\{\{steps\.(\w+)\.outputs\.(\w+)\}\}', var_ref)
        if step_match:
            step_id = step_match.group(1)
            output_key = step_match.group(2)
            
            if step_id in self._step_outputs:
                return self._step_outputs[step_id].get(output_key, var_ref)
            return var_ref
        
        # Return as-is if not a variable reference
        return var_ref
    
    def _resolve_workflow_outputs(
        self,
        workflow: SkillWorkflow
    ) -> Dict[str, Any]:
        """Resolve final workflow output mappings"""
        resolved = {}
        
        for key, var_ref in workflow.outputs.items():
            resolved[key] = self._resolve_variable(var_ref, {})
        
        return resolved
    
    def get_workflow_status(
        self,
        workflow: SkillWorkflow
    ) -> Dict[str, Any]:
        """Get current status of a workflow execution"""
        return {
            "workflow_id": workflow.id,
            "steps": [
                {
                    "step_id": s.step_id,
                    "skill_id": s.skill_id,
                    "status": s.status.value,
                    "execution_time": s.execution_time
                }
                for s in workflow.steps
            ],
            "completed": sum(1 for s in workflow.steps 
                           if s.status == SkillWorkflowStepStatus.COMPLETED),
            "failed": sum(1 for s in workflow.steps 
                         if s.status == SkillWorkflowStepStatus.FAILED),
            "pending": sum(1 for s in workflow.steps 
                          if s.status == SkillWorkflowStepStatus.PENDING)
        }


