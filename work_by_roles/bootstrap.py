#!/usr/bin/env python3
"""
快速接入脚本 - 将 Multi-Role Skills Workflow 框架集成到新项目
用法: python bootstrap.py [--template TEMPLATE_NAME]
"""

import sys
import shutil
from pathlib import Path
import argparse


def get_template_dir() -> Path:
    """获取模板目录路径"""
    # 尝试从包中获取
    try:
        import work_by_roles
        pkg_path = Path(work_by_roles.__file__).parent
        template_dir = pkg_path / "templates"
        if template_dir.exists():
            return template_dir
    except ImportError:
        pass
    
    # 回退到本地路径（开发模式）
    return Path(__file__).parent / "templates"


def copy_template_files(target: Path, template_name: str):
    """复制模板文件到目标项目"""
    template_dir = get_template_dir() / template_name
    if not template_dir.exists():
        raise FileNotFoundError(f"模板 '{template_name}' 不存在")
    
    # Ensure .workflow directory exists and create temp subdirectory
    workflow_dir = target / ".workflow"
    workflow_dir.mkdir(exist_ok=True)
    temp_dir = workflow_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    required_files = ["role_schema.yaml", "workflow_schema.yaml"]
    for filename in required_files:
        src = template_dir / filename
        if src.exists():
            shutil.copy(src, workflow_dir / filename)
            print(f"  ✅ {filename} -> .workflow/")
        else:
            print(f"  ⚠️  警告: {filename} 在模板中不存在")

    # Copy shared skills into workspace/skills
    template_skills = template_dir / "skills"
    if template_skills.exists() and template_skills.is_dir():
        skills_dir = target / "skills"
        shutil.copytree(template_skills, skills_dir, dirs_exist_ok=True)
        print(f"  ✅ skills -> {skills_dir}")


def copy_core_files(target: Path):
    """复制核心引擎文件到 .workflow/"""
    workflow_dir = target / ".workflow"
    workflow_dir.mkdir(exist_ok=True)
    temp_dir = workflow_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    # 尝试从包中复制引擎文件（如果需要）
    # 注意：现在可以直接从包导入，不需要复制文件
    # 保留此逻辑仅用于向后兼容
    try:
        import work_by_roles
        # 复制引擎（从 core/engine.py）
        engine_path = Path(work_by_roles.__file__).parent / "core" / "engine.py"
        if engine_path.exists():
            shutil.copy(engine_path, workflow_dir / "workflow_engine.py")
            print(f"  ✅ workflow_engine.py -> .workflow/")
    except ImportError:
        pass
    
    # 复制 CLI
    try:
        import work_by_roles.cli as cli
        cli_path = Path(cli.__file__)
        if cli_path.exists():
            shutil.copy(cli_path, workflow_dir / "workflow_cli.py")
            print(f"  ✅ workflow_cli.py -> .workflow/")
    except ImportError:
        # 开发模式回退
        framework_root = Path(__file__).parent.parent
        src = framework_root / "work_by_roles" / "cli.py"
        if src.exists():
            shutil.copy(src, workflow_dir / "workflow_cli.py")
            print(f"  ✅ workflow_cli.py -> .workflow/")
        else:
            # 最后回退：从项目根目录或当前目录复制
            framework_root = Path(__file__).parent.parent
            # 尝试从项目根目录复制 workflow_cli.py（如果存在）
            cli_src = framework_root / "work_by_roles" / "cli.py"
            if cli_src.exists():
                shutil.copy(cli_src, workflow_dir / "workflow_cli.py")
                print(f"  ✅ workflow_cli.py -> .workflow/")
            else:
                print(f"  ⚠️  警告: workflow_cli.py 未找到")
            # 尝试从 core/engine.py 复制
            engine_src = framework_root / "work_by_roles" / "core" / "engine.py"
            if engine_src.exists():
                shutil.copy(engine_src, workflow_dir / "workflow_engine.py")
                print(f"  ✅ workflow_engine.py -> .workflow/")
            else:
                print(f"  ⚠️  警告: workflow_engine.py 未找到")


def create_cursorrules(target: Path):
    """创建 .cursorrules 文件"""
    content = """# Multi-Role Workflow Rules

You are operating within a structured Multi-Role Skills Workflow. 
To ensure project stability and follow best practices, adhere to these rules:

1. **Role Awareness**: Before making changes, check `.workflow/state.yaml` to identify the current active stage and role.
2. **Constraint Enforcement**: Respect the `allowed_actions` and `forbidden_actions` defined in `role_schema.yaml` for the current role.
3. **Stage Boundaries**: 
   - Do not skip stages.
   - Do not perform implementation tasks while in the `requirements` or `architecture` stages.
   - If the current stage does not match the task, advise the user to run `python .workflow/workflow_cli.py start <stage> <role>`.
4. **Quality Gates**: Ensure all quality gates and required outputs defined in `workflow_schema.yaml` are satisfied before attempting to complete a stage.
5. **Skill Compliance**: Refer to Skill.md files in skills/ directory for dimensions and tools associated with each skill required by your current role.
6. **Team Context**: When user mentions `@[team]` or `@team`, read `.workflow/TEAM_CONTEXT.md` for current team state and enforce role constraints.
   - When user uses `@[team]` with workflow automation requests (e.g., "run full workflow", "execute all stages", "wfauto"), execute `workflow wfauto` to automatically run all workflow stages sequentially.

Current project status can be viewed at any time by running `python .workflow/workflow_cli.py status`.
"""
    cursorrules_path = target / ".cursorrules"
    cursorrules_path.write_text(content, encoding='utf-8')
    print(f"  ✅ .cursorrules")


