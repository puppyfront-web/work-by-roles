# 30秒快速接入

## 安装

```bash
pip install -e .
```

## 使用（2步，完全自动化）

### 方式 1: 一键接入（推荐新项目）

```bash
# 1. 一键接入（自动配置角色和技能）
workflow setup

# 2. 直接使用角色
workflow role-execute product_analyst "分析用户需求"
workflow role-execute system_architect "设计系统架构"
```

**完成！** 就这么简单。

### 方式 2: 完整工作流（适合大型项目）

```bash
# 1. 初始化（快速模式，最小配置）
workflow init --quick

# 2. 一键执行（自动使用 Agent + Skills）
workflow wfauto
```

**完成！** 就这么简单。

> 💡 **提示**: 
> - 方式1（一键接入）适合IDE环境，直接使用角色，无需配置workflow
> - 方式2（完整工作流）适合大型项目，需要多阶段流程管理
> - 默认不生成文档，专注于代码实现
> - 自动使用 Agent + Skills 执行，无需手动操作
> - 质量门禁默认宽松模式，不阻塞流程

## 常用命令

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

## 需要更多？

查看 [README.md](README.md) 了解详细功能。
