# Work-by-Roles 项目架构文档

> 本文档用于向 ChatGPT 等 AI 工具提供项目架构分析，包含完整的系统设计、组件关系和数据流。

## 1. 项目概述

**Work-by-Roles** 是一个多角色技能工作流框架，通过角色边界和工作流阶段来规范开发流程。项目支持两种执行模式：

- **Workflow 模式**：多阶段流程，适用于需要结构化流程的大型项目
- **Role Executor 模式**：简化模式，直接调用角色处理需求，适用于 IDE 环境（如 Cursor）

### 1.1 核心特性

- ✅ 角色（Role）驱动的任务分配
- ✅ 技能（Skill）库管理，支持 Anthropic 标准格式
- ✅ 工作流（Workflow）阶段管理
- ✅ 质量门控（Quality Gates）系统
- ✅ Agent 编排和执行
- ✅ 团队（Team）配置管理
- ✅ 项目上下文扫描和感知

### 1.2 技术栈

- **语言**: Python 3.8+
- **依赖**: PyYAML, pytest
- **可选依赖**: jsonschema（用于 schema 验证）
- **包管理**: setuptools, pyproject.toml

## 2. 系统架构

### 2.1 三层架构设计

项目采用严格的三层架构，确保 Reasoning Layer 和 Skill Invocation Layer 完全分离：

```
┌─────────────────────────────────────────┐
│   Reasoning Layer (Agent)              │
│   - Task understanding                 │
│   - Goal clarification                 │
│   - Strategy & decisions               │
│   - Uncertainty handling               │
│   ❌ NO SKILLS HERE                    │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│   Skill Invocation Layer                │
│   (AgentOrchestrator)                   │
│   - Skill selection                    │
│   - Input validation                   │
│   - Skill execution                    │
│   - Result validation                  │
│   ✅ SKILLS ONLY HERE                  │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│   Execution Layer                      │
│   - Tool/API execution                 │
│   - Database operations                │
│   - Code execution                     │
│   - UI operations                      │
└─────────────────────────────────────────┘
```

### 2.2 核心组件关系图

```
┌─────────────────────────────────────────────────────────────┐
│                    WorkflowEngine                           │
│  (核心引擎，协调所有组件)                                     │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ RoleManager  │    │ Workflow     │    │ Project      │
│              │    │ Executor     │    │ Scanner      │
│ - 角色管理    │    │              │    │              │
│ - 技能库管理  │    │ - 阶段执行    │    │ - 项目扫描    │
│ - 验证       │    │ - 状态管理    │    │ - 上下文构建  │
└──────────────┘    └──────────────┘    └──────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
                    ┌──────────────────┐
                    │ AgentOrchestrator│
                    │                  │
                    │ - Agent 编排     │
                    │ - 技能执行       │
                    │ - 结果汇总       │
                    └──────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            ┌──────────────┐    ┌──────────────┐
            │    Agent     │    │ SkillSelector│
            │              │    │              │
            │ - 推理层      │    │ - 技能选择    │
            │ - 上下文管理  │    │ - 匹配算法    │
            └──────────────┘    └──────────────┘
```

## 3. 核心模块详解

### 3.1 核心引擎 (`work_by_roles/core/engine.py`)

**WorkflowEngine** 是整个系统的核心协调器，负责：

- 工作流初始化和管理
- 组件生命周期管理
- 状态持久化
- 错误处理和恢复

**关键类**:
- `WorkflowEngine`: 主引擎类
- `Agent`: 角色代理，处理推理层
- `AgentOrchestrator`: Agent 编排器，管理技能调用层
- `RoleExecutor`: 角色执行器（简化模式）
- `SkillWorkflowExecutor`: 技能工作流执行器
- `SkillInvoker`: 技能调用器系列（PlaceholderSkillInvoker, LLMSkillInvoker, CompositeSkillInvoker）

### 3.2 数据模型 (`work_by_roles/core/models.py`)

所有数据模型集中在此模块，遵循单一职责原则：

**技能相关模型**:
- `Skill`: 技能定义
- `SkillExecution`: 技能执行记录
- `SkillRequirement`: 角色技能要求
- `SkillBundle`: 技能包