def detect_project_type(workspace: Path) -> str:
    """
    自动检测项目类型并推荐模板
    
    Returns:
        推荐的模板名称
    """
    # 检查常见文件/目录
    if (workspace / "package.json").exists() or (workspace / "node_modules").exists():
        if (workspace / "src" / "App.jsx").exists() or (workspace / "src" / "App.tsx").exists():
            return "web-app"
        elif (workspace / "server.js").exists() or (workspace / "server.ts").exists():
            return "api-service"
    
    if (workspace / "requirements.txt").exists() or (workspace / "pyproject.toml").exists():
        if (workspace / "app.py").exists() or (workspace / "main.py").exists():
            try:
                with open(workspace / "requirements.txt", "r") as f:
                    content = f.read()
                    if "flask" in content.lower() or "fastapi" in content.lower():
                        return "api-service"
            except:
                pass
        
        if (workspace / "setup.py").exists() or (workspace / "pyproject.toml").exists():
            try:
                if (workspace / "pyproject.toml").exists():
                    try:
                        import tomli
                        with open(workspace / "pyproject.toml", "rb") as f:
                            data = tomli.load(f)
                            if "project" in data and "scripts" in data.get("project", {}):
                                return "cli-tool"
                    except ImportError:
                        # Fallback: try to parse as TOML manually
                        pass
            except:
                pass
    
    if (workspace / "go.mod").exists() or (workspace / "main.go").exists():
        return "api-service"
    
    if (workspace / "Cargo.toml").exists():
        return "cli-tool"
    
    return "standard_agile"


def interactive_template_selection(workspace: Path) -> str:
    """交互式模板选择"""
    print("\n请选择工作流模板:")
    print("-" * 60)
    
    # 检测项目类型
    detected = detect_project_type(workspace)
    templates = {
        "1": ("standard_agile", "标准敏捷团队（推荐）", "适合大多数项目"),
        "2": ("minimalist", "最小化模板", "最简单的配置，适合个人项目"),
        "3": ("security_focused", "安全优先模板", "适合安全敏感项目"),
    }
    
    # 如果有检测到的模板，显示推荐
    if detected in ["web-app", "api-service", "cli-tool"]:
        print(f"💡 检测到项目类型: {detected}")
        print(f"   推荐使用: standard_agile 模板\n")
    
    for key, (template_id, name, desc) in templates.items():
        marker = "⭐" if template_id == "1" else "  "
        print(f"{marker} {key}. {name}")
        print(f"     {desc}")
    
    while True:
        try:
            choice = input("\n选择模板编号 [1-3] (默认: 1): ").strip()
            if not choice:
                choice = "1"
            if choice in templates:
                return templates[choice][0]
            else:
                print("❌ 无效选择，请输入 1-3")
        except (KeyboardInterrupt, EOFError):
            print("\n\n❌ 已取消")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="快速接入 Multi-Role Skills Workflow 框架")
    parser.add_argument(
        "--template", "-t",
        help="选择团队模板 (standard_agile, minimalist, security_focused, web-app, api-service, cli-tool)"
    )
    parser.add_argument(
        "--target", "-d",
        type=str,
        default=".",
        help="目标项目目录 (默认: 当前目录)"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="交互式引导模式"
    )
    parser.add_argument(
        "--minimal", "-m",
        action="store_true",
        help="使用最小化配置"
    )
    
    args = parser.parse_args()
    
    target = Path(args.target).resolve()
    
    print("=" * 60)
    print("Multi-Role Skills Workflow - 快速接入")
    print("=" * 60)
    print(f"\n目标项目: {target}")
    
    # 确定模板
    template = args.template
    if args.minimal:
        template = "minimalist"
    elif args.interactive or template is None:
        template = interactive_template_selection(target)
    
    # 如果模板是新的类型，映射到现有模板
    template_map = {
        "web-app": "standard_agile",
        "api-service": "standard_agile",
        "cli-tool": "standard_agile",
    }
    template = template_map.get(template, template)
    
    print(f"使用模板: {template}")
    print("\n正在复制文件...")
    
    try:
        # 1. 复制模板文件
        copy_template_files(target, args.template)
        
        # 2. 复制核心文件到 .workflow/
        copy_core_files(target)
        
        # 3. 创建 .cursorrules
        create_cursorrules(target)
        
        # 4. 初始化项目上下文
        print("\n正在初始化项目上下文...")
        import subprocess
        result = subprocess.run(
            [sys.executable, str(target / ".workflow" / "workflow_cli.py"), "init"],
            cwd=target,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"  ⚠️  初始化警告: {result.stderr}")
        
        print("\n" + "=" * 60)
        print("✅ 接入完成！")
        print("=" * 60)
        print("\n下一步:")
        print(f"  1. 查看状态: python .workflow/workflow_cli.py status")
        print(f"  2. 启动阶段: python .workflow/workflow_cli.py start <stage> <role>")
        print(f"  3. 查看团队: python .workflow/workflow_cli.py check-team")
        print(f"\n💡 提示: 在对话中使用 @[team] 来让 AI 自动应用当前工作流约束")
        print(f"   使用 @[team] 并请求 'wfauto' 或 '运行完整工作流' 可自动执行所有阶段")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

