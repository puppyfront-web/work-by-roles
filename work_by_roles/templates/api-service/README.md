# API Service 开发模板

适用于API服务开发的工作流模板。

## 特点

- 针对RESTful API、GraphQL等API服务优化
- 包含API设计、实现、测试等阶段
- 适合FastAPI、Flask、Express等框架

## 使用

```bash
workflow-bootstrap --template api-service
```

或使用快速启动：

```python
from work_by_roles import Workflow
workflow = Workflow.from_template("api-service")
```