**工作流相关模型**:
- `SkillStep`: 技能工作流步骤
- `SkillWorkflow`: 技能工作流定义
- `SkillWorkflowConfig`: 工作流配置
- `ConditionalBranch`: 条件分支
- `LoopConfig`: 循环配置

**角色和工作流模型**:
- `Role`: 角色定义
- `Stage`: 工作流阶段
- `Workflow`: 工作流定义
- `QualityGate`: 质量门控

**上下文模型**:
- `ProjectContext`: 项目上下文
- `AgentContext`: Agent 上下文
- `ExecutionState`: 执行状态
- `ContextSummary`: 上下文摘要

### 3.3 角色管理 (`work_by_roles/core/role_manager.py`)

**RoleManager** 负责：

- 加载和验证角色定义（从 YAML）
- 管理技能库（支持标准格式和 Anthropic 格式）
- 验证角色技能要求
- 管理技能包和工作流
- 支持角色继承和层次结构

**关键方法**:
- `load_roles()`: 加载角色定义
- `load_skill_library()`: 加载技能库
- `validate_role_skills()`: 验证角色技能
- `get_role()`: 获取角色定义

### 3.4 工作流执行器 (`work_by_roles/core/workflow_executor.py`)

**WorkflowExecutor** 负责：

- 验证工作流结构
- 管理阶段状态转换
- 检查前置条件
- 跟踪完成状态

**关键方法**:
- `start_stage()`: 开始阶段
- `complete_stage()`: 完成阶段
- `can_transition_to()`: 检查是否可以转换到指定阶段
- `get_current_stage()`: 获取当前阶段

### 3.5 技能选择器 (`work_by_roles/core/skill_selector.py`)

**SkillSelector** 负责智能选择最合适的技能：

- 基于任务描述匹配技能
- 考虑角色约束
- 使用历史执行记录评分
- 检查前置条件

**关键方法**:
- `select_skill()`: 选择单个技能
- `select_skills()`: 选择多个候选技能
- `_match_skills_by_task()`: 基于任务匹配技能
- `_score_skills()`: 基于历史记录评分

### 3.6 项目扫描器 (`work_by_roles/core/project_scanner.py`)

**ProjectScanner** 负责扫描项目结构并构建上下文：

- 识别项目路径（src, tests, docs, config）
- 扫描规范文件（OpenAPI, Swagger, spec 文件）
- 检测代码标准和工具
- 构建项目上下文

### 3.7 其他核心模块

- **`condition_evaluator.py`**: 条件表达式求值器
- **`variable_resolver.py`**: 变量解析器（支持 `${variable}` 语法）
- **`execution_tracker.py`**: 执行跟踪器，记录技能执行历史
- **`state_storage.py`**: 状态存储接口和文件实现
- **`quality_gates.py`**: 质量门控系统
- **`team_manager.py`**: 团队配置管理
- **`schema_loader.py`**: Schema 加载器
- **`config_loader.py`**: 配置加载器

## 4. 执行模式

### 4.1 Workflow 模式

多阶段流程模式，适用于需要结构化流程的大型项目：

```
用户需求 → 初始化工作流 → 执行阶段1 → 质量门控 → 执行阶段2 → ... → 完成
```

**关键组件**:
- `WorkflowEngine`: 管理整个工作流
- `WorkflowExecutor`: 执行阶段
- `AgentOrchestrator`: 编排 Agent 执行任务

### 4.2 Role Executor 模式

简化模式，直接调用角色处理需求，适用于 IDE 环境：

```
用户需求 → 选择角色 → 选择技能 → 执行技能 → 返回结果
```

**关键组件**:
- `RoleExecutor`: 简化的角色执行器
- `Agent`: 处理推理
- `SkillSelector`: 选择技能

## 5. 数据流

### 5.1 Workflow 模式数据流

```
1. 初始化阶段
   User → CLI/Python API → WorkflowEngine.init()
   → ProjectScanner.scan() → ProjectContext
   → SchemaLoader.load() → Role, Skill, Workflow definitions
   → RoleManager.load_roles() → Role objects
   → WorkflowExecutor(workflow, role_manager)

2. 执行阶段
   User → WorkflowEngine.start("stage_id")
   → WorkflowExecutor.start_stage()
   → AgentOrchestrator.execute_stage()
   → Agent.prepare() [Reasoning Layer]
   → AgentOrchestrator.execute_skill() [Skill Invocation Layer]
   → SkillInvoker.invoke() [Execution Layer]
   → QualityGateSystem.validate()
   → WorkflowExecutor.complete_stage()

3. 状态持久化
   ExecutionState → StateStorage.save()
```

