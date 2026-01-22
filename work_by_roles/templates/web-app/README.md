# Web App 开发模板

适用于Web应用开发的工作流模板。

## 特点

- 针对前端+后端Web应用优化
- 包含前端开发、后端API、集成测试等阶段
- 适合React、Vue、Next.js等现代Web框架

## 使用

```bash
# 方式 1: 使用 init 命令
workflow init --template web-app

# 方式 2: 使用 setup 命令（推荐，自动检测项目类型）
workflow setup
```

或使用 Python API：

```python
from work_by_roles import Workflow
workflow = Workflow.from_template("web-app")
```

