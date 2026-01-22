# API Documentation

The Multi-Role Skills Workflow framework provides Python APIs at two levels.

## 1. High-Level API (Recommended)

The high-level API is provided through `work_by_roles.Workflow`, designed for "zero-config" and "progressive" experience.

### `work_by_roles.Workflow`

#### `quick_start(workspace: Path = None, template: str = None) -> Workflow`
Quick start workflow.
- Automatically detect project type.
- Automatically generate `.workflow/` directory and configuration files.
- Automatically load configuration and initialize engine.

#### `from_template(template: str, workspace: Path = None) -> Workflow`
Start from specified template. Supported templates include: `web-app`, `api-service`, `cli-tool`, `minimalist`, `standard_agile`.

#### `start(stage_id: str, role_id: str = None)`
Start a stage. If `role_id` is not provided, it will be automatically inferred from stage definition.

#### `complete(stage_id: str = None) -> tuple[bool, list]`
Complete specified stage (defaults to current stage). Will trigger quality gate validation.

#### `status() -> dict`
Get current workflow status summary.

---

## 2. Low-Level API (Advanced Users)

The low-level API provides fine-grained control over engine, role management, and execution process.

### `work_by_roles.WorkflowEngine`

Core engine class responsible for coordinating all subsystems.

- `load_skill_library(path: Path)`
- `load_roles(path: Path)`
- `load_workflow(path: Path)`
- `start_stage(stage_id: str, role_id: str)`
- `complete_stage(stage_id: str) -> tuple[bool, list]`
- `validate_action(role_id: str, action: str) -> bool`

### `work_by_roles.RoleManager`

Responsible for role definition and skill requirement management.

- `get_role(role_id: str) -> Role`
- `check_skills(role_id: str, required_skills: list) -> bool`

### `work_by_roles.AgentOrchestrator`

Used for integrating skills and executing more complex Agent tasks.

- `execute_skill(skill_id: str, input_data: dict) -> dict`
- `execute_skill_workflow(workflow_id: str, inputs: dict) -> ExecutionResult`

### `work_by_roles.SkillSelector`

Enhanced skill selector supporting semantic matching and context awareness.

- `select_skill(task_description: str, role: Role, context: Optional[Dict] = None) -> Optional[Skill]`
  - Select single most suitable skill
  
- `select_skills(task_description: str, role: Role, context: Optional[Dict] = None, max_results: int = 5) -> List[Tuple[Skill, float]]`
  - Return multiple candidate skills, sorted by relevance

### `work_by_roles.SkillWorkflowExecutor`

Execute skill workflows, supporting conditional branches, loops, and dynamic skill selection.

- `execute_workflow(workflow_id: str, inputs: Dict[str, Any], stage_id: Optional[str] = None, role_id: Optional[str] = None) -> SkillWorkflowExecution`
  - Execute workflow, supporting:
    - Conditional branches (dynamically select path based on execution results)
    - Loops (while and for_each)
    - Dynamic skill selection (select skills at runtime)

### `work_by_roles.ConditionEvaluator`

Evaluate conditional expressions in workflows.

- `evaluate(condition: str) -> bool`
  - Evaluate conditional expressions, supporting variable references and comparison operators

---

## 3. Command Line Interface (CLI)

In addition to Python API, the framework also provides powerful command-line tools:

### Basic Commands
- `workflow init`: Initialize project context (automatically uses teams/standard-delivery/ configuration).
- `workflow status`: View workflow status.
- `workflow start <stage>`: Start stage (can automatically infer role).
- `workflow complete`: Complete current stage (automatically run quality gates).
- `workflow wfauto`: One-click sequential execution of all stages.

### View Commands
- `workflow list-stages`: List all stages and their details.
- `workflow list-roles`: List all roles and their permissions.
- `workflow list-skills`: List all skills.

### Team Management
- `workflow team list`: List all teams.
- `workflow team create <id> --template <name>`: Create new team.
- `workflow team switch <id>`: Switch to specified team.
- `workflow team current`: Display current active team.

### Skill Management
- `workflow generate-skill <id> <name>`: Generate skill template.
- `workflow validate-skills <file>`: Validate skill definitions.
- `workflow interactive-skill`: Interactively create skill.

### Other Commands
- `workflow validate <role> <action>`: Validate role permissions.
- `workflow check-team`: Perform team health check.
