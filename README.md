# 多角色技能工作流框架

一个轻量级的工作流约束框架，通过角色边界和工作流阶段来规范开发流程。

## 🚀 30秒快速接入

👉 **[查看快速开始指南](QUICKSTART.md)** - 2步完成接入

```bash
pip install -e .
workflow init --quick
workflow wfauto  # 自动使用 Agent + Skills 执行
```

> 💡 **完全自动化** - 自动使用 Agent + Skills，默认不生成文档，专注于代码实现

## 核心概念

### 模式 1: Workflow 模式（多阶段流程，可选）
- **角色（Role）**: 谁做什么
- **阶段（Stage）**: 什么时候做什么
- **适用场景**: 需要结构化流程的大型项目

### 模式 2: Role Executor 模式（简化模式，推荐用于 IDE）
- **角色（Role）**: 谁做什么
- **技能（Skills）**: 角色使用什么能力（Anthropic 标准格式）
- **直接执行**: 无需定义 workflow 阶段，直接调用角色处理需求
- **适用场景**: IDE 环境（如 Cursor），快速响应需求

**就这么简单！** 在 IDE（如 Cursor）中，推荐使用 Role Executor 模式，更简单直接。

### Skills 格式

项目使用 **Anthropic 标准格式**，每个技能是一个目录，包含 `Skill.md` 文件：

```
skills/
  requirements_analysis/
    Skill.md  # YAML frontmatter + Markdown
```

这种格式便于在不同项目间共享和复用技能。

## 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 安装/开发模式（推荐）
pip install -e .
```

## 常用命令

### 新项目一键接入（推荐）
```bash
workflow setup             # 一键接入，自动配置角色和技能
workflow list-roles        # 查看所有可用角色
workflow list-skills       # 查看所有可用技能
workflow role-execute <role> "<requirement>"  # 使用角色执行任务
```

### 在 Cursor IDE 中使用（最简单）
```bash
# 1. 接入项目
workflow setup

# 2. 在 Cursor 对话中直接使用：
#    @product_analyst 分析用户需求
#    @system_architect 设计系统架构
#    @team 实现完整功能
```

👉 **[查看 Cursor 使用指南](docs/CURSOR_GUIDE.md)** - 详细说明如何在 Cursor 中使用

### Workflow 模式（多阶段流程，可选）
```bash
workflow init --quick      # 快速初始化（推荐）
workflow wfauto            # 一键执行全部阶段（自动使用 Agent + Skills）
workflow status            # 查看状态
workflow team list         # 列出所有团队
```

### Role Executor 模式（简化模式，推荐用于 IDE）
```bash
workflow role-execute <role_id> "<requirement>"  # 直接执行角色处理需求
workflow role-execute product_analyst "分析用户登录功能需求"
workflow role-execute system_architect "设计微服务架构" --use-llm
```

> 💡 **核心特性**: 
> - `workflow wfauto` 自动使用 Agent + Skills 执行，完全自动化，无需手动干预
> - `workflow role-execute` 简化模式，无需定义 workflow 阶段，直接在 IDE 中使用

## LLM 配置

使用 `--use-llm` 参数时需要配置 LLM 客户端。系统支持两种配置方式：

### 方式 1: 环境变量（推荐）

```bash
# OpenAI
export OPENAI_API_KEY='your-api-key'

# 或 Anthropic
export ANTHROPIC_API_KEY='your-api-key'

# 可选：指定模型
export LLM_MODEL='gpt-4'

# 可选：指定自定义端点（用于本地部署或其他兼容服务）
export OPENAI_BASE_URL='http://localhost:11434/v1'
```

### 方式 2: 配置文件

创建 `.workflow/config.yaml` 文件：

```yaml
llm:
  provider: openai  # 或 "anthropic"
  api_key: your-api-key  # 或从环境变量读取（留空）
  model: gpt-4  # 可选
  base_url: https://api.openai.com/v1  # 可选，用于自定义端点（如本地部署的模型）
```

**支持自定义模型端点**：通过 `base_url` 可以连接兼容 OpenAI API 的其他服务，如：
- 本地部署的模型（如 Ollama、LocalAI）
- 其他云服务商的兼容 API
- 代理服务

示例（连接本地 Ollama）：
```yaml
llm:
  provider: openai
  api_key: not-needed  # 本地部署可能不需要 API key
  model: llama2
  base_url: http://localhost:11434/v1
```

**配置优先级**: 环境变量 > 配置文件

**注意**: 如果使用 `--use-llm` 但未配置 LLM 客户端，系统会抛出错误并提示配置方法。

## Python API

```python
from work_by_roles import Workflow

workflow = Workflow.quick_start()
workflow.start("requirements")
workflow.complete()
```

更多API详情见 [API文档](docs/API.md)

## 文档

- 📖 [快速开始](QUICKSTART.md) - 30秒接入指南
- 📚 [完整使用指南](docs/USAGE_GUIDE.md) - 包含IDE集成、测试、快速参考
- 🎭 [Role Executor 指南](docs/ROLE_EXECUTOR_GUIDE.md) - 简化模式使用指南（推荐用于 IDE）
- 🧠 [API文档](docs/API.md) - 详细API参考
- ⭐ [技能指南](docs/SKILLS_GUIDE.md) - 自定义技能（高级功能）

## 开源协议

MIT License - 详见 [LICENSE](LICENSE)

## 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献指南。

## 社区

- 报告问题：[GitHub Issues](https://github.com/puppyfront-web/work-by-roles/issues)
- 功能建议：[GitHub Discussions](https://github.com/puppyfront-web/work-by-roles/discussions)

## 项目状态

✅ **生产就绪** - 所有核心功能已实现并通过测试

