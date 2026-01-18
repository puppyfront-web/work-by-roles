"""
Data model classes for the workflow engine.
Following Single Responsibility Principle - all data models in one module.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime

if TYPE_CHECKING:
    from .role_manager import RoleManager

from .exceptions import WorkflowError
from .enums import SkillWorkflowStepStatus, StageStatus


# ============================================================================
# Skill Models
# ============================================================================

@dataclass
class Skill:
    """Skill definition loaded from the skill library"""
    id: str
    name: str
    description: str
    category: str  # 技能分类：frontend, backend, design, etc.
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    # 可选字段（向后兼容）
    dimensions: List[str] = field(default_factory=list)
    levels: Dict[int, str] = field(default_factory=dict)
    tools: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    error_handling: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SkillExecution:
    """Record of a skill execution"""
    skill_id: str
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]]
    status: str  # "success", "failed", "retried", "skipped"
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    stage_id: Optional[str] = None
    role_id: Optional[str] = None


@dataclass
class SkillRequirement:
    """Skill requirement on a role"""
    skill_id: str
    min_level: int = 1
    focus: Optional[List[str]] = None


@dataclass
class SkillBundle:
    """A collection of skill requirements that can be assigned as a unit"""
    id: str
    name: str
    description: str
    skills: List[SkillRequirement]


# ============================================================================
# Skill Workflow Models
# ============================================================================

@dataclass
class ConditionalBranch:
    """Conditional branch configuration for workflow steps"""
    condition: str  # Expression to evaluate, e.g., "step_1.result.status == 'success'"
    target_step_id: str  # Step to execute if condition is true
    else_step_id: Optional[str] = None  # Optional step to execute if condition is false


@dataclass
class LoopConfig:
    """Configuration for loop execution in workflow steps"""
    type: str  # "for_each" | "while"
    condition: Optional[str] = None  # Condition expression for while loops
    items_source: Optional[str] = None  # Variable path for for_each loops (e.g., "step_1.result.items")
    max_iterations: int = 100  # Maximum iterations to prevent infinite loops
    break_on_failure: bool = False  # Break loop if step fails


@dataclass
class SkillStepConfig:
    """Configuration for a skill workflow step"""
    timeout: int = 300                    # Timeout in seconds
    retry_on_failure: bool = True         # Whether to retry on failure
    max_retries: int = 3                  # Maximum retry attempts
    required: bool = False                # Must succeed for workflow to complete
    parallel_with: List[str] = field(default_factory=list)  # Steps that can run in parallel


@dataclass
class SkillStep:
    """
    A single step in a skill workflow.
    
    Represents the execution of one skill with specific inputs/outputs mappings.
    """
    step_id: str
    skill_id: str
    name: str
    order: int
    depends_on: List[str] = field(default_factory=list)
    inputs: Dict[str, str] = field(default_factory=dict)   # Input variable mappings
    outputs: List[str] = field(default_factory=list)        # Declared output names
    config: SkillStepConfig = field(default_factory=SkillStepConfig)
    condition: Optional[str] = None  # Execution condition expression
    branches: List[ConditionalBranch] = field(default_factory=list)  # Conditional branches
    loop_config: Optional[LoopConfig] = None  # Loop configuration
    dynamic_skill: bool = False  # Whether to dynamically select skill
    skill_selector_config: Optional[Dict[str, Any]] = None  # Configuration for skill selection
    fallback_skill_id: Optional[str] = None  # Fallback skill if selection fails
    
    # Runtime state (not from YAML)
    status: SkillWorkflowStepStatus = field(default=SkillWorkflowStepStatus.PENDING)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    iteration_count: int = 0  # For loop tracking
    selected_skill_id: Optional[str] = None  # Dynamically selected skill ID


@dataclass
class SkillWorkflowTrigger:
    """Trigger configuration for a skill workflow"""
    stage_id: Optional[str] = None        # Which stage triggers this workflow
    condition: str = "manual"              # auto | manual | on_event
    event_type: Optional[str] = None       # For on_event condition


@dataclass
class SkillWorkflowConfig:
    """Configuration for a skill workflow"""
    max_parallel: int = 2                  # Maximum parallel steps
    fail_fast: bool = False                # Stop on first failure
    retry_failed_steps: bool = True        # Retry failed steps
    timeout: int = 3600                    # Overall workflow timeout


@dataclass
class SkillWorkflow:
    """
    A workflow composed of multiple skill steps with dependencies.
    
    Represents a directed acyclic graph (DAG) of skill executions.
    """
    id: str
    name: str
    description: str
    steps: List[SkillStep]
    trigger: SkillWorkflowTrigger = field(default_factory=SkillWorkflowTrigger)
    outputs: Dict[str, str] = field(default_factory=dict)  # Final output mappings
    config: SkillWorkflowConfig = field(default_factory=SkillWorkflowConfig)
    
    def get_step(self, step_id: str) -> Optional[SkillStep]:
        """Get step by ID"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None
    
    def get_ready_steps(self) -> List[SkillStep]:
        """Get steps that are ready to execute (dependencies met)"""
        completed_ids = {s.step_id for s in self.steps if s.status == SkillWorkflowStepStatus.COMPLETED}
        ready = []
        for step in self.steps:
            if step.status == SkillWorkflowStepStatus.PENDING:
                # Check if all dependencies are completed
                if all(dep in completed_ids for dep in step.depends_on):
                    ready.append(step)
        return ready
    
    def get_parallel_groups(self) -> List[List[SkillStep]]:
        """Get steps grouped by order for parallel execution"""
        groups: Dict[int, List[SkillStep]] = {}
        for step in self.steps:
            if step.order not in groups:
                groups[step.order] = []
            groups[step.order].append(step)
        return [groups[k] for k in sorted(groups.keys())]
    
    def topological_sort(self) -> List[SkillStep]:
        """Return steps in topological order respecting dependencies"""
        # Build dependency graph
        in_degree = {s.step_id: 0 for s in self.steps}
        graph: Dict[str, List[str]] = {s.step_id: [] for s in self.steps}
        
        for step in self.steps:
            for dep in step.depends_on:
                if dep in graph:
                    graph[dep].append(step.step_id)
                    in_degree[step.step_id] += 1
        
        # Kahn's algorithm
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        result = []
        step_map = {s.step_id: s for s in self.steps}
        
        while queue:
            # Sort by order to maintain deterministic ordering
            queue.sort(key=lambda x: step_map[x].order)
            current = queue.pop(0)
            result.append(step_map[current])
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if len(result) != len(self.steps):
            raise WorkflowError("Circular dependency detected in skill workflow")
        
        return result
    
    def validate(self, skill_library: Dict[str, Skill]) -> List[str]:
        """Validate the workflow definition"""
        errors = []
        step_ids = {s.step_id for s in self.steps}
        
        for step in self.steps:
            # Check skill exists
            if step.skill_id not in skill_library:
                errors.append(f"Step '{step.step_id}' references unknown skill '{step.skill_id}'")
            
            # Check dependencies exist
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(f"Step '{step.step_id}' depends on unknown step '{dep}'")
        
        # Check for circular dependencies
        try:
            self.topological_sort()
        except WorkflowError as e:
            errors.append(str(e))
        
        return errors


