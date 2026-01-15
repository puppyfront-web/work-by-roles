# 在其他项目中使用工作流框架

本指南说明如何在其他项目中使用 Multi-Role Skills Workflow 框架。

## 🚀 快速开始（推荐）

### 步骤 1: 安装工作流框架

```bash
# 方式 A: 从本地安装（开发模式，推荐）
cd /path/to/work-by-roles
pip install -e .

# 方式 B: 从 Git 仓库安装（如果已发布）
pip install git+https://github.com/puppyfront-web/work-by-roles.git
```

### 步骤 2: 在新项目中一键接入

```bash
# 进入你的项目目录
cd /path/to/your-project

# 一键接入（自动配置角色和技能）
workflow setup
```

**完成！** 现在你的项目已经可以使用工作流框架了。

### 步骤 3: 开始使用

#### 在 Cursor IDE 中使用（推荐）

在 Cursor 的对话中直接使用：

```
@product_analyst 分析用户登录功能的需求
@system_architect 设计微服务架构
@core_framework_engineer 实现用户认证模块
@qa_reviewer 检查代码质量和测试覆盖率
```

或者使用 `@team` 触发完整工作流：

```
@team 实现用户登录功能
```

**沉浸式体验**：在 Cursor IDE 中执行工作流时，会自动显示：
- 实时工作流进度和阶段状态
- 生成的文档内容预览（需求文档、架构文档等）
- 代码编写过程追踪
- 质量检查结果反馈

#### 命令行使用

```bash
# 查看可用角色
workflow list-roles

# 查看可用技能
workflow list-skills

# 使用角色执行任务
workflow role-execute product_analyst "分析用户登录功能的需求"
workflow role-execute system_architect "设计微服务架构"
workflow role-execute core_framework_engineer "实现用户认证模块"

# 使用完整工作流（如果配置了 workflow_schema.yaml）
workflow init --quick
workflow wfauto
```

## 📋 详细步骤说明

### 方式一：安装包方式（推荐）

#### 1. 安装框架

```bash
# 在框架项目目录
cd /Users/tutu/apps/work-by-roles
pip install -e .
```

安装后，全局可以使用 `workflow` 命令。

#### 2. 在新项目中接入

```bash
# 进入你的项目目录
cd /path/to/your-project

# 一键接入
workflow setup
```

这个命令会：
- 创建 `.workflow/` 目录
- 复制角色配置（`role_schema.yaml`）
- 复制技能目录（`skills/`）
- 可选复制工作流配置（`workflow_schema.yaml`）
- 生成项目上下文文件
- 生成使用说明（`.workflow/USAGE.md`）

#### 3. 验证安装

```bash
# 检查命令是否可用
workflow --help

# 查看可用角色
workflow list-roles

# 查看可用技能
workflow list-skills
```

### 方式二：直接使用 bootstrap（无需安装）

如果你不想安装包，可以直接使用 bootstrap.py：

```bash
# 1. 在新项目目录中
cd /path/to/your-project

# 2. 使用 bootstrap（指定框架路径）
python /path/to/work-by-roles/work_by_roles/bootstrap.py \
  --template standard-delivery \
  --target .

# 3. 然后使用本地 CLI
python .workflow/workflow_cli.py setup
```

## 🎯 使用场景

### 场景 1: IDE 环境（Cursor）快速使用

**最简单的方式** - 直接使用角色：

```bash
# 1. 接入项目
workflow setup

# 2. 在 Cursor 对话中使用
@product_analyst 分析用户需求
@system_architect 设计架构
@core_framework_engineer 实现功能
```

### 场景 2: 大型项目完整工作流

**适合需要多阶段流程管理的项目**：

```bash
# 1. 接入项目
workflow setup

# 2. 初始化完整工作流
workflow init --quick

# 3. 一键执行全部阶段
workflow wfauto

# 4. 查看状态
workflow status
```

### 场景 3: 自定义团队配置

**如果你的项目有自定义的团队配置**：

```bash
# 1. 确保项目中有 teams/your-team/ 目录
#    包含: role_schema.yaml, skills/, workflow_schema.yaml

# 2. 使用指定团队初始化
workflow init --template your-team

# 3. 使用
workflow wfauto
```

