# 30-Second Quick Start

## Installation

```bash
# After cloning or downloading the project
pip install -e .
```

## Usage (2 Steps, Fully Automated)

### 🎯 Method 1: One-Click Setup (Recommended for IDE environments)

```bash
# 1. One-click setup (automatically configure roles and skills)
workflow setup

# 2. Directly use roles to execute tasks
workflow role-execute product_analyst "Analyze user login feature requirements"
workflow role-execute system_architect "Design microservices architecture"
```

**Use Cases**:
- ✅ IDE environments like Cursor, VS Code
- ✅ Quick response to requirements without complex processes
- ✅ Direct role invocation for task handling

**Done!** It's that simple.

### 🔄 Method 2: Full Workflow (Suitable for large projects)

```bash
# 1. Quick initialization (automatically detect project type)
workflow init --quick

# 2. Auto-execute all stages (automatically use Agent + Skills)
workflow wfauto
```

**Use Cases**:
- ✅ Large projects requiring multi-stage process management
- ✅ Complete development process tracking
- ✅ Team collaboration requiring staged delivery

**Done!** It's that simple.

### ⭐ Method 3: Generate Team from SOP Document (Project Highlight)

If you have a Standard Operating Procedure (SOP) document, you can generate a complete team configuration with one click:

```bash
# Automatically generate roles, skills, and workflow from SOP document
workflow import-sop your_sop.md
```

> 💡 **Core Features**: 
> - 🎯 **Fully Automated** - Automatically use Agent + Skills without manual intervention
> - 📝 **Code-Focused** - Default to not generating documentation, focus on code implementation
> - 🚀 **Zero-Config Startup** - Automatically detect project type and use appropriate templates
> - ⭐ **SOP Import** - Generate virtual team configuration from SOP documents with one click

## 🎉 Next Steps After Setup

1. **View Available Roles and Skills**
   ```bash
   workflow list-roles   # View all roles
   workflow list-skills  # View all skills
   ```

2. **Start Using Roles**
   ```bash
   # Use directly in IDE
   workflow role-execute product_analyst "Analyze user requirements"
   ```

3. **Generate Team from SOP Document (⭐ Recommended)**
   ```bash
   # If you have an SOP document, generate configuration with one click
   workflow import-sop your_sop.md
   ```

4. **View Project Context**
   - Open `.workflow/TEAM_CONTEXT.md` to understand project configuration
   - In Cursor, AI will automatically read this file

## 📚 Common Commands Quick Reference

### After One-Click Setup
```bash
workflow list-roles        # View all available roles
workflow list-skills       # View all available skills
workflow role-execute <role> "<requirement>"  # Use role to execute task
```

### Full Workflow Mode
```bash
workflow status          # View status
workflow start <stage>  # Start stage
workflow complete       # Complete current stage
workflow wfauto         # Auto-execute all stages
```

### SOP Import
```bash
workflow import-sop <sop_file>  # Generate configuration from SOP document
```

## 🐛 FAQ

### Q: How to reset workflow state?

```bash
# Delete state file
rm .workflow/state.yaml

# Or use --no-restore-state parameter
workflow wfauto --no-restore-state
```

### Q: How to re-setup the project?

```bash
# Delete existing configuration
rm -rf .workflow/

# Re-setup
workflow setup
```

### Q: How to view detailed information about a role?

```bash
workflow list-roles | grep product_analyst
```

### Q: How to customize skills?

Create a skill directory under `.workflow/skills/`, and create a `Skill.md` file following the existing skill format (Anthropic standard format: YAML frontmatter + Markdown).

### Q: What to do if workflow execution fails?

1. Check log files in `.workflow/logs/` directory
2. Check error information in `.workflow/state.yaml`
3. Use `workflow status` to view current state
4. You can manually fix and continue execution

### Q: How to share skills between different projects?

- Create a `skills/` directory in the project root
- Place skill files in this directory
- The system will automatically recognize and use shared skills
- You can also use symbolic links to point to a shared skill library

### Q: Which LLM providers are supported?

- OpenAI (GPT-3.5, GPT-4, etc.)
- Anthropic (Claude series)
- Any service compatible with OpenAI API (such as Ollama, LocalAI)

### Q: How to test if LLM configuration is correct?

```bash
# Test with --use-llm parameter
workflow role-execute product_analyst "Test" --use-llm
```

### Q: How to switch between different LLM providers?

Modify the `provider` field in `.workflow/config.yaml`, or set the corresponding environment variables (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`).

## 📖 Need More?

- 📖 View [README.md](README.md) for detailed features and tips
- 🔗 View [Roles and Skills Guide](ROLES_AND_SKILLS.md) to understand how to configure roles and skills
- 🧠 View [API Documentation](docs/API.md) to learn Python API usage