@dataclass
class SkillWorkflowExecution:
    """Record of a skill workflow execution"""
    workflow_id: str
    status: str  # "running", "completed", "failed", "cancelled"
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    execution_time: float = 0.0


# ============================================================================
# Role and Workflow Models
# ============================================================================

@dataclass
class Role:
    """Role definition"""
    id: str
    name: str
    description: str
    skills: List[str]  # 简化：直接引用技能ID列表
    domain: str  # 领域：frontend, backend, fullstack, etc.
    responsibility: str  # 职责描述，用于任务匹配
    extends: Optional[List[str]] = None
    constraints: Dict[str, List[str]] = field(default_factory=dict)
    validation_rules: List[str] = field(default_factory=list)
    instruction_template: str = ""  # Role-specific base prompt for Agent
    
    def can_handle_task(self, task_description: str, role_manager: 'RoleManager') -> bool:
        """
        判断角色是否能处理该任务（博弈反馈的核心逻辑）
        
        例如：前端角色判断任务是否属于前端工作
        """
        task_lower = task_description.lower()
        desc_lower = self.description.lower()
        resp_lower = self.responsibility.lower()
        
        # 1. 检查领域匹配
        if self.domain:
            domain_keywords = {
                "frontend": ["前端", "ui", "界面", "组件", "react", "vue", "页面", "frontend", "页面"],
                "backend": ["后端", "api", "服务", "数据库", "server", "backend", "rest"],
                "fullstack": ["全栈", "fullstack"],
                "design": ["设计", "ui设计", "ux", "design"],
                "qa": ["测试", "质量", "qa", "quality"],
                "general": []  # general domain accepts all
            }
            keywords = domain_keywords.get(self.domain.lower(), [])
            if keywords:  # Only check if domain has specific keywords
                # 检查是否有其他领域的明显关键词（如果任务明显属于其他领域，则拒绝）
                other_domains = {k: v for k, v in domain_keywords.items() if k != self.domain.lower() and k != "general"}
                for other_domain, other_keywords in other_domains.items():
                    if other_keywords and any(kw in task_lower for kw in other_keywords):
                        # 如果任务明显属于其他领域，且当前领域不是general，则拒绝
                        if self.domain.lower() != "general":
                            return False
        
        # 2. 检查职责匹配（更宽松的匹配）
        if self.responsibility:
            # 简单关键词匹配（可以用LLM增强）
            responsibility_keywords = [w for w in resp_lower.split() if len(w) > 1]  # 过滤单字符
            if len(responsibility_keywords) > 0:
                matches = sum(1 for kw in responsibility_keywords if kw in task_lower)
                # 至少20%的关键词匹配，或者至少1个关键词匹配
                if matches == 0 and len(responsibility_keywords) > 2:
                    # 如果有很多关键词但一个都不匹配，可能不匹配
                    # 但对于短职责描述，允许不匹配
                    if len(responsibility_keywords) > 3:
                        return False
        
        # 3. 检查约束
        forbidden = self.constraints.get('forbidden_actions', [])
        if any(action.lower() in task_lower for action in forbidden):
            return False
        
        # 4. 检查技能匹配（更宽松）
        if self.skills and role_manager and role_manager.skill_library:
            # 基于技能判断任务是否匹配
            skill_keywords = []
            for skill_id in self.skills:
                skill = role_manager.skill_library.get(skill_id)
                if skill:
                    skill_keywords.extend(skill.name.lower().split())
                    skill_keywords.extend(skill.description.lower().split()[:3])  # 只取前3个词
            
            if skill_keywords:
                matches = sum(1 for kw in skill_keywords if kw in task_lower and len(kw) > 2)  # 只匹配长度>2的关键词
                # 如果有很多技能关键词但一个都不匹配，且职责也不匹配，才拒绝
                if matches == 0 and len(skill_keywords) > 5:
                    # 如果职责也不匹配，才拒绝
                    if self.responsibility:
                        resp_keywords = [w for w in self.responsibility.lower().split() if len(w) > 1]
                        resp_matches = sum(1 for kw in resp_keywords if kw in task_lower)
                        if resp_matches == 0:
                            return False
        
        return True
    
    def evaluate_task(self, task: 'Task', role_manager: 'RoleManager') -> Tuple[bool, Optional[str]]:
        """
        评估任务并返回是否接受 + 反馈信息
        
        Returns:
            (can_handle: bool, feedback: str)
        """
        can_handle = self.can_handle_task(task.description, role_manager)
        
        if can_handle:
            feedback = f"✅ {self.name} accepts this task. It aligns with my responsibilities: {self.responsibility}"
        else:
            feedback = f"❌ {self.name} cannot handle this task. This task is not within my domain ({self.domain}) or responsibilities ({self.responsibility})."
        
        return can_handle, feedback
    
    def match_score(self, task_description: str, task_category: str, role_manager: Optional['RoleManager'] = None) -> float:
        """计算角色与任务的匹配分数（用于自动分配）"""
        score = 0.0
        task_lower = task_description.lower()
        
        # 领域匹配
        if self.domain.lower() == task_category.lower():
            score += 0.5
        
        # 职责匹配
        if self.responsibility:
            resp_lower = self.responsibility.lower()
            matches = sum(1 for word in resp_lower.split() if word in task_lower)
            score += matches * 0.1
        
        # 技能匹配
        if self.skills and role_manager and role_manager.skill_library:
            skill_count = len(self.skills)
            # 检查技能关键词匹配
            matched_skills = 0
            for skill_id in self.skills:
                skill = role_manager.skill_library.get(skill_id)
                if skill:
                    skill_name_lower = skill.name.lower()
                    skill_desc_lower = skill.description.lower()
                    if any(kw in task_lower for kw in skill_name_lower.split()):
                        matched_skills += 1
                    elif any(kw in task_lower for kw in skill_desc_lower.split()[:3]):
                        matched_skills += 0.5
            
            if skill_count > 0:
                score += (matched_skills / skill_count) * 0.3
        
        return min(score, 1.0)  # 限制在0-1之间


