"""
Task Decomposer for breaking down goals into subtasks.
Following Single Responsibility Principle - handles task decomposition only.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path

from .exceptions import WorkflowError
from .models import Task, TaskDecomposition, Role
from .workflow_engine import WorkflowEngine


class TaskDecomposer:
    """
    Decomposes high-level goals into subtasks and assigns them to appropriate roles.
    
    Supports two modes:
    - LLM mode: Uses LLM for intelligent task decomposition
    - Rule mode: Uses predefined rules for decomposition (fallback)
    """
    
    def __init__(
        self,
        engine: 'WorkflowEngine',
        llm_client: Optional[Any] = None
    ):
        """
        Initialize Task Decomposer.
        
        Args:
            engine: WorkflowEngine instance
            llm_client: Optional LLM client for intelligent decomposition
        """
        self.engine = engine
        self.llm_client = llm_client
        self.llm_enabled = llm_client is not None
    
    def decompose(
        self,
        goal: str,
        available_roles: Optional[List[Role]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> TaskDecomposition:
        """
        Decompose a goal into subtasks.
        
        Args:
            goal: High-level goal to decompose
            available_roles: List of available roles (defaults to all roles in engine)
            context: Optional context information
            
        Returns:
            TaskDecomposition with tasks and execution order
            
        Raises:
            WorkflowError: If decomposition fails or is invalid
        """
        if available_roles is None:
            available_roles = list(self.engine.role_manager.roles.values())
        
        # Try LLM decomposition first if available
        if self.llm_enabled:
            try:
                return self._decompose_with_llm(goal, available_roles, context)
            except Exception as e:
                # Fallback to rule-based decomposition
                print(f"⚠️ LLM decomposition failed, falling back to rule-based: {e}")
        
        # Rule-based decomposition
        return self._decompose_with_rules(goal, available_roles, context)
    
    def _decompose_with_llm(
        self,
        goal: str,
        available_roles: List[Role],
        context: Optional[Dict[str, Any]]
    ) -> TaskDecomposition:
        """
        Decompose using LLM (intelligent mode).
        
        This would use the LLM to intelligently break down the goal.
        For now, this is a placeholder that falls back to rule-based.
        """
        # TODO: Implement LLM-based decomposition
        # This would involve:
        # 1. Creating a prompt with goal, available roles, and context
        # 2. Calling LLM to generate task breakdown
        # 3. Parsing LLM response into Task objects
        # 4. Validating and returning TaskDecomposition
        
        # For now, fallback to rule-based
        return self._decompose_with_rules(goal, available_roles, context)
    
    def _decompose_with_rules(
        self,
        goal: str,
        available_roles: List[Role],
        context: Optional[Dict[str, Any]]
    ) -> TaskDecomposition:
        """
        Decompose using predefined rules (fallback mode).
        
        This uses simple heuristics to break down tasks based on:
        - Role capabilities and constraints
        - Common workflow patterns
        - Task dependencies
        """
        tasks: List[Task] = []
        task_counter = 1
        
        # Analyze goal to identify key components
        goal_lower = goal.lower()
        
        # Check if goal matches common patterns
        if any(keyword in goal_lower for keyword in ["需求", "requirement", "分析", "analyze"]):
            # Requirements analysis task
            analyst_role = self._find_role_by_keywords(available_roles, ["analyst", "需求", "product"])
            if analyst_role:
                tasks.append(Task(
                    id=f"task_{task_counter}",
                    description=f"分析需求: {goal}",
                    assigned_role=analyst_role.id,
                    status="pending",
                    priority=1
                ))
                task_counter += 1
        
        if any(keyword in goal_lower for keyword in ["架构", "architecture", "设计", "design"]):
            # Architecture design task
            architect_role = self._find_role_by_keywords(available_roles, ["architect", "架构", "system"])
            if architect_role:
                deps = [t.id for t in tasks if "analyst" in t.assigned_role.lower() or "需求" in t.assigned_role.lower()]
                tasks.append(Task(
                    id=f"task_{task_counter}",
                    description=f"设计架构: {goal}",
                    assigned_role=architect_role.id,
                    dependencies=deps,
                    status="pending",
                    priority=2
                ))
                task_counter += 1
        
        if any(keyword in goal_lower for keyword in ["实现", "implement", "开发", "develop", "代码", "code"]):
            # Implementation task
            engineer_role = self._find_role_by_keywords(available_roles, ["engineer", "开发", "implement", "core"])
            if engineer_role:
                deps = [t.id for t in tasks if "architect" in t.assigned_role.lower() or "架构" in t.assigned_role.lower()]
                tasks.append(Task(
                    id=f"task_{task_counter}",
                    description=f"实现功能: {goal}",
                    assigned_role=engineer_role.id,
                    dependencies=deps,
                    status="pending",
                    priority=3
                ))
                task_counter += 1
        
        if any(keyword in goal_lower for keyword in ["测试", "test", "验证", "validate", "质量", "quality"]):
            # Testing/QA task
            qa_role = self._find_role_by_keywords(available_roles, ["qa", "测试", "quality", "reviewer"])
            if qa_role:
                deps = [t.id for t in tasks if "engineer" in t.assigned_role.lower() or "开发" in t.assigned_role.lower()]
                tasks.append(Task(
                    id=f"task_{task_counter}",
                    description=f"测试验证: {goal}",
                    assigned_role=qa_role.id,
                    dependencies=deps,
                    status="pending",
                    priority=4
                ))
                task_counter += 1
        
        # If no specific pattern matched, create a generic task
        if not tasks:
            # Assign to first available role or a general role
            default_role = available_roles[0] if available_roles else None
            if default_role:
                tasks.append(Task(
                    id=f"task_{task_counter}",
                    description=goal,
                    assigned_role=default_role.id,
                    status="pending",
                    priority=1
                ))
        
        # Build execution order based on dependencies
        execution_order = self._build_execution_order(tasks)
        
        # Build dependency map
        dependencies = {task.id: task.dependencies for task in tasks}
        
        # Calculate total estimated time
        total_time = sum(task.estimated_time or 0 for task in tasks)
        
        decomposition = TaskDecomposition(
            tasks=tasks,
            execution_order=execution_order,
            dependencies=dependencies,
            total_estimated_time=total_time if total_time > 0 else None
        )
        
        # Validate decomposition
        errors = decomposition.validate()
        if errors:
            raise WorkflowError(f"Invalid task decomposition: {'; '.join(errors)}")
        
        return decomposition
    
    def _find_role_by_keywords(
        self,
        roles: List[Role],
        keywords: List[str]
    ) -> Optional[Role]:
        """Find a role matching any of the keywords"""
        for role in roles:
            role_text = f"{role.id} {role.name} {role.description}".lower()
            if any(keyword.lower() in role_text for keyword in keywords):
                return role
        return None
    
    def _build_execution_order(self, tasks: List[Task]) -> List[str]:
        """
        Build execution order respecting dependencies (topological sort).
        
        Args:
            tasks: List of tasks
            
        Returns:
            List of task IDs in execution order
        """
        # Build dependency graph
        in_degree = {task.id: 0 for task in tasks}
        graph: Dict[str, List[str]] = {task.id: [] for task in tasks}
        
        for task in tasks:
            for dep in task.dependencies:
                if dep in graph:
                    graph[dep].append(task.id)
                    in_degree[task.id] += 1
        
        # Kahn's algorithm
        queue = [task_id for task_id, deg in in_degree.items() if deg == 0]
        result = []
        task_map = {task.id: task for task in tasks}
        
        # Sort queue by priority (higher priority first)
        queue.sort(key=lambda x: task_map[x].priority, reverse=True)
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    # Re-sort queue to maintain priority order
                    queue.sort(key=lambda x: task_map[x].priority, reverse=True)
        
        if len(result) != len(tasks):
            raise WorkflowError("Circular dependency detected in task decomposition")
        
        return result
    
    def _analyze_dependencies(self, tasks: List[Task]) -> Dict[str, List[str]]:
        """
        Analyze task dependencies.
        
        Args:
            tasks: List of tasks
            
        Returns:
            Dictionary mapping task ID to list of dependency task IDs
        """
        return {task.id: task.dependencies for task in tasks}
    
    def _assign_role(
        self,
        task_description: str,
        available_roles: List[Role]
    ) -> Optional[Role]:
        """
        Assign a role to a task based on task description and role capabilities.
        
        Args:
            task_description: Description of the task
            available_roles: List of available roles
            
        Returns:
            Best matching role or None
        """
        # Simple keyword matching
        desc_lower = task_description.lower()
        
        # Check role skills and constraints
        for role in available_roles:
            role_text = f"{role.id} {role.name} {role.description}".lower()
            
            # Check if role constraints match task
            allowed = role.constraints.get('allowed_actions', [])
            forbidden = role.constraints.get('forbidden_actions', [])
            
            # Skip if task matches forbidden actions
            if any(action in desc_lower for action in forbidden):
                continue
            
            # Prefer roles with matching allowed actions
            if any(action in desc_lower for action in allowed):
                return role
        
        # Fallback: return first available role
        return available_roles[0] if available_roles else None

