# 安装和使用指南

## 方式一：作为 Python 包安装（推荐）

### 1. 从本地安装（开发模式）

```bash
# 在框架项目根目录
pip install -e .

# 或者指定路径
pip install -e /path/to/work-by-roles
```

### 2. 从 Git 仓库安装

```bash
pip install git+https://github.com/puppyfront-web/work-by-roles.git
```

### 3. 安装后使用

安装后，你可以使用全局命令：

```bash
# 快速接入新项目
workflow-bootstrap --template standard_agile --target /path/to/new/project

# 使用 CLI
workflow-cli status
workflow-cli start requirements product_analyst
```

### 4. 在 Python 代码中使用

```python
from work_by_roles import WorkflowEngine
from pathlib import Path

engine = WorkflowEngine(Path("."))
engine.load_all_configs(
    skill_file=Path("skill_library.yaml"),
    roles_file=Path("role_schema.yaml"),
    workflow_file=Path("workflow_schema.yaml")
)
```

## 方式二：直接使用 bootstrap.py（无需安装）

如果你不想安装包，可以直接使用 bootstrap.py：

```bash
# 1. 克隆或下载框架
git clone https://github.com/puppyfront-web/work-by-roles.git
cd work-by-roles

# 2. 在新项目中使用
python bootstrap.py --template standard_agile --target /path/to/new/project
```

## 在新项目中使用

### 步骤 1: 快速接入

```bash
# 方式 A: 使用全局命令（如果已安装）
workflow-bootstrap --template standard_agile

# 方式 B: 使用 bootstrap.py（如果未安装）
python /path/to/work-by-roles/bootstrap.py --template standard_agile
```

### 步骤 2: 初始化工作流

```bash
cd /path/to/new/project
python .workflow/workflow_cli.py init
```

### 步骤 3: 开始工作

```bash
# 查看可用阶段和角色
python .workflow/workflow_cli.py list-stages
python .workflow/workflow_cli.py list-roles

# 启动阶段
python .workflow/workflow_cli.py start requirements product_analyst

# 查看状态
python .workflow/workflow_cli.py status

# 完成阶段
python .workflow/workflow_cli.py complete requirements
```

### 步骤 4: 在 Vibe Coding 中使用

在 Cursor 或其他 AI 编辑器中，使用 `@[team]` 语法：

```
@[team] 帮我修复这个 bug
@[team] wfauto  # 自动执行完整工作流
@[team] 运行完整工作流  # 同样会触发 wfauto
```

AI 会自动读取 `.workflow/TEAM_CONTEXT.md` 并应用当前角色的约束。当使用 `@[team]` 并请求工作流自动化时，会自动执行 `workflow wfauto` 命令。

## 验证安装

```bash
# 检查包是否安装
python -c "import work_by_roles; print(work_by_roles.__version__)"

# 检查命令是否可用
workflow-cli --help
workflow-bootstrap --help
```

## 卸载

```bash
pip uninstall work-by-roles
```

