# 多角色技能工作流框架

> 一个轻量级的工作流约束框架，通过角色边界和工作流阶段来规范开发流程。

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[中文](README.md) | [English](README_EN.md)

## ✨ 核心特性

- 🎯 **角色驱动** - 通过角色边界规范任务分配和执行
- 🛠️ **技能库管理** - 支持 Anthropic 标准格式的技能定义
- 🔄 **双模式支持** - Workflow 模式（多阶段）和 Role Executor 模式（简化）
- ⭐ **SOP 导入** - 从标准操作流程文档一键生成团队配置
- 🤖 **Agent 编排** - 自动使用 Agent + Skills 执行任务
- 🔌 **MCP 集成** - 支持 Model Context Protocol 调用外部服务
- 📦 **零配置启动** - 自动检测项目类型，使用合适模板

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/puppyfront-web/work-by-roles.git
cd work-by-roles
pip install -e .
```

### 使用（2 种方式）

**方式 1：一键接入（推荐，适合 IDE 环境）**
```bash
workflow setup
workflow role-execute product_analyst "分析用户登录功能需求"
```

**方式 2：完整工作流（适合大型项目）**
```bash
workflow init --quick
workflow wfauto --intent "实现用户登录功能"
```

📖 **详细指南**: [QUICKSTART.md](QUICKSTART.md) | [完整文档](#-文档)

## 🎯 核心概念

### 两种工作模式

**Workflow 模式** - 多阶段流程，适合大型项目
```
需求分析 → 系统设计 → 架构设计 → 代码实现 → 质量保证 → 完成
```

**Role Executor 模式** - 简化模式，适合 IDE 环境（推荐）
```
用户需求 → 直接调用角色 → 角色使用技能 → 完成任务
```

### 关键概念

- **角色（Role）**: 谁做什么（如：产品分析师、系统架构师）
- **技能（Skill）**: 角色使用的能力（Anthropic 标准格式）
- **阶段（Stage）**: 什么时候做什么（Workflow 模式）

## 📚 常用命令

| 命令 | 说明 |
|------|------|
| `workflow setup` | 一键接入项目 |
| `workflow list-roles` | 列出所有角色 |
| `workflow list-skills` | 列出所有技能 |
| `workflow role-execute <role> "<requirement>"` | 执行角色任务 |
| `workflow import-sop <file>` | 从 SOP 文档生成配置 |
| `workflow status` | 查看工作流状态 |

**工作流模式命令**:
```bash
workflow init --quick      # 快速初始化
workflow wfauto            # 自动执行全部阶段
workflow start <stage>     # 启动特定阶段
workflow complete          # 完成当前阶段
```

## ⭐ 核心功能

### SOP 文档导入

从标准操作流程文档自动生成团队配置：

```bash
workflow import-sop your_sop.md
```

**功能特点**:
- 🎯 智能提取角色、技能和工作流
- 🔄 自动匹配团队模板
- 📝 生成 Anthropic 标准格式技能文件
- 🤖 支持 LLM 增强分析（可选）

📖 [查看示例](examples/ecommerce_order_sop.md)

### LLM 配置

支持多种 LLM 提供商（OpenAI、Anthropic、Ollama 等）：

**环境变量方式**:
```bash
export OPENAI_API_KEY='your-api-key'
export LLM_MODEL='gpt-4'
```

**配置文件方式** (`.workflow/config.yaml`):
```yaml
llm:
  provider: openai
  api_key: your-api-key
  model: gpt-4
```

📖 [详细配置指南](docs/ARCHITECTURE.md#6-配置系统)

### MCP 集成

支持通过 Model Context Protocol 调用外部服务：

```yaml
# 在技能定义中添加 MCP 配置
metadata:
  mcp:
    action: fetch_resource
    server: cursor-browser-extension
    resource_uri: "mcp://cursor-browser-extension/page/content"
```

📖 [MCP 集成指南](docs/ARCHITECTURE.md#38-mcp-集成)

## 💡 使用场景

**快速分析需求**
```bash
workflow role-execute product_analyst "分析用户登录功能需求" --use-llm
```

**设计系统架构**
```bash
workflow role-execute system_architect "设计微服务架构" --use-llm
```

**完整功能实现**
```bash
workflow wfauto --intent "实现用户登录功能，包含注册、登录、登出和密码重置"
```

**代码审查**
```bash
workflow role-execute qa_reviewer "检查代码质量和测试覆盖率" --use-llm
```

## 🐍 Python API

```python
from work_by_roles import Workflow

# 零配置启动
workflow = Workflow.quick_start()

# 启动阶段
workflow.start("requirements")

# 完成阶段
workflow.complete()

# 查看状态
status = workflow.status()
```

📖 [完整 API 文档](docs/API.md)

## 📖 文档

- 📖 [快速开始](QUICKSTART.md) - 30秒接入指南
- 🔗 [角色与技能关系指南](ROLES_AND_SKILLS.md) - 理解角色和技能的关系
- 🧠 [API 文档](docs/API.md) - 详细 API 参考
- 🏗️ [架构文档](docs/ARCHITECTURE.md) - 系统架构和设计说明
- 📊 [技能分层分类](docs/SKILLS_LAYERED_CLASSIFICATION.md) - 技能分类体系

## 🐛 常见问题

**Q: 如何重置工作流状态？**
```bash
rm .workflow/state.yaml
# 或使用 --no-restore-state 参数
workflow wfauto --no-restore-state
```

**Q: 如何自定义技能？**
在 `.workflow/skills/` 目录下创建技能目录，参考现有技能格式创建 `Skill.md` 文件（Anthropic 标准格式）。

**Q: 支持哪些 LLM 提供商？**
OpenAI、Anthropic、以及任何兼容 OpenAI API 的服务（如 Ollama、LocalAI）。

**Q: 工作流执行失败怎么办？**
1. 查看 `.workflow/logs/` 目录下的日志文件
2. 检查 `.workflow/state.yaml` 中的错误信息
3. 使用 `workflow status` 查看当前状态

📖 [更多常见问题](QUICKSTART.md#常见问题)

## 📊 项目状态

✅ **生产就绪** - 所有核心功能已实现并通过测试

**功能特性**:
- ✅ 一键接入，零配置启动
- ✅ 支持多种 IDE（Cursor、VS Code 等）
- ✅ 自动使用 Agent + Skills 执行
- ✅ 支持多种 LLM 提供商
- ✅ MCP 协议集成
- ✅ 完整的 Python API
- ✅ 丰富的项目模板

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献指南。

## 📄 开源协议

MIT License - 详见 [LICENSE](LICENSE)

## 🔗 相关链接

- 📝 [报告问题](https://github.com/puppyfront-web/work-by-roles/issues)
- 💬 [功能建议](https://github.com/puppyfront-web/work-by-roles/discussions)
- 📧 联系: puppy.front@gmail.com

---

**开始使用**: [快速开始](#-快速开始) | [查看文档](#-文档) | [报告问题](https://github.com/puppyfront-web/work-by-roles/issues)
