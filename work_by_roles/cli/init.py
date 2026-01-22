"""
CLI command: init
"""

import sys
from pathlib import Path
from ..core.project_manager import ProjectManager

def cmd_init(args):
    """Initialize project context with template selection"""
    workspace = Path(args.workspace or ".")
    pm = ProjectManager(workspace)
    shared_skills_dir = pm.get_shared_skills_dir()
    print(f"🔍 正在初始化项目: {workspace.absolute()}")

    pm.ensure_workflow_dir()

    # 0. 检查快速模式或指定模板
    template_name = getattr(args, 'template', None)
    quick_mode = getattr(args, 'quick', False)
    if quick_mode and not template_name:
        template_name = "vibe-coding"
    
    template_applied = False
    
    if template_name:
        teams_template = workspace / "teams" / template_name
        if teams_template.exists() and teams_template.is_dir():
            print(f"\n✅ 检测到团队模板: teams/{template_name}/")
            if pm.apply_template(teams_template, shared_skills_dir=shared_skills_dir):
                print(f"✅ 已将 {template_name} 配置复制到 .workflow/ 目录")
                template_applied = True
            else:
                print("   ⚠️  .workflow/ 目录已存在配置文件，跳过复制")
                template_applied = True
    
    if not template_applied:
        teams_standard_delivery = workspace / "teams" / "standard-delivery"
        if teams_standard_delivery.exists() and teams_standard_delivery.is_dir():
            print("\n✅ 检测到项目标准配置: teams/standard-delivery/")
            if pm.apply_template(teams_standard_delivery, shared_skills_dir=shared_skills_dir):
                print(f"✅ 已将标准配置复制到 .workflow/ 目录")
                template_applied = True
            else:
                print("   ⚠️  .workflow/ 目录已存在配置文件，跳过复制")
                template_applied = True
    
    # 2. 如果没有使用模板，使用原来的模板选择逻辑
    if not template_applied:
        # Note: _get_templates_dir is currently in cli.py, should be moved to utility or ProjectManager
        from ..cli import _get_templates_dir
        templates_dir = _get_templates_dir()
        if templates_dir.exists():
            templates = sorted([d for d in templates_dir.iterdir() if d.is_dir()])
            if templates:
                print("\n请选择团队模板:")
                for i, t in enumerate(templates, 1):
                    display_name = t.name.replace("_", " ").title()
                    print(f"  {i}. {display_name} ({t.name})")
                print(f"  {len(templates)+1}. 仅扫描结构 (不应用模板)")
                
                try:
                    choice = input(f"\n选择编号 [1-{len(templates)+1}]: ").strip()
                    if choice and choice.isdigit():
                        idx = int(choice) - 1
                        if 0 <= idx < len(templates):
                            selected = templates[idx]
                            print(f"✅ 已选择模板: {selected.name}")
                            if pm.apply_template(selected, shared_skills_dir=shared_skills_dir):
                                print(f"✅ 已将模板文件复制到 .workflow/ 目录")
                                template_applied = True
                except (KeyboardInterrupt, EOFError):
                    print("\n❌ 已取消选择")
    
    # 2. Project scanning
    print(f"\n🔍 正在扫描项目结构...")
    context = pm.scan_project()
    print(f"✅ 项目上下文已保存")
    
    # 2.5. Check for spec files
    if not context.specs:
        print("\n⚠️  未检测到项目规范文件 (spec files)")
        try:
            generate_spec = input("是否生成初始规范文件模板? [y/N]: ").strip().lower()
            if generate_spec in ['y', 'yes']:
                from ..cli import _generate_spec_template
                _generate_spec_template(workspace)
        except (KeyboardInterrupt, EOFError):
            print("\n跳过规范文件生成")
    
    # 3. Generate .cursorrules
    if pm.setup_cursor_rules():
        print(f"✅ 已生成/更新 .cursorrules 文件")
    
    # 4. Generate initial state and TEAM_CONTEXT.md
    workflow_file = pm.workflow_dir / "workflow_schema.yaml"
    roles_file = pm.workflow_dir / "role_schema.yaml"
    
    if workflow_file.exists() and roles_file.exists():
        try:
            engine = pm.initialize_state(roles_file, workflow_file, shared_skills_dir=shared_skills_dir)
            print(f"✅ 已初始化工作流状态和团队上下文")
            
            current_stage = engine.get_current_stage()
            if current_stage:
                print(f"\n✅ 初始化完成！当前活动阶段: {current_stage.name} ({current_stage.id})")
        except Exception as e:
            print(f"⚠️  初始化状态失败: {e}")
    else:
        print("💡 提示: 未检测到完整的流程配置，请手动配置后运行 'workflow start'")
