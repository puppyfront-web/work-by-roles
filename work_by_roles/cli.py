#!/usr/bin/env python3
"""
工作流命令行工具
提供便捷的命令行接口来管理工作流
"""

import sys
import json
import yaml
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Callable, Tuple
try:
    # Try importing from the same package
    from .core.engine import (
        WorkflowEngine, 
        WorkflowError, 
        ValidationError, 
        StageStatus,
        ProjectScanner,
        AgentOrchestrator,
        TeamManager,
        RoleExecutor
    )
    from .core.llm_client_loader import LLMClientLoader
    from .core.execution_mode_analyzer import ExecutionModeAnalyzer
    from .core.tool_mapper import ToolMapper
    _agents_available = True
except (ImportError, ValueError):
    # Fallback: try from .engine (forwarding module)
    try:
        from .engine import (
            WorkflowEngine, 
            WorkflowError, 
            ValidationError, 
            StageStatus,
            ProjectScanner,
            AgentOrchestrator,
            TeamManager,
            RoleExecutor
        )
        from .core.llm_client_loader import LLMClientLoader
        from .core.execution_mode_analyzer import ExecutionModeAnalyzer
        from .core.tool_mapper import ToolMapper
        _agents_available = True
    except (ImportError, ValueError):
        # Final fallback: try absolute import from core.engine
        try:
            from work_by_roles.core.engine import (
                WorkflowEngine, 
                WorkflowError, 
                ValidationError, 
                StageStatus,
                ProjectScanner,
                AgentOrchestrator,
                TeamManager,
                RoleExecutor
            )
            try:
                from work_by_roles.core.llm_client_loader import LLMClientLoader
            except ImportError:
                LLMClientLoader = None
            try:
                from work_by_roles.core.execution_mode_analyzer import ExecutionModeAnalyzer
                from work_by_roles.core.tool_mapper import ToolMapper
            except ImportError:
                ExecutionModeAnalyzer = None
                ToolMapper = None
            _agents_available = True
        except (ImportError, ValueError):
            # If all imports fail, set to unavailable
            _agents_available = False
            WorkflowEngine = None
            WorkflowError = Exception
            ValidationError = Exception
            StageStatus = None
            ProjectScanner = None
            AgentOrchestrator = None
            TeamManager = None
            RoleExecutor = None
            LLMClientLoader = None
            ExecutionModeAnalyzer = None
            ToolMapper = None


def print_status(engine: WorkflowEngine):
    """打印工作流状态"""
    print("\n" + "=" * 60)
    print("工作流状态")
    print("=" * 60)
    
    if not engine.workflow or not engine.executor:
        print("当前阶段: 无")
        print("\n⚠️  工作流未初始化或未加载执行器")
        return
    
    current = engine.get_current_stage()
    if current:
        print(f"当前阶段: {current.name} (ID: {current.id})")
        print(f"当前角色: {engine.executor.state.current_role}")
    else:
        print("当前阶段: 无")
    
    print("\n所有阶段:")
    for stage in engine.workflow.stages:
        status = engine.get_stage_status(stage.id)
        status_str = status.value if status else "pending"
        marker = "→" if current and current.id == stage.id else " "
        print(f"  {marker} [{status_str:12}] {stage.name} (角色: {stage.role})")
    
    if engine.executor:
        completed = engine.executor.get_completed_stages()
        if completed:
            print(f"\n已完成阶段: {', '.join(completed)}")


def _init_engine(args) -> Tuple[WorkflowEngine, Path, Path]:
    """Initialize engine with skill library, supporting team context"""
    workspace = Path(args.workspace or ".")
    workflow_dir = workspace / ".workflow"
    workflow_dir.mkdir(exist_ok=True)
    temp_dir = workflow_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    # 初始化团队管理器
    team_manager = TeamManager(workspace)
    
    # 如果指定了团队，使用团队配置；否则使用命令行参数或默认配置
    team_id = getattr(args, 'team', None)
    if team_id:
        # 使用指定的团队配置
        team_config = team_manager.get_team_config(team_id)
        skill_file = team_config["skills"]
        roles_file = team_config["roles"]
        workflow_file = team_config["workflow"]
        context_file = team_config["context"]
        state_file = team_config["state"]
    else:
        # 检查是否有当前活动团队
        current_team = team_manager.get_current_team()
        if current_team and not (args.workflow or args.roles or args.skills):
            # 使用当前团队配置（如果没有显式指定命令行参数）
            team_config = team_manager.get_team_config(current_team)
            skill_file = team_config["skills"]
            roles_file = team_config["roles"]
            workflow_file = team_config["workflow"]
            context_file = team_config["context"]
            state_file = team_config["state"]
        else:
            # 使用命令行参数或默认配置
            skill_file = Path(args.skills) if args.skills else workflow_dir / "skills"
            roles_file = Path(args.roles) if args.roles else workflow_dir / "role_schema.yaml"
            workflow_file = Path(args.workflow) if args.workflow else workflow_dir / "workflow_schema.yaml"
            context_file = Path(args.context) if args.context else workflow_dir / "project_context.yaml"
            state_file = Path(args.state) if args.state else workflow_dir / "state.yaml"
    
    # Check if auto-restore is disabled
    auto_restore = not getattr(args, 'no_restore_state', False)
    auto_save = not getattr(args, 'no_auto_save', False)

    engine = WorkflowEngine(
        workspace,
        auto_save_state=auto_save,
        state_file=state_file
    )
    
    # Load context if exists
    if context_file.exists():
        engine.load_context(context_file)
        
    if not skill_file.exists():
        raise WorkflowError(f"Skill library not found: {skill_file}")
    engine.load_skill_library(skill_file)
    engine.load_roles(roles_file)
    engine.load_workflow(workflow_file)
    
    # State is now auto-restored in load_workflow if auto_restore is True
    # Manual load_state call is no longer needed, but kept for explicit control
    if not auto_restore and state_file.exists():
        engine.load_state(state_file, auto_restore=False)
        
    return engine, workflow_file, state_file


def _load_llm_client(workspace: Path) -> Optional[Any]:
    """
    Load LLM client from environment variables or configuration file.
    
    Args:
        workspace: Workspace root path
        
    Returns:
        LLM client instance or None if not configured
    """
    loader = LLMClientLoader(workspace)
    return loader.load()


def _get_templates_dir() -> Path:
    """Get templates directory path"""
    # Try from package
    try:
        import work_by_roles
        pkg_path = Path(work_by_roles.__file__).parent
        template_dir = pkg_path / "templates"
        if template_dir.exists():
            return template_dir
    except ImportError:
        pass
    
    # Fallback to local (development mode)
    return Path(__file__).parent / "templates"