### 5.2 Role Executor 模式数据流

```
1. 初始化
   User → RoleExecutor(engine)
   → Engine already initialized with roles and skills

2. 执行
   User → RoleExecutor.execute_role(role_id, requirement)
   → Agent(role, engine)
   → Agent.prepare(requirement) [Reasoning Layer]
   → SkillSelector.select_skill(task, role) [Skill Selection]
   → AgentOrchestrator.execute_skill() [Skill Invocation Layer]
   → SkillInvoker.invoke() [Execution Layer]
   → Result aggregation
   → Response generation (optional LLM)
```

## 6. 配置系统

### 6.1 配置文件结构

项目使用 YAML 配置文件：

```
.workflow/
├── role_schema.yaml      # 角色定义
├── skill_library.yaml    # 技能库定义
└── workflow_schema.yaml  # 工作流定义
```

### 6.2 团队配置

支持多团队配置，位于 `teams/` 目录：

```
teams/
├── standard-delivery/    # 标准交付团队
│   ├── role_schema.yaml
│   ├── skill_library.yaml
│   ├── workflow_schema.yaml
│   └── skills/          # Anthropic 格式技能
│       ├── requirements_analysis/
│       │   └── Skill.md
│       └── ...
└── vibe-coding/          # 其他团队配置
    └── ...
```

### 6.3 技能格式

支持两种技能格式：

1. **标准格式**（skill_library.yaml）:
```yaml
skills:
  - id: skill_id
    name: Skill Name
    description: Description
    dimensions: [dim1, dim2]
    levels:
      1: Level 1 description
    tools: [tool1, tool2]
    constraints: [constraint1]
    input_schema: {...}
    output_schema: {...}
```

2. **Anthropic 格式**（Skill.md）:
```markdown
---
name: skill_name
description: Description
input_schema:
  type: object
  properties: {...}
---

# Skill Content
...
```

## 7. CLI 接口

### 7.1 主要命令

- `workflow init`: 初始化工作流
- `workflow setup`: 一键接入项目
- `workflow wfauto`: 自动执行全部阶段
- `workflow status`: 查看状态
- `workflow role-execute <role> "<requirement>"`: 执行角色（简化模式）
- `workflow list-roles`: 列出所有角色
- `workflow list-skills`: 列出所有技能
- `workflow team list`: 列出所有团队

### 7.2 CLI 实现

CLI 实现在 `work_by_roles/cli.py`，使用 argparse 构建命令行接口。

## 8. Python API

### 8.1 高级 API（推荐）

```python
from work_by_roles import Workflow

workflow = Workflow.quick_start()
workflow.start("requirements")
workflow.complete()
```

### 8.2 底层 API

```python
from work_by_roles.core.engine import WorkflowEngine, RoleExecutor

# Workflow 模式
engine = WorkflowEngine(workspace_path=".")
engine.load_skill_library(Path("skill_library.yaml"))
engine.load_roles(Path("role_schema.yaml"))
engine.load_workflow(Path("workflow_schema.yaml"))
engine.start("stage_id")

# Role Executor 模式
executor = RoleExecutor(engine)
result = executor.execute_role("role_id", "requirement")
```

## 9. 错误处理

### 9.1 异常层次

```
Exception
├── WorkflowError          # 工作流相关错误
├── ValidationError        # 验证错误
└── SecurityError          # 安全错误
```

### 9.2 错误类型

- `SkillErrorType.VALIDATION_ERROR`: 输入验证失败
- `SkillErrorType.EXECUTION_ERROR`: 执行失败
- `SkillErrorType.TIMEOUT_ERROR`: 超时
- `SkillErrorType.TEST_FAILURE`: 测试失败
- `SkillErrorType.INSUFFICIENT_CONTEXT`: 上下文不足

## 10. 状态管理

### 10.1 执行状态

