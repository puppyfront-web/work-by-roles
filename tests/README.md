# 测试文档

## 测试结构

```
tests/
├── conftest.py              # 共享fixtures和测试配置
├── fixtures/                # 测试数据
│   ├── workflows/          # 工作流配置
│   ├── teams/              # 团队配置
│   └── skills/             # 技能定义
├── unit/                   # 单元测试
│   ├── test_models.py                    # 数据模型测试
│   ├── test_agent_message_bus.py         # Agent消息总线测试
│   ├── test_task_decomposer.py           # 任务分解器测试
│   ├── test_agent.py                     # Agent类测试
│   ├── test_agent_orchestrator.py        # AgentOrchestrator测试
│   ├── test_skill_selector.py            # 技能选择器测试
│   ├── test_execution_tracker.py         # 执行追踪器测试
│   ├── test_workflow_executor.py         # 工作流执行器测试
│   ├── test_role_manager.py              # 角色管理器测试
│   ├── test_state_storage.py             # 状态存储测试
│   └── test_quality_gates.py             # 质量门控测试
├── integration/            # 集成测试
│   ├── test_workflow_integration.py      # 工作流集成测试
│   ├── test_agent_collaboration.py      # Agent协作集成测试
│   └── test_skill_system.py             # 技能系统集成测试
├── e2e/                    # 端到端测试
│   ├── test_full_workflow.py            # 完整工作流E2E测试
│   ├── test_multi_agent_collaboration.py # 多Agent协作E2E测试
│   └── test_setup_in_new_project.py     # 在其他项目中使用工作流框架的E2E测试
├── cli/                    # CLI命令测试
│   ├── test_basic_commands.py           # 基础命令测试
│   ├── test_agent_commands.py           # Agent命令测试
│   ├── test_team_commands.py            # 团队管理命令测试
│   └── test_workflow_commands.py       # 工作流命令测试
└── performance/            # 性能测试（待实现）
```

## 运行测试

### 运行所有测试
```bash
pytest tests/
```

### 运行特定类型的测试
```bash
# 单元测试
pytest tests/unit/

# 集成测试
pytest tests/integration/

# 端到端测试
pytest tests/e2e/

# CLI测试
pytest tests/cli/
```

### 运行特定测试文件
```bash
pytest tests/unit/test_models.py
```

### 运行特定测试用例
```bash
pytest tests/unit/test_models.py::TestAgentMessage::test_agent_message_creation
```

### 详细输出
```bash
pytest tests/ -v
```

### 显示覆盖率（需要pytest-cov）
```bash
pytest tests/ --cov=work_by_roles --cov-report=html
```

## 测试统计

- **总测试数**: 122+ (包含新增的 setup 测试)
- **通过率**: 100%
- **测试覆盖范围**:
  - 数据模型: ✅
  - Agent消息总线: ✅
  - 任务分解器: ✅
  - Agent类: ✅
  - AgentOrchestrator: ✅
  - 技能选择器: ✅
  - 执行追踪器: ✅
  - 工作流执行器: ✅
  - 角色管理器: ✅
  - 状态存储: ✅
  - 质量门控: ✅
  - 工作流集成: ✅
  - Agent协作: ✅
  - 技能系统: ✅
  - CLI命令: ✅
  - 在其他项目中使用工作流框架: ✅ (新增)

## 测试Fixtures

### temp_workspace
创建临时工作空间目录，测试后自动清理。

### sample_role
创建示例角色用于测试。

### sample_stage
创建示例阶段用于测试。

### sample_workflow
创建示例工作流用于测试。

### sample_skill
创建示例技能用于测试。

### workflow_engine
创建WorkflowEngine实例用于测试。

### message_bus
创建AgentMessageBus实例用于测试。

### sample_workflow_config
创建完整的示例工作流配置（包括角色、工作流、技能）。

## 编写新测试

1. 在相应的测试目录中创建测试文件
2. 使用现有的fixtures或创建新的fixtures
3. 遵循命名约定：`test_*.py` 和 `test_*` 函数
4. 使用适当的pytest标记（@pytest.mark.unit, @pytest.mark.integration等）
5. 确保测试独立且可重复运行

## 手动测试

### 测试在其他项目中使用工作流框架

项目根目录提供了一个手动测试脚本，可以测试完整的 setup 流程：

```bash
# 确保已安装工作流框架
pip install -e .

# 运行手动测试脚本
./test_setup_manual.sh
```

该脚本会：
1. 创建一个临时测试项目
2. 运行 `workflow setup` 命令
3. 验证所有配置文件是否正确创建
4. 测试基本命令是否可用

## 注意事项

- 所有测试使用临时目录，不会影响实际项目文件
- 测试后会自动清理临时文件
- 异步测试需要使用 `@pytest.mark.asyncio` 标记
- CLI测试可能需要模拟文件系统操作
- E2E测试 `test_setup_in_new_project.py` 测试了在其他项目中使用工作流框架的完整流程

