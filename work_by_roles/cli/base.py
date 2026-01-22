"""
Base utilities for CLI commands.
"""

import sys
from pathlib import Path
from typing import Tuple, Optional, Any

from ..core.engine import WorkflowEngine, TeamManager

def _init_engine(args) -> Tuple[WorkflowEngine, Path, Path]:
    """Initialize engine with skill library, supporting team context"""
    workspace = Path(args.workspace or ".")
    workflow_dir = workspace / ".workflow"
    workflow_dir.mkdir(exist_ok=True)
    
    # Initialize team manager
    team_manager = TeamManager(workspace)
    
    # If team specified, use team config; otherwise use args or default
    team_id = getattr(args, 'team', None)
    if team_id:
        team_config = team_manager.get_team_config(team_id)
        skill_file = team_config["skills"]
        roles_file = team_config["roles"]
        workflow_file = team_config["workflow"]
        context_file = team_config["context"]
        state_file = team_config["state"]
    else:
        current_team = team_manager.get_current_team()
        if current_team and not (getattr(args, 'workflow', None) or getattr(args, 'roles', None) or getattr(args, 'skills', None)):
            team_config = team_manager.get_team_config(current_team)
            skill_file = team_config["skills"]
            roles_file = team_config["roles"]
            workflow_file = team_config["workflow"]
            context_file = team_config["context"]
            state_file = team_config["state"]
        else:
            skill_file = Path(getattr(args, 'skills', None)) if getattr(args, 'skills', None) else workflow_dir / "skills"
            roles_file = Path(getattr(args, 'roles', None)) if getattr(args, 'roles', None) else workflow_dir / "role_schema.yaml"
            workflow_file = Path(getattr(args, 'workflow', None)) if getattr(args, 'workflow', None) else workflow_dir / "workflow_schema.yaml"
            context_file = Path(getattr(args, 'context', None)) if getattr(args, 'context', None) else workflow_dir / "project_context.yaml"
            state_file = Path(getattr(args, 'state', None)) if getattr(args, 'state', None) else workflow_dir / "state.yaml"
    
    auto_restore = not getattr(args, 'no_restore_state', False)
    auto_save = not getattr(args, 'no_auto_save', False)

    engine = WorkflowEngine(
        workspace,
        auto_save_state=auto_save,
        state_file=state_file
    )
    
    if context_file.exists():
        engine.load_context(context_file)
        
    shared_skills_dir = workspace / "skills"
    has_shared_skills = shared_skills_dir.exists() and shared_skills_dir.is_dir()
    has_team_skills = skill_file.exists()
    
    if not has_team_skills and not has_shared_skills:
        raise RuntimeError(
            f"Skill library not found: {skill_file}\n"
            f"Please run 'workflow setup' to initialize the project, or ensure a 'skills' directory exists in the workspace root."
        )
        
    engine.load_skill_library(skill_file, shared_skills_dir=shared_skills_dir if has_shared_skills else None)
    engine.load_roles(roles_file)
    engine.load_workflow(workflow_file)
    
    if not auto_restore and state_file.exists():
        engine.load_state(state_file, auto_restore=False)
        
    return engine, workflow_file, state_file