`ExecutionState` 跟踪：
- 当前阶段
- 当前角色
- 已完成阶段
- 技能执行历史

### 10.2 状态持久化

通过 `StateStorage` 接口实现，默认使用 `FileStateStorage`（文件存储）。

状态保存在 `.workflow/state.json`。

## 11. 质量门控

### 11.1 质量门控系统

`QualityGateSystem` 提供：
- 自定义验证器
- 阶段完成前检查
- 输出验证
- 约束检查

### 11.2 质量门控类型

- 文件存在检查
- 代码质量检查
- 测试覆盖率
- 自定义验证器

## 12. 扩展点

### 12.1 自定义技能

通过创建 `Skill.md` 文件定义新技能，支持：
- 输入/输出 schema
- 工具列表
- 约束条件
- 错误处理

### 12.2 自定义验证器

实现 `QualityGate` 验证器接口，支持自定义质量检查。

### 12.3 自定义技能调用器

实现 `SkillInvoker` 接口，支持自定义技能执行逻辑。

## 13. 测试

### 13.1 测试结构

测试位于 `tests/` 目录：
- `test_e2e_functionality.py`: 端到端功能测试
- `test_skill_system.py`: 技能系统测试
- `test_workflow.py`: 工作流测试
- `test_skill_workflows.py`: 技能工作流测试
- `test_skill_selector_enhanced.py`: 技能选择器测试

### 13.2 测试工具

使用 pytest 作为测试框架。

## 14. 项目结构

```
work-by-roles/
├── work_by_roles/          # 主包
│   ├── __init__.py
│   ├── cli.py              # CLI 接口
│   ├── bootstrap.py        # 引导脚本
│   ├── quick_start.py      # 快速启动
│   └── core/               # 核心模块
│       ├── engine.py       # 核心引擎（大文件，包含多个类）
│       ├── models.py       # 数据模型
│       ├── role_manager.py # 角色管理
│       ├── workflow_executor.py # 工作流执行器
│       ├── skill_selector.py    # 技能选择器
│       ├── project_scanner.py   # 项目扫描器
│       ├── condition_evaluator.py # 条件求值器
│       ├── variable_resolver.py   # 变量解析器
│       ├── execution_tracker.py   # 执行跟踪器
│       ├── state_storage.py       # 状态存储
│       ├── quality_gates.py       # 质量门控
│       ├── team_manager.py        # 团队管理
│       ├── schema_loader.py        # Schema 加载器
│       ├── config_loader.py        # 配置加载器
│       ├── enums.py                # 枚举类型
│       └── exceptions.py           # 异常定义
├── teams/                  # 团队配置
│   ├── standard-delivery/  # 标准交付团队
│   └── vibe-coding/        # 其他团队
├── templates/              # 项目模板
├── tests/                  # 测试
├── docs/                   # 文档
├── examples/               # 示例
└── tools/                  # 工具脚本
```

## 15. 关键设计决策

### 15.1 三层架构分离

**决策**: 严格分离 Reasoning Layer、Skill Invocation Layer 和 Execution Layer

**原因**: 
- 确保 Agent 推理阶段不使用技能
- 清晰的职责划分
- 便于测试和维护

### 15.2 数据模型集中管理

**决策**: 所有数据模型集中在 `models.py`

**原因**:
- 单一职责原则
- 便于维护和理解
- 避免循环依赖

### 15.3 支持两种执行模式

**决策**: 同时支持 Workflow 模式和 Role Executor 模式

**原因**:
- 适应不同使用场景
- Workflow 模式适合大型项目
- Role Executor 模式适合 IDE 环境

### 15.4 技能格式支持

**决策**: 支持标准格式和 Anthropic 格式

**原因**:
- 兼容性
- 便于技能共享
- 支持不同工具链

## 16. Agent 协作架构

### 16.1 Agent 消息总线 (AgentMessageBus)

**AgentMessageBus** 提供 agent 之间的消息传递和上下文共享机制：

- **消息类型**: request, response, notification, context_share
- **核心功能**:
  - `publish()`: 发布消息给指定 agent 或广播
  - `subscribe()`: 订阅并获取消息（消息会被移除）
  - `peek_messages()`: 查看消息但不移除
  - `share_context()`: 共享上下文给其他 agent
  - `get_context()`: 获取共享上下文
  - `broadcast()`: 广播消息给所有 agent