@dataclass
class QualityGate:
    """Quality gate definition"""
    type: str
    criteria: List[str]
    validator: str
    strict: bool = True  # If False, failures are warnings only (for quick mode)


@dataclass
class Output:
    """Expected output definition"""
    type: str
    format: str
    required: bool
    name: str


@dataclass
class Stage:
    """Workflow stage definition"""
    id: str
    name: str
    role: str
    order: int
    prerequisites: List[str]
    entry_criteria: List[str]
    exit_criteria: List[str]
    quality_gates: List[QualityGate]
    outputs: List[Output]
    goal_template: str = ""  # Stage-specific goal template for Agent


@dataclass
class Workflow:
    """Workflow definition"""
    id: str
    name: str
    description: str
    stages: List[Stage]


@dataclass
class ExecutionState:
    """Current workflow execution state"""
    current_stage: Optional[str] = None
    stage_status: Dict[str, StageStatus] = field(default_factory=dict)
    completed_stages: Set[str] = field(default_factory=set)
    current_role: Optional[str] = None
    violations: List[str] = field(default_factory=list)
    active_agents: List[str] = field(default_factory=list)  # List of active agent IDs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_stage": self.current_stage,
            "stage_status": {k: v.value for k, v in self.stage_status.items()},
            "completed_stages": list(self.completed_stages),
            "current_role": self.current_role,
            "violations": self.violations,
            "active_agents": self.active_agents
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionState':
        return cls(
            current_stage=data.get("current_stage"),
            stage_status={k: StageStatus(v) for k, v in data.get("stage_status", {}).items()},
            completed_stages=set(data.get("completed_stages", [])),
            current_role=data.get("current_role"),
            violations=data.get("violations", []),
            active_agents=data.get("active_agents", [])
        )


