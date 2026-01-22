# API Service 开发模板

适用于API服务开发的工作流模板。

## 特点

- 针对RESTful API、GraphQL等API服务优化
- 包含API设计、实现、测试等阶段
- 适合FastAPI、Flask、Express等框架

## 使用

```bash
# 方式 1: 使用 init 命令
workflow init --template api-service

# 方式 2: 使用 setup 命令（推荐，自动检测项目类型）
workflow setup
```

或使用 Python API：

```python
from work_by_roles import Workflow
workflow = Workflow.from_template("api-service")
```

