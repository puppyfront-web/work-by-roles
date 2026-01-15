"""
Immersive workflow display for showing complete workflow execution in Cursor IDE conversations.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from .workflow_progress_manager import WorkflowProgressManager
from .document_preview_generator import DocumentPreviewGenerator
from .code_writing_tracker import CodeWritingTracker
from .stream_writer import StreamWriter
from .progress_stream import ProgressStream


class ImmersiveWorkflowDisplay:
    """Immersive workflow display coordinator for Cursor IDE conversations"""
    
    def __init__(self, workspace_path: Path, use_streaming: bool = True):
        self.workspace_path = workspace_path
        self.progress_manager = WorkflowProgressManager(workspace_path)
        self.doc_preview = DocumentPreviewGenerator(workspace_path)
        self.code_tracker = CodeWritingTracker(workspace_path)
        
        # Streaming support
        self.use_streaming = use_streaming
        self.stream_writer = StreamWriter() if use_streaming else None
        self.progress_stream = ProgressStream(self.stream_writer) if use_streaming and self.stream_writer else None
    
    def display_workflow_status(self) -> str:
        """Display complete workflow status"""
        sections = []
        
        # 1. Workflow progress
        sections.append(self.progress_manager.get_progress_markdown())
        sections.append("")
        sections.append("---")
        sections.append("")
        
        # 2. Generated documents
        sections.append("## 📚 生成的文档")
        sections.append("")
        
        documents = self.doc_preview.list_all_documents()
        if documents:
            for doc in documents:
                doc_name = doc['name']
                preview = self.doc_preview.format_document_for_display(
                    doc_name,
                    show_full=False
                )
                sections.append(preview)
                sections.append("")
        else:
            sections.append("暂无生成的文档")
            sections.append("")
        
        sections.append("---")
        sections.append("")
        
        # 3. Code writing process
        sections.append(self.code_tracker.format_code_changes_for_display())
        sections.append("")
        
        return "\n".join(sections)
    
    def display_stage_start(self, stage_id: str, stage_name: str) -> str:
        """Display stage start"""
        self.progress_manager.start_stage(stage_id, stage_name)
        
        lines = []
        lines.append("=" * 60)
        lines.append(f"🚀 开始阶段: {stage_name}")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"**阶段 ID**: `{stage_id}`")
        lines.append(f"**开始时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        content = "\n".join(lines)
        
        # Stream output if enabled
        if self.use_streaming and self.stream_writer:
            self.stream_writer.write_markdown(content, flush=True)
        
        return content
    
    def display_stage_progress(
        self,
        stage_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Display stage progress update"""
        self.progress_manager.update_stage(
            stage_id,
            status="running",
            details={"current_action": action, **(details or {})}
        )
        
        lines = []
        lines.append(f"🔄 **{action}**")
        if details:
            for key, value in details.items():
                if key != "current_action":
                    lines.append(f"   - {key}: {value}")
        lines.append("")
        
        content = "\n".join(lines)
        
        # Stream output if enabled
        if self.use_streaming and self.stream_writer:
            self.stream_writer.write_markdown(content, flush=True)
        
        # Update progress stream if available
        if self.progress_stream:
            self.progress_stream.update_stage(stage_id, "running", details or {})
        
        return content
    
    def display_document_generated(self, document_name: str) -> str:
        """Display document generation"""
        current_progress = self.progress_manager.current_progress
        if current_progress and current_progress.current_stage:
            self.progress_manager.update_stage(
                current_progress.current_stage,
                output_files=[document_name]
            )
        
        preview = self.doc_preview.format_document_for_display(document_name)
        
        lines = []
        lines.append("=" * 60)
        lines.append(f"✅ 文档已生成: {document_name}")
        lines.append("=" * 60)
        lines.append("")
        lines.append(preview)
        lines.append("")
        
        content = "\n".join(lines)
        
        # Stream output if enabled
        if self.use_streaming and self.stream_writer:
            self.stream_writer.write_markdown(content, flush=True)
        
        return content
    
    def display_code_written(
        self,
        file_path: str,
        content: str,
        stage_id: str,
        skill_id: Optional[str] = None
    ) -> str:
        """Display code writing"""
        self.code_tracker.track_file_creation(file_path, content, stage_id, skill_id)
        
        lines = []
        lines.append("=" * 60)
        lines.append(f"💻 代码已编写: {file_path}")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"**文件**: `{file_path}`")
        lines.append(f"**大小**: {len(content)} 字符, {len(content.splitlines())} 行")
        if skill_id:
            lines.append(f"**技能**: {skill_id}")
        lines.append("")
        lines.append("**代码预览**:")
        lines.append("```python")
        # Show first 30 lines of code
        code_lines = content.splitlines()[:30]
        lines.append('\n'.join(code_lines))
        total_lines = len(content.splitlines())
        if total_lines > 30:
            lines.append(f"\n... (还有 {total_lines - 30} 行)")
        lines.append("```")
        lines.append("")
        
        content_str = "\n".join(lines)
        
        # Stream output if enabled
        if self.use_streaming and self.stream_writer:
            self.stream_writer.write_markdown(content_str, flush=True)
        
        return content_str
    
    def display_quality_check(
        self,
        stage_id: str,
        quality_report: Dict[str, Any]
    ) -> str:
        """Display quality check results"""
        lines = []
        lines.append("=" * 60)
        lines.append("🔍 质量检查结果")
        lines.append("=" * 60)
        lines.append("")
        
        if quality_report.get("passed"):
            lines.append("✅ **所有质量门控通过**")
        else:
            lines.append("⚠️ **部分质量门控未通过**")
        
        lines.append("")
        
        if quality_report.get("issues"):
            lines.append("**发现的问题**:")
            for issue in quality_report["issues"]:
                severity = issue.get("severity", "info")
                icon = {
                    "critical": "🔴",
                    "warning": "🟡",
                    "info": "🔵"
                }.get(severity, "⚪")
                lines.append(f"{icon} {issue.get('message', 'Unknown issue')}")
        
        auto_fixed = quality_report.get("auto_fixed", 0)
        if auto_fixed > 0:
            lines.append("")
            lines.append(f"✨ **自动修复**: {auto_fixed} 个问题已自动修复")
        
        lines.append("")
        
        return "\n".join(lines)
    
    def display_stage_complete(
        self,
        stage_id: str,
        summary: Optional[str] = None
    ) -> str:
        """Display stage completion"""
        self.progress_manager.update_stage(stage_id, status="completed")
        
        lines = []
        lines.append("=" * 60)
        lines.append("✅ 阶段完成")
        lines.append("=" * 60)
        lines.append("")
        
        if summary:
            lines.append(summary)
            lines.append("")
        
        # Show current overall progress
        progress = self.progress_manager.get_progress_markdown()
        lines.append(progress)
        lines.append("")
        
        content = "\n".join(lines)
        
        # Stream output if enabled
        if self.use_streaming and self.stream_writer:
            self.stream_writer.write_markdown(content, flush=True)
        
        # Update progress stream if available
        if self.progress_stream:
            current_progress = self.progress_manager.current_progress
            if current_progress:
                self.progress_stream.update(
                    current_progress.overall_progress,
                    f"阶段 {stage_id} 完成"
                )
        
        return content

