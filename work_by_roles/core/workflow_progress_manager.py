"""
Workflow progress manager for tracking and displaying workflow execution progress.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import json


@dataclass
class ProgressStep:
    """Progress step tracking a single stage execution"""
    step_id: str
    name: str
    status: str  # "pending", "running", "completed", "failed"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    details: Dict[str, Any] = field(default_factory=dict)
    output_files: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "details": self.details,
            "output_files": self.output_files
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProgressStep':
        """Create from dictionary"""
        return cls(
            step_id=data["step_id"],
            name=data["name"],
            status=data["status"],
            start_time=datetime.fromisoformat(data["start_time"]) if data.get("start_time") else None,
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            details=data.get("details", {}),
            output_files=data.get("output_files", [])
        )


@dataclass
class WorkflowProgress:
    """Workflow progress tracking overall execution"""
    workflow_id: str
    current_stage: Optional[str] = None
    stages: List[ProgressStep] = field(default_factory=list)
    overall_progress: float = 0.0  # 0.0 - 1.0
    started_at: datetime = field(default_factory=datetime.now)
    estimated_completion: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "workflow_id": self.workflow_id,
            "current_stage": self.current_stage,
            "stages": [stage.to_dict() for stage in self.stages],
            "overall_progress": self.overall_progress,
            "started_at": self.started_at.isoformat(),
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowProgress':
        """Create from dictionary"""
        return cls(
            workflow_id=data["workflow_id"],
            current_stage=data.get("current_stage"),
            stages=[ProgressStep.from_dict(s) for s in data.get("stages", [])],
            overall_progress=data.get("overall_progress", 0.0),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else datetime.now(),
            estimated_completion=datetime.fromisoformat(data["estimated_completion"]) if data.get("estimated_completion") else None
        )


class WorkflowProgressManager:
    """Manages workflow progress tracking and display"""
    
    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.progress_file = workspace_path / ".workflow" / "progress.json"
        self.current_progress: Optional[WorkflowProgress] = None
    
    def start_workflow(self, workflow_id: str) -> WorkflowProgress:
        """Start tracking a workflow"""
        self.current_progress = WorkflowProgress(
            workflow_id=workflow_id,
            started_at=datetime.now()
        )
        self._save_progress()
        return self.current_progress
    
    def start_stage(self, stage_id: str, stage_name: str) -> ProgressStep:
        """Start tracking a stage"""
        if not self.current_progress:
            raise ValueError("Workflow not started. Call start_workflow() first.")
        
        step = ProgressStep(
            step_id=stage_id,
            name=stage_name,
            status="running",
            start_time=datetime.now()
        )
        
        self.current_progress.current_stage = stage_id
        self.current_progress.stages.append(step)
        self._update_overall_progress()
        self._save_progress()
        return step
    
    def update_stage(
        self,
        stage_id: str,
        status: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        output_files: Optional[List[str]] = None
    ) -> None:
        """Update stage status and details"""
        if not self.current_progress:
            return
        
        step = self._get_step(stage_id)
        if not step:
            return
        
        if status:
            step.status = status
            if status == "completed":
                step.end_time = datetime.now()
            elif status == "failed":
                step.end_time = datetime.now()
        
        if details:
            step.details.update(details)
        
        if output_files:
            step.output_files.extend(output_files)
            # Remove duplicates while preserving order
            seen = set()
            step.output_files = [f for f in step.output_files if not (f in seen or seen.add(f))]
        
        self._update_overall_progress()
        self._save_progress()
    
    def get_progress_markdown(self) -> str:
        """Generate markdown representation of progress"""
        if not self.current_progress:
            return "## 工作流进度\n\n暂无活动工作流"
        
        lines = []
        lines.append("## 📊 工作流进度")
        lines.append("")
        
        # Overall progress
        progress_pct = int(self.current_progress.overall_progress * 100)
        progress_bar_length = 20
        filled = progress_pct // 5
        empty = progress_bar_length - filled
        progress_bar = "█" * filled + "░" * empty
        lines.append(f"**总体进度**: {progress_pct}% `{progress_bar}`")
        lines.append("")
        
        # Current stage
        if self.current_progress.current_stage:
            current_step = self._get_step(self.current_progress.current_stage)
            if current_step:
                status_icon = {
                    "pending": "⏳",
                    "running": "🔄",
                    "completed": "✅",
                    "failed": "❌"
                }.get(current_step.status, "❓")
                lines.append(f"**当前阶段**: {status_icon} {current_step.name} ({current_step.status})")
                lines.append("")
        
        # Stage list
        lines.append("### 阶段详情")
        lines.append("")
        
        for step in self.current_progress.stages:
            status_icon = {
                "pending": "⏳",
                "running": "🔄",
                "completed": "✅",
                "failed": "❌"
            }.get(step.status, "❓")
            
            lines.append(f"{status_icon} **{step.name}** (`{step.step_id}`)")
            
            if step.status == "running" and step.details:
                current_action = step.details.get('current_action', '执行中...')
                lines.append(f"   - {current_action}")
            
            if step.output_files:
                lines.append("   - 生成文件:")
                for file in step.output_files:
                    lines.append(f"     - `{file}`")
            
            if step.end_time and step.start_time:
                duration = (step.end_time - step.start_time).total_seconds()
                lines.append(f"   - 耗时: {duration:.1f}秒")
            elif step.start_time:
                duration = (datetime.now() - step.start_time).total_seconds()
                lines.append(f"   - 已运行: {duration:.1f}秒")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _get_step(self, stage_id: str) -> Optional[ProgressStep]:
        """Get step by stage ID"""
        if not self.current_progress:
            return None
        return next((s for s in self.current_progress.stages if s.step_id == stage_id), None)
    
    def _update_overall_progress(self) -> None:
        """Update overall progress percentage"""
        if not self.current_progress or not self.current_progress.stages:
            return
        
        total_stages = len(self.current_progress.stages)
        if total_stages == 0:
            return
        
        completed = sum(1 for s in self.current_progress.stages if s.status == "completed")
        self.current_progress.overall_progress = completed / total_stages
    
    def _save_progress(self) -> None:
        """Save progress to file"""
        if not self.current_progress:
            return
        
        try:
            self.progress_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_progress.to_dict(), f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            # Don't fail workflow if progress saving fails
            import warnings
            warnings.warn(f"Failed to save progress: {e}")
    
    def load_progress(self) -> Optional[WorkflowProgress]:
        """Load progress from file"""
        if not self.progress_file.exists():
            return None
        
        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return WorkflowProgress.from_dict(data)
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to load progress: {e}")
            return None

