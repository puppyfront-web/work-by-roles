"""
Progress stream for real-time progress updates.
"""

from typing import Dict, Optional, Any
from datetime import datetime
from .stream_writer import StreamWriter


class ProgressStream:
    """Real-time progress stream updater"""
    
    def __init__(self, stream_writer: StreamWriter):
        """
        Initialize progress stream.
        
        Args:
            stream_writer: Stream writer instance
        """
        self.stream_writer = stream_writer
        self.current_progress = 0.0
        self.last_update: Optional[datetime] = None
        self.last_message = ""
    
    def update(self, percentage: float, message: str = "", flush: bool = True) -> None:
        """
        Update progress percentage.
        
        Args:
            percentage: Progress percentage (0.0-1.0)
            message: Optional progress message
            flush: Whether to flush immediately
        """
        self.current_progress = max(0.0, min(1.0, percentage))
        self.last_update = datetime.now()
        
        if message:
            self.last_message = message
        
        # Generate progress bar
        progress_bar = self._generate_progress_bar(self.current_progress)
        pct_text = f"{int(self.current_progress * 100)}%"
        
        if message:
            progress_text = f"\r{message} {progress_bar} {pct_text}"
        else:
            progress_text = f"\r{progress_bar} {pct_text}"
        
        self.stream_writer.write(progress_text, flush=flush)
    
    def update_stage(
        self,
        stage_id: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update stage progress.
        
        Args:
            stage_id: Stage ID
            status: Stage status
            details: Optional details dictionary
        """
        status_icon = {
            "pending": "⏳",
            "running": "🔄",
            "completed": "✅",
            "failed": "❌"
        }.get(status, "❓")
        
        message = f"{status_icon} {stage_id}: {status}"
        if details:
            action = details.get('current_action', '')
            if action:
                message += f" - {action}"
        
        self.stream_writer.writeline(message, flush=True)
    
    def complete(self, message: str = "Complete") -> None:
        """
        Mark progress as complete.
        
        Args:
            message: Completion message
        """
        # Clear progress line and write completion
        if self.stream_writer.is_interactive():
            self.stream_writer.clear_line()
        self.stream_writer.writeline(f"✅ {message} 100%", flush=True)
    
    def _generate_progress_bar(self, percentage: float, length: int = 20) -> str:
        """
        Generate a text progress bar.
        
        Args:
            percentage: Progress percentage (0.0-1.0)
            length: Bar length in characters
            
        Returns:
            Progress bar string
        """
        filled = int(percentage * length)
        empty = length - filled
        return "█" * filled + "░" * empty
    
    def write_status(self, status: str, flush: bool = True) -> None:
        """
        Write a status message (non-progress update).
        
        Args:
            status: Status message
            flush: Whether to flush immediately
        """
        self.stream_writer.writeline(status, flush=flush)

