# 测试Fixtures使用指南

本目录包含增强的测试fixtures和辅助类，用于简化workflow setup和CLI命令的自动化测试。

## 核心组件

### ProjectTestHelper类

封装项目操作的辅助类，提供以下方法：

- `setup(template=None)`: 运行workflow setup命令
- `reset()`: 清理.workflow目录
- `run_command(command)`: 执行CLI命令
- `assert_setup_success(result)`: 验证setup成功
- `assert_file_exists(path)`: 验证文件存在
- `assert_workflow_file_exists(filename)`: 验证workflow配置文件存在
- `read_yaml(path)`: 读取YAML文件
- `create_project_file(path, content)`: 创建项目文件

### CommandTester类

封装命令测试的辅助类，提供以下方法：

- `test_setup(template=None)`: 测试setup命令
- `test_status()`: 测试status命令
- `test_list_roles()`: 测试list-roles命令
- `test_list_skills()`: 测试list-skills命令
- `test_wfauto(intent=None, **kwargs)`: 测试wfauto命令
- `test_init(template=None, quick=False)`: 测试init命令
- `test_role_execute(role, requirement)`: 测试role-execute命令

## Fixtures

### clean_project

创建干净的临时项目（无.workflow），测试后自动清理。

```python
def test_something(clean_project: ProjectTestHelper):
    result = clean_project.setup()
    clean_project.assert_setup_success(result)
```

### fresh_project

创建已运行setup的项目，自动重置和清理。

```python
def test_something(fresh_project: ProjectTestHelper):
    # .workflow目录已存在，可以直接测试命令
    assert fresh_project.workflow_dir.exists()
```

### project_with_files

创建包含真实文件结构的项目（src/, tests/, requirements.txt等）。

```python
def test_setup_with_files(project_with_files: ProjectTestHelper):
    result = project_with_files.setup()
    # 验证项目上下文包含文件信息
```

### project_with_template

参数化测试不同模板（standard-delivery, vibe-coding等）。

```python
def test_template(project_with_template: ProjectTestHelper):
    # 自动测试多个模板
    assert project_with_template.workflow_dir.exists()
```

### command_tester

基于fresh_project创建CommandTester实例。

```python
def test_commands(command_tester: CommandTester):
    assert command_tester.test_list_roles()["success"]
    assert command_tester.test_list_skills()["success"]
```

### command_tester_clean

基于clean_project创建CommandTester实例（未setup）。

```python
def test_init(command_tester_clean: CommandTester):
    result = command_tester_clean.test_init(quick=True)
    assert result["success"]
```

## 使用示例

### 基本使用

```python
def test_setup_and_verify(clean_project: ProjectTestHelper):
    """测试setup并验证文件创建"""
    result = clean_project.setup()
    clean_project.assert_setup_success(result)
    
    # 验证文件存在
    clean_project.assert_workflow_file_exists("role_schema.yaml")
    clean_project.assert_workflow_file_exists("workflow_schema.yaml")
```

### 测试命令

```python
def test_all_commands(command_tester: CommandTester):
    """测试所有CLI命令"""
    assert command_tester.test_status()["success"]
    assert command_tester.test_list_roles()["success"]
    assert command_tester.test_list_skills()["success"]
    assert command_tester.test_wfauto(no_agent=True)["success"]
```

### 测试完整流程

```python
def test_complete_flow(clean_project: ProjectTestHelper):
    """测试完整的setup和命令执行流程"""
    # Setup
    result = clean_project.setup()
    clean_project.assert_setup_success(result)
    
    # 创建CommandTester
    tester = CommandTester(clean_project)
    
    # 测试命令
    assert tester.test_status()["success"]
    assert tester.test_list_roles()["success"]
    assert tester.test_list_skills()["success"]
```

### 测试不同模板

```python
def test_templates(project_with_template: ProjectTestHelper):
    """参数化测试不同模板"""
    # 自动测试standard-delivery, vibe-coding等
    assert project_with_template.workflow_dir.exists()
    project_with_template.assert_workflow_file_exists("role_schema.yaml")
```

### 测试重置和重试

```python
def test_reset(clean_project: ProjectTestHelper):
    """测试重置项目"""
    # 第一次setup
    result1 = clean_project.setup()
    clean_project.assert_setup_success(result1)
    
    # 重置
    clean_project.reset()
    assert not clean_project.workflow_dir.exists()
    
    # 第二次setup
    result2 = clean_project.setup()
    clean_project.assert_setup_success(result2)
```

## 优势

1. **自动化**：无需手动切换项目或删除.workflow目录
2. **隔离**：每个测试使用独立的临时项目
3. **可重复**：测试完全独立，可重复运行
4. **参数化**：自动测试多个模板
5. **简洁**：测试代码更简洁，易于维护

## 注意事项

- 所有临时项目在测试后自动清理
- 确保测试不依赖外部项目状态
- 使用`command_tester`时，确保项目已运行setup（使用`fresh_project`或手动setup）
- 参数化fixture（如`project_with_template`）会自动为每个参数运行测试

## 迁移指南

### 从旧方式迁移

**旧方式**：
```python
def test_setup(temp_workspace):
    project_dir = temp_workspace / "new_project"
    project_dir.mkdir()
    
    result = subprocess.run(
        [sys.executable, "-m", "work_by_roles.cli", "setup"],
        cwd=project_dir,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
```

**新方式**：
```python
def test_setup(clean_project: ProjectTestHelper):
    result = clean_project.setup()
    clean_project.assert_setup_success(result)
```

新方式更简洁，自动处理项目创建和清理。
