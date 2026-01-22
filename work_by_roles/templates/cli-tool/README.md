# CLI Tool 开发模板

适用于命令行工具开发的工作流模板。

## 特点

- 针对CLI工具开发优化
- 包含命令设计、参数解析、测试等阶段
- 适合Python、Go、Rust等语言的CLI工具

## 使用

```bash
# 方式 1: 使用 init 命令
workflow init --template cli-tool

# 方式 2: 使用 setup 命令（推荐，自动检测项目类型）
workflow setup
```

或使用 Python API：

```python
from work_by_roles import Workflow
workflow = Workflow.from_template("cli-tool")
```

