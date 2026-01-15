"""
Team manager for managing multiple virtual team configurations.
Following Single Responsibility Principle - handles team management only.
"""

import yaml
import warnings
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any

from .exceptions import WorkflowError
from .schema_loader import SchemaLoader


class TeamManager:
    """管理多个虚拟团队配置"""
    
    def __init__(self, workspace_path: Path):
        """
        Initialize team manager.
        
        Args:
            workspace_path: Path to workspace root
        """
        self.workspace_path = Path(workspace_path)
        self.workflow_dir = self.workspace_path / ".workflow"
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = self.workflow_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.teams_file = self.workflow_dir / "teams.yaml"
        self.current_team_file = self.workflow_dir / ".current_team"
        self.teams: Dict[str, Dict[str, Any]] = {}
        self._load_teams()
    
    def _load_teams(self) -> None:
        """加载团队配置"""
        if self.teams_file.exists():
            try:
                data = SchemaLoader.load_schema(self.teams_file)
                self.teams = data.get("teams", {})
            except Exception as e:
                warnings.warn(f"Failed to load teams config: {e}", UserWarning)
                self.teams = {}
    
    def save_teams(self) -> None:
        """保存团队配置"""
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = self.workflow_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": "1.0",
            "teams": self.teams
        }
        with open(self.teams_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    def get_current_team(self) -> Optional[str]:
        """获取当前活动团队"""
        if self.current_team_file.exists():
            try:
                team_id = self.current_team_file.read_text(encoding='utf-8').strip()
                if team_id and team_id in self.teams:
                    return team_id
            except Exception:
                pass
        return None
    
    def set_current_team(self, team_id: str) -> None:
        """设置当前活动团队"""
        if team_id not in self.teams:
            raise WorkflowError(f"Team '{team_id}' not found")
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = self.workflow_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.current_team_file.write_text(team_id, encoding='utf-8')
    
    def get_team_config(self, team_id: Optional[str] = None) -> Dict[str, Path]:
        """
        获取团队配置路径
        
        Args:
            team_id: 团队 ID，如果为 None 则使用当前活动团队或默认配置
            
        Returns:
            包含配置路径的字典
        """
        team_id = team_id or self.get_current_team()
        
        if not team_id:
            # 默认使用 .workflow 目录
            workflow_dir = self.workflow_dir
            return {
                "workflow": workflow_dir / "workflow_schema.yaml",
                "roles": workflow_dir / "role_schema.yaml",
                "skills": workflow_dir / "skills",
                "state": workflow_dir / "state.yaml",
                "context": workflow_dir / "project_context.yaml"
            }
        
        if team_id not in self.teams:
            raise WorkflowError(f"Team '{team_id}' not found")
        
        team_config = self.teams[team_id]
        # 获取团队目录，支持相对路径和绝对路径
        team_dir_str = team_config.get("dir", f".workflow-{team_id}")
        if Path(team_dir_str).is_absolute():
            team_dir = Path(team_dir_str)
        else:
            team_dir = self.workspace_path / team_dir_str
        
        # 构建配置路径，支持相对路径和绝对路径
        def resolve_path(path_str: str, default: str) -> Path:
            if Path(path_str).is_absolute():
                return Path(path_str)
            return self.workspace_path / path_str
        
        return {
            "workflow": resolve_path(
                team_config.get("workflow", str(team_dir / "workflow_schema.yaml")),
                str(team_dir / "workflow_schema.yaml")
            ),
            "roles": resolve_path(
                team_config.get("roles", str(team_dir / "role_schema.yaml")),
                str(team_dir / "role_schema.yaml")
            ),
            "skills": resolve_path(
                team_config.get("skills", str(team_dir / "skills")),
                str(team_dir / "skills")
            ),
            "state": resolve_path(
                team_config.get("state", str(team_dir / "state.yaml")),
                str(team_dir / "state.yaml")
            ),
            "context": resolve_path(
                team_config.get("context", str(team_dir / "project_context.yaml")),
                str(team_dir / "project_context.yaml")
            )
        }
    
    def list_teams(self) -> List[Dict[str, Any]]:
        """列出所有团队"""
        result = []
        current = self.get_current_team()
        
        for team_id, config in self.teams.items():
            result.append({
                "id": team_id,
                "name": config.get("name", team_id),
                "description": config.get("description", ""),
                "dir": config.get("dir", f".workflow-{team_id}"),
                "is_current": team_id == current
            })
        
        return result
    
    def create_team(
        self,
        team_id: str,
        name: str,
        description: str = "",
        template: Optional[str] = None,
        dir_name: Optional[str] = None
    ) -> Path:
        """
        创建新团队
        
        Args:
            team_id: 团队唯一标识符
            name: 团队名称
            description: 团队描述
            template: 可选模板名称，用于初始化团队配置
            dir_name: 可选目录名称，默认使用 .workflow-{team_id}
            
        Returns:
            团队目录路径
        """
        if team_id in self.teams:
            raise WorkflowError(f"Team '{team_id}' already exists")
        
        team_dir = self.workspace_path / (dir_name or f".workflow-{team_id}")
        team_dir.mkdir(parents=True, exist_ok=True)
        
        # 如果指定了模板，复制模板文件
        if template:
            # 尝试从多个位置查找模板（优先级：teams目录 > 内置templates > 项目templates）
            templates_dirs = [
                self.workspace_path / "teams" / template,  # 项目 teams 目录（最高优先级）
                Path(__file__).parent.parent / "templates" / template,  # 内置 templates
                self.workspace_path / "templates" / template,  # 项目 templates
            ]
            
            template_found = False
            for templates_dir in templates_dirs:
                if templates_dir.exists() and templates_dir.is_dir():
                    for f in templates_dir.iterdir():
                        # 复制所有配置文件，包括 README.md
                        if f.is_file() and f.suffix in ['.yaml', '.yml', '.md', '.txt']:
                            shutil.copy(f, team_dir / f.name)
                    template_found = True
                    break
            
            if not template_found:
                warnings.warn(
                    f"Template '{template}' not found in teams/, templates/, or built-in templates. Creating team without template files",
                    UserWarning
                )
        
        # 添加团队配置
        team_dir_rel = team_dir.relative_to(self.workspace_path)
        self.teams[team_id] = {
            "name": name,
            "description": description,
            "dir": str(team_dir_rel),
            "workflow": str(team_dir_rel / "workflow_schema.yaml"),
            "roles": str(team_dir_rel / "role_schema.yaml"),
            "skills": str(team_dir_rel / "skills"),
            "state": str(team_dir_rel / "state.yaml"),
            "context": str(team_dir_rel / "project_context.yaml")
        }
        
        self.save_teams()
        return team_dir
    
    def delete_team(self, team_id: str, remove_files: bool = False) -> None:
        """
        删除团队
        
        Args:
            team_id: 团队 ID
            remove_files: 是否同时删除团队文件目录
        """
        if team_id not in self.teams:
            raise WorkflowError(f"Team '{team_id}' not found")
        
        if self.get_current_team() == team_id:
            # 清除当前团队标记
            if self.current_team_file.exists():
                self.current_team_file.unlink()
        
        if remove_files:
            team_dir_str = self.teams[team_id].get("dir", f".workflow-{team_id}")
            if Path(team_dir_str).is_absolute():
                team_dir = Path(team_dir_str)
            else:
                team_dir = self.workspace_path / team_dir_str
            
            if team_dir.exists() and team_dir.is_dir():
                shutil.rmtree(team_dir)
        
        del self.teams[team_id]
        self.save_teams()