@dataclass
class ProjectContext:
    """Project-specific context discovered during initialization"""
    root_path: Path
    paths: Dict[str, str] = field(default_factory=dict)
    specs: Dict[str, str] = field(default_factory=dict)
    standards: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paths": self.paths,
            "specs": self.specs,
            "standards": self.standards
        }

    @classmethod
    def from_dict(cls, root_path: Path, data: Dict[str, Any]) -> 'ProjectContext':
        return cls(
            root_path=root_path,
            paths=data.get("paths", {}),
            specs=data.get("specs", {}),
            standards=data.get("standards", {})
        )


# ============================================================================
# Checkpoint Models
# ============================================================================

@dataclass
class Checkpoint:
    """Workflow checkpoint for state recovery"""
    checkpoint_id: str
    name: str
    workflow_id: str
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    stage_id: Optional[str] = None
    execution_state: 'ExecutionState' = None
    progress_data: Optional[Dict[str, Any]] = None  # WorkflowProgress as dict
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    output_files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "checkpoint_id": self.checkpoint_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "workflow_id": self.workflow_id,
            "stage_id": self.stage_id,
            "execution_state": self.execution_state.to_dict() if self.execution_state else None,
            "progress_data": self.progress_data,
            "context_snapshot": self.context_snapshot,
            "output_files": self.output_files,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """Create from dictionary"""
        from .workflow_progress_manager import WorkflowProgress
        
        execution_state = None
        if data.get("execution_state"):
            execution_state = ExecutionState.from_dict(data["execution_state"])
        
        return cls(
            checkpoint_id=data["checkpoint_id"],
            name=data["name"],
            description=data.get("description"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            workflow_id=data["workflow_id"],
            stage_id=data.get("stage_id"),
            execution_state=execution_state,
            progress_data=data.get("progress_data"),
            context_snapshot=data.get("context_snapshot", {}),
            output_files=data.get("output_files", []),
            metadata=data.get("metadata", {})
        )


@dataclass
class AgentContext:
    """Context for Agent execution"""
    goal: str
    workspace_path: Path
    project_context: Optional[ProjectContext] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    decisions: List[str] = field(default_factory=list)
    shared_contexts: Dict[str, 'AgentContext'] = field(default_factory=dict)  # Contexts shared by other agents


@dataclass
class ContextSummary:
    """
    Lightweight context summary for token optimization.
    
    Instead of passing full context history (which can be thousands of tokens),
    this class only stores key information summaries.
    """
    stage_summary: str  # Summary of completed stages: "需求分析完成 → PRD生成完成"
    key_outputs: List[str]  # Only output file names, not content
    current_goal: str  # Current stage goal
    completed_stages: List[str]  # List of completed stage IDs
    current_role: Optional[str] = None
    
    def to_text(self) -> str:
        """Convert summary to text format for LLM prompts"""
        parts = []
        if self.stage_summary:
            parts.append(f"阶段摘要: {self.stage_summary}")
        if self.key_outputs:
            parts.append(f"关键输出: {', '.join(self.key_outputs)}")
        if self.current_goal:
            parts.append(f"当前目标: {self.current_goal}")
        return "\n".join(parts)
    
    @classmethod
    def from_engine(cls, engine: 'WorkflowEngine', current_stage_id: Optional[str] = None) -> 'ContextSummary':
        """Create context summary from WorkflowEngine"""
        if not engine.executor:
            return cls(
                stage_summary="工作流未初始化",
                key_outputs=[],
                current_goal="",
                completed_stages=[],
                current_role=None
            )
        
        completed = engine.executor.get_completed_stages()
        current = engine.executor.state.current_role
        
        # Build stage summary
        stage_names = []
        for stage_id in sorted(completed):
            stage = engine.executor._get_stage_by_id(stage_id)
            if stage:
                stage_names.append(stage.name)
        
        stage_summary = " → ".join(stage_names) if stage_names else "无已完成阶段"
        if current_stage_id:
            current_stage = engine.executor._get_stage_by_id(current_stage_id)
            if current_stage:
                stage_summary += f" → {current_stage.name} (进行中)"
        
        # Get key outputs (only file names)
        key_outputs = []
        for stage_id in completed:
            stage = engine.executor._get_stage_by_id(stage_id)
            if stage and stage.outputs:
                for output in stage.outputs:
                    # Get output path using unified path calculation
                    workflow_id = engine.workflow.id if engine.workflow else "default"
                    if output.type in ("document", "report"):
                        # All document and report types go to .workflow/outputs/{workflow_id}/{stage_id}/
                        output_path = engine.workspace_path / ".workflow" / "outputs" / workflow_id / stage.id / output.name
                    else:
                        output_path = engine.workspace_path / output.name
                    if output_path.exists():
                        key_outputs.append(output.name)
        
        # Get current goal
        current_goal = ""
        if current_stage_id:
            stage = engine.executor._get_stage_by_id(current_stage_id)
            if stage:
                current_goal = stage.goal_template or stage.name
        
        return cls(
            stage_summary=stage_summary,
            key_outputs=key_outputs,
            current_goal=current_goal,
            completed_stages=list(completed),
            current_role=current
        )


# ============================================================================
# Agent Collaboration Models
# ============================================================================

@dataclass
class AgentMessage:
    """Agent 间消息（与 agent_message_bus.py 中的 AgentMessage 保持一致）"""
    from_agent: str
    to_agent: str  # "*" for broadcast
    message_type: str  # "request", "response", "notification", "context_share"
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = ""
    
    def __post_init__(self):
        """Generate message ID if not provided"""
        if not self.message_id:
            self.message_id = f"{self.from_agent}_{self.to_agent}_{self.timestamp.timestamp()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "message_id": self.message_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMessage':
        """Create from dictionary"""
        return cls(
            message_id=data.get("message_id", ""),
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            message_type=data["message_type"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat()))
        )


