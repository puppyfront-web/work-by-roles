"""
CLI commands for inspecting workflow and roles: analyze, list-stages, list-roles, export-graph, check-team
"""

import sys
from pathlib import Path
from .base import _init_engine
from ..core.enums import StageStatus

def cmd_analyze(args):
    """Analyze current workflow state and requirements"""
    try:
        engine, _, _ = _init_engine(args)
        
        current = engine.get_current_stage()
        if not current:
            print("⏳ 状态: 无活动阶段")
            return
            
        print(f"📊 分析阶段: {current.name} ({current.id})")
        print(f"👤 负责角色: {engine.executor.state.current_role}")
        
        # Show outputs
        if current.outputs:
            print("\n必需输出:")
            workflow_id = engine.workflow.id if engine.workflow else "default"
            for output in current.outputs:
                if output.type in ("document", "report"):
                    output_path = engine.workspace_path / ".workflow" / "outputs" / workflow_id / current.id / output.name
                else:
                    output_path = engine.workspace_path / output.name
                exists = output_path.exists()
                marker = "✅" if exists else "⏳"
                print(f"  {marker} {output.name} ({output.type}) - {'已存在' if exists else '缺失'}")
                
        # Show quality gates
        if current.quality_gates:
            print("\n质量门禁:")
            for gate in current.quality_gates:
                print(f"  - {gate.type}: {', '.join(gate.criteria)}")
                
    except Exception as e:
        print(f"❌ 分析失败: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_list_stages(args):
    """List all workflow stages"""
    try:
        engine, _, _ = _init_engine(args)
        
        print(f"\n📋 工作流: {engine.workflow.name}")
        print("=" * 60)
        for stage in sorted(engine.workflow.stages, key=lambda s: s.order):
            print(f"\n阶段 {stage.order}: {stage.name}")
            print(f"  ID: {stage.id}")
            print(f"  角色: {stage.role}")
            if stage.prerequisites:
                print(f"  前置条件: {', '.join(stage.prerequisites)}")
            print(f"  质量门禁: {len(stage.quality_gates)} 个")
            print(f"  必需输出: {len([o for o in stage.outputs if o.required])} 个")
            
    except Exception as e:
        print(f"❌ 列表获取失败: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_list_roles(args):
    """List all roles and their skills"""
    try:
        engine, _, _ = _init_engine(args)
        
        print("\n👤 可用角色列表:")
        print("=" * 60)
        for role_id, role in engine.role_manager.roles.items():
            print(f"\n角色: {role.name} ({role_id})")
            print(f"  描述: {role.description}")
            if role.skills:
                print(f"  技能: {', '.join(role.skills)}")
            if role.extends:
                print(f"  继承自: {', '.join(role.extends)}")
                
    except Exception as e:
        print(f"❌ 列表获取失败: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_export_graph(args):
    """Export workflow graph"""
    try:
        engine, _, _ = _init_engine(args)
        mermaid = engine.to_mermaid(include_roles=not args.no_roles)
        
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(mermaid, encoding='utf-8')
            print(f"✅ 已导出到: {output_path}")
        else:
            print("\nMermaid 图表代码:")
            print("-" * 60)
            print(mermaid)
            print("-" * 60)
            
    except Exception as e:
        print(f"❌ 导出失败: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_check_team(args):
    """Health check for team and workflow"""
    try:
        engine, _, _ = _init_engine(args)
        
        print("🔍 正在执行健康检查...")
        
        # Check files
        workflow_dir = engine.workspace_path / ".workflow"
        if not workflow_dir.exists():
            print("❌ 错误: .workflow 目录不存在")
            return
            
        # Check workflow
        if not engine.workflow:
            print("❌ 错误: 工作流未加载")
        else:
            print(f"✅ 工作流已加载: {engine.workflow.name}")
            
        # Check roles
        if not engine.role_manager.roles:
            print("❌ 错误: 未找到角色定义")
        else:
            print(f"✅ 已加载 {len(engine.role_manager.roles)} 个角色")
            
        # Check skills
        if not engine.role_manager.skill_library:
            print("⚠️  警告: 未找到技能库")
        else:
            print(f"✅ 已加载 {len(engine.role_manager.skill_library)} 个技能")
            
        print("\n✨ 健康检查完成")
        
    except Exception as e:
        print(f"❌ 检查失败: {e}", file=sys.stderr)
        sys.exit(1)