- **消息持久化**: 可选的消息持久化到 `.workflow/messages/` 目录

### 16.2 任务分解器 (TaskDecomposer)

**TaskDecomposer** 负责将高级目标分解为子任务：

- **分解模式**:
  - LLM 模式: 使用 LLM 智能分解（如果可用）
  - 规则模式: 基于预定义规则分解（fallback）

- **核心功能**:
  - `decompose()`: 分解目标为任务列表
  - `_analyze_dependencies()`: 分析任务依赖关系
  - `_assign_role()`: 为任务分配合适的角色
  - `_build_execution_order()`: 构建执行顺序（拓扑排序）

- **输出**: `TaskDecomposition` 对象，包含任务列表、执行顺序和依赖关系

### 16.3 并行执行

**AgentOrchestrator** 支持并行执行多个阶段：

- **并行执行方法**:
  - `execute_parallel_stages()`: 异步并行执行（使用 asyncio）
  - `execute_parallel_stages_sync()`: 同步包装器

- **依赖处理**: 自动处理阶段依赖关系，无依赖的阶段可以并行执行

- **协作执行**:
  - `execute_with_collaboration()`: 多 agent 协作执行目标
    - 自动分解目标为任务
    - 创建多个 agent 并分配任务
    - 通过消息总线协调执行
    - 支持 agent 间反馈和 review

### 16.4 Agent 协作方法

**Agent** 类新增协作方法：

- `review_output()`: Review 其他 agent 的输出
- `request_feedback()`: 向其他 agent 请求反馈
- `send_message()`: 发送消息给其他 agent
- `check_messages()`: 检查新消息（不移除）
- `get_messages()`: 获取并移除新消息
- `share_context()`: 共享上下文给其他 agent

### 16.5 协作流程

```
用户目标 → TaskDecomposer.decompose()
         → 任务列表 + 依赖关系
         → AgentOrchestrator.execute_with_collaboration()
         → 创建多个 Agent
         → 通过 AgentMessageBus 协调
         → 并行执行无依赖任务
         → Agent 间消息传递和反馈
         → 汇总结果
```

## 17. 未来扩展方向

1. ✅ **并行阶段支持**: 已实现，支持并行执行无依赖阶段
2. **更多技能调用器**: 支持更多执行后端
3. **可视化界面**: Web UI 或 IDE 插件显示 agent 协作状态
4. **技能市场**: 共享技能库
5. **性能优化**: 大规模项目支持
6. **动态 Agent 管理**: 支持运行时添加/移除 agent
7. **更复杂的协作模式**: Leader-follower、Peer review 等

## 17. 关键代码位置

- **核心引擎**: `work_by_roles/core/engine.py` (约 4000 行)
- **数据模型**: `work_by_roles/core/models.py`
- **CLI 接口**: `work_by_roles/cli.py` (约 3200 行)
- **角色管理**: `work_by_roles/core/role_manager.py`
- **工作流执行**: `work_by_roles/core/workflow_executor.py`
- **技能选择**: `work_by_roles/core/skill_selector.py`

## 18. 依赖关系

```
WorkflowEngine
├── RoleManager
│   ├── Skill (models)
│   ├── Role (models)
│   └── VariableResolver
├── WorkflowExecutor
│   ├── Workflow (models)
│   ├── Stage (models)
│   └── RoleManager
├── ProjectScanner
│   └── ProjectContext (models)
├── AgentOrchestrator
│   ├── Agent
│   ├── SkillSelector
│   └── SkillInvoker
└── StateStorage
    └── ExecutionState (models)
```

## 19. 总结

Work-by-Roles 是一个设计良好的多角色技能工作流框架，具有：

- ✅ 清晰的架构分层
- ✅ 灵活的配置系统
- ✅ 强大的扩展能力
- ✅ 完善的错误处理
- ✅ 良好的代码组织

适合用于：
- 大型项目的结构化开发流程
- IDE 环境中的快速任务执行
- 团队协作和角色管理
- 技能驱动的自动化开发

---

**文档版本**: 1.0  
**最后更新**: 2024  
**维护者**: Work-by-Roles Team




