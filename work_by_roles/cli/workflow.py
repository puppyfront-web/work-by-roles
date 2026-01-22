"""
CLI commands for workflow management: start, complete, status, wfauto, role-execute, replay, dry-run
"""

import sys
import json
from pathlib import Path
from typing import Optional, Any
from .base import _init_engine
from ..core.enums import StageStatus
from ..core.agent_orchestrator import AgentOrchestrator
from ..core.exceptions import WorkflowError

def _load_llm_client(workspace: Path) -> Optional[Any]:
    """
    Load LLM client from environment variables or configuration file.
    """
    from ..core.llm_client_loader import LLMClientLoader
    loader = LLMClientLoader(workspace)
    return loader.load()

def _check_required_outputs_for_stage(stage, workspace_path, workflow_id=None):
    """Check if all required outputs exist for a stage"""
    missing = []
    if not stage.outputs:
        return missing
    
    workflow_id = workflow_id or "default"
    for output in stage.outputs:
        if not output.required:
            continue
        
        if output.type in ("document", "report"):
            output_path = workspace_path / ".workflow" / "outputs" / workflow_id / stage.id / output.name
        else:
            output_path = workspace_path / output.name
            
        if not output_path.exists():
            missing.append((output.name, output_path))
    return missing

def cmd_start(args):
    """Start a workflow stage"""
    try:
        engine, workflow_file, state_file = _init_engine(args)
        stage_id = args.stage
        role_id = getattr(args, 'role', None)
        
        if not stage_id:
            from .inspect import cmd_list_stages
            cmd_list_stages(args)
            return
            
        if not role_id:
            stage = engine.executor._get_stage_by_id(stage_id) if engine.executor else None
            if stage:
                role_id = stage.role
            else:
                print(f"❌ 阶段 '{stage_id}' 未找到", file=sys.stderr)
                sys.exit(1)
        
        engine.start_stage(stage_id, role_id)
        print(f"✅ 已启动阶段: {stage_id} (角色: {role_id})")
        
    except Exception as e:
        print(f"❌ 启动失败: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_complete(args):
    """Complete a workflow stage"""
    try:
        engine, _, _ = _init_engine(args)
        stage_id = args.stage
        if not stage_id:
            current = engine.get_current_stage()
            if not current:
                print("❌ 没有活动阶段", file=sys.stderr)
                sys.exit(1)
            stage_id = current.id
            
        success, errors = engine.complete_stage(stage_id)
        if success:
            print(f"✅ 阶段 '{stage_id}' 已完成")
            if errors:
                print("\n⚠️  警告:")
                for e in errors:
                    print(f"  - {e}")
        else:
            print(f"❌ 阶段 '{stage_id}' 无法完成:")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ 操作失败: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_status(args):
    """Show current workflow status"""
    try:
        engine, _, _ = _init_engine(args)
        if not engine.workflow:
            print("❌ 工作流未加载")
            return
            
        print(f"📋 工作流: {engine.workflow.name}")
        current = engine.get_current_stage()
        if current:
            print(f"🔄 当前阶段: {current.name} ({current.id})")
            print(f"👤 当前角色: {engine.executor.state.current_role}")
        else:
            print("⏳ 状态: 无活动阶段")
            
        completed = engine.executor.get_completed_stages() if engine.executor else set()
        if completed:
            print(f"\n✅ 已完成阶段: {', '.join(completed)}")
            
    except Exception as e:
        print(f"❌ 获取状态失败: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_wfauto(args):
    """Run full workflow automatically"""
    failed_stages = []
    try:
        engine, _, _ = _init_engine(args)
        workspace = Path(args.workspace or ".")
        llm_client = _load_llm_client(workspace)
        use_llm = getattr(args, 'use_llm', False)
        
        if use_llm and not llm_client:
            raise WorkflowError("LLM client not configured but --use-llm flag is set")
        
        if not engine.workflow:
            print("❌ 未加载工作流", file=sys.stderr)
            sys.exit(1)
        
        keep_state = getattr(args, 'keep_state', False)
        if not keep_state:
            engine.reset_state()
            print("🔄 已重置工作流状态\n")
        
        stages = sorted(engine.workflow.stages, key=lambda s: s.order)
        print("🚀 wfauto: 开始全流程执行\n")
        
        for stage in stages:
            if keep_state and engine.get_stage_status(stage.id) == StageStatus.COMPLETED:
                print(f"✅ 跳过已完成阶段: {stage.id}")
                continue

            print(f"🔄 启动阶段: {stage.id} (角色: {stage.role})")
            engine.start_stage(stage.id, stage.role)
            
            passed, errors = engine.complete_stage(stage.id)
            if passed:
                print(f"✅ 完成阶段: {stage.id}")
            else:
                print(f"❌ 阶段 {stage.id} 质量门禁失败")
                failed_stages.append(stage.id)
                    
        if failed_stages:
            print(f"\n❌ 执行结束，以下阶段失败: {', '.join(failed_stages)}")
            sys.exit(1)
        else:
            print("\n✅ 所有阶段执行成功！")
            
    except Exception as e:
        print(f"❌ 全流程执行失败: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_role_execute(args):
    """Execute a role directly"""
    try:
        from ..core.role_executor import RoleExecutor
        engine, _, _ = _init_engine(args)
        workspace = Path(args.workspace or ".")
        llm_client = _load_llm_client(workspace)
        
        if args.use_llm and not llm_client:
            raise RuntimeError("LLM client not configured but --use-llm flag is set")
            
        executor = RoleExecutor(engine, llm_client=llm_client)
        inputs = json.loads(args.inputs) if args.inputs else {}
        
        print(f"🚀 执行角色: {args.role_id}")
        result = executor.execute_role(args.role_id, args.requirement, inputs=inputs, use_llm=args.use_llm)
        print(f"\n✅ 执行完成:\n{result.get('response', '')}")
        
    except Exception as e:
        print(f"❌ 角色执行失败: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_replay_workflow(args):
    """Replay workflow from state"""
    print("⚠️  工作流重放功能正在开发中...")

def cmd_dry_run_stage(args):
    """Dry run a stage"""
    print(f"🧪 模拟运行阶段: {args.stage_id}")
    print("✅ 模拟运行完成")
