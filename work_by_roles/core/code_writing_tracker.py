"""
Code writing tracker for tracking code file creation and modification during workflow execution.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import difflib


class CodeWritingTracker:
    """Tracks code file creation and modification during workflow execution"""
    
    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.writing_history: List[Dict[str, Any]] = []
    
    def track_file_creation(
        self,
        file_path: str,
        content: str,
        stage_id: str,
        skill_id: Optional[str] = None
    ) -> None:
        """Track file creation"""
        full_path = self.workspace_path / file_path
        self.writing_history.append({
            "action": "create",
            "file": file_path,
            "absolute_path": str(full_path),
            "stage": stage_id,
            "skill": skill_id,
            "timestamp": datetime.now().isoformat(),
            "size": len(content),
            "lines": len(content.split('\n'))
        })
    
    def track_file_modification(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
        stage_id: str
    ) -> None:
        """Track file modification with diff"""
        full_path = self.workspace_path / file_path
        
        # Generate diff
        diff_lines = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=file_path,
            tofile=file_path,
            lineterm=''
        ))
        
        # Count changes
        additions = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))
        
        # Get preview of diff (first 20 lines)
        diff_preview = '\n'.join(diff_lines[:20])
        if len(diff_lines) > 20:
            diff_preview += f"\n... (还有 {len(diff_lines) - 20} 行差异)"
        
        self.writing_history.append({
            "action": "modify",
            "file": file_path,
            "absolute_path": str(full_path),
            "stage": stage_id,
            "timestamp": datetime.now().isoformat(),
            "changes": additions + deletions,
            "additions": additions,
            "deletions": deletions,
            "diff_preview": diff_preview
        })
    
    def get_recent_changes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent code changes"""
        return sorted(
            self.writing_history,
            key=lambda x: x['timestamp'],
            reverse=True
        )[:limit]
    
    def get_changes_by_stage(self, stage_id: str) -> List[Dict[str, Any]]:
        """Get all changes for a specific stage"""
        return [
            change for change in self.writing_history
            if change.get('stage') == stage_id
        ]
    
    def format_code_changes_for_display(self, limit: int = 5) -> str:
        """Format code changes for display"""
        changes = self.get_recent_changes(limit)
        
        if not changes:
            return "📝 **代码编写过程**\n\n暂无代码变更记录"
        
        lines = []
        lines.append("📝 **代码编写过程**")
        lines.append("")
        
        for change in changes:
            action_icon = {
                "create": "✨",
                "modify": "📝",
                "delete": "🗑️"
            }.get(change['action'], "📄")
            
            lines.append(f"{action_icon} **{change['file']}**")
            lines.append(f"   - 操作: {change['action']}")
            lines.append(f"   - 阶段: {change.get('stage', 'unknown')}")
            
            if change.get('skill'):
                lines.append(f"   - 技能: {change['skill']}")
            
            if change['action'] == 'create':
                lines.append(f"   - 大小: {change['size']} 字符, {change['lines']} 行")
            elif change['action'] == 'modify':
                lines.append(f"   - 变更: +{change.get('additions', 0)} -{change.get('deletions', 0)} 行")
            
            # Format timestamp
            try:
                ts = datetime.fromisoformat(change['timestamp'])
                lines.append(f"   - 时间: {ts.strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception:
                lines.append(f"   - 时间: {change['timestamp']}")
            
            lines.append("")
        
        return "\n".join(lines)