## 📁 项目结构

接入后，你的项目会包含：

```
your-project/
├── .workflow/              # 工作流配置目录
│   ├── role_schema.yaml   # 角色定义
│   ├── skills/            # 技能目录
│   │   ├── requirements_analysis/
│   │   ├── system_design/
│   │   └── ...
│   ├── workflow_schema.yaml  # 工作流定义（可选）
│   ├── project_context.yaml  # 项目上下文
│   └── USAGE.md            # 使用说明
└── ...
```

## 🔧 高级配置

### 自定义技能

```bash
# 生成新技能模板
workflow generate-skill my_custom_skill

# 编辑技能
# 编辑 .workflow/skills/my_custom_skill/Skill.md
```

### 自定义角色

编辑 `.workflow/role_schema.yaml` 添加新角色或修改现有角色。

### 使用不同的团队模板

```bash
# 查看可用模板
ls /path/to/work-by-roles/work_by_roles/templates/

# 使用指定模板
workflow init --template standard_agile
```

## ❓ 常见问题

### Q: 如何卸载？

```bash
pip uninstall work-by-roles
```

然后删除项目中的 `.workflow/` 目录。

### Q: 如何更新框架？

```bash
# 重新安装
cd /path/to/work-by-roles
git pull
pip install -e . --upgrade
```

### Q: 多个项目可以共享配置吗？

可以！你可以：
1. 在项目间共享 `teams/` 目录配置
2. 使用 Git submodule 共享团队配置
3. 使用符号链接共享技能目录

### Q: 如何在 CI/CD 中使用？

```bash
# 在 CI 脚本中
pip install git+https://github.com/puppyfront-web/work-by-roles.git
workflow setup
workflow wfauto
```

## Checkpoint 机制

工作流支持检查点（checkpoint）功能，可以在执行过程中保存状态，支持中断恢复和调试。

### 创建检查点

```bash
# 手动创建检查点
workflow checkpoint create --name "before_implementation" --description "实现前检查点"

# 在特定阶段创建检查点
workflow checkpoint create --stage requirements --name "需求分析完成"
```

### 列出检查点

```bash
# 列出所有检查点
workflow checkpoint list

# 列出特定工作流的检查点
workflow checkpoint list --workflow standard_delivery
```

### 从检查点恢复

```bash
# 从检查点恢复工作流状态
workflow checkpoint restore checkpoint_abc123
```

### 查看检查点详情

```bash
# 显示检查点详细信息
workflow checkpoint info checkpoint_abc123
```

### 删除检查点

```bash
# 删除检查点
workflow checkpoint delete checkpoint_abc123
```

### 自动检查点

在 `workflow wfauto` 执行时，可以启用自动检查点：

```bash
# 启用自动检查点（在配置中设置）
# 系统会在每个阶段开始和完成时自动创建检查点
```

## 流式输出

工作流支持流式输出，实时显示执行进度和 LLM 响应。

### 自动启用

流式输出在 Cursor IDE 中自动启用，无需额外配置。系统会实时显示：

- 工作流进度更新
- LLM 响应逐字显示（如果 LLM 客户端支持）
- 文档生成过程
- 代码编写过程
- 质量检查结果

### 禁用流式输出

如果需要禁用流式输出（例如在 CI/CD 环境中）：

```bash
# 通过环境变量禁用
export WORKFLOW_NO_STREAM=1
workflow wfauto
```

## 📚 更多资源

- [快速开始指南](../QUICKSTART.md)
- [完整使用指南](USAGE_GUIDE.md)
- [API 文档](API.md)
- [架构文档](ARCHITECTURE.md)
- [技能指南](SKILLS_GUIDE.md)

## 🎉 开始使用

现在你已经知道如何在其他项目中使用工作流框架了！

最简单的开始方式：

```bash
# 1. 安装框架
cd /path/to/work-by-roles
pip install -e .

# 2. 在新项目中接入
cd /path/to/your-project
workflow setup

# 3. 开始使用
workflow list-roles
```

然后在 Cursor 中使用 `@角色名` 或 `@team` 开始工作！

