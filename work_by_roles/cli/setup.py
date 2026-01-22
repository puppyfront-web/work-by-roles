"""
CLI command: setup
"""

import sys
from pathlib import Path
from ..core.project_manager import ProjectManager

def cmd_setup(args):
    """一键接入：自动设置项目，让用户可以直接使用角色"""
    workspace = Path(args.workspace or ".")
    pm = ProjectManager(workspace)
    print("=" * 60)
    print("🚀 一键接入 Multi-Role Skills Workflow")
    print("=" * 60)
    print(f"\n目标项目: {workspace.absolute()}\n")
    
    # 检查是否已存在配置
    workflow_dir = workspace / ".workflow"
    roles_file = workflow_dir / "role_schema.yaml"
    skills_dir = workflow_dir / "skills"
    
    if roles_file.exists() and skills_dir.exists():
        print("⚠️  项目已接入，配置已存在")
        print(f"   - 角色配置: {roles_file}")
        print(f"   - 技能目录: {skills_dir}")
        print("\n💡 如需重新接入，请先删除 .workflow/ 目录")
        return
    
    # 查找标准模板
    template_sources = [
        workspace / "teams" / "standard-delivery",
        Path(__file__).parent.parent.parent / "teams" / "standard-delivery",
        Path(__file__).parent.parent / "templates" / "standard_agile",
    ]
    
    template_dir = next((s for s in template_sources if s.exists() and s.is_dir()), None)
    if not template_dir:
        print("❌ 错误: 未找到标准模板")
        sys.exit(1)
    
    print(f"✅ 使用模板: {template_dir}")
    # Pass None to copy skills to .workflow/skills (default behavior)
    pm.apply_template(template_dir, shared_skills_dir=None)
    print(f"  ✅ 已复制配置和技能")
    
    # 扫描项目
    print("\n🔍 正在扫描项目结构...")
    pm.scan_project()
    print(f"  ✅ 已生成项目上下文")
    
    # 生成使用说明
    usage_file = pm.generate_usage_guide()
    print(f"  ✅ 已生成使用说明: {usage_file.name}")
    
    # 生成 Cursor 规则
    if pm.setup_cursor_rules():
        print(f"  ✅ 已生成 Cursor IDE 配置文件")
    else:
        print(f"  ℹ️  未检测到 Cursor IDE 环境，跳过配置文件生成")
    
    print("\n" + "=" * 60)
    print("✅ 接入完成！")
    print("=" * 60)
