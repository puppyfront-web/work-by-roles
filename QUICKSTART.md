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

## 📖 需要更多？

- 📖 查看 [README.md](README.md) 了解详细功能和实用技巧
- 🔗 查看 [角色与技能关系指南](ROLES_AND_SKILLS.md) 了解如何配置角色和技能
- 🧠 查看 [API文档](docs/API.md) 了解 Python API 使用方法