@dataclass
class Task:
    """任务定义"""
    id: str
    description: str
    category: str  # 任务分类：frontend, backend, design, etc.
    assigned_role: Optional[str] = None  # 初始分配的角色
    dependencies: List[str] = field(default_factory=list)  # Task IDs this task depends on
    status: str = "pending"  # "pending", "accepted", "rejected", "in_progress", "completed", "failed"
    rejection_reason: Optional[str] = None  # 如果被拒绝，记录原因
    reassigned_to: Optional[str] = None  # 如果被重新分配
    priority: int = 0  # Higher number = higher priority
    estimated_time: Optional[float] = None  # Estimated execution time in seconds
    actual_time: Optional[float] = None  # Actual execution time in seconds
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class TaskAssignment:
    """任务分配结果"""
    task_id: str
    assigned_role: str
    status: str  # "accepted" | "rejected" | "pending"
    feedback: Optional[str] = None  # 角色的反馈信息
    suggested_role: Optional[str] = None  # 如果拒绝，建议分配给哪个角色


@dataclass
class TaskDecomposition:
    """任务分解结果"""
    tasks: List[Task]
    execution_order: List[str]  # Task IDs in execution order
    dependencies: Dict[str, List[str]]  # Map from task ID to list of dependency task IDs
    total_estimated_time: Optional[float] = None  # Total estimated time for all tasks
    
    def get_ready_tasks(self) -> List[Task]:
        """Get tasks that are ready to execute (all dependencies completed)"""
        completed_ids = {t.id for t in self.tasks if t.status == "completed"}
        ready = []
        for task in self.tasks:
            if task.status == "pending":
                if all(dep in completed_ids for dep in task.dependencies):
                    ready.append(task)
        return ready
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def validate(self) -> List[str]:
        """Validate task decomposition"""
        errors = []
        task_ids = {t.id for t in self.tasks}
        
        # Check all dependencies exist
        for task in self.tasks:
            for dep in task.dependencies:
                if dep not in task_ids:
                    errors.append(f"Task '{task.id}' depends on unknown task '{dep}'")
        
        # Check for circular dependencies
        visited = set()
        rec_stack = set()
        
        def has_cycle(task_id: str) -> bool:
            if task_id in rec_stack:
                return True
            if task_id in visited:
                return False
            
            visited.add(task_id)
            rec_stack.add(task_id)
            
            task = self.get_task(task_id)
            if task:
                for dep in task.dependencies:
                    if has_cycle(dep):
                        return True
            
            rec_stack.remove(task_id)
            return False
        
        for task in self.tasks:
            if task.id not in visited:
                if has_cycle(task.id):
                    errors.append(f"Circular dependency detected involving task '{task.id}'")
        
        return errors


# ============================================================================
# Team and Company Models
# ============================================================================

@dataclass
class Team:
    """团队 - 由角色组成"""
    id: str
    name: str
    description: str
    roles: List[str]  # 角色ID列表
    company_id: Optional[str] = None  # 可选：所属公司


@dataclass
class Company:
    """公司 - 由团队组成（可选层级）"""
    id: str
    name: str
    description: str
    teams: List[str]  # 团队ID列表
