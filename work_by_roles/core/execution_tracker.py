"""
Execution tracker for skill execution history and statistics.
Following Single Responsibility Principle - tracks execution history only.
"""

import json
import yaml
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .models import SkillExecution


@dataclass
class ExecutionTracker:
    """Tracks skill execution history and statistics"""
    
    def __init__(self):
        self.executions: List[SkillExecution] = []
    
    def record_execution(self, skill_execution: SkillExecution) -> None:
        """Record a skill execution"""
        self.executions.append(skill_execution)
    
    def get_skill_history(self, skill_id: str) -> List[SkillExecution]:
        """Get execution history for a specific skill"""
        return [e for e in self.executions if e.skill_id == skill_id]
    
    def get_success_rate(self, skill_id: str) -> float:
        """Calculate success rate for a skill"""
        history = self.get_skill_history(skill_id)
        if not history:
            return 0.0
        successful = sum(1 for e in history if e.status == "success")
        return successful / len(history)
    
    def get_avg_execution_time(self, skill_id: str) -> float:
        """Calculate average execution time for a skill"""
        history = self.get_skill_history(skill_id)
        if not history:
            return 0.0
        total_time = sum(e.execution_time for e in history)
        return total_time / len(history)
    
    def get_total_executions(self, skill_id: Optional[str] = None) -> int:
        """Get total number of executions, optionally filtered by skill_id"""
        if skill_id:
            return len(self.get_skill_history(skill_id))
        return len(self.executions)
    
    def export_trace(self, format: str = "json") -> str:
        """Export execution trace in specified format"""
        if format == "json":
            executions_dict = [
                {
                    "skill_id": e.skill_id,
                    "input": e.input,
                    "output": e.output,
                    "status": e.status,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                    "execution_time": e.execution_time,
                    "timestamp": e.timestamp.isoformat(),
                    "retry_count": e.retry_count,
                    "stage_id": e.stage_id,
                    "role_id": e.role_id,
                }
                for e in self.executions
            ]
            return json.dumps(executions_dict, indent=2, default=str)
        elif format == "yaml":
            executions_dict = [
                {
                    "skill_id": e.skill_id,
                    "input": e.input,
                    "output": e.output,
                    "status": e.status,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                    "execution_time": e.execution_time,
                    "timestamp": e.timestamp.isoformat(),
                    "retry_count": e.retry_count,
                    "stage_id": e.stage_id,
                    "role_id": e.role_id,
                }
                for e in self.executions
            ]
            return yaml.dump(executions_dict, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics"""
        skill_ids = set(e.skill_id for e in self.executions)
        skills_stats: Dict[str, Any] = {}
        stats: Dict[str, Any] = {
            "total_executions": len(self.executions),
            "unique_skills": len(skill_ids),
            "skills": skills_stats
        }
        
        for skill_id in skill_ids:
            history = self.get_skill_history(skill_id)
            skills_stats[skill_id] = {
                "total_executions": len(history),
                "success_rate": self.get_success_rate(skill_id),
                "avg_execution_time": self.get_avg_execution_time(skill_id),
                "total_retries": sum(e.retry_count for e in history),
            }
        
        return stats

