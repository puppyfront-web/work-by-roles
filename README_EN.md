# Multi-Role Skills Workflow Framework

> A lightweight workflow constraint framework that standardizes development processes through role boundaries and workflow stages.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[中文](README.md) | English

## ✨ Core Features

- 🎯 **Role-Driven** - Standardize task assignment and execution through role boundaries
- 🛠️ **Skill Library Management** - Support for Anthropic standard format skill definitions
- 🔄 **Dual Mode Support** - Workflow mode (multi-stage) and Role Executor mode (simplified)
- ⭐ **SOP Import** - Generate team configurations from standard operating procedure documents with one click
- 🤖 **Agent Orchestration** - Automatically execute tasks using Agent + Skills
- 🔌 **MCP Integration** - Support for Model Context Protocol to call external services
- 📦 **Zero-Config Startup** - Automatically detect project type and use appropriate templates

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/puppyfront-web/work-by-roles.git
cd work-by-roles
pip install -e .
```

### Usage (2 Ways)

**Method 1: One-Click Setup (Recommended for IDE environments)**
```bash
workflow setup
workflow role-execute product_analyst "Analyze user login feature requirements"
```

**Method 2: Full Workflow (Suitable for large projects)**
```bash
workflow init --quick
workflow wfauto --intent "Implement user login functionality"
```

📖 **Detailed Guide**: [QUICKSTART_EN.md](QUICKSTART_EN.md) | [Full Documentation](#-documentation)

## 🎯 Core Concepts

### Two Working Modes

**Workflow Mode** - Multi-stage process, suitable for large projects
```
Requirements Analysis → System Design → Architecture Design → Code Implementation → Quality Assurance → Complete
```

**Role Executor Mode** - Simplified mode, suitable for IDE environments (Recommended)
```
User Requirements → Direct Role Call → Role Uses Skills → Complete Task
```

### Key Concepts

- **Role**: Who does what (e.g., Product Analyst, System Architect)
- **Skill**: Capabilities used by roles (Anthropic standard format)
- **Stage**: When to do what (Workflow mode)

## 📚 Common Commands

| Command | Description |
|---------|-------------|
| `workflow setup` | One-click project setup |
| `workflow list-roles` | List all roles |
| `workflow list-skills` | List all skills |
| `workflow role-execute <role> "<requirement>"` | Execute role task |
| `workflow import-sop <file>` | Generate configuration from SOP document |
| `workflow status` | View workflow status |

**Workflow Mode Commands**:
```bash
workflow init --quick      # Quick initialization
workflow wfauto            # Auto-execute all stages
workflow start <stage>     # Start specific stage
workflow complete          # Complete current stage
```

## ⭐ Core Features

### SOP Document Import

Automatically generate team configurations from standard operating procedure documents:

```bash
workflow import-sop your_sop.md
```

**Features**:
- 🎯 Intelligent extraction of roles, skills, and workflows
- 🔄 Automatic team template matching
- 📝 Generate Anthropic standard format skill files
- 🤖 Support for LLM-enhanced analysis (optional)

📖 [View Example](examples/ecommerce_order_sop.md) (Chinese example, English version coming soon)

### LLM Configuration

Support for multiple LLM providers (OpenAI, Anthropic, Ollama, etc.):

**Environment Variables**:
```bash
export OPENAI_API_KEY='your-api-key'
export LLM_MODEL='gpt-4'
```

**Configuration File** (`.workflow/config.yaml`):
```yaml
llm:
  provider: openai
  api_key: your-api-key
  model: gpt-4
```

📖 [Detailed Configuration Guide](docs/ARCHITECTURE.md#6-配置系统) (See Architecture docs for LLM configuration details)

### MCP Integration

Support for calling external services through Model Context Protocol:

```yaml
# Add MCP configuration in skill definition
metadata:
  mcp:
    action: fetch_resource
    server: cursor-browser-extension
    resource_uri: "mcp://cursor-browser-extension/page/content"
```

📖 [MCP Integration Guide](docs/ARCHITECTURE.md#38-mcp-集成) (See Architecture docs for MCP integration details)

## 💡 Use Cases

**Quick Requirements Analysis**
```bash
workflow role-execute product_analyst "Analyze user login feature requirements" --use-llm
```

**System Architecture Design**
```bash
workflow role-execute system_architect "Design microservices architecture" --use-llm
```

**Complete Feature Implementation**
```bash
workflow wfauto --intent "Implement user login functionality including registration, login, logout, and password reset"
```

**Code Review**
```bash
workflow role-execute qa_reviewer "Check code quality and test coverage" --use-llm
```

## 🐍 Python API

```python
from work_by_roles import Workflow

# Zero-config startup
workflow = Workflow.quick_start()

# Start stage
workflow.start("requirements")

# Complete stage
workflow.complete()

# View status
status = workflow.status()
```

📖 [Full API Documentation](docs/API_EN.md)

## 📖 Documentation

- 📖 [Quick Start](QUICKSTART_EN.md) - 30-second setup guide
- 🔗 [Roles and Skills Guide](ROLES_AND_SKILLS_EN.md) - Understanding role and skill relationships
- 🧠 [API Documentation](docs/API_EN.md) - Detailed API reference
- 🏗️ [Architecture Documentation](docs/ARCHITECTURE.md) - System architecture and design (Chinese, English version coming soon)
- 📊 [Skills Layered Classification](docs/SKILLS_LAYERED_CLASSIFICATION_EN.md) - Skills classification system

## 🐛 FAQ

**Q: How to reset workflow state?**
```bash
rm .workflow/state.yaml
# Or use --no-restore-state parameter
workflow wfauto --no-restore-state
```

**Q: How to customize skills?**
Create a skill directory under `.workflow/skills/`, and create a `Skill.md` file following the existing skill format (Anthropic standard format).

**Q: Which LLM providers are supported?**
OpenAI, Anthropic, and any service compatible with OpenAI API (such as Ollama, LocalAI).

**Q: What to do if workflow execution fails?**
1. Check log files in `.workflow/logs/` directory
2. Check error information in `.workflow/state.yaml`
3. Use `workflow status` to view current state

📖 [More FAQs](QUICKSTART_EN.md#faq)

## 📊 Project Status

✅ **Production Ready** - All core features implemented and tested

**Features**:
- ✅ One-click setup, zero-config startup
- ✅ Support for multiple IDEs (Cursor, VS Code, etc.)
- ✅ Automatic execution using Agent + Skills
- ✅ Support for multiple LLM providers
- ✅ MCP protocol integration
- ✅ Complete Python API
- ✅ Rich project templates

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING_EN.md](CONTRIBUTING_EN.md) for contribution guidelines.

## 📄 License

MIT License - See [LICENSE](LICENSE) for details

## 🔗 Links

- 📝 [Report Issues](https://github.com/puppyfront-web/work-by-roles/issues)
- 💬 [Feature Suggestions](https://github.com/puppyfront-web/work-by-roles/discussions)
- 📧 Contact: puppy.front@gmail.com

---

**Get Started**: [Quick Start](#-quick-start) | [Documentation](#-documentation) | [Report Issues](https://github.com/puppyfront-web/work-by-roles/issues)