def cmd_init(args):
    """Initialize project context with template selection"""
    workspace = Path(args.workspace or ".")
    print(f"🔍 正在初始化项目: {workspace.absolute()}")

    # Ensure .workflow directory exists and create temp subdirectory
    workflow_dir = workspace / ".workflow"
    workflow_dir.mkdir(exist_ok=True)
    temp_dir = workflow_dir / "temp"
    temp_dir.mkdir(exist_ok=True)

    # 0. 检查快速模式或指定模板
    template_name = getattr(args, 'template', None)
    quick_mode = getattr(args, 'quick', False)
    
    # 快速模式默认使用vibe-coding模板
    if quick_mode and not template_name:
        template_name = "vibe-coding"
    
    # 1. 优先检查 teams/ 目录中的模板（包括vibe-coding）
    template_applied = False
    
    if template_name:
        # 检查teams目录
        teams_template = workspace / "teams" / template_name
        if teams_template.exists() and teams_template.is_dir():
            print(f"\n✅ 检测到团队模板: teams/{template_name}/")
            print(f"   使用 {template_name} 团队配置")
            
            workflow_file = workflow_dir / "workflow_schema.yaml"
            roles_file = workflow_dir / "role_schema.yaml"
            skills_dir = workflow_dir / "skills"
            
            if not (workflow_file.exists() and roles_file.exists() and skills_dir.exists()):
                import shutil
                for f in teams_template.iterdir():
                    if f.is_file() and f.suffix in ['.yaml', '.yml']:
                        shutil.copy(f, workflow_dir / f.name)
                    elif f.is_dir() and f.name == "skills":
                        # Copy skills directory
                        shutil.copytree(f, skills_dir, dirs_exist_ok=True)
                print(f"✅ 已将 {template_name} 配置复制到 .workflow/ 目录")
                template_applied = True
            else:
                print("   ⚠️  .workflow/ 目录已存在配置文件，跳过复制")
    
    # 1.5. 如果没有指定模板，优先检查 teams/standard-delivery/ 配置（项目规范）
    if not template_applied:
        teams_standard_delivery = workspace / "teams" / "standard-delivery"
        
        if teams_standard_delivery.exists() and teams_standard_delivery.is_dir():
            print("\n✅ 检测到项目标准配置: teams/standard-delivery/")
            print("   自动使用标准交付团队配置（符合项目规范）")
            
            # 检查是否已有配置文件，避免覆盖
            workflow_file = workflow_dir / "workflow_schema.yaml"
            roles_file = workflow_dir / "role_schema.yaml"
            skills_dir = workflow_dir / "skills"
            
            if not (workflow_file.exists() and roles_file.exists() and skills_dir.exists()):
                # 复制配置文件到 .workflow 目录
                import shutil
                for f in teams_standard_delivery.iterdir():
                    if f.is_file() and f.suffix in ['.yaml', '.yml']:
                        shutil.copy(f, workflow_dir / f.name)
                    elif f.is_dir() and f.name == "skills":
                        # 复制skills目录
                        shutil.copytree(f, skills_dir, dirs_exist_ok=True)
                print(f"✅ 已将标准配置复制到 .workflow/ 目录")
                template_applied = True
            else:
                print("   ⚠️  .workflow/ 目录已存在配置文件，跳过复制")
                print("   💡 如需重新初始化，请先删除现有配置文件")
                template_applied = True  # 标记为已应用，避免继续执行模板选择
    
    # 2. 如果没有使用 teams/standard-delivery，使用原来的模板选择逻辑
    if not template_applied:
        templates_dir = _get_templates_dir()
        if templates_dir.exists():
            templates = sorted([d for d in templates_dir.iterdir() if d.is_dir()])
            if templates:
                print("\n请选择团队模板:")
                for i, t in enumerate(templates, 1):
                    # Try to get a nicer name from the directory name
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
                            # Copy files to .workflow directory
                            import shutil
                            for f in selected.iterdir():
                                if f.is_file() and f.suffix in ['.yaml', '.yml', '.md']:
                                    shutil.copy(f, workflow_dir / f.name)
                                elif f.is_dir() and f.name == "skills":
                                    # Copy skills directory
                                    skills_dir = workflow_dir / "skills"
                                    shutil.copytree(f, skills_dir, dirs_exist_ok=True)
                            print(f"✅ 已将模板文件复制到 .workflow/ 目录")
                            template_applied = True
                except (KeyboardInterrupt, EOFError):
                    print("\n❌ 已取消选择")
    
    # 2. Project scanning
    print(f"\n🔍 正在扫描项目结构...")
    scanner = ProjectScanner(workspace)
    context = scanner.scan()
    
    context_file = workflow_dir / "project_context.yaml"
    
    with open(context_file, 'w', encoding='utf-8') as f:
        yaml.dump(context.to_dict(), f, default_flow_style=False, allow_unicode=True)
        
    print(f"✅ 项目上下文已保存到: {context_file}")
    
    # 2.5. Check for spec files and prompt user
    if not context.specs:
        print("\n⚠️  未检测到项目规范文件 (spec files)")
        print("   规范文件有助于工作流更好地理解项目需求")
        try:
            generate_spec = input("是否生成初始规范文件模板? [y/N]: ").strip().lower()
            if generate_spec in ['y', 'yes']:
                _generate_spec_template(workspace)
        except (KeyboardInterrupt, EOFError):
            print("\n跳过规范文件生成")
    else:
        print(f"\n✅ 检测到 {len(context.specs)} 个规范文件:")
        for spec_name, spec_path in list(context.specs.items())[:5]:  # Show first 5
            print(f"   - {spec_name}: {spec_path}")
        if len(context.specs) > 5:
            print(f"   ... 还有 {len(context.specs) - 5} 个")
    
    # 3. Generate .cursorrules (only in Cursor IDE, merges autopilot.md content)
    if generate_cursorrules(workspace):
        print(f"✅ 已生成/更新 .cursorrules 文件，增强 AI 角色感知（包含自动执行规则）")
    else:
        print(f"ℹ️  未检测到 Cursor IDE 环境，跳过 .cursorrules 生成")
    
    # 4. Generate initial TEAM_CONTEXT.md if workflow files exist
    workflow_file = workflow_dir / "workflow_schema.yaml"
    roles_file = workflow_dir / "role_schema.yaml"
    skills_dir = workflow_dir / "skills"
    state_file = workflow_dir / "state.yaml"
    
    if workflow_file.exists() and roles_file.exists():
        try:
            # Initialize engine to generate TEAM_CONTEXT.md
            engine = WorkflowEngine(
                workspace_path=workspace,
                auto_save_state=True  # Enable auto-save to create initial state
            )
            # Try to load workflow if files exist
            try:
                # Load skill library if exists
                if skills_dir.exists() and skills_dir.is_dir():
                    engine.load_skill_library(skills_dir)
                else:
                    print("⚠️  未找到 skills 目录，跳过技能库加载")
                
                engine.load_roles(roles_file)
                engine.load_workflow(workflow_file)
                
                # Ensure executor is created (should be created by load_workflow)
                if not engine.executor:
                    raise WorkflowError("Failed to create workflow executor")
                
                # Always create/update state file after loading workflow
                # This ensures workflow is "initialized" even without an active stage
                # Note: load_workflow may have called load_state, but it won't create file if it doesn't exist
                # So we explicitly save state here to ensure the file exists
                try:
                    engine.save_state(state_file)
                    if state_file.exists():
                        print(f"✅ 已创建/更新工作流状态文件: {state_file}")
                    else:
                        print(f"⚠️  警告: 状态文件创建可能失败，请检查权限: {state_file}")
                except Exception as e:
                    print(f"⚠️  警告: 保存状态文件时出错: {e}")
                
                # Auto-start first stage if no active stage exists
                # This ensures workflow is truly "initialized" and ready to use
                if engine.workflow and engine.workflow.stages:
                    current_stage = engine.get_current_stage()
                    
                    if not current_stage:
                        # Find first stage (lowest order)
                        first_stage = min(engine.workflow.stages, key=lambda s: s.order)
                        
                        # Check if we can start the first stage
                        can_transition, errors = engine.executor.can_transition_to(first_stage.id)
                        if can_transition:
                            try:
                                engine.start_stage(first_stage.id, first_stage.role)
                                engine.save_state(state_file)  # Save state after starting stage
                                print(f"✅ 已自动启动第一个阶段: {first_stage.name} ({first_stage.id})")
                                print(f"   角色: {first_stage.role}")
                            except Exception as e:
                                print(f"⚠️  警告: 自动启动第一个阶段失败: {e}")
                                print(f"   请手动运行: workflow start {first_stage.id}")
                        else:
                            # First stage has prerequisites that aren't met (unusual but possible)
                            print(f"💡 提示: 第一个阶段 '{first_stage.name}' 需要满足前置条件:")
                            for error in errors:
                                print(f"   - {error}")
                            print(f"   请手动运行: workflow start {first_stage.id}")
                    else:
                        # Already has an active stage
                        print(f"✅ 当前活动阶段: {current_stage.name} ({current_stage.id})")
                
                # Generate initial TEAM_CONTEXT.md (if not already generated by load_workflow)
                # load_workflow may have called update_vibe_context if auto_save_state=True,
                # but we call it again to ensure it's up-to-date
                context_file = engine.update_vibe_context()
                generate_cursorrules(engine.workspace_path, engine)
                print(f"✅ 已生成初始团队上下文: {context_file}")
                
                # Show summary
                current_stage = engine.get_current_stage()
                if current_stage:
                    print(f"\n✅ 初始化完成！当前活动阶段: {current_stage.name} ({current_stage.id})")
                elif engine.workflow and engine.workflow.stages:
                    first_stage = min(engine.workflow.stages, key=lambda s: s.order)
                    print(f"\n✅ 初始化完成！下一步: 运行 'workflow start {first_stage.id}' 启动第一个阶段")
            except Exception as e:
                # If workflow files exist but can't be loaded, create a minimal TEAM_CONTEXT.md
                team_context_file = workspace / ".workflow" / "TEAM_CONTEXT.md"
                minimal_content = """# Team Context - Current Workflow State

**Generated**: {timestamp}

## Current Active Stage

- **Status**: No active stage

**Action Required**: Run `workflow start <stage> <role>` to begin.

## Workflow Overview

Workflow files detected but not yet initialized. Please run:
```bash
workflow start <stage> <role>
```

---
*This file is auto-generated. Do not edit manually.*
""".format(timestamp=__import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                team_context_file.write_text(minimal_content, encoding='utf-8')
                print(f"✅ 已生成初始团队上下文: {team_context_file}")
                print(f"⚠️  工作流加载失败: {e}")
        except Exception as e:
            # If engine initialization fails, create a minimal TEAM_CONTEXT.md
            team_context_file = workspace / ".workflow" / "TEAM_CONTEXT.md"
            minimal_content = """# Team Context - Current Workflow State

**Generated**: {timestamp}

## Current Active Stage

- **Status**: No active stage

**Action Required**: Run `workflow start <stage> <role>` to begin.

---
*This file is auto-generated. Do not edit manually.*
""".format(timestamp=__import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            team_context_file.write_text(minimal_content, encoding='utf-8')
            print(f"✅ 已生成初始团队上下文: {team_context_file}")
            print(f"⚠️  引擎初始化失败: {e}")
    else:
        # Create minimal TEAM_CONTEXT.md even if workflow files don't exist
        team_context_file = workspace / ".workflow" / "TEAM_CONTEXT.md"
        minimal_content = """# Team Context - Current Workflow State

**Generated**: {timestamp}

## Current Active Stage

- **Status**: No active stage

**Action Required**: 
1. Ensure `.workflow/workflow_schema.yaml` and `.workflow/role_schema.yaml` exist
2. Run `workflow start <stage> <role>` to begin

---
*This file is auto-generated. Do not edit manually.*
""".format(timestamp=__import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        team_context_file.write_text(minimal_content, encoding='utf-8')
        print(f"✅ 已生成初始团队上下文: {team_context_file}")


def _prompt_skill_accumulation(engine: WorkflowEngine, workspace: Path):
    """
    提示用户进行技能沉淀（Skill Accumulation）
    
    在工作流所有阶段完成后，询问用户是否要将本次实现的能力沉淀为技能
    """
    try:
        print("\n💡 技能沉淀（Skill Accumulation）")
        print("   本次工作流已完成，您可以将实现的能力沉淀为技能，供后续复用。")
        
        response = input("\n是否要将本次能力沉淀为技能? [y/N]: ").strip().lower()
        if response not in ['y', 'yes']:
            print("   已跳过技能沉淀")
            return
        
        # Ask for skills directory path
        default_skills_dir = workspace / ".workflow" / "skills"
        skills_dir_input = input(f"\n技能目录路径 [默认: {default_skills_dir}]: ").strip()
        
        if skills_dir_input:
            skills_dir = Path(skills_dir_input)
        else:
            skills_dir = default_skills_dir
        
        # Ensure directory exists
        skills_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📂 技能目录: {skills_dir}")
        print("   正在分析现有技能和本次实现...")
        
        # Analyze existing skills
        existing_skills = {}
        if skills_dir.exists():
            for skill_file in skills_dir.glob("*.yaml"):
                try:
                    with open(skill_file, 'r', encoding='utf-8') as f:
                        skill_data = yaml.safe_load(f)
                        if skill_data and 'id' in skill_data:
                            existing_skills[skill_data['id']] = {
                                'file': skill_file,
                                'data': skill_data
                            }
                except Exception as e:
                    print(f"   ⚠️  无法读取技能文件 {skill_file}: {e}")
        
        print(f"   ✅ 发现 {len(existing_skills)} 个现有技能")
        
        # Analyze project outputs to suggest skill
        # This is a simplified version - in practice, you might want to analyze:
        # - Generated files
        # - Implemented features
        # - Used tools and patterns
        
        # Get completed stages info
        completed_stages = []
        if engine.executor and engine.workflow:
            for stage_id in engine.executor.get_completed_stages():
                stage = engine.executor._get_stage_by_id(stage_id)
                if stage:
                    completed_stages.append({
                        'id': stage.id,
                        'name': stage.name,
                        'role': stage.role
                    })
        
        print(f"\n📋 本次完成的工作流阶段:")
        for stage_info in completed_stages:
            print(f"   - {stage_info['name']} ({stage_info['id']}) - 角色: {stage_info['role']}")
        
        # Prompt for skill details
        print("\n📝 请输入技能信息:")
        skill_id = input("   技能 ID (如: user_auth_implementation): ").strip()
        if not skill_id:
            print("   ⚠️  技能 ID 不能为空，已取消")
            return
        
        skill_name = input("   技能名称 (如: User Authentication Implementation): ").strip() or skill_id.replace("_", " ").title()
        skill_description = input("   技能描述: ").strip() or f"Implementation skill for {skill_name}"
        
        # Check for duplicates
        if skill_id in existing_skills:
            print(f"\n⚠️  技能 '{skill_id}' 已存在")
            update = input("   是否更新现有技能? [y/N]: ").strip().lower()
            if update not in ['y', 'yes']:
                print("   已取消")
                return
        
        # Generate skill YAML
        skill_data = {
            'id': skill_id,
            'name': skill_name,
            'description': skill_description,
            'dimensions': ['implementation', 'quality', 'testing'],
            'tools': ['python', 'pytest', 'ruff', 'mypy'],
            'levels': {
                1: {
                    'name': 'Basic',
                    'description': 'Basic implementation with minimal testing'
                },
                2: {
                    'name': 'Intermediate',
                    'description': 'Well-structured implementation with comprehensive tests'
                },
                3: {
                    'name': 'Advanced',
                    'description': 'Production-ready implementation with full test coverage and documentation'
                }
            },
            'constraints': [
                'must_use_type_hints',
                'must_cover_tests',
                'must_pass_linter'
            ],
            'metadata': {
                'created_from_workflow': True,
                'workflow_id': engine.workflow.id if engine.workflow else None,
                'completed_stages': [s['id'] for s in completed_stages],
                'created_at': __import__('datetime').datetime.now().isoformat()
            }
        }
        
        # Save skill file
        skill_file = skills_dir / f"{skill_id}_skill.yaml"
        with open(skill_file, 'w', encoding='utf-8') as f:
            yaml.dump(skill_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        print(f"\n✅ 技能已保存到: {skill_file}")
        print(f"   ID: {skill_id}")
        print(f"   名称: {skill_name}")
        print(f"\n💡 提示: 您可以在 role_schema.yaml 中引用此技能")
        
    except KeyboardInterrupt:
        print("\n\n   已取消技能沉淀")
    except Exception as e:
        print(f"\n⚠️  技能沉淀过程中出错: {e}")
        import traceback
        traceback.print_exc()


def _generate_spec_template(workspace: Path):
    """Generate a basic spec template file"""
    workflow_dir = workspace / ".workflow"
    workflow_dir.mkdir(exist_ok=True)
    temp_dir = workflow_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    spec_template = """# Project Specification

## Overview
Describe your project's purpose and goals here.

## Requirements

### Functional Requirements
- [ ] Requirement 1
- [ ] Requirement 2

### Non-Functional Requirements
- Performance: ...
- Security: ...
- Scalability: ...

## API Specification
(If applicable, describe your API endpoints here)

## Architecture
(Describe system architecture and components)

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Notes
Add any additional notes or constraints here.
"""
    
    spec_file = workflow_dir / "project.spec.md"
    spec_file.write_text(spec_template, encoding='utf-8')
    print(f"✅ 已生成规范文件模板: {spec_file}")
    print("   请编辑此文件以描述您的项目需求")


def is_cursor_ide() -> bool:
    """
    检测是否在 Cursor IDE 环境中
    
    Returns:
        bool: 如果在 Cursor IDE 中返回 True，否则返回 False
    """
    # 方法1: 检查环境变量（Cursor 可能会设置）
    if os.environ.get('CURSOR_APP') or os.environ.get('CURSOR'):
        return True
    
    # 方法2: 检查父进程名称（如果可能）
    try:
        import psutil
        current_process = psutil.Process()
        parent = current_process.parent()
        if parent:
            parent_name = parent.name().lower()
            if 'cursor' in parent_name:
                return True
    except ImportError:
        # psutil 未安装，忽略
        pass
    except (AttributeError, psutil.NoSuchProcess, psutil.AccessDenied):
        # psutil 可用但无法访问父进程，忽略
        pass
    
    # 方法3: 检查是否在 Cursor 的终端中（通过 TERM_PROGRAM 等环境变量）
    term_program = os.environ.get('TERM_PROGRAM', '').lower()
    if 'cursor' in term_program:
        return True
    
    return False


def generate_cursorrules(workspace: Path, engine=None):
    """Generate .cursorrules file for AI awareness with dynamic context support
    
    Only generates if running in Cursor IDE environment.
    Merges autopilot.md content into .cursorrules to avoid duplication.
    """
    # 检查是否在 Cursor IDE 环境中
    if not is_cursor_ide():
        return False
    
    # 检查当前团队
    team_manager = TeamManager(workspace)
    current_team = team_manager.get_current_team()
    team_context = ""
    
    if current_team:
        try:
            team_config = team_manager.get_team_config(current_team)
            team_info = team_manager.teams[current_team]
            team_dir = team_config['workflow'].parent
            team_context = f"""
# CURRENT_TEAM: {current_team}
# Team Name: {team_info.get('name', current_team)}
# Team Directory: {team_dir}
"""
        except Exception:
            # 如果获取团队配置失败，忽略团队上下文
            pass
    
    # 获取可用角色列表和执行模式（从技能定义中读取）
    roles_list = ""
    role_execution_modes = {}  # role_id -> execution_mode info
    
    try:
        if engine and engine.role_manager and engine.role_manager.roles:
            roles = list(engine.role_manager.roles.keys())
            roles_list = f"\nAvailable roles (use @role_name to invoke): {', '.join(roles)}"
            
            # 使用 ExecutionModeAnalyzer 分析角色执行模式
            for role_id, role in engine.role_manager.roles.items():
                if engine.role_manager.skill_library:
                    mode_info = ExecutionModeAnalyzer.get_execution_mode_info(
                        role=role,
                        skill_library=engine.role_manager.skill_library,
                        environment="cursor"
                    )
                    role_execution_modes[role_id] = {
                        'mode': mode_info['mode'],
                        'tools': mode_info['tools'] if mode_info['tools'] else None,
                        'generic_tools': mode_info['generic_tools'] if mode_info['generic_tools'] else None,
                        'capabilities': mode_info['capabilities'] if mode_info['capabilities'] else None
                    }
        else:
            # 尝试从配置文件读取
            roles_file = workspace / ".workflow" / "role_schema.yaml"
            if not roles_file.exists():
                roles_file = workspace / "teams" / "standard-delivery" / "role_schema.yaml"
            if roles_file.exists():
                import yaml
                with open(roles_file, 'r', encoding='utf-8') as f:
                    roles_data = yaml.safe_load(f)
                    if roles_data and 'roles' in roles_data:
                        roles = [r.get('id', '') for r in roles_data['roles'] if r.get('id')]
                        roles_list = f"\nAvailable roles (use @role_name to invoke): {', '.join(roles)}"
    except Exception as e:
        # 如果出错，使用默认值
        pass
    
    # 根据技能定义生成角色执行规则
    role_execution_rules = ""
    if role_execution_modes:
        role_execution_rules = "\n1. **Role Invocation via @mention**:\n"
        role_execution_rules += "   - When user types `@role_name`, you MUST:\n"
        role_execution_rules += "     a. Load the role configuration from `.workflow/role_schema.yaml`\n"
        role_execution_rules += "     b. Identify the role's `required_skills` from skill definitions\n"
        role_execution_rules += "     c. **Execution mode is determined by skills' `execution_mode` metadata** (generic, not Cursor-specific):\n\n"
        
        # 按执行模式分组角色
        mode_groups = {}
        for role_id, mode_info in role_execution_modes.items():
            mode = mode_info['mode']
            if mode not in mode_groups:
                mode_groups[mode] = []
            mode_groups[mode].append((role_id, mode_info))
        
        # 生成每个模式的规则
        for mode, roles in mode_groups.items():
            if mode == 'analysis':
                role_execution_rules += f"   **Analysis Mode** (skills define: `execution_mode: analysis`):\n"
                role_execution_rules += f"   - Roles: {', '.join([r[0] for r in roles])}\n"
                role_execution_rules += "   - These roles focus on analysis, design, and documentation\n"
                role_execution_rules += "   - Use `workflow role-execute <role_id> \"<requirement>\" --use-llm` to execute\n"
                role_execution_rules += "   - Skills define capabilities like: write_documentation, create_requirements_doc, write_architecture_doc\n"
                role_execution_rules += "   - Example: `@product_analyst 分析用户需求` → Execute `workflow role-execute product_analyst \"分析用户需求\" --use-llm`\n\n"
            
            elif mode == 'implementation':
                role_execution_rules += f"   **Implementation Mode** (skills define: `execution_mode: implementation`):\n"
                role_execution_rules += f"   - Roles: {', '.join([r[0] for r in roles])}\n"
                role_execution_rules += "   - **CRITICAL: These roles MUST directly execute code operations, NOT just analysis**\n"
                role_execution_rules += "   - When mentioned, you MUST:\n"
                role_execution_rules += "     1. Understand the requirement\n"
                role_execution_rules += "     2. **Directly use Cursor's tools** (mapped from skills' generic `execution_tools`):\n"
                
                # 收集所有实现角色的工具
                all_tools = set()
                all_capabilities = []
                for role_id, mode_info in roles:
                    if mode_info.get('tools'):
                        all_tools.update(mode_info['tools'])
                    if mode_info.get('capabilities'):
                        all_capabilities.extend(mode_info['capabilities'])
                
                if all_tools:
                    role_execution_rules += f"        - Available tools: {', '.join(sorted(all_tools))}\n"
                if all_capabilities:
                    role_execution_rules += f"     3. Use capabilities defined in skills: {', '.join(set(all_capabilities))}\n"
                
                role_execution_rules += "     4. **Actually implement** - create/modify files, write code, write tests\n"
                role_execution_rules += "     5. Do NOT just call `workflow role-execute` and return analysis - you must ACTUALLY WRITE CODE\n"
                role_execution_rules += "   - Example: `@core_framework_engineer 实现用户认证模块` → \n"
                role_execution_rules += "     * Read requirements/architecture docs\n"
                role_execution_rules += "     * Use `write` to create Python files in appropriate directories\n"
                role_execution_rules += "     * Use `search_replace` to modify existing code\n"
                role_execution_rules += "     * Write tests using defined test tools\n\n"
            
            elif mode == 'validation':
                role_execution_rules += f"   **Validation Mode** (skills define: `execution_mode: validation`):\n"
                role_execution_rules += f"   - Roles: {', '.join([r[0] for r in roles])}\n"
                role_execution_rules += "   - These roles focus on testing, validation, and quality assurance\n"
                role_execution_rules += "   - Use tools defined in skills' `execution_tools` (mapped to Cursor tools) to run tests and validate functionality\n"
                
                all_tools = set()
                all_capabilities = []
                for role_id, mode_info in roles:
                    if mode_info.get('tools'):
                        all_tools.update(mode_info['tools'])
                    if mode_info.get('capabilities'):
                        all_capabilities.extend(mode_info['capabilities'])
                
                if all_tools:
                    role_execution_rules += f"   - Available tools: {', '.join(sorted(all_tools))}\n"
                if all_capabilities:
                    role_execution_rules += f"   - Capabilities: {', '.join(set(all_capabilities))}\n"
                role_execution_rules += "\n"
        
        role_execution_rules += "   **Note**: Execution mode is automatically determined from skill metadata. Tools are automatically mapped to Cursor-specific tools.\n"
    else:
        # 回退到默认规则
        role_execution_rules = "\n1. **Role Invocation via @mention**:\n"
        role_execution_rules += "   - Load role configuration and identify required skills\n"
        role_execution_rules += "   - Check skill definitions for `cursor_execution_mode` and `cursor_tools` metadata\n"
        role_execution_rules += "   - Execute according to skill-defined execution mode\n"
    
    # Static base rules
    static_rules = f"""# Multi-Role Workflow Rules
{team_context}
You are operating within a structured Multi-Role Skills Workflow. 
To ensure project stability and follow best practices, adhere to these rules:

## 🎭 Role-Based Execution (Cursor IDE Integration)

**CRITICAL: When user mentions @role_name, automatically use that role's skills**

{role_execution_rules}

2. **Team Workflow via @team**:
   - When user mentions `@team` or `@[team]`, immediately execute `workflow wfauto` to run the complete workflow
   - This triggers all stages sequentially: requirements → architecture → implementation → validation
   - Example: `@team 实现用户登录功能` → Execute `workflow wfauto --intent "实现用户登录功能"`

{roles_list}

## 📋 Core Rules

1. **Role Awareness**: Before making changes, check the workflow state file to identify the current active stage and role.
2. **Constraint Enforcement**: Respect the `allowed_actions` and `forbidden_actions` defined in the role schema for the current role.
3. **Stage Boundaries**: 
   - Do not skip stages.
   - Do not perform implementation tasks while in the `requirements` or `architecture` stages.
   - If the current stage does not match the task, advise the user to run `workflow start <stage> <role>`.
4. **Quality Gates**: Ensure all quality gates and required outputs defined in the workflow schema are satisfied before attempting to complete a stage.
5. **Skill-Based Execution**:
   - Execution mode is automatically determined from skill metadata
   - **Analysis skills**: Use `workflow role-execute` for analysis and documentation
   - **Implementation skills**: Directly use Cursor tools to write/modify code files (do NOT just call commands)
   - **Validation skills**: Use tools to run tests and validate functionality
7. **Agent Execution**:
   - For automated execution, use `workflow agent-execute [stage]`.
   - When acting as an agent, follow the `instruction_template` in the role definition and the `goal_template` in the stage definition.
7. **Team Context & Auto Workflow Execution**: 
   - **CRITICAL: Fully Automated Execution**:
     - **Every @[team] mention**: When user mentions `@[team]` or `@team`, **immediately execute** `workflow wfauto` to run the complete workflow with Agent + Skills automation. This is the default behavior - no explicit request needed.
     - **Fully Automated**: Execute the complete workflow automatically without asking for confirmation at each step. Only pause if critical issues arise (e.g., API keys, environment configuration, external dependencies).
     - **No User Intervention**: The workflow runs end-to-end automatically, similar to Lovable/MetaGPT. Do not ask "Should I proceed?" or "Is this okay?" - just execute.
   - When user mentions `@[team]`, `@team`, or asks about "team workflow", **immediately read** the TEAM_CONTEXT.md file (if exists).
   - Current team configuration is loaded from the active team context.
   - The `workflow wfauto` command automatically:
     - Uses AgentOrchestrator for multi-agent collaboration
     - Automatically selects and executes relevant skills for each stage
     - Runs skill workflows with auto-trigger
     - Uses relaxed quality gates (won't block on failures)
     - Completes all stages without user intervention (except for critical issues)

## 🚀 Autonomous Workflow Pilot (Autopilot Mode)

You are the **Workflow Pilot**. Your mission is to execute user requests end-to-end while adhering to the Multi-Role Skills Workflow framework.

### Intent Recognition & Auto-Trigger
- **Default Behavior**: When the user uses the slash command `/wfauto [goal]` or expresses a desire for you to "just do it" or "handle the whole process", immediately transition into **Autopilot Mode**.
- **CRITICAL**: When the user mentions `@[team]` or `@team`, **immediately execute** `workflow wfauto` - this is the default behavior, no explicit request needed.
- **Every conversation**: When the user expresses any task, goal, or starts a conversation, automatically execute the full workflow to analyze requirements through all stages.

### Autopilot Execution Protocol
Follow this exact sequence without asking for permission for each step:

**Note**: When triggered via `@[team]` or any user conversation, **always execute** `workflow wfauto` to run all stages sequentially. This automatically uses **Agent + Skills** for fully automated execution (similar to Lovable/MetaGPT).

**CRITICAL**: The `workflow wfauto` command automatically:
- Uses AgentOrchestrator for multi-agent collaboration
- Automatically selects and executes relevant skills
- Runs skill workflows with auto-trigger
- Uses relaxed quality gates (won't block on failures)

1. **Preparation**: If the `.workflow/` directory or state file doesn't exist, run `workflow init --quick` (uses vibe-coding template by default).
2. **Automatic Execution**: Run `workflow wfauto` - this will automatically:
   - Execute all stages sequentially using Agent + Skills
   - For each stage:
     - Create Agent for the stage role
     - Automatically select relevant skills based on stage goal
     - Execute selected skills
     - Complete stage with relaxed quality gates
   - No manual intervention needed - fully automated like Lovable/MetaGPT
3. **Self-Healing**: If any stage fails, the system will:
   - Show warnings but continue (relaxed mode)
   - Retry failed skills if configured
   - Fall back to traditional mode if Agent system unavailable
4. **Skill Accumulation Phase (Optional)**:
   - After the project is successfully validated, skill accumulation is **optional and non-blocking**.
   - In automated mode (Agent + Skills), skill accumulation is skipped automatically.
   - Users can manually run `workflow skill-accumulate` if they want to persist capabilities as skills.

### Communication Guidelines
- **Silent Mode**: Do not ask "Should I move to the next stage?" or "Is this requirement okay?". Just proceed.
- **Fully Automated**: When triggered via `@team`, execute the complete workflow automatically without asking for confirmation at each step.
- **Progress Updates**: Provide brief, one-line updates after completing each major stage (e.g., "✅ Requirements finalized. Moving to Architecture...").
- **Exception Awakening**: ONLY stop and ask the user if:
  - You are stuck in a self-healing loop for more than 3 attempts.
  - There is a critical contradiction in the requirements.
  - **Critical external dependencies**: API keys, environment-specific credentials, or other external resources that cannot be automatically configured.

### Constraint Awareness
- Always respect the `allowed_actions` and `forbidden_actions` in `.workflow/role_schema.yaml`.
- Use the tools provided in the environment (Python, Ruff, Pytest, etc.) to verify your work.

**Start your execution now by running the first necessary command.**
"""
    
    # Dynamic context anchor
    current_stage_id = "None"
    current_role_id = "None"
    
    if engine and engine.executor and engine.executor.state:
        current_stage = engine.get_current_stage()
        if current_stage:
            current_stage_id = current_stage.id
        current_role_id = engine.executor.state.current_role or "None"
        
    dynamic_anchor = f"\n# DYNAMIC_CONTEXT_ANCHOR\nCURRENT_STAGE: {current_stage_id}\nCURRENT_ROLE: {current_role_id}\n"
    
    footer = """
Current project status can be viewed at any time by running `workflow status`.
"""
    
    content = static_rules + dynamic_anchor + footer
    cursorrules_path = workspace / ".cursorrules"
    cursorrules_path.write_text(content, encoding='utf-8')
    return True


def cmd_start(args):
    """启动阶段"""
    try:
        engine, workflow_file, state_file = _init_engine(args)
        
        # Smart inference: if stage not provided, show status and available options
        stage_id = args.stage
        role_id = args.role_alt or args.role  # Support --as flag
        
        if not stage_id:
            # Show current status and available stages/roles instead of auto-starting
            print("\n" + "=" * 60)
            print("工作流状态与可用选项")
            print("=" * 60)
            
            # Show current status
            current = engine.get_current_stage()
            if current:
                print(f"\n当前活动阶段: {current.name} (ID: {current.id})")
                print(f"当前角色: {engine.executor.state.current_role if engine.executor else 'None'}")
                print(f"\n⚠️  已有活动阶段，请先完成当前阶段:")
                print(f"   workflow complete {current.id}")
                print(f"\n或查看状态:")
                print(f"   workflow status")
                sys.exit(0)
            else:
                print("\n当前阶段: 无活动阶段")
            
            # Show available stages
            print("\n可用阶段:")
            print("-" * 60)
            completed = engine.executor.get_completed_stages() if engine.executor else set()
            
            for stage in sorted(engine.workflow.stages, key=lambda s: s.order):
                status = engine.get_stage_status(stage.id) if engine.executor else None
                status_icon = "✅" if stage.id in completed else ("🔄" if status == StageStatus.IN_PROGRESS else "⏳")
                
                # Check if can transition
                can_start = False
                if engine.executor:
                    can_transition, errors = engine.executor.can_transition_to(stage.id)
                    can_start = can_transition
                elif not completed:
                    # First stage can always start if nothing completed
                    can_start = (stage.order == 1)
                
                print(f"\n{status_icon} 阶段 {stage.order}: {stage.name}")
                print(f"   ID: {stage.id}")
                print(f"   角色: {stage.role}")
                if stage.prerequisites:
                    print(f"   前置条件: {', '.join(stage.prerequisites)}")
                if can_start:
                    print(f"   💡 可以启动: workflow start {stage.id}")
                elif stage.id in completed:
                    print(f"   ✅ 已完成")
                elif engine.executor:
                    can_transition, errors = engine.executor.can_transition_to(stage.id)
                    if not can_transition:
                        print(f"   ⚠️  无法启动: {', '.join(errors[:2])}")
            
            # Show available roles
            print("\n可用角色:")
            print("-" * 60)
            for role_id_item, role in engine.role_manager.roles.items():
                print(f"   - {role.name} (ID: {role_id_item})")
                desc = role.description[:60] + "..." if len(role.description) > 60 else role.description
                print(f"     描述: {desc}")
            
            # Show next suggested action
            print("\n" + "=" * 60)
            if not completed:
                first_stage = min(engine.workflow.stages, key=lambda s: s.order)
                print(f"💡 建议: 启动第一个阶段")
                print(f"   workflow start {first_stage.id}")
            else:
                # Find next uncompleted stage
                next_suggested = False
                for stage in sorted(engine.workflow.stages, key=lambda s: s.order):
                    if stage.id not in completed:
                        if engine.executor:
                            can_transition, errors = engine.executor.can_transition_to(stage.id)
                            if can_transition:
                                print(f"💡 建议: 启动下一阶段")
                                print(f"   workflow start {stage.id}")
                                next_suggested = True
                                break
                        else:
                            print(f"💡 建议: 启动阶段")
                            print(f"   workflow start {stage.id}")
                            next_suggested = True
                            break
                if not next_suggested:
                    print("✅ 所有阶段已完成！")
            
            print("\n其他命令:")
            print("   workflow status          - 查看详细状态")
            print("   workflow list-stages     - 列出所有阶段")
            print("   workflow list-roles      - 列出所有角色")
            sys.exit(0)
        
        # Original logic for when stage_id is provided
        if not role_id:
            # Infer role from stage
            stage = engine.executor._get_stage_by_id(stage_id) if engine.executor else None
            if stage:
                role_id = stage.role
                print(f"💡 自动推断角色: {role_id}")
            else:
                print(f"❌ 无法推断角色，请明确指定: workflow start {stage_id} <role>", file=sys.stderr)
                sys.exit(1)
        
        engine.start_stage(stage_id, role_id)
        generate_cursorrules(engine.workspace_path, engine)
        # State is now auto-saved, but keep manual save for explicit control
        if getattr(args, 'no_auto_save', False):
            engine.save_state(state_file)
        print(f"✅ 阶段 '{stage_id}' 已启动 (角色: {role_id})")
        
        if args.status:
            print_status(engine)
            
    except WorkflowError as e:
        print(f"❌ 工作流错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)



def cmd_complete(args):
    """完成阶段"""
    try:
        engine, workflow_file, state_file = _init_engine(args)
        
        stage_id = args.stage
        
        if not stage_id:
            # Show available stages to complete
            print("\n" + "=" * 60)
            print("可完成的阶段")
            print("=" * 60)
            
            current = engine.get_current_stage()
            if not current:
                print("\n⚠️  当前没有活动阶段")
                print("   请先启动一个阶段: workflow start <stage>")
                print("\n或查看所有阶段:")
                print("   workflow list-stages")
                sys.exit(1)
            
            print(f"\n当前活动阶段: {current.name} (ID: {current.id})")
            print(f"当前角色: {engine.executor.state.current_role if engine.executor else 'None'}")
            
            # Show required outputs
            if current.outputs:
                print("\n必需输出:")
                workflow_id = engine.workflow.id if engine.workflow else "default"
                for output in current.outputs:
                    # Get output path using unified path calculation
                    if output.type in ("document", "report"):
                        output_path = engine.workspace_path / ".workflow" / "outputs" / workflow_id / current.id / output.name
                    else:
                        output_path = engine.workspace_path / output.name
                    exists = output_path.exists()
                    marker = "✅" if exists else "⏳"
                    print(f"  {marker} {output.name} ({'已存在' if exists else '缺失'})")
            
            # Show quality gates
            if current.quality_gates:
                print("\n质量门禁:")
                for gate in current.quality_gates:
                    print(f"  - {gate.type}: {', '.join(gate.criteria)}")
            
            print(f"\n💡 完成当前阶段:")
            print(f"   workflow complete {current.id}")
            print(f"\n或查看详细分析:")
            print(f"   workflow analyze")
            sys.exit(0)
        
        passed, errors = engine.complete_stage(stage_id)
        generate_cursorrules(engine.workspace_path, engine)
        
        if passed:
            # State is now auto-saved, but keep manual save for explicit control
            if getattr(args, 'no_auto_save', False):
                engine.save_state(state_file)
            print(f"✅ 阶段 '{stage_id}' 已完成")
            
            # Check if all stages are completed (skill accumulation trigger)
            if engine.executor and engine.workflow:
                completed = engine.executor.get_completed_stages()
                all_stages = {s.id for s in engine.workflow.stages}
                
                # If all stages are completed, prompt for skill accumulation
                if completed == all_stages:
                    print("\n" + "=" * 60)
                    print("🎉 恭喜！所有工作流阶段已完成")
                    print("=" * 60)
                    _prompt_skill_accumulation(engine, engine.workspace_path)
        else:
            print(f"❌ 阶段 '{stage_id}' 质量门禁失败:", file=sys.stderr)
            for error in errors:
                print(f"   - {error}", file=sys.stderr)
            sys.exit(1)
        
        if args.status:
            print_status(engine)
            
    except WorkflowError as e:
        print(f"❌ 工作流错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args):
    """显示状态"""
    try:
        engine, workflow_file, state_file = _init_engine(args)
        print_status(engine)
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_validate(args):
    """验证动作"""
    try:
        engine, _, _ = _init_engine(args)
        
        result = engine.validate_action(args.role, args.action)
        
        if result:
            print(f"✅ 角色 '{args.role}' 可以执行动作 '{args.action}'")
        else:
            print(f"❌ 角色 '{args.role}' 不能执行动作 '{args.action}'")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list_stages(args):
    """列出所有阶段"""
    try:
        engine, workflow_file, _ = _init_engine(args)
        
        print("\n工作流阶段列表:")
        print("=" * 60)
        for stage in engine.workflow.stages:
            print(f"\n阶段 {stage.order}: {stage.name}")
            print(f"  ID: {stage.id}")
            print(f"  角色: {stage.role}")
            print(f"  前置条件: {', '.join(stage.prerequisites) if stage.prerequisites else '无'}")
            print(f"  质量门禁: {len(stage.quality_gates)} 个")
            print(f"  必需输出: {len([o for o in stage.outputs if o.required])} 个")
            
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list_roles(args):
    """列出所有角色"""
    try:
        engine, _, _ = _init_engine(args)
        
        print("\n角色列表:")
        print("=" * 60)
        for role_id, role in engine.role_manager.roles.items():
            print(f"\n角色: {role.name}")
            print(f"  ID: {role_id}")
            print(f"  描述: {role.description}")
            print(f"  允许的动作: {len(role.constraints.get('allowed_actions', []))} 个")
            print(f"  禁止的动作: {len(role.constraints.get('forbidden_actions', []))} 个")
            print(f"  所需技能:")
            # Role模型使用skills字段（技能ID列表），不是required_skills
            if hasattr(role, 'required_skills') and role.required_skills:
                # 兼容旧格式
                for req in role.required_skills:
                    skill = engine.role_manager.skill_library.get(req.skill_id) if engine.role_manager.skill_library else None
                    if skill:
                        print(f"    - {skill.name} (等级≥{req.min_level})")
                    else:
                        print(f"    - {req.skill_id}")
            elif hasattr(role, 'skills') and role.skills:
                # 新格式：直接使用技能ID列表
                for skill_id in role.skills:
                    skill = engine.role_manager.skill_library.get(skill_id) if engine.role_manager.skill_library else None
                    if skill:
                        print(f"    - {skill.name}")
                    else:
                        print(f"    - {skill_id}")
            else:
                print("    - 无")
            
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_export_graph(args):
    """Export workflow graph to Mermaid or HTML"""
    try:
        engine, _, _ = _init_engine(args)
        mermaid_code = engine.to_mermaid(include_roles=not args.no_roles)
        
        if args.format == "html":
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Workflow Visualization</title>
    <style>
        body {{ font-family: sans-serif; margin: 2em; line-height: 1.5; }}
        .mermaid {{ margin-top: 2em; }}
        h1 {{ color: #333; }}
        .desc {{ color: #666; font-style: italic; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <script>mermaid.initialize({{startOnLoad:true, theme: 'default'}});</script>
</head>
<body>
    <h1>{engine.workflow.name if engine.workflow else 'Workflow'}</h1>
    <p class="desc">{engine.workflow.description if engine.workflow else ''}</p>
    <div class="mermaid">
{mermaid_code}
    </div>
</body>
</html>"""
            output_file = Path(args.output or "workflow_viz.html")
            output_file.write_text(html_content, encoding='utf-8')
            print(f"✅ 可视化 HTML 已保存到: {output_file}")
        else:
            if args.output:
                output_file = Path(args.output)
                output_file.write_text(mermaid_code, encoding='utf-8')
                print(f"✅ Mermaid 代码已保存到: {output_file}")
            else:
                print("\nMermaid 代码:")
                print("=" * 60)
                print(mermaid_code)
                print("=" * 60)
                
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_check_team(args):
    """Perform a health check of the team and workflow configuration"""
    try:
        engine, _, _ = _init_engine(args)
        
        print("\n" + "=" * 60)
        print("团队与工作流健康检查报告")
        print("=" * 60)
        
        issues = []
        
        # 1. Role Coverage
        print("\n1. 角色覆盖检查:")
        if not engine.workflow:
            print("  - ❌ 错误: 未加载工作流定义")
            return
            
        stages = engine.workflow.stages
        stage_roles = set(s.role for s in stages)
        all_roles = set(engine.role_manager.roles.keys())
        
        print(f"  - 阶段定义的角色: {', '.join(stage_roles)}")
        print(f"  - 系统定义的角色: {', '.join(all_roles)}")
        
        unused_roles = all_roles - stage_roles
        if unused_roles:
            print(f"  - ⚠️ 警告: 以下角色未在任何阶段中使用: {', '.join(unused_roles)}")
        
        # 2. Skill Gap Analysis
        print("\n2. 技能缺口分析:")
        for role_id, role in engine.role_manager.roles.items():
            if not role.required_skills:
                print(f"  - ⚠️ 警告: 角色 '{role_id}' 未定义任何所需技能")
            else:
                for req in role.required_skills:
                    if not engine.role_manager.skill_library or req.skill_id not in engine.role_manager.skill_library:
                        issues.append(f"角色 '{role_id}' 要求的技能 '{req.skill_id}' 不存在")
        
        # 3. Workflow Continuity
        print("\n3. 工作流连续性检查:")
        orders = sorted([s.order for s in stages])
        if orders:
            expected_orders = list(range(min(orders), max(orders) + 1))
            if orders != expected_orders:
                issues.append(f"工作流阶段顺序不连续: {orders}")
            else:
                print("  - ✅ 阶段顺序连续")
        
        # 4. Quality Gate Check
        print("\n4. 质量门禁检查:")
        for stage in stages:
            if not stage.quality_gates:
                print(f"  - ⚠️ 警告: 阶段 '{stage.id}' 未定义任何质量门禁")
            if not stage.outputs:
                print(f"  - ⚠️ 警告: 阶段 '{stage.id}' 未定义任何必需输出")

        print("\n总结:")
        if not issues:
            print("  - ✅ 未发现严重配置问题。团队配置符合基本要求。")
        else:
            print(f"  - ❌ 发现 {len(issues)} 个潜在问题:")
            for issue in issues:
                print(f"    - {issue}")
                
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_team_list(args):
    """列出所有团队"""
    try:
        workspace = Path(args.workspace or ".")
        team_manager = TeamManager(workspace)
        teams = team_manager.list_teams()
        
        if not teams:
            print("📋 未找到任何团队配置")
            print("\n💡 提示: 使用 'workflow team create <team_id>' 创建新团队")
            return
        
        print("\n" + "=" * 60)
        print("虚拟团队列表")
        print("=" * 60)
        
        current = team_manager.get_current_team()
        for team in teams:
            marker = "→" if team["is_current"] else " "
            status = "【当前】" if team["is_current"] else ""
            print(f"\n{marker} {team['id']} {status}")
            print(f"   名称: {team['name']}")
            if team['description']:
                print(f"   描述: {team['description']}")
            print(f"   目录: {team['dir']}")
        
        if not current:
            print("\n⚠️  未设置当前活动团队，使用默认配置 (.workflow/)")
            print("💡 提示: 使用 'workflow team switch <team_id>' 切换团队")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_team_templates(args):
    """列出可用的团队配置模板"""
    try:
        workspace = Path(args.workspace or ".")
        
        print("\n" + "=" * 60)
        print("可用的团队配置模板")
        print("=" * 60)
        
        # 查找 teams 目录
        teams_dir = workspace / "teams"
        templates_found = False
        
        if teams_dir.exists() and teams_dir.is_dir():
            templates = sorted([d for d in teams_dir.iterdir() if d.is_dir()])
            if templates:
                print("\n📂 项目团队配置 (teams/):")
                for template in templates:
                    readme_file = template / "README.md"
                    description = ""
                    if readme_file.exists():
                        # 读取第一行作为描述
                        try:
                            first_line = readme_file.read_text(encoding='utf-8').split('\n')[0]
                            if first_line.startswith('#'):
                                description = first_line.lstrip('#').strip()
                        except Exception:
                            pass
                    
                    print(f"  • {template.name}")
                    if description:
                        print(f"    {description}")
                templates_found = True
        
        # 查找内置 templates
        try:
            from .engine import TeamManager
            import work_by_roles
            builtin_templates_dir = Path(work_by_roles.__file__).parent / "templates"
            if builtin_templates_dir.exists():
                builtin_templates = sorted([d for d in builtin_templates_dir.iterdir() if d.is_dir()])
                if builtin_templates:
                    print("\n📦 内置模板 (work_by_roles/templates/):")
                    for template in builtin_templates:
                        print(f"  • {template.name}")
                    templates_found = True
        except Exception:
            pass
        
        if not templates_found:
            print("\n⚠️  未找到任何团队配置模板")
            print("\n💡 提示:")
            print("   1. 在 teams/ 目录下创建团队配置")
            print("   2. 使用 'workflow team create <team_id> --template <template_name>' 创建团队")
        else:
            print("\n💡 使用方法:")
            print("   workflow team create <team_id> --template <template_name>")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_team_switch(args):
    """切换到指定团队"""
    try:
        workspace = Path(args.workspace or ".")
        team_manager = TeamManager(workspace)
        
        team_id = args.team_id
        if team_id not in team_manager.teams:
            print(f"❌ 团队 '{team_id}' 不存在", file=sys.stderr)
            print("\n可用团队:")
            for team in team_manager.list_teams():
                print(f"  - {team['id']}: {team['name']}")
            sys.exit(1)
        
        team_manager.set_current_team(team_id)
        team_config = team_manager.get_team_config(team_id)
        team_info = team_manager.teams[team_id]
        
        print(f"✅ 已切换到团队: {team_id}")
        print(f"   名称: {team_info.get('name', team_id)}")
        print(f"   工作流: {team_config['workflow']}")
        print(f"   角色: {team_config['roles']}")
        print(f"   技能: {team_config['skills']}")
        print(f"\n💡 现在可以使用 'workflow start' 等命令，将自动使用该团队配置")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_team_create(args):
    """创建新团队"""
    try:
        workspace = Path(args.workspace or ".")
        team_manager = TeamManager(workspace)
        
        team_id = args.team_id
        name = args.name or team_id.replace("_", " ").title()
        description = args.description or ""
        template = args.template
        dir_name = args.dir
        
        team_dir = team_manager.create_team(
            team_id=team_id,
            name=name,
            description=description,
            template=template,
            dir_name=dir_name
        )
        
        print(f"✅ 已创建团队: {team_id}")
        print(f"   名称: {name}")
        print(f"   目录: {team_dir}")
        
        if template:
            print(f"   模板: {template}")
        
        print(f"\n💡 下一步:")
        print(f"   1. 编辑团队配置: {team_dir}/")
        print(f"   2. 切换到该团队: workflow team switch {team_id}")
        print(f"   3. 开始使用: workflow start <stage>")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_team_current(args):
    """显示当前活动团队"""
    try:
        workspace = Path(args.workspace or ".")
        team_manager = TeamManager(workspace)
        
        current = team_manager.get_current_team()
        if current:
            team_config = team_manager.get_team_config(current)
            team_info = team_manager.teams[current]
            
            print("\n" + "=" * 60)
            print("当前活动团队")
            print("=" * 60)
            print(f"团队 ID: {current}")
            print(f"名称: {team_info.get('name', current)}")
            if team_info.get('description'):
                print(f"描述: {team_info['description']}")
            print(f"\n配置文件:")
            print(f"  工作流: {team_config['workflow']}")
            print(f"  角色: {team_config['roles']}")
            print(f"  技能: {team_config['skills']}")
            print(f"  状态: {team_config['state']}")
        else:
            print("⚠️  未设置当前活动团队")
            print("   使用默认配置: .workflow/")
            print("\n💡 提示: 使用 'workflow team switch <team_id>' 切换团队")
            print("   使用 'workflow team list' 查看所有团队")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_team_delete(args):
    """删除团队"""
    try:
        workspace = Path(args.workspace or ".")
        team_manager = TeamManager(workspace)
        
        team_id = args.team_id
        if team_id not in team_manager.teams:
            print(f"❌ 团队 '{team_id}' 不存在", file=sys.stderr)
            sys.exit(1)
        
        # 确认删除
        if not args.force:
            confirm = input(f"⚠️  确定要删除团队 '{team_id}' 吗? [y/N]: ").strip().lower()
            if confirm not in ['y', 'yes']:
                print("已取消")
                return
        
        team_manager.delete_team(team_id, remove_files=args.remove_files)
        print(f"✅ 已删除团队: {team_id}")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_analyze(args):
    """Perform comprehensive workflow analysis for current stage"""
    try:
        engine, _, _ = _init_engine(args)
        
        current_stage = engine.get_current_stage()
        if not current_stage:
            print("⚠️  当前没有活动阶段")
            print("   运行 'workflow start' 开始工作流")
            sys.exit(0)
        
        print("\n" + "=" * 60)
        print(f"工作流分析报告 - {current_stage.name}")
        print("=" * 60)
        
        # 1. Stage Overview
        print("\n📋 阶段概览:")
        print(f"  - 阶段ID: {current_stage.id}")
        print(f"  - 阶段名称: {current_stage.name}")
        print(f"  - 顺序: {current_stage.order}")
        print(f"  - 角色: {engine.executor.state.current_role}")
        
        # 2. Role Analysis
        role_id = engine.executor.state.current_role
        if role_id:
            role = engine.role_manager.get_role(role_id)
            if role:
                print("\n👤 角色分析:")
                print(f"  - 角色名称: {role.name}")
                print(f"  - 描述: {role.description}")
                
                # Skills
                if role.required_skills:
                    print("\n  📚 所需技能:")
                    for req in role.required_skills:
                        skill = engine.role_manager.skill_library.get(req.skill_id) if engine.role_manager.skill_library else None
                        if skill:
                            level_desc = skill.levels.get(req.min_level, f"Level {req.min_level}")
                            print(f"    - {skill.name} (≥{req.min_level}): {level_desc}")
                            if skill.tools:
                                print(f"      工具: {', '.join(skill.tools)}")
                
                # Constraints
                allowed = role.constraints.get('allowed_actions', [])
                forbidden = role.constraints.get('forbidden_actions', [])
                print(f"\n  ✅ 允许的动作 ({len(allowed)}):")
                for action in allowed[:5]:  # Show first 5
                    print(f"    - {action}")
                if len(allowed) > 5:
                    print(f"    ... 还有 {len(allowed) - 5} 个")
                
                if forbidden:
                    print(f"\n  ❌ 禁止的动作 ({len(forbidden)}):")
                    for action in forbidden[:5]:
                        print(f"    - {action}")
                    if len(forbidden) > 5:
                        print(f"    ... 还有 {len(forbidden) - 5} 个")
        
        # 3. Requirements Analysis
        print("\n📝 阶段要求:")
        
        # Required Outputs
        if current_stage.outputs:
            print("\n  必需输出:")
            workflow_id = engine.workflow.id if engine.workflow else "default"
            for output in current_stage.outputs:
                # Get output path using unified path calculation
                if output.type in ("document", "report"):
                    output_path = engine.workspace_path / ".workflow" / "outputs" / workflow_id / current_stage.id / output.name
                else:
                    output_path = engine.workspace_path / output.name
                status = "✅ 已完成" if output_path.exists() else "⏳ 待完成"
                print(f"    - {status}: {output.name} ({output.type})")
        
        # Quality Gates
        if current_stage.quality_gates:
            print("\n  质量门禁:")
            for gate in current_stage.quality_gates:
                print(f"    - {gate.type}: {', '.join(gate.criteria)}")
                # Evaluate gate
                passed, errors = engine.quality_gates.evaluate_gate(gate, current_stage, engine.workspace_path)
                if passed:
                    print(f"      ✅ 通过")
                else:
                    print(f"      ❌ 未通过:")
                    for error in errors[:3]:  # Show first 3 errors
                        print(f"        - {error}")
                    if len(errors) > 3:
                        print(f"        ... 还有 {len(errors) - 3} 个错误")
        
        # 4. Prerequisites Check
        if current_stage.prerequisites:
            print("\n🔗 前置条件:")
            completed = engine.executor.get_completed_stages()
            for prereq in current_stage.prerequisites:
                status = "✅" if prereq in completed else "⏳"
                prereq_stage = next((s for s in engine.workflow.stages if s.id == prereq), None)
                prereq_name = prereq_stage.name if prereq_stage else prereq
                print(f"    {status} {prereq_name} ({prereq})")
        
        # 5. Next Steps
        print("\n🎯 下一步建议:")
        completed = engine.executor.get_completed_stages()
        
        # Check if current stage can be completed
        can_complete = True
        missing_outputs = []
        workflow_id = engine.workflow.id if engine.workflow else "default"
        for output in current_stage.outputs:
            if output.required:
                # Get output path using unified path calculation
                if output.type in ("document", "report"):
                    output_path = engine.workspace_path / ".workflow" / "outputs" / workflow_id / current_stage.id / output.name
                else:
                    output_path = engine.workspace_path / output.name
                if not output_path.exists():
                    can_complete = False
                    missing_outputs.append(output.name)
        
        if can_complete:
            print("  ✅ 当前阶段可以完成:")
            print(f"     workflow complete {current_stage.id}")
        else:
            print("  ⏳ 需要完成以下输出才能完成阶段:")
            for output in missing_outputs:
                print(f"     - {output}")
        
        # Suggest next stage
        next_stages = [s for s in engine.workflow.stages 
                      if s.order > current_stage.order 
                      and s.id not in completed]
        if next_stages:
            next_stage = min(next_stages, key=lambda s: s.order)
            can_transition, errors = engine.executor.can_transition_to(next_stage.id)
            if can_transition:
                print(f"\n  ➡️  下一阶段: {next_stage.name} ({next_stage.id})")
                print(f"     角色: {next_stage.role}")
                print(f"     命令: workflow start {next_stage.id} --as {next_stage.role}")
        
        # 6. Team Context Reference
        print("\n💡 AI 协作提示:")
        print("  在 Cursor 中使用 '@[team]' 或 '@team' 让 AI 自动应用当前角色约束")
        print(f"  AI 会自动读取: .workflow/TEAM_CONTEXT.md")
        print("  使用 '@[team] wfauto' 或 '@[team] 运行完整工作流' 可自动执行所有阶段")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_add_role(args):
    """Add a new role interactively"""
    try:
        workspace = Path(args.workspace or ".")
        roles_file = Path(args.roles or "role_schema.yaml")
        
        if not roles_file.exists():
            print(f"❌ 角色文件不存在: {roles_file}", file=sys.stderr)
            sys.exit(1)
        
        # Load existing roles
        with open(roles_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Interactive input
        role_id = args.role_id or input("角色 ID (如: frontend_dev): ").strip()
        name = args.name or input("角色名称: ").strip()
        description = args.description or input("角色描述: ").strip()
        
        # Get allowed actions
        print("\n允许的动作 (每行一个，空行结束):")
        allowed = []
        while True:
            action = input("  > ").strip()
            if not action:
                break
            allowed.append(action)
        
        # Get forbidden actions
        print("\n禁止的动作 (每行一个，空行结束):")
        forbidden = []
        while True:
            action = input("  > ").strip()
            if not action:
                break
            forbidden.append(action)
        
        # Create role entry
        new_role = {
            "id": role_id,
            "name": name,
            "description": description,
            "extends": None,
            "constraints": {
                "allowed_actions": allowed,
                "forbidden_actions": forbidden
            },
            "required_skills": [],
            "validation_rules": []
        }
        
        # Add to roles list
        if 'roles' not in data:
            data['roles'] = []
        data['roles'].append(new_role)
        
        # Save
        with open(roles_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        print(f"\n✅ 角色 '{role_id}' 已添加到 {roles_file}")
        
    except KeyboardInterrupt:
        print("\n\n❌ 已取消")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_add_stage(args):
    """Add a new stage interactively"""
    # ... existing implementation ...


def cmd_migrate_skills(args):
    """Migrate skill_library.yaml to Anthropic Skill.md format
    
    Note: This command is deprecated. The system now uses Skill.md files exclusively.
    skill_library.yaml files are no longer supported.
    """
    import subprocess
    from pathlib import Path
    
    print("⚠️  Warning: skill_library.yaml is deprecated. The system now uses Skill.md files exclusively.", file=sys.stderr)
    print("   This migration tool is provided for legacy support only.\n", file=sys.stderr)
    
    yaml_file = Path(args.yaml_file)
    output_dir = Path(args.output) if args.output else Path("skills")
    
    if not yaml_file.exists():
        print(f"❌ File not found: {yaml_file}", file=sys.stderr)
        sys.exit(1)
    
    # Run migration tool
    tool_path = Path(__file__).parent.parent / "tools" / "migrate_to_anthropic_skills.py"
    if not tool_path.exists():
        print(f"❌ Migration tool not found: {tool_path}", file=sys.stderr)
        sys.exit(1)
    
    cmd = [sys.executable, str(tool_path), str(yaml_file), "--output", str(output_dir)]
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print(f"\n✅ Migration complete! Update your config to use: {output_dir}")
    else:
        sys.exit(result.returncode)


def cmd_setup(args):
    """一键接入：自动设置项目，让用户可以直接使用角色"""
    workspace = Path(args.workspace or ".")
    print("=" * 60)
    print("🚀 一键接入 Multi-Role Skills Workflow")
    print("=" * 60)
    print(f"\n目标项目: {workspace.absolute()}\n")
    
    # 创建 .workflow 目录和 temp 子目录
    workflow_dir = workspace / ".workflow"
    workflow_dir.mkdir(exist_ok=True)
    temp_dir = workflow_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    
    # 检查是否已存在配置
    roles_file = workflow_dir / "role_schema.yaml"
    skills_dir = workflow_dir / "skills"
    
    if roles_file.exists() and skills_dir.exists():
        print("⚠️  项目已接入，配置已存在")
        print(f"   - 角色配置: {roles_file}")
        print(f"   - 技能目录: {skills_dir}")
        print("\n💡 如需重新接入，请先删除 .workflow/ 目录")
        return
    
    # 查找标准模板（优先使用 teams/standard-delivery）
    template_sources = [
        workspace / "teams" / "standard-delivery",  # 项目内团队配置
        Path(__file__).parent.parent / "teams" / "standard-delivery",  # 框架内置
        Path(__file__).parent / "templates" / "standard_agile",  # 内置模板
    ]
    
    template_dir = None
    for source in template_sources:
        if source.exists() and source.is_dir():
            template_dir = source
            break
    
    if not template_dir:
        print("❌ 错误: 未找到标准模板")
        print("   请确保项目包含 teams/standard-delivery/ 配置")
        sys.exit(1)
    
    print(f"✅ 使用模板: {template_dir.relative_to(workspace) if template_dir.is_relative_to(workspace) else template_dir}")
    
    # 复制角色配置
    import shutil
    template_roles = template_dir / "role_schema.yaml"
    if template_roles.exists():
        shutil.copy(template_roles, roles_file)
        print(f"  ✅ 已复制角色配置: {roles_file.name}")
    else:
        print(f"  ⚠️  警告: 模板中未找到 role_schema.yaml")
    
    # 复制技能目录
    template_skills = template_dir / "skills"
    if template_skills.exists() and template_skills.is_dir():
        if skills_dir.exists():
            shutil.rmtree(skills_dir)
        shutil.copytree(template_skills, skills_dir)
        skill_count = len(list(skills_dir.rglob("Skill.md")))
        print(f"  ✅ 已复制技能目录: {skill_count} 个技能")
    else:
        print(f"  ⚠️  警告: 模板中未找到 skills/ 目录")
    
    # 可选：复制 workflow_schema.yaml（如果存在）
    template_workflow = template_dir / "workflow_schema.yaml"
    workflow_file = workflow_dir / "workflow_schema.yaml"
    if template_workflow.exists() and not workflow_file.exists():
        shutil.copy(template_workflow, workflow_file)
        print(f"  ✅ 已复制工作流配置（可选）: {workflow_file.name}")
    
    # 生成项目上下文（简化版）
    from work_by_roles.core.engine import ProjectScanner
    print("\n🔍 正在扫描项目结构...")
    scanner = ProjectScanner(workspace)
    context = scanner.scan()
    
    context_file = workflow_dir / "project_context.yaml"
    with open(context_file, 'w', encoding='utf-8') as f:
        yaml.dump(context.to_dict(), f, default_flow_style=False, allow_unicode=True)
    print(f"  ✅ 已生成项目上下文: {context_file.name}")
    
    # 生成使用说明
    usage_file = workflow_dir / "USAGE.md"
    usage_content = """# 快速使用指南

## ✅ 接入完成！

项目已成功接入 Multi-Role Skills Workflow 框架。

## 🚀 立即开始使用

### 方式 1: 在 Cursor IDE 中使用（推荐）

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

### 方式 2: 命令行使用

```bash
# 使用产品分析师角色分析需求
workflow role-execute product_analyst "分析用户登录功能的需求"

# 使用系统架构师角色设计架构
workflow role-execute system_architect "设计微服务架构"

# 使用核心框架工程师实现功能
workflow role-execute core_framework_engineer "实现用户认证模块"

# 使用QA审查员进行质量检查
workflow role-execute qa_reviewer "检查代码质量和测试覆盖率"
```

### 方式 3: 使用工作流（可选，适合大型项目）

```bash
# 查看可用角色
workflow list-roles

# 查看可用技能
workflow list-skills

# 启动工作流（如果配置了 workflow_schema.yaml）
workflow wfauto
```

## 📋 可用角色

运行 `workflow list-roles` 查看所有可用角色及其技能。

## 🛠️ 可用技能

运行 `workflow list-skills` 查看所有可用技能。

## 💡 提示

- **在 Cursor 中使用**: 使用 `@角色名` 或 `@team` 来让 AI 自动使用对应的角色和技能
- **自定义技能**: 使用 `workflow generate-skill` 创建新技能
- **自定义角色**: 编辑 `.workflow/role_schema.yaml` 添加新角色

## 📚 更多信息

查看项目文档了解更多功能：
- `README.md` - 完整文档
- `docs/CURSOR_GUIDE.md` - Cursor IDE 使用指南
- `docs/SKILLS_GUIDE.md` - 技能使用指南
- `docs/USAGE_GUIDE.md` - 使用指南
"""
    usage_file.write_text(usage_content, encoding='utf-8')
    print(f"  ✅ 已生成使用说明: {usage_file.name}")
    
    # 生成 Cursor 配置文件（仅当在 Cursor IDE 中时）
    from work_by_roles.cli import generate_cursorrules
    if generate_cursorrules(workspace):
        print(f"  ✅ 已生成 Cursor IDE 配置文件（.cursorrules，包含自动执行规则）")
    else:
        print(f"  ℹ️  未检测到 Cursor IDE 环境，跳过配置文件生成")
    
    # 显示完成信息
    print("\n" + "=" * 60)
    print("✅ 接入完成！")
    print("=" * 60)
    print("\n📋 下一步:")
    print("  1. 查看可用角色: workflow list-roles")
    print("  2. 查看可用技能: workflow list-skills")
    print("  3. 使用角色执行任务:")
    print("     workflow role-execute <role_id> \"<requirement>\"")
    print("\n💡 示例:")
    print("   workflow role-execute product_analyst \"分析用户需求\"")
    print("   workflow role-execute system_architect \"设计系统架构\"")
    print(f"\n📖 详细使用说明: {usage_file}")
    print("=" * 60)


def cmd_role_execute(args):
    """
    使用指定角色处理需求（简化模式，无需workflow）
    
    这是重构后的简化接口，适用于IDE环境（如Cursor）。
    用户指定角色和需求，角色使用skills来处理并返回结果。
    """
    if not _agents_available:
        print("❌ Agent 系统未可用，请确保已安装完整包", file=sys.stderr)
        sys.exit(1)
    
    try:
        engine, _, _ = _init_engine(args)
        workspace = Path(args.workspace or ".")
        
        # 获取角色信息（在执行前）
        role = engine.role_manager.get_role(args.role_id)
        if not role:
            print(f"❌ 角色 '{args.role_id}' 未找到", file=sys.stderr)
            sys.exit(1)
        
        # 获取执行模式信息
        execution_mode_info = None
        if engine.role_manager.skill_library:
            execution_mode_info = ExecutionModeAnalyzer.get_execution_mode_info(
                role=role,
                skill_library=engine.role_manager.skill_library,
                environment="cursor"
            )
        
        # 加载 LLM 客户端
        llm_client = _load_llm_client(workspace)
        
        # 如果使用 --use-llm 但未配置 LLM 客户端，抛出错误
        if args.use_llm and not llm_client:
            error_msg = (
                "❌ LLM client not configured. Please:\n"
                "  1. Set environment variable (e.g., OPENAI_API_KEY or ANTHROPIC_API_KEY)\n"
                "  2. Or create .workflow/config.yaml with llm configuration\n"
                "  3. Or remove --use-llm flag to use lightweight mode\n"
                "\n"
                "Example environment variables:\n"
                "  export OPENAI_API_KEY='your-api-key'\n"
                "  export ANTHROPIC_API_KEY='your-api-key'\n"
                "\n"
                "Example config file (.workflow/config.yaml):\n"
                "  llm:\n"
                "    provider: openai\n"
                "    api_key: your-api-key\n"
                "    model: gpt-4\n"
                "    base_url: https://api.openai.com/v1  # 可选，用于自定义端点"
            )
            print(error_msg, file=sys.stderr)
            raise WorkflowError("LLM client not configured but --use-llm flag is set")
        
        # 解析输入数据
        inputs = {}
        if args.inputs:
            try:
                inputs = json.loads(args.inputs)
            except json.JSONDecodeError as e:
                print(f"❌ 输入数据JSON格式错误: {e}", file=sys.stderr)
                sys.exit(1)
        
        # 创建沉浸式显示（如果支持）
        immersive_display = None
        try:
            from .core.immersive_workflow_display import ImmersiveWorkflowDisplay
            immersive_display = ImmersiveWorkflowDisplay(workspace, use_streaming=True)
        except Exception:
            # 如果沉浸式显示不可用，继续使用普通模式
            pass
        
        # 显示醒目的角色信息横幅（普通模式）
        if not immersive_display:
            print("\n" + "=" * 70)
            print("🎭 角色执行模式".center(70))
            print("=" * 70)
            print(f"\n👤 角色: {role.name} ({args.role_id})")
            print(f"📝 描述: {role.description}")
            
            if execution_mode_info:
                mode_icons = {
                    'analysis': '📊',
                    'implementation': '💻',
                    'validation': '✅'
                }
                mode_names = {
                    'analysis': '分析模式',
                    'implementation': '实现模式',
                    'validation': '验证模式'
                }
                icon = mode_icons.get(execution_mode_info['mode'], '🔧')
                mode_name = mode_names.get(execution_mode_info['mode'], execution_mode_info['mode'])
                print(f"{icon} 执行模式: {mode_name}")
                
                if execution_mode_info.get('tools'):
                    print(f"🛠️  可用工具: {', '.join(execution_mode_info['tools'][:5])}")
                    if len(execution_mode_info['tools']) > 5:
                        print(f"   ... 还有 {len(execution_mode_info['tools']) - 5} 个工具")
            
            print(f"\n📋 任务需求: {args.requirement}")
            print(f"🤖 LLM模式: {'启用' if args.use_llm else '禁用（轻量模式）'}")
            if inputs:
                print(f"📥 输入数据: {len(inputs)} 项")
            
            print("\n" + "-" * 70)
            print("🚀 开始执行...")
            print("-" * 70 + "\n")
        
        # 创建RoleExecutor
        role_executor = RoleExecutor(engine, llm_client=llm_client)
        
        # 执行角色（传入沉浸式显示）
        result = role_executor.execute_role(
            role_id=args.role_id,
            requirement=args.requirement,
            inputs=inputs,
            use_llm=args.use_llm,
            immersive_display=immersive_display
        )
        
        # 显示结果（如果使用沉浸式显示，大部分信息已经在流式输出中显示）
        if not immersive_display:
            print("\n" + "=" * 70)
            print(f"📊 {role.name} 执行结果".center(70))
            print("=" * 70)
            print(f"\n✅ 执行的技能: {', '.join(result['skills_executed'])}")
            
            # 显示技能执行结果（带角色标识）
            print(f"\n🔧 {role.name} 的技能执行详情:")
            for skill_result in result['skill_results']:
                skill_id = skill_result['skill_id']
                if 'result' in skill_result:
                    if skill_result['result'].get('success'):
                        print(f"  ✅ [{role.name}] {skill_id}: 执行成功")
                    else:
                        print(f"  ❌ [{role.name}] {skill_id}: 执行失败")
                        if skill_result['result'].get('error'):
                            print(f"     错误: {skill_result['result']['error']}")
                elif 'error' in skill_result:
                    print(f"  ❌ [{role.name}] {skill_id}: 错误 - {skill_result['error']}")
            
            # 显示最终响应（以角色身份呈现）
            print(f"\n💬 {role.name} 的响应:")
            print("-" * 70)
            # 添加角色标识前缀
            response_with_role = f"[{role.name}] {result['response']}"
            print(response_with_role)
            print("-" * 70)
            
            # 如果使用LLM，显示提示
            if args.use_llm:
                print(f"\n💡 提示: {role.name} 已使用LLM生成响应")
            else:
                print(f"\n💡 提示: 当前为轻量模式，使用 --use-llm 让 {role.name} 生成更详细的响应")
        else:
            # 即使使用沉浸式显示，也要显示最终响应
            if result.get('response'):
                print("\n" + "=" * 70)
                print(f"💬 {role.name} 的响应:")
                print("-" * 70)
                response_with_role = f"[{role.name}] {result['response']}"
                print(response_with_role)
                print("-" * 70)
        
        return result
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
def cmd_agent_execute(args):
    """使用 Agent 执行工作流阶段（类似 MetaGPT）"""
    if not _agents_available:
        print("❌ Agent 系统未可用，请确保已安装完整包", file=sys.stderr)
        sys.exit(1)
    
    try:
        engine, _, _ = _init_engine(args)
        workspace = Path(args.workspace or ".")
        
        # 加载 LLM 客户端
        llm_client = _load_llm_client(workspace)
        
        # 确定是否使用LLM
        use_llm = getattr(args, 'use_llm', False) and not getattr(args, 'no_llm', False)
        
        # 如果使用 --use-llm 但未配置 LLM 客户端，抛出错误
        if use_llm and not llm_client:
            error_msg = (
                "❌ LLM client not configured. Please:\n"
                "  1. Set environment variable (e.g., OPENAI_API_KEY or ANTHROPIC_API_KEY)\n"
                "  2. Or create .workflow/config.yaml with llm configuration\n"
                "  3. Or remove --use-llm flag to use lightweight mode\n"
                "\n"
                "Example environment variables:\n"
                "  export OPENAI_API_KEY='your-api-key'\n"
                "  export ANTHROPIC_API_KEY='your-api-key'\n"
                "\n"
                "Example config file (.workflow/config.yaml):\n"
                "  llm:\n"
                "    provider: openai\n"
                "    api_key: your-api-key\n"
                "    model: gpt-4\n"
                "    base_url: https://api.openai.com/v1  # 可选，用于自定义端点"
            )
            print(error_msg, file=sys.stderr)
            raise WorkflowError("LLM client not configured but --use-llm flag is set")
        
        orchestrator = AgentOrchestrator(engine, llm_client=llm_client)
        
        stage_id = args.stage
        if not stage_id:
            # Auto-infer next stage
            current = engine.get_current_stage()
            completed = engine.executor.get_completed_stages() if engine.executor else set()
            
            if not completed:
                first_stage = min(engine.workflow.stages, key=lambda s: s.order)
                stage_id = first_stage.id
            else:
                for stage in sorted(engine.workflow.stages, key=lambda s: s.order):
                    if stage.id not in completed:
                        can_transition, _ = engine.executor.can_transition_to(stage.id)
                        if can_transition:
                            stage_id = stage.id
                            break
        
        if not stage_id:
            print("✅ 所有阶段已完成！")
            sys.exit(0)
        
        # 确保阶段已启动
        stage = engine.executor._get_stage_by_id(stage_id)
        if not stage:
            print(f"❌ 阶段 '{stage_id}' 不存在", file=sys.stderr)
            sys.exit(1)
        
        # 启动阶段（如果未启动）
        current = engine.get_current_stage()
        if not current or current.id != stage_id:
            engine.start_stage(stage_id, stage.role)
        
        collaborate = getattr(args, 'collaborate', False)
        
        print(f"\n🤖 Agent 执行模式 - {stage.name}")
        print("=" * 60)
        print(f"阶段: {stage.name} ({stage_id})")
        print(f"Agent: {stage.role}")
        print(f"模式: {'LLM执行' if use_llm else '约束检查（轻量模式）'}")
        if collaborate:
            print(f"协作模式: 已启用（Agent 间消息传递和反馈）")
        
        # 执行阶段
        result = orchestrator.execute_stage(stage_id, use_llm=use_llm)
        
        # 如果启用协作模式，检查消息
        if collaborate and result.get("agent"):
            agent = result["agent"]
            messages = agent.check_messages()
            if messages:
                print(f"\n📨 收到 {len(messages)} 条来自其他 Agent 的消息")
                for msg in messages[:3]:  # 只显示前3条
                    print(f"  - 来自 {msg.from_agent}: {msg.message_type}")
                if len(messages) > 3:
                    print(f"  ... 还有 {len(messages) - 3} 条消息")
        agent = result["agent"]
        context = result["context"]
        
        if use_llm and result.get("llm_used", False):
            print(f"\n✅ Agent '{agent.role.name}' 已准备就绪（LLM模式）")
            if "prompt" in result:
                print(f"📝 已生成LLM提示（{len(result['prompt'])} 字符）")
        else:
            print(f"\n✅ 约束检查完成 - Agent '{agent.role.name}'")
            if result.get("can_start", True):
                print("✅ 阶段可以启动")
            else:
                print("❌ 阶段无法启动:")
                for error in result.get("errors", []):
                    print(f"   - {error}")
        
        print(f"📥 输入上下文: {len(context.inputs)} 项")
        
        # 显示可用操作
        print("\n💡 Agent 可用操作:")
        allowed = agent.role.constraints.get('allowed_actions', [])
        for action in allowed[:5]:
            print(f"  - {action}")
        if len(allowed) > 5:
            print(f"  ... 还有 {len(allowed) - 5} 个")
        
        if not use_llm:
            print("\n💡 提示:")
            print("  - 当前为轻量模式（无LLM调用）")
            print("  - 使用 --use-llm 启用LLM执行（需要配置llm_client）")
            print("  - 使用 Python API 调用 agent 的方法:")
            print("    agent.make_decision('...')")
            print("    agent.produce_output('file.md', content)")
        else:
            print("\n📝 提示:")
            print("  - 使用 Python API 调用 agent 的方法:")
            print("    agent.make_decision('...')")
            print("    agent.produce_output('file.md', content)")
            print("    agent.review('item', 'feedback')")
        print("  - 完成后运行: workflow agent-complete " + stage_id)
        
        return result
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        # traceback.print_exc()
        sys.exit(1)


def cmd_agent_complete(args):
    """完成 Agent 执行的任务"""
    if not _agents_available:
        print("❌ Agent 系统未可用", file=sys.stderr)
        sys.exit(1)
    
    try:
        engine, _, _ = _init_engine(args)
        orchestrator = AgentOrchestrator(engine)
        
        stage_id = args.stage
        if not stage_id:
            current = engine.get_current_stage()
            if current:
                stage_id = current.id
            else:
                print("❌ 没有活动阶段", file=sys.stderr)
                sys.exit(1)
        
        print(f"\n🤖 完成 Agent 任务 - {stage_id}")
        print("=" * 60)
        
        result = orchestrator.complete_stage(stage_id)
        
        if result["quality_gates_passed"]:
            print("✅ 阶段完成")
            # print(f"📊 输出文件: {len(result['result']['outputs'])} 个")
            # print(f"💭 决策记录: {len(result['result']['decisions'])} 条")
        else:
            print("❌ 质量门禁未通过:")
            for error in result["errors"]:
                print(f"  - {error}")
            sys.exit(1)
        
        # 显示执行摘要
        summary = orchestrator.get_execution_summary()
        print(f"\n📈 执行摘要:")
        print(f"  - 已完成阶段: {summary['total_stages_executed']}")
        print(f"  - 使用的 Agents: {', '.join(summary['agents_used'])}")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_team_collaborate(args):
    """启动多 Agent 协作模式执行任务"""
    if not _agents_available:
        print("❌ Agent 系统未可用，请确保已安装完整包", file=sys.stderr)
        sys.exit(1)
    
    try:
        engine, _, _ = _init_engine(args)
        workspace = Path(args.workspace or ".")
        
        goal = args.goal
        role_ids = getattr(args, 'roles', None)
        use_llm = getattr(args, 'use_llm', False)
        
        # 加载 LLM 客户端
        llm_client = _load_llm_client(workspace)
        
        # 如果使用 --use-llm 但未配置 LLM 客户端，抛出错误
        if use_llm and not llm_client:
            error_msg = (
                "❌ LLM client not configured. Please:\n"
                "  1. Set environment variable (e.g., OPENAI_API_KEY or ANTHROPIC_API_KEY)\n"
                "  2. Or create .workflow/config.yaml with llm configuration\n"
                "  3. Or remove --use-llm flag to use rule-based decomposition\n"
                "\n"
                "Example environment variables:\n"
                "  export OPENAI_API_KEY='your-api-key'\n"
                "  export ANTHROPIC_API_KEY='your-api-key'\n"
                "\n"
                "Example config file (.workflow/config.yaml):\n"
                "  llm:\n"
                "    provider: openai\n"
                "    api_key: your-api-key\n"
                "    model: gpt-4\n"
                "    base_url: https://api.openai.com/v1  # 可选，用于自定义端点"
            )
            print(error_msg, file=sys.stderr)
            raise WorkflowError("LLM client not configured but --use-llm flag is set")
        
        orchestrator = AgentOrchestrator(engine, llm_client=llm_client)
        
        print(f"\n🤝 多 Agent 协作模式")
        print("=" * 60)
        print(f"目标: {goal}")
        if role_ids:
            print(f"参与角色: {', '.join(role_ids)}")
        else:
            print(f"参与角色: 所有可用角色")
        print(f"任务分解: {'LLM智能分解' if use_llm else '规则引擎分解'}")
        print()
        
        # 执行协作
        result = orchestrator.execute_with_collaboration(
            goal=goal,
            role_ids=role_ids,
            inputs=None,
            use_llm=use_llm
        )
        
        # 显示结果
        print("\n✅ 协作执行完成")
        print("=" * 60)
        
        decomposition = result["decomposition"]
        print(f"\n📋 任务分解:")
        print(f"  - 总任务数: {len(decomposition.tasks)}")
        print(f"  - 执行顺序: {' → '.join(decomposition.execution_order)}")
        
        print(f"\n👥 参与的 Agents:")
        for agent_id, agent_info in result["agents"].items():
            print(f"  - {agent_info['role']} ({agent_id})")
        
        summary = result["collaboration_summary"]
        print(f"\n📊 执行摘要:")
        print(f"  - 完成任务: {summary['completed_tasks']}/{summary['total_tasks']}")
        print(f"  - 失败任务: {summary['failed_tasks']}")
        print(f"  - 活跃 Agents: {len(summary['active_agents'])}")
        
        # 显示任务结果
        if result["task_results"]:
            print(f"\n📝 任务结果:")
            for task_id, task_result in result["task_results"].items():
                status_icon = "✅" if task_result["status"] == "completed" else "❌"
                print(f"  {status_icon} {task_id}: {task_result['status']}")
                if task_result.get("error"):
                    print(f"     错误: {task_result['error']}")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_decompose_task(args):
    """分解目标为子任务"""
    if not _agents_available:
        print("❌ Agent 系统未可用，请确保已安装完整包", file=sys.stderr)
        sys.exit(1)
    
    try:
        engine, _, _ = _init_engine(args)
        workspace = Path(args.workspace or ".")
        from work_by_roles.core.task_decomposer import TaskDecomposer
        
        goal = args.goal
        role_ids = getattr(args, 'roles', None)
        use_llm = getattr(args, 'use_llm', False)
        output_json = getattr(args, 'json', False)
        
        # 加载 LLM 客户端
        llm_client = _load_llm_client(workspace)
        
        # 如果使用 --use-llm 但未配置 LLM 客户端，抛出错误
        if use_llm and not llm_client:
            error_msg = (
                "❌ LLM client not configured. Please:\n"
                "  1. Set environment variable (e.g., OPENAI_API_KEY or ANTHROPIC_API_KEY)\n"
                "  2. Or create .workflow/config.yaml with llm configuration\n"
                "  3. Or remove --use-llm flag to use rule-based decomposition\n"
                "\n"
                "Example environment variables:\n"
                "  export OPENAI_API_KEY='your-api-key'\n"
                "  export ANTHROPIC_API_KEY='your-api-key'\n"
                "\n"
                "Example config file (.workflow/config.yaml):\n"
                "  llm:\n"
                "    provider: openai\n"
                "    api_key: your-api-key\n"
                "    model: gpt-4\n"
                "    base_url: https://api.openai.com/v1  # 可选，用于自定义端点"
            )
            print(error_msg, file=sys.stderr)
            raise WorkflowError("LLM client not configured but --use-llm flag is set")
        
        # Get available roles
        if role_ids:
            available_roles = [
                engine.role_manager.get_role(role_id)
                for role_id in role_ids
                if engine.role_manager.get_role(role_id)
            ]
        else:
            available_roles = list(engine.role_manager.roles.values())
        
        # Create decomposer
        decomposer = TaskDecomposer(engine, llm_client)
        
        # Decompose
        decomposition = decomposer.decompose(goal, available_roles, None)
        
        if output_json:
            import json
            output = {
                "goal": goal,
                "tasks": [
                    {
                        "id": task.id,
                        "description": task.description,
                        "assigned_role": task.assigned_role,
                        "dependencies": task.dependencies,
                        "status": task.status,
                        "priority": task.priority
                    }
                    for task in decomposition.tasks
                ],
                "execution_order": decomposition.execution_order,
                "dependencies": decomposition.dependencies
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print(f"\n📋 任务分解结果")
            print("=" * 60)
            print(f"目标: {goal}")
            print(f"\n任务列表 ({len(decomposition.tasks)} 个):")
            
            for i, task in enumerate(decomposition.tasks, 1):
                deps_str = f" (依赖: {', '.join(task.dependencies)})" if task.dependencies else ""
                print(f"\n{i}. {task.id}")
                print(f"   描述: {task.description}")
                print(f"   角色: {task.assigned_role}")
                print(f"   状态: {task.status}{deps_str}")
                if task.priority > 0:
                    print(f"   优先级: {task.priority}")
            
            print(f"\n执行顺序:")
            print(f"  {' → '.join(decomposition.execution_order)}")
            
            if decomposition.total_estimated_time:
                print(f"\n预计总时间: {decomposition.total_estimated_time:.1f} 秒")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_generate_skill(args):
    """Generate a skill template"""
    try:
        from tools.generate_skill_template import build_skill_template, write_template

        output_file = Path(args.output) if args.output else Path(f"{args.skill_id}_skill.yaml")
        
        template = build_skill_template(
            args.skill_id,
            args.name
        )
        
        write_template(template, output_file)
        print(f"✅ 技能模板已生成: {output_file}")
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_validate_skills(args):
    """Validate a skill library definition"""
    try:
        from tools.validate_skills import run_validation

        skill_file = Path(args.file)

        if not skill_file.exists():
            print(f"❌ 文件不存在: {skill_file}", file=sys.stderr)
            sys.exit(1)

        success, errors = run_validation(skill_file, quiet=args.quiet)
        if not success:
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list_skills(args):
    """List all loaded skills"""
    try:
        engine, _, _ = _init_engine(args)

        if not engine.role_manager.skill_library:
            print("⚠️ 未加载技能库，请使用 --skills 指定 skills 目录")
            sys.exit(0)

        print("\n技能库列表:")
        print("=" * 60)
        for skill_id, skill in engine.role_manager.skill_library.items():
            print(f"\n技能: {skill.name}")
            print(f"  ID: {skill_id}")
            print(f"  描述: {skill.description}")
            print(f"  维度: {', '.join(skill.dimensions)}")
            print(f"  工具: {', '.join(skill.tools)}")
            print(f"  等级数: {len(skill.levels)}")
            if skill.constraints:
                print(f"  约束: {', '.join(skill.constraints)}")

        if hasattr(engine.role_manager, 'skill_bundles') and engine.role_manager.skill_bundles:
            print("\n技能包 (Bundles):")
            print("-" * 60)
            for bundle_id, bundle in engine.role_manager.skill_bundles.items():
                print(f"\n技能包: {bundle.name}")
                print(f"  ID: {bundle_id}")
                print(f"  描述: {bundle.description}")
                print(f"  包含技能:")
                for s in bundle.skills:
                    print(f"    - {s.skill_id} (等级≥{s.min_level})")

    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_interactive_skill(args):
    """Interactive skill wizard"""
    try:
        from tools.interactive_skill_creator import interactive_main

        interactive_main()
    except KeyboardInterrupt:
        print("\n\n❌ 已取消")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_skill_trace(args):
    """View skill execution history"""
    try:
        engine, _, _ = _init_engine(args)
        
        if not hasattr(engine, 'create_orchestrator'):
            # Create orchestrator if not available
            from work_by_roles.core.engine import AgentOrchestrator
            orchestrator = AgentOrchestrator(engine)
        else:
            orchestrator = engine.create_orchestrator()
        
        skill_id = args.skill_id
        history = orchestrator.execution_tracker.get_skill_history(skill_id)
        
        if not history:
            print(f"⚠️ 技能 '{skill_id}' 没有执行历史")
            sys.exit(0)
        
        print(f"\n技能执行历史: {skill_id}")
        print("=" * 60)
        for i, execution in enumerate(history, 1):
            print(f"\n执行 #{i}:")
            print(f"  状态: {execution.status}")
            print(f"  执行时间: {execution.execution_time:.2f}s")
            print(f"  时间戳: {execution.timestamp}")
            if execution.retry_count > 0:
                print(f"  重试次数: {execution.retry_count}")
            if execution.error_type:
                print(f"  错误类型: {execution.error_type}")
            if execution.error_message:
                print(f"  错误消息: {execution.error_message}")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_skill_stats(args):
    """View skill execution statistics"""
    try:
        engine, _, _ = _init_engine(args)
        
        if not hasattr(engine, 'create_orchestrator'):
            from work_by_roles.core.engine import AgentOrchestrator
            orchestrator = AgentOrchestrator(engine)
        else:
            orchestrator = engine.create_orchestrator()
        
        stats = orchestrator.execution_tracker.get_statistics()
        
        print("\n技能执行统计")
        print("=" * 60)
        print(f"总执行次数: {stats['total_executions']}")
        print(f"唯一技能数: {stats['unique_skills']}")
        print("\n各技能统计:")
        print("-" * 60)
        
        for skill_id, skill_stats in stats['skills'].items():
            print(f"\n{skill_id}:")
            print(f"  总执行次数: {skill_stats['total_executions']}")
            print(f"  成功率: {skill_stats['success_rate']:.2%}")
            print(f"  平均执行时间: {skill_stats['avg_execution_time']:.2f}s")
            print(f"  总重试次数: {skill_stats['total_retries']}")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_export_trace(args):
    """Export execution trace data"""
    try:
        engine, _, _ = _init_engine(args)
        
        if not hasattr(engine, 'create_orchestrator'):
            from work_by_roles.core.engine import AgentOrchestrator
            orchestrator = AgentOrchestrator(engine)
        else:
            orchestrator = engine.create_orchestrator()
        
        format_type = args.format or "json"
        trace_data = orchestrator.execution_tracker.export_trace(format_type)
        
        if args.output:
            output_file = Path(args.output)
            output_file.write_text(trace_data, encoding='utf-8')
            print(f"✅ 追踪数据已导出到: {output_file}")
        else:
            print(trace_data)
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_benchmark_skill(args):
    """Benchmark a skill with test cases"""
    try:
        engine, _, _ = _init_engine(args)
        
        if not hasattr(engine, 'create_orchestrator'):
            from work_by_roles.core.engine import AgentOrchestrator, SkillBenchmark
            orchestrator = AgentOrchestrator(engine)
        else:
            orchestrator = engine.create_orchestrator()
            from work_by_roles.core.engine import SkillBenchmark
        
        benchmark = SkillBenchmark(engine, orchestrator)
        
        # Load test cases
        test_cases_file = Path(args.test_cases)
        if not test_cases_file.exists():
            print(f"❌ 测试用例文件不存在: {test_cases_file}", file=sys.stderr)
            sys.exit(1)
        
        import yaml
        with test_cases_file.open('r', encoding='utf-8') as f:
            test_data = yaml.safe_load(f)
        
        test_cases = test_data.get('test_cases', [])
        if not test_cases:
            print("⚠️ 测试用例文件为空", file=sys.stderr)
            sys.exit(1)
        
        # Check if multi-model comparison requested (P2 optimization)
        if args.models:
            from work_by_roles.core.skill_benchmark import SkillBenchmark
            benchmark = SkillBenchmark(engine, orchestrator)
            results = benchmark.benchmark_with_models(args.skill_id, args.models, test_cases)
            print(f"\n多模型基准测试结果: {args.skill_id}")
            print("=" * 60)
            for model_name, model_results in results['models'].items():
                if 'error' in model_results:
                    print(f"{model_name}: ❌ {model_results['error']}")
                else:
                    print(f"{model_name}:")
                    print(f"  成功率: {model_results['success_rate']:.2%}")
                    print(f"  平均执行时间: {model_results['avg_execution_time']:.2f}s")
            if results['best_model']:
                print(f"\n最佳模型: {results['best_model']}")
        else:
            results = benchmark.benchmark_skill(args.skill_id, test_cases)
            
            if args.report:
                report = benchmark.generate_report(results)
                print(report)
            else:
                print(f"\n基准测试结果: {args.skill_id}")
                print("=" * 60)
                print(f"总测试数: {results['total_tests']}")
                print(f"成功测试数: {results['successful_tests']}")
                print(f"成功率: {results['success_rate']:.2%}")
                print(f"平均执行时间: {results['avg_execution_time']:.2f}s")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_skill_test(args):
    """Test a skill with input and expected output/schema"""
    try:
        engine, _, _ = _init_engine(args)
        
        if not hasattr(engine, 'create_orchestrator'):
            from work_by_roles.core.agent_orchestrator import AgentOrchestrator
            from work_by_roles.core.skill_benchmark import SkillBenchmark
            orchestrator = AgentOrchestrator(engine)
        else:
            orchestrator = engine.create_orchestrator()
            from work_by_roles.core.skill_benchmark import SkillBenchmark
        
        benchmark = SkillBenchmark(engine, orchestrator)
        
        # Load input data
        input_data = {}
        if args.input:
            input_file = Path(args.input)
            if input_file.exists():
                import json
                import yaml
                with input_file.open('r', encoding='utf-8') as f:
                    if input_file.suffix in ['.yaml', '.yml']:
                        input_data = yaml.safe_load(f) or {}
                    else:
                        input_data = json.load(f)
            else:
                print(f"⚠️ 输入文件不存在: {input_file}", file=sys.stderr)
        
        # Load expected output if provided
        expected_output = None
        if args.expect:
            expect_file = Path(args.expect)
            if expect_file.exists():
                import json
                import yaml
                with expect_file.open('r', encoding='utf-8') as f:
                    if expect_file.suffix in ['.yaml', '.yml']:
                        expected_output = yaml.safe_load(f)
                    else:
                        expected_output = json.load(f)
            else:
                print(f"⚠️ 期望输出文件不存在: {expect_file}", file=sys.stderr)
        
        # Load expected schema if provided
        expected_schema = None
        if args.schema:
            schema_file = Path(args.schema)
            if schema_file.exists():
                import json
                import yaml
                with schema_file.open('r', encoding='utf-8') as f:
                    if schema_file.suffix in ['.yaml', '.yml']:
                        expected_schema = yaml.safe_load(f)
                    else:
                        expected_schema = json.load(f)
            else:
                print(f"⚠️ Schema 文件不存在: {schema_file}", file=sys.stderr)
        
        # Determine snapshot file path
        snapshot_file = None
        if args.snapshot:
            snapshot_file = Path(args.snapshot)
        
        # Run test
        result = benchmark.test_skill(
            args.skill_id,
            input_data,
            expected_output,
            expected_schema,
            snapshot_file
        )
        
        # Print results
        print(f"\n技能测试结果: {args.skill_id}")
        print("=" * 60)
        print(f"执行成功: {'✅' if result['success'] else '❌'}")
        print(f"执行时间: {result['execution_time']:.2f}s")
        
        if 'error' in result:
            print(f"错误: {result['error']}")
        
        validation = result.get('validation', {})
        if validation:
            print(f"\n验证结果:")
            print(f"  整体有效: {'✅' if validation['valid'] else '❌'}")
            if 'snapshot_match' in validation:
                print(f"  Snapshot 匹配: {'✅' if validation['snapshot_match'] else '❌'}")
            if 'schema_valid' in validation:
                print(f"  Schema 验证: {'✅' if validation['schema_valid'] else '❌'}")
            
            if validation.get('differences'):
                print(f"\n差异:")
                for diff in validation['differences']:
                    print(f"  - {diff}")
            
            if validation.get('schema_errors'):
                print(f"\nSchema 错误:")
                for error in validation['schema_errors']:
                    print(f"  - {error}")
        
        if result.get('snapshot_saved'):
            print(f"\n✅ Snapshot 已保存到: {snapshot_file}")
        
        if not result['success']:
            sys.exit(1)
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_replay_workflow(args):
    """Replay workflow from event log"""
    try:
        engine, _, _ = _init_engine(args)
        
        if not engine.executor:
            print("❌ 工作流未初始化", file=sys.stderr)
            sys.exit(1)
        
        # Load event log
        event_log_file = Path(args.event_log)
        if not event_log_file.exists():
            print(f"❌ 事件日志文件不存在: {event_log_file}", file=sys.stderr)
            sys.exit(1)
        
        from work_by_roles.core.workflow_events import WorkflowEvent
        import json
        import yaml
        
        with event_log_file.open('r', encoding='utf-8') as f:
            if event_log_file.suffix in ['.yaml', '.yml']:
                events_data = yaml.safe_load(f)
            else:
                events_data = json.load(f)
        
        events = [WorkflowEvent.from_dict(e) for e in events_data]
        
        # Replay events
        engine.executor.replay_from_events(events)
        
        print(f"✅ 已回放 {len(events)} 个事件")
        print(f"当前阶段: {engine.executor.state.current_stage}")
        print(f"已完成阶段: {', '.join(engine.executor.state.completed_stages)}")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_dry_run_stage(args):
    """Dry-run a stage without executing skills"""
    try:
        engine, _, _ = _init_engine(args)
        
        if not engine.executor:
            print("❌ 工作流未初始化", file=sys.stderr)
            sys.exit(1)
        
        result = engine.executor.dry_run(args.stage_id)
        
        print(f"\n阶段干运行结果: {result['stage_name']}")
        print("=" * 60)
        print(f"可以转换: {'✅' if result['can_transition'] else '❌'}")
        print(f"前提条件满足: {'✅' if result['prerequisites_met'] else '❌'}")
        
        if result['errors']:
            print(f"\n错误:")
            for error in result['errors']:
                print(f"  - {error}")
        
        print(f"\n当前状态:")
        print(f"  当前阶段: {result['current_state']['current_stage'] or 'None'}")
        print(f"  已完成阶段: {', '.join(result['current_state']['completed_stages']) or 'None'}")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_import_sop(args):
    """Import SOP document and generate configurations"""
    try:
        from work_by_roles.core.sop_importer import SOPImporter
        
        sop_file = Path(args.sop_file)
        if not sop_file.exists():
            print(f"❌ SOP 文件不存在: {sop_file}", file=sys.stderr)
            sys.exit(1)
        
        output_dir = Path(args.output) if args.output else Path.cwd() / ".workflow"
        
        importer = SOPImporter()
        generated_files = importer.generate_config_files(
            sop_file,
            output_dir,
            overwrite=args.overwrite
        )
        
        print(f"\n✅ SOP 导入完成")
        print("=" * 60)
        for config_type, file_path in generated_files.items():
            print(f"  {config_type}: {file_path}")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ============================================================================
# Skill Workflow Commands - 多技能工作流命令
# ============================================================================

def cmd_list_skill_workflows(args):
    """列出所有技能工作流"""
    try:
        engine, _, _ = _init_engine(args)
        orchestrator = AgentOrchestrator(engine)
        
        workflows = orchestrator.list_skill_workflows()
        
        if not workflows:
            print("⚠️ 未定义任何技能工作流")
            print("   在 skills 目录中的 Skill.md 文件中添加 skill_workflows 部分")
            sys.exit(0)
        
        print("\n技能工作流列表:")
        print("=" * 60)
        
        for wf in workflows:
            print(f"\n📋 {wf['name']} (ID: {wf['id']})")
            print(f"   描述: {wf['description']}")
            print(f"   步骤数: {wf['steps']}")
            trigger = wf['trigger']
            if trigger['stage_id']:
                print(f"   触发: 阶段 '{trigger['stage_id']}' ({trigger['condition']})")
            else:
                print(f"   触发: {trigger['condition']}")
        
        print("\n" + "=" * 60)
        print("💡 使用 'workflow skill-workflow-detail <id>' 查看详情")
        print("💡 使用 'workflow run-skill-workflow <id>' 执行工作流")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_skill_workflow_detail(args):
    """显示技能工作流详情"""
    try:
        engine, _, _ = _init_engine(args)
        orchestrator = AgentOrchestrator(engine)
        
        workflow_id = args.workflow_id
        details = orchestrator.get_workflow_details(workflow_id)
        
        if not details:
            print(f"❌ 工作流 '{workflow_id}' 不存在", file=sys.stderr)
            sys.exit(1)
        
        print(f"\n📋 技能工作流详情: {details['name']}")
        print("=" * 60)
        print(f"ID: {details['id']}")
        print(f"描述: {details['description']}")
        
        # Trigger
        trigger = details['trigger']
        print(f"\n触发条件:")
        print(f"  - 触发方式: {trigger['condition']}")
        if trigger['stage_id']:
            print(f"  - 触发阶段: {trigger['stage_id']}")
        
        # Config
        config = details['config']
        print(f"\n配置:")
        print(f"  - 最大并行: {config['max_parallel']}")
        print(f"  - 快速失败: {'是' if config['fail_fast'] else '否'}")
        print(f"  - 重试失败步骤: {'是' if config['retry_failed_steps'] else '否'}")
        print(f"  - 超时: {config['timeout']}秒")
        
        # Steps
        print(f"\n步骤 ({len(details['steps'])} 个):")
        print("-" * 60)
        for step in details['steps']:
            deps = f" [依赖: {', '.join(step['depends_on'])}]" if step['depends_on'] else ""
            print(f"\n  {step['order']}. {step['name']} (ID: {step['step_id']}){deps}")
            print(f"     技能: {step['skill_id']}")
            if step['inputs']:
                print(f"     输入: {list(step['inputs'].keys())}")
            if step['outputs']:
                print(f"     输出: {step['outputs']}")
        
        # Execution order
        print(f"\n执行顺序:")
        print(f"  {' → '.join(details['execution_order'])}")
        
        # Final outputs
        if details['outputs']:
            print(f"\n最终输出映射:")
            for key, ref in details['outputs'].items():
                print(f"  - {key}: {ref}")
        
        print("\n" + "=" * 60)
        print(f"💡 运行: workflow run-skill-workflow {workflow_id} --inputs '{{\"goal\": \"...\"}}'")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_run_skill_workflow(args):
    """执行技能工作流"""
    try:
        engine, _, _ = _init_engine(args)
        orchestrator = AgentOrchestrator(engine)
        
        workflow_id = args.workflow_id
        
        # Parse inputs
        inputs = {}
        if args.inputs:
            try:
                inputs = json.loads(args.inputs)
            except json.JSONDecodeError:
                print(f"❌ 无效的 JSON 输入: {args.inputs}", file=sys.stderr)
                sys.exit(1)
        
        # Get optional context
        stage_id = args.stage
        role_id = args.role
        
        print(f"\n🚀 执行技能工作流: {workflow_id}")
        print("=" * 60)
        print(f"输入: {json.dumps(inputs, ensure_ascii=False, indent=2)}")
        if stage_id:
            print(f"阶段上下文: {stage_id}")
        if role_id:
            print(f"角色上下文: {role_id}")
        print("-" * 60)
        
        # Execute workflow
        result = orchestrator.execute_skill_workflow(
            workflow_id=workflow_id,
            inputs=inputs,
            stage_id=stage_id,
            role_id=role_id
        )
        
        # Display results
        print(f"\n执行状态: {result.status.upper()}")
        print(f"执行时间: {result.execution_time:.2f}秒")
        
        # Step results
        print(f"\n步骤结果:")
        for step_id, step_result in result.step_results.items():
            status_icon = "✅" if step_result['status'] == 'completed' else (
                "❌" if step_result['status'] == 'failed' else "⏭️"
            )
            print(f"  {status_icon} {step_id}: {step_result['status']} ({step_result['execution_time']:.2f}s)")
            if step_result.get('error'):
                print(f"      错误: {step_result['error']}")
        
        # Errors
        if result.errors:
            print(f"\n❌ 错误:")
            for error in result.errors:
                print(f"  - {error}")
        
        # Final outputs
        if result.outputs:
            print(f"\n📤 最终输出:")
            for key, value in result.outputs.items():
                print(f"  - {key}: {value}")
        
        # Summary
        print("\n" + "=" * 60)
        if result.status == "completed":
            print("✅ 工作流执行成功!")
        elif result.status == "failed":
            print("❌ 工作流执行失败")
            sys.exit(1)
        else:
            print(f"⚠️ 工作流状态: {result.status}")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_show_progress(args):
    """显示工作流进度"""
    try:
        engine, _, _ = _init_engine(args)
        from work_by_roles.core.immersive_workflow_display import ImmersiveWorkflowDisplay
        display = ImmersiveWorkflowDisplay(engine.workspace_path)
        print(display.display_workflow_status())
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_show_doc(args):
    """显示文档内容"""
    try:
        engine, _, _ = _init_engine(args)
        from work_by_roles.core.immersive_workflow_display import ImmersiveWorkflowDisplay
        display = ImmersiveWorkflowDisplay(engine.workspace_path)
        doc_name = args.document
        full = getattr(args, 'full', False)
        print(display.doc_preview.format_document_for_display(doc_name, show_full=full))
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list_docs(args):
    """列出所有生成的文档"""
    try:
        engine, _, _ = _init_engine(args)
        from work_by_roles.core.immersive_workflow_display import ImmersiveWorkflowDisplay
        display = ImmersiveWorkflowDisplay(engine.workspace_path)
        docs = display.doc_preview.list_all_documents()
        
        if not docs:
            print("📚 **生成的文档**\n\n暂无生成的文档")
            return
        
        print("📚 **生成的文档**\n")
        for doc in docs:
            print(f"📄 **{doc['name']}**")
            print(f"   - 路径: `{doc['path']}`")
            print(f"   - 大小: {doc['size_chars']} 字符, {doc['lines']} 行")
            print(f"   - 最后修改: {doc['last_modified'].strftime('%Y-%m-%d %H:%M:%S')}")
            print()
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_checkpoint_create(args):
    """创建检查点"""
    try:
        engine, _, _ = _init_engine(args)
        
        if not engine.workflow:
            print("❌ 未加载工作流", file=sys.stderr)
            sys.exit(1)
        
        checkpoint = engine.create_checkpoint(
            name=args.name,
            description=args.description,
            stage_id=args.stage
        )
        
        print(f"✅ 检查点已创建: {checkpoint.checkpoint_id}")
        print(f"   名称: {checkpoint.name}")
        if checkpoint.description:
            print(f"   描述: {checkpoint.description}")
        print(f"   工作流: {checkpoint.workflow_id}")
        if checkpoint.stage_id:
            print(f"   阶段: {checkpoint.stage_id}")
        print(f"   创建时间: {checkpoint.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_checkpoint_list(args):
    """列出所有检查点"""
    try:
        engine, _, _ = _init_engine(args)
        from work_by_roles.core.checkpoint_manager import CheckpointManager
        
        checkpoint_manager = CheckpointManager(engine.workspace_path)
        workflow_id = getattr(args, 'workflow', None)
        
        if engine.workflow and not workflow_id:
            workflow_id = engine.workflow.id
        
        checkpoints = checkpoint_manager.list_checkpoints(workflow_id)
        
        if not checkpoints:
            print("📋 **检查点列表**\n\n暂无检查点")
            return
        
        print("📋 **检查点列表**\n")
        for cp in checkpoints:
            print(f"🔖 **{cp.name}** (`{cp.checkpoint_id}`)")
            if cp.description:
                print(f"   - 描述: {cp.description}")
            print(f"   - 工作流: {cp.workflow_id}")
            if cp.stage_id:
                print(f"   - 阶段: {cp.stage_id}")
            print(f"   - 创建时间: {cp.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            if cp.output_files:
                print(f"   - 输出文件: {len(cp.output_files)} 个")
            print()
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_checkpoint_restore(args):
    """从检查点恢复"""
    try:
        engine, _, _ = _init_engine(args)
        from work_by_roles.core.checkpoint_manager import CheckpointManager
        from work_by_roles.core.immersive_workflow_display import ImmersiveWorkflowDisplay
        
        checkpoint_manager = CheckpointManager(engine.workspace_path)
        checkpoint_id = args.checkpoint_id
        
        # Get checkpoint info
        checkpoint = checkpoint_manager.get_checkpoint(checkpoint_id)
        if not checkpoint:
            print(f"❌ 检查点 '{checkpoint_id}' 不存在", file=sys.stderr)
            sys.exit(1)
        
        print(f"🔄 从检查点恢复: {checkpoint.name}")
        print(f"   工作流: {checkpoint.workflow_id}")
        if checkpoint.stage_id:
            print(f"   阶段: {checkpoint.stage_id}")
        print(f"   创建时间: {checkpoint.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Restore with progress manager if available
        progress_manager = None
        try:
            display = ImmersiveWorkflowDisplay(engine.workspace_path)
            progress_manager = display.progress_manager
        except Exception:
            pass
        
        result = checkpoint_manager.restore_from_checkpoint(
            checkpoint_id=checkpoint_id,
            engine=engine,
            progress_manager=progress_manager
        )
        
        print("✅ 检查点恢复成功")
        print(f"   执行状态: {'已恢复' if result['execution_state_restored'] else '未恢复'}")
        print(f"   进度: {'已恢复' if result['progress_restored'] else '未恢复'}")
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_checkpoint_delete(args):
    """删除检查点"""
    try:
        engine, _, _ = _init_engine(args)
        from work_by_roles.core.checkpoint_manager import CheckpointManager
        
        checkpoint_manager = CheckpointManager(engine.workspace_path)
        checkpoint_id = args.checkpoint_id
        
        checkpoint = checkpoint_manager.get_checkpoint(checkpoint_id)
        if not checkpoint:
            print(f"❌ 检查点 '{checkpoint_id}' 不存在", file=sys.stderr)
            sys.exit(1)
        
        deleted = checkpoint_manager.delete_checkpoint(checkpoint_id)
        if deleted:
            print(f"✅ 检查点 '{checkpoint_id}' 已删除")
        else:
            print(f"⚠️  检查点 '{checkpoint_id}' 删除失败", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_checkpoint_info(args):
    """显示检查点详情"""
    try:
        engine, _, _ = _init_engine(args)
        from work_by_roles.core.checkpoint_manager import CheckpointManager
        
        checkpoint_manager = CheckpointManager(engine.workspace_path)
        checkpoint_id = args.checkpoint_id
        
        checkpoint = checkpoint_manager.get_checkpoint(checkpoint_id)
        if not checkpoint:
            print(f"❌ 检查点 '{checkpoint_id}' 不存在", file=sys.stderr)
            sys.exit(1)
        
        print("📋 **检查点详情**\n")
        print(f"**ID**: `{checkpoint.checkpoint_id}`")
        print(f"**名称**: {checkpoint.name}")
        if checkpoint.description:
            print(f"**描述**: {checkpoint.description}")
        print(f"**工作流**: {checkpoint.workflow_id}")
        if checkpoint.stage_id:
            print(f"**阶段**: {checkpoint.stage_id}")
        print(f"**创建时间**: {checkpoint.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if checkpoint.execution_state:
            print(f"\n**执行状态**:")
            print(f"  - 当前阶段: {checkpoint.execution_state.current_stage or '无'}")
            print(f"  - 当前角色: {checkpoint.execution_state.current_role or '无'}")
            print(f"  - 已完成阶段: {len(checkpoint.execution_state.completed_stages)} 个")
        
        if checkpoint.progress_data:
            print(f"\n**进度**:")
            progress_pct = checkpoint.progress_data.get('overall_progress', 0.0) * 100
            print(f"  - 总体进度: {progress_pct:.1f}%")
            print(f"  - 阶段数: {len(checkpoint.progress_data.get('stages', []))}")
        
        if checkpoint.output_files:
            print(f"\n**输出文件**: {len(checkpoint.output_files)} 个")
            for file in checkpoint.output_files[:5]:
                print(f"  - {file}")
            if len(checkpoint.output_files) > 5:
                print(f"  ... 还有 {len(checkpoint.output_files) - 5} 个")
        
        if checkpoint.metadata:
            print(f"\n**元数据**:")
            for key, value in checkpoint.metadata.items():
                print(f"  - {key}: {value}")
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_skill_workflow_graph(args):
    """生成技能工作流的依赖图"""
    try:
        engine, _, _ = _init_engine(args)
        orchestrator = AgentOrchestrator(engine)
        
        workflow_id = args.workflow_id
        workflow = orchestrator.get_skill_workflow(workflow_id)
        
        if not workflow:
            print(f"❌ 工作流 '{workflow_id}' 不存在", file=sys.stderr)
            sys.exit(1)
        
        # Generate Mermaid graph
        mermaid_lines = [
            "```mermaid",
            "graph TD",
            f"    subgraph {workflow.name}",
        ]
        
        # Add nodes
        for step in workflow.steps:
            skill = engine.role_manager.skill_library.get(step.skill_id)
            skill_name = skill.name if skill else step.skill_id
            mermaid_lines.append(f"        {step.step_id}[\"{step.name}<br/><small>{skill_name}</small>\"]")
        
        mermaid_lines.append("    end")
        
        # Add edges
        for step in workflow.steps:
            for dep in step.depends_on:
                mermaid_lines.append(f"    {dep} --> {step.step_id}")
        
        # Styling
        mermaid_lines.append("")
        mermaid_lines.append("    classDef default fill:#f9f,stroke:#333,stroke-width:2px;")
        mermaid_lines.append("```")
        
        mermaid_code = "\n".join(mermaid_lines)
        
        if args.output:
            output_file = Path(args.output)
            if args.format == "html":
                html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Skill Workflow: {workflow.name}</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <script>mermaid.initialize({{startOnLoad:true}});</script>
    <style>
        body {{ font-family: sans-serif; margin: 2em; }}
        h1 {{ color: #333; }}
    </style>
</head>
<body>
    <h1>{workflow.name}</h1>
    <p>{workflow.description}</p>
    <div class="mermaid">
{mermaid_code.replace('```mermaid', '').replace('```', '')}
    </div>
</body>
</html>"""
                output_file.write_text(html_content, encoding='utf-8')
            else:
                output_file.write_text(mermaid_code, encoding='utf-8')
            print(f"✅ 图表已保存到: {output_file}")
        else:
            print(mermaid_code)
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


def _check_required_outputs_for_stage(stage, workspace_path: Path, workflow_id: Optional[str] = None) -> List[Tuple[str, Path]]:
    """
    Check if all required outputs exist for a stage.
    
    Args:
        stage: Stage definition
        workspace_path: Workspace root path
        workflow_id: Optional workflow ID (defaults to "default" if not provided)
        
    Returns:
        List of tuples (output_name, output_path) for missing required outputs
    """
    missing = []
    if not stage.outputs:
        return missing
    
    # Get workflow_id
    workflow_id = workflow_id or "default"
    
    for output in stage.outputs:
        if not output.required:
            continue
        
        # Get output path using unified path calculation
        if output.type in ("document", "report"):
            # All document and report types go to .workflow/outputs/{workflow_id}/{stage_id}/
            output_path = workspace_path / ".workflow" / "outputs" / workflow_id / stage.id / output.name
        else:
            # Code, tests, and other types go to workspace root
            output_path = workspace_path / output.name
        
        if not output_path.exists():
            missing.append((output.name, output_path))
    
    return missing


def cmd_wfauto(args):
    """
    一键跑完整工作流（顺序执行所有阶段）。
    支持智能路由模式：根据用户输入自动识别需要执行的阶段。
    
    行为：
      1) 每次执行前自动重置状态（确保每次执行都是独立的）
      2) 如果提供了 --intent 参数，进行意图识别
      3) 依次 start 每个阶段（使用阶段声明的 role）
      4) 依次 complete 每个阶段（执行质量门禁）
      5) 已完成阶段自动跳过（但在重置后不会发生）
    """
    # Initialize failed stages tracking
    failed_stages = []
    
    try:
        engine, _, _ = _init_engine(args)
        workspace = Path(args.workspace or ".")
        
        # 加载 LLM 客户端
        llm_client = _load_llm_client(workspace)
        
        # 检查是否使用 LLM
        use_llm = getattr(args, 'use_llm', False)
        if use_llm and not llm_client:
            error_msg = (
                "❌ LLM client not configured. Please:\n"
                "  1. Set environment variable (e.g., OPENAI_API_KEY or ANTHROPIC_API_KEY)\n"
                "  2. Or create .workflow/config.yaml with llm configuration\n"
                "  3. Or remove --use-llm flag to use lightweight mode\n"
                "\n"
                "Example environment variables:\n"
                "  export OPENAI_API_KEY='your-api-key'\n"
                "  export ANTHROPIC_API_KEY='your-api-key'\n"
                "\n"
                "Example config file (.workflow/config.yaml):\n"
                "  llm:\n"
                "    provider: openai\n"
                "    api_key: your-api-key\n"
                "    model: gpt-4\n"
                "    base_url: https://api.openai.com/v1  # 可选，用于自定义端点"
            )
            print(error_msg, file=sys.stderr)
            raise WorkflowError("LLM client not configured but --use-llm flag is set")
        
        if not engine.workflow:
            print("❌ 未加载工作流，检查 workflow 文件配置", file=sys.stderr)
            sys.exit(1)
        
        # 每次执行前自动重置状态，确保每次工作流执行都是独立的
        # 除非用户明确指定 --keep-state 保留状态
        keep_state = getattr(args, 'keep_state', False)
        if not keep_state:
            engine.reset_state()
            print("🔄 已重置工作流状态，开始新的独立执行\n")
        
        # 虚拟团队工作流：默认执行完整工作流
        # 只有在用户明确指定部分阶段时才使用智能路由
        stages_to_execute = None
        if hasattr(args, 'intent') and args.intent:
            user_input = args.intent.lower()
            
            # 检测是否明确指定只执行部分阶段
            explicit_partial_keywords = ["只做", "只要", "仅", "only", "just", "跳过", "不要", "不需要"]
            is_explicit_partial = any(kw in user_input for kw in explicit_partial_keywords)
            
            # 检测@[team]或完整流程关键词
            team_mention = "@[team]" in args.intent or "@team" in args.intent
            full_workflow_keywords = ["完整", "全部", "整个", "end-to-end", "e2e", "从头", "全流程", "wfauto"]
            is_full_workflow = any(kw in user_input for kw in full_workflow_keywords)
            
            # 如果是@[team]或明确请求完整流程，直接执行完整工作流
            if team_mention or is_full_workflow:
                stages_to_execute = None  # 执行完整工作流
                print("🚀 虚拟团队工作流：检测到@[team]或完整流程请求，执行完整工作流\n")
            elif is_explicit_partial:
                # 用户明确指定部分阶段，使用智能路由
                from work_by_roles.core.engine import IntentRouter
                
                router = IntentRouter(engine, llm_client=llm_client)
                
                # 确定是否使用LLM
                use_llm = None
                if hasattr(args, 'use_llm') and args.use_llm:
                    use_llm = True
                elif hasattr(args, 'no_llm') and args.no_llm:
                    use_llm = False
                
                intent_result = router.analyze_intent(args.intent, use_llm=use_llm)
                
                print(f"\n🧠 意图识别结果 ({intent_result['method']}):")
                print(f"   类型: {intent_result['intent_type']}")
                print(f"   置信度: {intent_result['confidence']:.2%}")
                print(f"   推理: {intent_result['reasoning']}")
                print(f"   将执行阶段: {', '.join(intent_result['stages'])}")
                
                if intent_result['confidence'] < 0.3:
                    print(f"\n⚠️  置信度较低，使用完整流程")
                    stages_to_execute = None  # 使用完整流程
                else:
                    stages_to_execute = intent_result['stages']
            else:
                # 默认行为：执行完整工作流（虚拟团队工作流特性）
                stages_to_execute = None
                print("🚀 虚拟团队工作流：默认执行完整工作流分析需求目标\n")
        
        # 确定要执行的阶段
        if stages_to_execute:
            # 智能路由模式：只执行匹配的阶段
            stages = [
                s for s in engine.workflow.stages 
                if s.id in stages_to_execute
            ]
            stages = sorted(stages, key=lambda s: s.order)
            print(f"\n🎯 智能路由模式：将执行 {len(stages)}/{len(engine.workflow.stages)} 个阶段\n")
        else:
            # 完整流程模式：执行所有阶段
            stages = sorted(engine.workflow.stages, key=lambda s: s.order)
            print("🚀 wfauto: 开始全流程执行\n")
        
        # 将用户意图传递到 engine context
        if hasattr(args, 'intent') and args.intent:
            if not engine.context:
                from work_by_roles.core.models import ProjectContext
                engine.context = ProjectContext(workspace_path=engine.workspace_path)
            if not engine.context.specs:
                engine.context.specs = {}
            engine.context.specs["global_goal"] = args.intent
            engine.context.specs["user_intent"] = args.intent
        
        # 尝试使用 Agent + Skills 自动执行（如果可用）
        use_agent = _agents_available and getattr(args, 'use_agent', True) and not getattr(args, 'no_agent', False)
        use_parallel = getattr(args, 'parallel', False)
        orchestrator = None
        
        if use_agent:
            try:
                # Initialize immersive display for Cursor IDE conversations
                from work_by_roles.core.immersive_workflow_display import ImmersiveWorkflowDisplay
                immersive_display = ImmersiveWorkflowDisplay(engine.workspace_path)
                
                # Start workflow progress tracking
                immersive_display.progress_manager.start_workflow(engine.workflow.id if engine.workflow else "workflow")
                
                orchestrator = AgentOrchestrator(engine, immersive_display=immersive_display)
                mode_str = "并行" if use_parallel else "顺序"
                print(f"🤖 使用 Agent + Skills 自动执行模式 ({mode_str})\n")
            except Exception as e:
                print(f"⚠️  Agent 系统不可用，使用传统模式: {e}")
                use_agent = False
        
        # 并行执行模式
        if use_parallel and use_agent and orchestrator:
            stage_ids = [stage.id for stage in stages]
            print(f"🚀 并行执行模式: {len(stage_ids)} 个阶段\n")
            try:
                results = orchestrator.execute_parallel_stages_sync(
                    stage_ids=stage_ids,
                    inputs={},
                    use_llm=False
                )
                
                # 处理结果
                for stage_id, result in results.items():
                    stage = engine.executor._get_stage_by_id(stage_id) if engine.executor else None
                    if result.get("status") == "failed":
                        print(f"❌ 阶段 {stage_id} 执行失败: {result.get('error', 'Unknown error')}")
                    else:
                        print(f"✅ 阶段 {stage_id} 执行完成")
                        # 完成阶段
                        try:
                            comp_result = orchestrator.complete_stage(stage_id)
                            if comp_result["quality_gates_passed"]:
                                print(f"✅ 完成阶段: {stage_id}")
                            else:
                                print(f"⚠️  阶段 {stage_id} 有质量门禁警告（宽松模式，继续执行）")
                        except Exception as e:
                            print(f"⚠️  完成阶段 {stage_id} 时出错: {e}")
            except Exception as e:
                print(f"⚠️  并行执行失败，回退到顺序执行: {e}")
                use_parallel = False
        
        # 顺序执行模式（默认或并行失败后的回退）
        if not use_parallel:
            for stage in stages:
                # 如果使用 --keep-state，跳过已完成阶段
                if keep_state:
                    status = engine.get_stage_status(stage.id)
                    if status == StageStatus.COMPLETED:
                        print(f"✅ 跳过已完成阶段: {stage.id} ({stage.name})")
                        continue

                print(f"🔄 启动阶段: {stage.id} ({stage.name})，角色: {stage.role}")
                try:
                    engine.start_stage(stage.id, stage.role)
                except Exception as e:
                    print(f"❌ start 失败: {e}", file=sys.stderr)
                    sys.exit(1)

                # 使用 Agent + Skills 自动执行
                if use_agent and orchestrator:
                    try:
                        # 准备输入数据，包含用户意图
                        stage_inputs = {}
                        if hasattr(args, 'intent') and args.intent:
                            stage_inputs["user_intent"] = args.intent
                            stage_inputs["goal"] = args.intent
                        
                        # 自动执行阶段（包含技能工作流）
                        stage_result = orchestrator.execute_stage_with_workflows(
                            stage_id=stage.id,
                            inputs=stage_inputs,
                            auto_execute_workflows=True
                        )
                        
                        # 输出阶段结论到对话
                        conversation_summary = stage_result.get("conversation_summary")
                        if conversation_summary:
                            print("\n" + "=" * 60)
                            print(f"📋 {stage.name} - 执行结论")
                            print("=" * 60)
                            print(conversation_summary)
                            print("=" * 60 + "\n")
                        
                        # 自动选择并执行相关技能
                        agent = stage_result.get("agent")
                        if agent and agent.context:
                            # 根据阶段目标自动选择技能
                            goal = stage.goal_template or f"Complete {stage.name}"
                            selected_skill = orchestrator.skill_selector.select_skill(goal, agent.role)
                            
                            if selected_skill:
                                print(f"  🎯 自动选择技能: {selected_skill.name}")
                                try:
                                    skill_result = orchestrator.execute_skill(
                                        skill_id=selected_skill.id,
                                        input_data={"goal": goal, "stage": stage.id},
                                        stage_id=stage.id,
                                        role_id=stage.role
                                    )
                                    if skill_result.get("success"):
                                        print(f"  ✅ 技能执行成功")
                                except Exception as e:
                                    print(f"  ⚠️  技能执行失败（继续）: {e}")
                        
                        # 检查必需输出是否已生成（Lovable 工作流模式）
                        import time
                        workflow_id = engine.workflow.id if engine.workflow else None
                        missing_outputs = _check_required_outputs_for_stage(stage, engine.workspace_path, workflow_id=workflow_id)
                        if missing_outputs:
                            print(f"\n⚠️  阶段 {stage.id} 的必需输出未生成，等待生成...")
                            for output_name, output_path in missing_outputs:
                                print(f"  - {output_name} (路径: {output_path.relative_to(engine.workspace_path)})")
                            
                            # 等待输出生成（最多等待3秒，每0.5秒检查一次）
                            max_wait = 3.0
                            wait_interval = 0.5
                            waited = 0.0
                            while missing_outputs and waited < max_wait:
                                time.sleep(wait_interval)
                                waited += wait_interval
                                missing_outputs = _check_required_outputs_for_stage(stage, engine.workspace_path, workflow_id=workflow_id)
                            
                            # 如果仍然缺失，报错
                            if missing_outputs:
                                print(f"\n❌ 必需输出生成失败，无法完成阶段 {stage.id}")
                                for output_name, output_path in missing_outputs:
                                    print(f"  - {output_name} (路径: {output_path.relative_to(engine.workspace_path)})")
                                print(f"\n💡 提示: 请检查技能执行是否成功，或手动生成必需输出")
                                sys.exit(1)
                            else:
                                print(f"✅ 必需输出已生成")
                        
                        # 完成阶段（必需输出检查已通过）
                        comp_result = orchestrator.complete_stage(stage.id)
                        if comp_result["quality_gates_passed"]:
                            print(f"✅ 完成阶段: {stage.id}")
                        else:
                            # 检查是否有必需输出缺失的错误（这些是严格检查，不能忽略）
                            strict_errors = [err for err in comp_result.get("errors", []) 
                                           if "必需输出" in err or "required output" in err.lower()]
                            if strict_errors:
                                print(f"❌ 阶段 {stage.id} 未通过必需输出检查:", file=sys.stderr)
                                for err in strict_errors:
                                    print(f"  - {err}", file=sys.stderr)
                                sys.exit(1)
                            
                            # 宽松模式：警告但不阻塞（非必需输出的错误）
                            print(f"⚠️  阶段 {stage.id} 有质量门禁警告（宽松模式，继续执行）:")
                            for err in comp_result.get("errors", []):
                                if "[宽松模式]" in err:
                                    print(f"  - {err}")
                                elif "必需输出" not in err and "required output" not in err.lower():
                                    print(f"  - {err}")
                    except Exception as e:
                        print(f"⚠️  Agent 执行失败，回退到传统模式: {e}")
                        # 回退到传统模式
                        passed, errors = engine.complete_stage(stage.id)
                        if passed:
                            print(f"✅ 完成阶段: {stage.id}")
                        else:
                            print(f"❌ 阶段 {stage.id} 未通过质量门禁:", file=sys.stderr)
                            for err in errors:
                                print(f"  - {err}", file=sys.stderr)
                            # 记录阶段失败，但不立即退出，继续检查其他阶段
                            failed_stages.append(stage.id)
                else:
                    # 传统模式：只检查质量门禁
                    passed, errors = engine.complete_stage(stage.id)
                    if passed:
                        print(f"✅ 完成阶段: {stage.id}")
                    else:
                        print(f"❌ 阶段 {stage.id} 未通过质量门禁:", file=sys.stderr)
                        for err in errors:
                            print(f"  - {err}", file=sys.stderr)
                        # 记录阶段失败，但不立即退出，继续检查其他阶段
                        failed_stages.append(stage.id)
        
        # Check execution results
        if engine.executor and engine.workflow:
            completed = engine.executor.get_completed_stages()
            all_stages = {s.id for s in engine.workflow.stages}
            
            if failed_stages:
                print("\n" + "=" * 60)
                print("❌ wfauto: 执行完成，但有阶段失败")
                print("=" * 60)
                print(f"失败阶段: {', '.join(failed_stages)}")
                print(f"完成阶段: {len(completed)}/{len(all_stages)}")
                sys.exit(1)
            elif completed == all_stages:
                print("\n" + "=" * 60)
                print("🎉 wfauto: 所有阶段执行完成")
                print("=" * 60)
                # 技能沉淀是可选的，不阻塞工作流完成
                # 只有在非自动化模式下才询问（避免在 @team 触发时阻塞）
                if not use_agent:
                    workspace = Path(engine.workspace_path)
                    _prompt_skill_accumulation(engine, workspace)
                else:
                    print("\n💡 提示: 如需将本次能力沉淀为技能，可运行 'workflow skill-accumulate'")
            else:
                print("\n" + "=" * 60)
                print("⚠️  wfauto: 执行完成，但部分阶段未完成")
                print("=" * 60)
                print(f"完成阶段: {len(completed)}/{len(all_stages)}")
                pending = all_stages - completed
                if pending:
                    print(f"待完成阶段: {', '.join(pending)}")
        else:
            if failed_stages:
                print("\n❌ wfauto: 执行完成，但有阶段失败")
                sys.exit(1)
            else:
                print("\n⚠️  wfauto: 执行完成（工作流状态未知）")
    except Exception as e:
        print(f"❌ wfauto 执行失败: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_intent(args):
    """分析用户意图并返回需要执行的阶段（IDE集成）"""
    try:
        engine, _, _ = _init_engine(args)
        workspace = Path(args.workspace or ".")
        
        user_input = getattr(args, 'input', None) or getattr(args, 'intent', None)
        if not user_input:
            print("❌ 请提供用户输入", file=sys.stderr)
            print("用法: workflow intent '<用户输入>' 或 workflow intent --intent '<用户输入>'", file=sys.stderr)
            sys.exit(1)
        
        # 加载LLM客户端
        llm_client = _load_llm_client(workspace)
        
        # 确定是否使用LLM
        use_llm = None
        if hasattr(args, 'use_llm') and args.use_llm:
            use_llm = True
            if not llm_client:
                error_msg = (
                    "❌ LLM client not configured. Please:\n"
                    "  1. Set environment variable (e.g., OPENAI_API_KEY or ANTHROPIC_API_KEY)\n"
                    "  2. Or create .workflow/config.yaml with llm configuration\n"
                    "  3. Or remove --use-llm flag to use rule-based mode\n"
                    "\n"
                    "Example environment variables:\n"
                    "  export OPENAI_API_KEY='your-api-key'\n"
                    "  export ANTHROPIC_API_KEY='your-api-key'\n"
                    "\n"
                    "Example config file (.workflow/config.yaml):\n"
                    "  llm:\n"
                    "    provider: openai\n"
                    "    api_key: your-api-key\n"
                    "    model: gpt-4"
                )
                print(error_msg, file=sys.stderr)
                raise WorkflowError("LLM client not configured but --use-llm flag is set")
        elif hasattr(args, 'no_llm') and args.no_llm:
            use_llm = False
        
        from work_by_roles.core.engine import IntentRouter
        router = IntentRouter(engine, llm_client=llm_client)
        
        # 确定是否使用LLM
        use_llm = None
        if hasattr(args, 'use_llm') and args.use_llm:
            use_llm = True
        elif hasattr(args, 'no_llm') and args.no_llm:
            use_llm = False
        
        # 分析意图
        result = router.analyze_intent(user_input, use_llm=use_llm)
        
        # 输出格式
        if hasattr(args, 'json') and args.json:
            import json
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"\n🧠 意图识别结果 ({result['method']}):")
            print(f"   类型: {result['intent_type']}")
            print(f"   置信度: {result['confidence']:.2%}")
            print(f"   推理: {result['reasoning']}")
            print(f"   将执行阶段: {', '.join(result['stages'])}")
            
            if result['stages']:
                if len(result['stages']) == len(engine.workflow.stages):
                    command = "workflow wfauto"
                else:
                    command = f"workflow wfauto --intent '{user_input}'"
                print(f"\n建议命令: {command}")
        
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Multi-Role Skills Workflow 命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s start requirements product_analyst
  %(prog)s complete requirements
  %(prog)s status
  %(prog)s validate product_analyst define_requirements
  %(prog)s list-stages
  %(prog)s list-roles
        """
    )
    
    parser.add_argument("--workspace", "-w", help="工作空间路径 (默认: 当前目录)")
    parser.add_argument("--roles", "-r", help="角色定义文件 (默认: role_schema.yaml)")
    parser.add_argument("--workflow", "-f", help="工作流定义文件 (默认: workflow_schema.yaml)")
    parser.add_argument("--skills", "-k", help="技能库目录 (默认: skills)")
    parser.add_argument("--context", "-c", help="项目上下文文件 (默认: .workflow/project_context.yaml)")
    parser.add_argument("--state", "-s", help="工作流状态文件 (默认: .workflow/state.yaml)")
    parser.add_argument("--team", "-t", help="指定使用的团队（覆盖当前团队）")
    parser.add_argument("--no-restore-state", action="store_true", help="禁用自动恢复状态")
    parser.add_argument("--no-auto-save", action="store_true", help="禁用自动保存状态")
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # setup 命令（一键接入）
    setup_parser = subparsers.add_parser("setup", help="一键接入：自动设置项目，让用户可以直接使用角色（推荐新项目使用）")
    setup_parser.set_defaults(func=cmd_setup)
    
    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化项目上下文并扫描结构")
    init_parser.add_argument("--quick", "-q", action="store_true", help="快速模式：使用vibe-coding模板，最小化文档要求")
    init_parser.add_argument("--template", "-t", help="指定使用的模板名称（如：vibe-coding, standard-delivery）")
    init_parser.set_defaults(func=cmd_init)
    
    # start 命令
    start_parser = subparsers.add_parser("start", help="启动阶段（可自动推断）")
    start_parser.add_argument("stage", nargs="?", help="阶段ID（可选，自动推断下一阶段）")
    start_parser.add_argument("role", nargs="?", help="角色ID（可选，从阶段自动推断）")
    start_parser.add_argument("--as", dest="role_alt", help="指定角色（替代位置参数）")
    start_parser.add_argument("--status", "-s", action="store_true", help="显示状态")
    start_parser.set_defaults(func=cmd_start)
    
    # complete 命令
    complete_parser = subparsers.add_parser("complete", help="完成阶段")
    complete_parser.add_argument("stage", nargs="?", help="阶段ID（可选，默认为当前活动阶段）")
    complete_parser.add_argument("--status", "-s", action="store_true", help="显示状态")
    complete_parser.set_defaults(func=cmd_complete)
    
    # status 命令
    status_parser = subparsers.add_parser("status", help="显示工作流状态")
    status_parser.set_defaults(func=cmd_status)
    
    # validate 命令
    validate_parser = subparsers.add_parser("validate", help="验证角色动作")
    validate_parser.add_argument("role", help="角色ID")
    validate_parser.add_argument("action", help="动作名称")
    validate_parser.set_defaults(func=cmd_validate)
    
    # generate-skill 命令
    generate_skill_parser = subparsers.add_parser(
        "generate-skill", help="生成技能模板"
    )
    generate_skill_parser.add_argument("skill_id", help="技能ID（如: python_dev）")
    generate_skill_parser.add_argument("name", help="技能名称（如: Python Development）")
    generate_skill_parser.add_argument("-o", "--output", help="输出文件路径")
    generate_skill_parser.set_defaults(func=cmd_generate_skill)

    # validate-skills 命令
    validate_skills_parser = subparsers.add_parser(
        "validate-skills", help="验证技能库定义"
    )
    validate_skills_parser.add_argument("file", help="技能库 YAML 文件路径")
    validate_skills_parser.add_argument("--quiet", action="store_true", help="只输出错误")
    validate_skills_parser.set_defaults(func=cmd_validate_skills)

    # list-skills 命令
    list_skills_parser = subparsers.add_parser(
        "list-skills", help="列出已加载的技能"
    )
    list_skills_parser.set_defaults(func=cmd_list_skills)

    # interactive-skill 命令
    interactive_skill_parser = subparsers.add_parser(
        "interactive-skill", help="交互式创建技能定义"
    )
    interactive_skill_parser.set_defaults(func=cmd_interactive_skill)
    
    # skill-trace 命令
    skill_trace_parser = subparsers.add_parser(
        "skill-trace", help="查看技能执行历史"
    )
    skill_trace_parser.add_argument("skill_id", help="技能 ID")
    skill_trace_parser.set_defaults(func=cmd_skill_trace)
    
    # skill-stats 命令
    skill_stats_parser = subparsers.add_parser(
        "skill-stats", help="查看所有技能的统计信息"
    )
    skill_stats_parser.set_defaults(func=cmd_skill_stats)
    
    # export-trace 命令
    export_trace_parser = subparsers.add_parser(
        "export-trace", help="导出完整追踪数据"
    )
    export_trace_parser.add_argument("--format", "-f", choices=["json", "yaml"], default="json", help="输出格式")
    export_trace_parser.add_argument("--output", "-o", help="输出文件路径")
    export_trace_parser.set_defaults(func=cmd_export_trace)
    
    # benchmark-skill 命令
    benchmark_skill_parser = subparsers.add_parser(
        "benchmark-skill", help="基准测试技能"
    )
    benchmark_skill_parser.add_argument("skill_id", help="技能 ID")
    benchmark_skill_parser.add_argument("--test-cases", required=True, help="测试用例 YAML 文件路径")
    benchmark_skill_parser.add_argument("--report", action="store_true", help="生成详细报告")
    benchmark_skill_parser.add_argument("--models", nargs="+", help="多模型对比（P2优化）")
    benchmark_skill_parser.set_defaults(func=cmd_benchmark_skill)
    
    # import-sop 命令 (P2 optimization)
    import_sop_parser = subparsers.add_parser(
        "import-sop", help="从 SOP 文档导入并生成 roles/skills/workflow 配置"
    )
    import_sop_parser.add_argument("sop_file", help="SOP 文档路径 (Markdown)")
    import_sop_parser.add_argument("--output", "-o", help="输出目录（默认: .workflow/）")
    import_sop_parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的配置文件")
    import_sop_parser.set_defaults(func=cmd_import_sop)
    
    # skill-test 命令 (P0 optimization)
    skill_test_parser = subparsers.add_parser(
        "skill-test", help="测试单个技能（支持 snapshot 对比和 schema 校验）"
    )
    skill_test_parser.add_argument("skill_id", help="技能 ID")
    skill_test_parser.add_argument("--input", "-i", help="输入数据文件路径 (JSON/YAML)")
    skill_test_parser.add_argument("--expect", "-e", help="期望输出文件路径 (JSON/YAML，用于 snapshot 对比)")
    skill_test_parser.add_argument("--schema", "-s", help="期望 Schema 文件路径 (JSON/YAML，用于 schema 校验)")
    skill_test_parser.add_argument("--snapshot", help="Snapshot 文件路径（如果提供，会保存/加载 snapshot）")
    skill_test_parser.set_defaults(func=cmd_skill_test)
    
    # workflow replay 命令 (P1 optimization)
    replay_parser = subparsers.add_parser(
        "replay", help="从事件日志回放工作流"
    )
    replay_parser.add_argument("event_log", help="事件日志文件路径 (JSON/YAML)")
    replay_parser.set_defaults(func=cmd_replay_workflow)
    
    # workflow dry-run 命令 (P1 optimization)
    dry_run_parser = subparsers.add_parser(
        "dry-run", help="干运行阶段（模拟执行，不实际调用技能）"
    )
    dry_run_parser.add_argument("stage_id", help="阶段 ID")
    dry_run_parser.set_defaults(func=cmd_dry_run_stage)

    # list-stages 命令
    list_stages_parser = subparsers.add_parser("list-stages", help="列出所有阶段")
    list_stages_parser.set_defaults(func=cmd_list_stages)
    
    # list-roles 命令
    list_roles_parser = subparsers.add_parser("list-roles", help="列出所有角色")
    list_roles_parser.set_defaults(func=cmd_list_roles)

    # export-graph 命令
    export_graph_parser = subparsers.add_parser("export-graph", help="导出工作流图表 (Mermaid/HTML)")
    export_graph_parser.add_argument("--format", "-f", choices=["mermaid", "html"], default="mermaid", help="输出格式 (默认: mermaid)")
    export_graph_parser.add_argument("--output", "-o", help="输出文件路径")
    export_graph_parser.add_argument("--no-roles", action="store_true", help="不包含角色继承图")
    export_graph_parser.set_defaults(func=cmd_export_graph)
    
    # check-team 命令
    check_team_parser = subparsers.add_parser("check-team", help="执行团队与工作流健康检查")
    check_team_parser.set_defaults(func=cmd_check_team)
    
    # team 命令组
    team_parser = subparsers.add_parser("team", help="管理虚拟团队")
    team_subparsers = team_parser.add_subparsers(dest="team_command", help="团队命令")
    
    # team list
    team_list_parser = team_subparsers.add_parser("list", help="列出所有团队")
    team_list_parser.set_defaults(func=cmd_team_list)
    
    # team switch
    team_switch_parser = team_subparsers.add_parser("switch", help="切换到指定团队")
    team_switch_parser.add_argument("team_id", help="团队 ID")
    team_switch_parser.set_defaults(func=cmd_team_switch)
    
    # team create
    team_create_parser = team_subparsers.add_parser("create", help="创建新团队")
    team_create_parser.add_argument("team_id", help="团队 ID")
    team_create_parser.add_argument("--name", help="团队名称")
    team_create_parser.add_argument("--description", help="团队描述")
    team_create_parser.add_argument("--template", help="使用的模板名称")
    team_create_parser.add_argument("--dir", help="团队目录名称（默认: .workflow-<team_id>）")
    team_create_parser.set_defaults(func=cmd_team_create)
    
    # team current
    team_current_parser = team_subparsers.add_parser("current", help="显示当前活动团队")
    team_current_parser.set_defaults(func=cmd_team_current)
    
    # team delete
    team_delete_parser = team_subparsers.add_parser("delete", help="删除团队")
    team_delete_parser.add_argument("team_id", help="团队 ID")
    team_delete_parser.add_argument("--force", action="store_true", help="不询问确认")
    team_delete_parser.add_argument("--remove-files", action="store_true", help="同时删除团队文件")
    team_delete_parser.set_defaults(func=cmd_team_delete)
    
    # team templates
    team_templates_parser = team_subparsers.add_parser("templates", help="列出可用的团队配置模板")
    team_templates_parser.set_defaults(func=cmd_team_templates)
    
    # analyze 命令
    analyze_parser = subparsers.add_parser("analyze", help="分析当前阶段的工作流状态和需求")
    analyze_parser.set_defaults(func=cmd_analyze)

    # wfauto 命令（自动依次执行所有阶段）
    wfauto_parser = subparsers.add_parser("wfauto", help="一键顺序执行所有阶段（自动使用 Agent + Skills）")
    wfauto_parser.add_argument("--intent", "-i", help="用户意图描述（启用智能路由模式，自动识别需要执行的阶段）")
    wfauto_parser.add_argument("--use-llm", action="store_true", help="强制使用LLM进行意图识别")
    wfauto_parser.add_argument("--no-llm", action="store_true", help="强制使用规则引擎（节省token）")
    wfauto_parser.add_argument("--no-agent", action="store_true", help="禁用 Agent + Skills 自动执行（使用传统模式）")
    wfauto_parser.add_argument("--keep-state", action="store_true", help="保留之前的工作流状态（默认每次执行前会重置状态）")
    wfauto_parser.add_argument("--parallel", action="store_true", help="并行执行无依赖的阶段（实验性功能）")
    wfauto_parser.set_defaults(func=cmd_wfauto, use_agent=True)
    
    # intent 命令（IDE集成）
    intent_parser = subparsers.add_parser("intent", help="分析用户意图（IDE集成）")
    intent_parser.add_argument("input", nargs="?", help="用户输入的自然语言")
    intent_parser.add_argument("--intent", "-i", help="用户输入（替代位置参数）")
    intent_parser.add_argument("--json", action="store_true", help="输出JSON格式")
    intent_parser.add_argument("--use-llm", action="store_true", help="强制使用LLM")
    intent_parser.add_argument("--no-llm", action="store_true", help="强制使用规则引擎")
    intent_parser.set_defaults(func=cmd_intent)
    
    # agent-execute 命令（类似 MetaGPT）
    if _agents_available:
        agent_execute_parser = subparsers.add_parser("agent-execute", help="使用 Agent 执行工作流阶段（类似 MetaGPT）")
        agent_execute_parser.add_argument("stage", nargs="?", help="阶段ID（可选，自动推断）")
        agent_execute_parser.add_argument("--no-llm", action="store_true", help="禁用LLM，只进行约束检查（轻量模式，默认）")
        agent_execute_parser.add_argument("--use-llm", action="store_true", help="启用LLM执行（需要配置llm_client）")
        agent_execute_parser.add_argument("--collaborate", action="store_true", help="启用协作模式（Agent 间消息传递和反馈）")
        agent_execute_parser.set_defaults(func=cmd_agent_execute)
        
        # team-collaborate 命令（多 Agent 协作）
        team_collab_parser = subparsers.add_parser("team-collaborate", help="启动多 Agent 协作模式执行任务")
        team_collab_parser.add_argument("goal", help="要完成的目标描述")
        team_collab_parser.add_argument("--roles", nargs="+", help="指定参与的角色ID（可选，默认使用所有角色）")
        team_collab_parser.add_argument("--use-llm", action="store_true", help="使用LLM进行任务分解")
        team_collab_parser.set_defaults(func=cmd_team_collaborate)
        
        # decompose-task 命令（任务分解）
        decompose_parser = subparsers.add_parser("decompose-task", help="分解目标为子任务")
        decompose_parser.add_argument("goal", help="要分解的目标描述")
        decompose_parser.add_argument("--roles", nargs="+", help="指定可用的角色ID（可选）")
        decompose_parser.add_argument("--use-llm", action="store_true", help="使用LLM进行智能分解")
        decompose_parser.add_argument("--json", action="store_true", help="输出JSON格式")
        decompose_parser.set_defaults(func=cmd_decompose_task)
        
        agent_complete_parser = subparsers.add_parser("agent-complete", help="完成 Agent 执行的任务")
        agent_complete_parser.add_argument("stage", nargs="?", help="阶段ID（可选，当前阶段）")
        agent_complete_parser.set_defaults(func=cmd_agent_complete)
    
    # add-role 命令
    add_role_parser = subparsers.add_parser("add-role", help="交互式添加新角色")
    add_role_parser.add_argument("--role-id", help="角色 ID (可选，否则交互式输入)")
    add_role_parser.add_argument("--name", help="角色名称 (可选)")
    add_role_parser.add_argument("--description", help="角色描述 (可选)")
    add_role_parser.set_defaults(func=cmd_add_role)
    
    # add-stage 命令
    add_stage_parser = subparsers.add_parser("add-stage", help="交互式添加新阶段")
    add_stage_parser.add_argument("--stage-id", help="阶段 ID (可选，否则交互式输入)")
    add_stage_parser.add_argument("--name", help="阶段名称 (可选)")
    add_stage_parser.add_argument("--role", help="角色 ID (可选)")
    add_stage_parser.set_defaults(func=cmd_add_stage)
    
    # ========================================================================
    # Migration Commands - 迁移命令
    # ========================================================================
    
    migrate_skills_parser = subparsers.add_parser(
        "migrate-skills",
        help="迁移 skill_library.yaml 到 Anthropic 标准格式"
    )
    migrate_skills_parser.add_argument("yaml_file", help="skill_library.yaml 文件路径（将被迁移）")
    migrate_skills_parser.add_argument(
        "--output", "-o",
        help="输出目录（默认: skills）"
    )
    migrate_skills_parser.set_defaults(func=cmd_migrate_skills)
    
    # ========================================================================
    # Role Execute Command - 简化的角色执行（无需workflow）
    # ========================================================================
    
    if _agents_available:
        role_execute_parser = subparsers.add_parser(
            "role-execute",
            help="使用指定角色处理需求（简化模式，无需workflow）"
        )
        role_execute_parser.add_argument("role_id", help="角色ID")
        role_execute_parser.add_argument("requirement", help="用户需求描述")
        role_execute_parser.add_argument(
            "--inputs", "-i",
            help="输入数据 (JSON格式)"
        )
        role_execute_parser.add_argument(
            "--use-llm",
            action="store_true",
            help="使用LLM生成响应（需要配置llm_client）"
        )
        role_execute_parser.set_defaults(func=cmd_role_execute)
    
    # ========================================================================
    # Skill Workflow Commands - 多技能工作流命令
    # ========================================================================
    
    # list-skill-workflows 命令
    list_skill_workflows_parser = subparsers.add_parser(
        "list-skill-workflows", 
        help="列出所有技能工作流"
    )
    list_skill_workflows_parser.set_defaults(func=cmd_list_skill_workflows)
    
    # skill-workflow-detail 命令
    skill_workflow_detail_parser = subparsers.add_parser(
        "skill-workflow-detail",
        help="显示技能工作流详情"
    )
    skill_workflow_detail_parser.add_argument("workflow_id", help="工作流 ID")
    skill_workflow_detail_parser.set_defaults(func=cmd_skill_workflow_detail)
    
    # run-skill-workflow 命令
    run_skill_workflow_parser = subparsers.add_parser(
        "run-skill-workflow",
        help="执行技能工作流"
    )
    run_skill_workflow_parser.add_argument("workflow_id", help="工作流 ID")
    run_skill_workflow_parser.add_argument(
        "--inputs", "-i",
        help="工作流输入 (JSON 格式)"
    )
    run_skill_workflow_parser.add_argument(
        "--stage", "-s",
        help="阶段上下文 (可选)"
    )
    run_skill_workflow_parser.add_argument(
        "--role", "-r",
        help="角色上下文 (可选)"
    )
    run_skill_workflow_parser.set_defaults(func=cmd_run_skill_workflow)
    
    # skill-workflow-graph 命令
    skill_workflow_graph_parser = subparsers.add_parser(
        "skill-workflow-graph",
        help="生成技能工作流依赖图"
    )
    skill_workflow_graph_parser.add_argument("workflow_id", help="工作流 ID")
    skill_workflow_graph_parser.add_argument(
        "--format", "-f",
        choices=["mermaid", "html"],
        default="mermaid",
        help="输出格式"
    )
    skill_workflow_graph_parser.add_argument(
        "--output", "-o",
        help="输出文件路径"
    )
    skill_workflow_graph_parser.set_defaults(func=cmd_skill_workflow_graph)
    
    # Checkpoint commands
    checkpoint_parser = subparsers.add_parser('checkpoint', help='检查点管理')
    checkpoint_subparsers = checkpoint_parser.add_subparsers(dest='checkpoint_command', help='检查点子命令')
    
    checkpoint_create_parser = checkpoint_subparsers.add_parser('create', help='创建检查点')
    checkpoint_create_parser.add_argument('--name', help='检查点名称')
    checkpoint_create_parser.add_argument('--description', help='检查点描述')
    checkpoint_create_parser.add_argument('--stage', help='阶段ID')
    checkpoint_create_parser.set_defaults(func=cmd_checkpoint_create)
    
    checkpoint_list_parser = checkpoint_subparsers.add_parser('list', help='列出所有检查点')
    checkpoint_list_parser.add_argument('--workflow', help='工作流ID（可选）')
    checkpoint_list_parser.set_defaults(func=cmd_checkpoint_list)
    
    checkpoint_restore_parser = checkpoint_subparsers.add_parser('restore', help='从检查点恢复')
    checkpoint_restore_parser.add_argument('checkpoint_id', help='检查点ID')
    checkpoint_restore_parser.set_defaults(func=cmd_checkpoint_restore)
    
    checkpoint_delete_parser = checkpoint_subparsers.add_parser('delete', help='删除检查点')
    checkpoint_delete_parser.add_argument('checkpoint_id', help='检查点ID')
    checkpoint_delete_parser.set_defaults(func=cmd_checkpoint_delete)
    
    checkpoint_info_parser = checkpoint_subparsers.add_parser('info', help='显示检查点详情')
    checkpoint_info_parser.add_argument('checkpoint_id', help='检查点ID')
    checkpoint_info_parser.set_defaults(func=cmd_checkpoint_info)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Handle team subcommands
    if args.command == "team" and hasattr(args, 'team_command') and args.team_command:
        # Team subcommand is already set via set_defaults(func=...)
        pass
    
    # Handle checkpoint subcommands
    if args.command == "checkpoint" and hasattr(args, 'checkpoint_command') and args.checkpoint_command:
        # Checkpoint subcommand is already set via set_defaults(func=...)
        pass
    
    args.func(args)


if __name__ == "__main__":
    main()

