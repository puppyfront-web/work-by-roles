# 30秒快速接入

## 安装

```bash
# 克隆或下载项目后
pip install -e .
```

## 使用（2步，完全自动化）

### 🎯 方式 1: 一键接入（推荐，适合 IDE 环境）

```bash
# 1. 一键接入（自动配置角色和技能）
workflow setup

# 2. 直接使用角色执行任务
workflow role-execute product_analyst "分析用户登录功能需求"
workflow role-execute system_architect "设计微服务架构"
```

**适用场景**：
- ✅ Cursor、VS Code 等 IDE 环境
- ✅ 快速响应需求，无需复杂流程
- ✅ 直接调用角色处理任务

**完成！** 就这么简单。

### 🔄 方式 2: 完整工作流（适合大型项目）

```bash
# 1. 快速初始化（自动检测项目类型）
workflow init --quick

# 2. 一键执行全部阶段（自动使用 Agent + Skills）
workflow wfauto
```

**适用场景**：
- ✅ 大型项目，需要多阶段流程管理
- ✅ 需要完整的开发流程跟踪
- ✅ 团队协作，需要阶段化交付

**完成！** 就这么简单。

### ⭐ 方式 3: 从 SOP 文档生成团队（项目亮点）

如果你有标准操作流程（SOP）文档，可以一键生成完整的团队配置：

```bash
# 从 SOP 文档自动生成 roles、skills 和 workflow
workflow import-sop your_sop.md
```

> 💡 **核心特性**: 
> - 🎯 **完全自动化** - 自动使用 Agent + Skills，无需手动干预
> - 📝 **专注代码** - 默认不生成文档，专注于代码实现
> - 🚀 **零配置启动** - 自动检测项目类型，使用合适模板
> - ⭐ **SOP 导入** - 从标准操作流程文档一键生成虚拟团队配置

## 🎉 接入完成后的下一步

1. **查看可用角色和技能**
   ```bash
   workflow list-roles   # 查看所有角色
   workflow list-skills  # 查看所有技能
   ```

2. **开始使用角色**
   ```bash
   # 在 IDE 中直接使用
   workflow role-execute product_analyst "分析用户需求"
   ```

3. **从 SOP 文档生成团队（⭐ 推荐）**
   ```bash
   # 如果你有标准操作流程文档，可以一键生成配置
   workflow import-sop your_sop.md
   ```

4. **查看项目上下文**
   - 打开 `.workflow/TEAM_CONTEXT.md` 了解项目配置
   - 在 Cursor 中，AI 会自动读取此文件

## 📚 常用命令速查

### 一键接入后
```bash
workflow list-roles        # 查看所有可用角色
workflow list-skills       # 查看所有可用技能
workflow role-execute <role> "<requirement>"  # 使用角色执行任务
```

### 完整工作流模式
```bash
workflow status          # 查看状态
workflow start <stage>  # 启动阶段
workflow complete       # 完成当前阶段
workflow wfauto         # 一键执行全部阶段
```

### SOP 导入
```bash
workflow import-sop <sop_file>  # 从 SOP 文档生成配置
```

## 🐛 常见问题

### Q: 如何重置工作流状态？

```bash
# 删除状态文件
rm .workflow/state.yaml

# 或使用 --no-restore-state 参数
workflow wfauto --no-restore-state
```

### Q: 如何重新接入项目？

```bash
# 删除现有配置
rm -rf .workflow/

# 重新接入
workflow setup
```

### Q: 如何查看某个角色的详细信息？

```bash
workflow list-roles | grep product_analyst
```

### Q: 如何自定义技能？

在 `.workflow/skills/` 目录下创建技能目录，参考现有技能的格式创建 `Skill.md` 文件，使用 Anthropic 标准格式（YAML frontmatter + Markdown）。

### Q: 工作流执行失败怎么办？

1. 查看 `.workflow/logs/` 目录下的日志文件
2. 检查 `.workflow/state.yaml` 中的错误信息
3. 使用 `workflow status` 查看当前状态
4. 可以手动修复后继续执行

### Q: 如何在不同项目间共享技能？

- 在项目根目录创建 `skills/` 目录
- 将技能文件放在该目录下
- 系统会自动识别并使用共享技能
- 也可以使用符号链接指向共享的技能库

### Q: 支持哪些 LLM 提供商？

- OpenAI（GPT-3.5, GPT-4 等）
- Anthropic（Claude 系列）
- 任何兼容 OpenAI API 的服务（如 Ollama、LocalAI）

### Q: 如何测试 LLM 配置是否正确？

```bash
# 使用 --use-llm 参数测试
workflow role-execute product_analyst "测试" --use-llm
```

### Q: 如何切换不同的 LLM 提供商？

修改 `.workflow/config.yaml` 中的 `provider` 字段，或设置相应的环境变量（`OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`）。

## 📖 需要更多？

- 📖 查看 [README.md](README.md) 了解详细功能和实用技巧
- 🔗 查看 [角色与技能关系指南](ROLES_AND_SKILLS.md) 了解如何配置角色和技能
- 🧠 查看 [API文档](docs/API.md) 了解 Python API 使用方法
