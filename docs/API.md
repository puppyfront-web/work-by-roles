# API 文档

Multi-Role Skills Workflow 框架提供两个层次的 Python API。

## 1. 高层 API (推荐)

高层 API 通过 `work_by_roles.Workflow` 提供，旨在实现"零配置"和"渐进式"体验。

### `work_by_roles.Workflow`

#### `quick_start(workspace: Path = None, template: str = None) -> Workflow`
快速启动工作流。
- 自动检测项目类型。
- 自动生成 `.workflow/` 目录和配置文件。
- 自动加载配置并初始化引擎。

#### `from_template(template: str, workspace: Path = None) -> Workflow`
从指定模板启动。支持的模板包括：`web-app`, `api-service`, `cli-tool`, `minimalist`, `standard_agile`。

#### `start(stage_id: str, role_id: str = None)`
启动一个阶段。如果未提供 `role_id`，将根据阶段定义自动推断。

#### `complete(stage_id: str = None) -> tuple[bool, list]`
完成指定阶段（默认为当前阶段）。会触发质量门禁验证。

#### `status() -> dict`
获取当前工作流状态汇总。

---

## 2. 底层 API (高级用户)

底层 API 提供了对引擎、角色管理和执行过程的细粒度控制。

### `work_by_roles.WorkflowEngine`

核心引擎类，负责协调所有子系统。

- `load_skill_library(path: Path)`
- `load_roles(path: Path)`
- `load_workflow(path: Path)`
- `start_stage(stage_id: str, role_id: str)`
- `complete_stage(stage_id: str) -> tuple[bool, list]`
- `validate_action(role_id: str, action: str) -> bool`

### `work_by_roles.RoleManager`

负责角色定义和技能要求的管理。

- `get_role(role_id: str) -> Role`
- `check_skills(role_id: str, required_skills: list) -> bool`

### `work_by_roles.AgentOrchestrator`

用于集成技能和执行更复杂的 Agent 任务。

- `execute_skill(skill_id: str, input_data: dict) -> dict`
- `execute_skill_workflow(workflow_id: str, inputs: dict) -> ExecutionResult`

### `work_by_roles.SkillSelector`

增强的技能选择器，支持语义匹配和上下文感知。

- `select_skill(task_description: str, role: Role, context: Optional[Dict] = None) -> Optional[Skill]`
  - 选择单个最合适的技能
  
- `select_skills(task_description: str, role: Role, context: Optional[Dict] = None, max_results: int = 5) -> List[Tuple[Skill, float]]`
  - 返回多个候选技能，按相关性排序

### `work_by_roles.SkillWorkflowExecutor`

执行技能工作流，支持条件分支、循环和动态技能选择。

- `execute_workflow(workflow_id: str, inputs: Dict[str, Any], stage_id: Optional[str] = None, role_id: Optional[str] = None) -> SkillWorkflowExecution`
  - 执行工作流，支持：
    - 条件分支（基于执行结果动态选择路径）
    - 循环（while 和 for_each）
    - 动态技能选择（运行时选择技能）

### `work_by_roles.ConditionEvaluator`

评估工作流中的条件表达式。

- `evaluate(condition: str) -> bool`
  - 评估条件表达式，支持变量引用和比较运算符

---

## 3. 命令行接口 (CLI)

除了 Python API，框架还提供了强大的命令行工具：

### 基础命令
- `workflow init`: 初始化项目上下文（自动使用 teams/standard-delivery/ 配置）。
- `workflow status`: 查看工作流状态。
- `workflow start <stage>`: 启动阶段（可自动推断角色）。
- `workflow complete`: 完成当前阶段（自动运行质量门禁）。
- `workflow wfauto`: 一键顺序执行全部阶段。

### 查看命令
- `workflow list-stages`: 列出所有阶段及其详情。
- `workflow list-roles`: 列出所有角色及其权限。
- `workflow list-skills`: 列出所有技能。

### 团队管理
- `workflow team list`: 列出所有团队。
- `workflow team create <id> --template <name>`: 创建新团队。
- `workflow team switch <id>`: 切换到指定团队。
- `workflow team current`: 显示当前活动团队。

### 技能管理
- `workflow generate-skill <id> <name>`: 生成技能模板。
- `workflow validate-skills <file>`: 验证技能定义。
- `workflow interactive-skill`: 交互式创建技能。

### 其他命令
- `workflow validate <role> <action>`: 验证角色权限。
- `workflow check-team`: 执行团队健康检查。
