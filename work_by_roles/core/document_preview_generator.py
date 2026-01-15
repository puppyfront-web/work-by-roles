"""
Document preview generator for displaying generated documents in conversations.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class DocumentPreviewGenerator:
    """Generates previews of documents for display in conversations"""
    
    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.temp_dir = workspace_path / ".workflow" / "temp"
    
    def get_document_preview(
        self,
        document_name: str,
        max_lines: int = 50,
        show_full: bool = False
    ) -> Dict[str, Any]:
        """Get document preview data"""
        doc_path = self.temp_dir / document_name
        
        if not doc_path.exists():
            return {
                "exists": False,
                "message": f"文档 {document_name} 尚未生成"
            }
        
        try:
            content = doc_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            if show_full or len(lines) <= max_lines:
                preview = content
                truncated = False
            else:
                preview = '\n'.join(lines[:max_lines])
                preview += f"\n\n... (还有 {len(lines) - max_lines} 行，使用 `--full` 查看完整内容)"
                truncated = True
            
            stat = doc_path.stat()
            return {
                "exists": True,
                "name": document_name,
                "path": str(doc_path.relative_to(self.workspace_path)),
                "absolute_path": str(doc_path),
                "preview": preview,
                "truncated": truncated,
                "total_lines": len(lines),
                "size": len(content),
                "size_bytes": stat.st_size,
                "last_modified": datetime.fromtimestamp(stat.st_mtime)
            }
        except Exception as e:
            return {
                "exists": False,
                "message": f"读取文档失败: {e}"
            }
    
    def format_document_for_display(
        self,
        document_name: str,
        show_full: bool = False
    ) -> str:
        """Format document for display in conversation"""
        preview_data = self.get_document_preview(document_name, show_full=show_full)
        
        if not preview_data.get("exists"):
            return f"📄 **{document_name}**\n\n{preview_data['message']}"
        
        lines = []
        lines.append(f"📄 **{document_name}**")
        lines.append("")
        lines.append(f"📁 路径: `{preview_data['path']}`")
        lines.append(f"📊 大小: {preview_data['size']} 字符, {preview_data['total_lines']} 行")
        lines.append(f"🕒 最后修改: {preview_data['last_modified'].strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(preview_data['preview'])
        
        if preview_data.get('truncated'):
            lines.append("")
            lines.append(f"💡 提示: 使用 `workflow show-doc {document_name} --full` 查看完整内容")
        
        return "\n".join(lines)
    
    def list_all_documents(self) -> List[Dict[str, Any]]:
        """List all generated documents"""
        if not self.temp_dir.exists():
            return []
        
        documents = []
        try:
            for doc_file in self.temp_dir.glob("*.md"):
                try:
                    stat = doc_file.stat()
                    content = doc_file.read_text(encoding='utf-8')
                    documents.append({
                        "name": doc_file.name,
                        "path": str(doc_file.relative_to(self.workspace_path)),
                        "absolute_path": str(doc_file),
                        "size": stat.st_size,
                        "size_chars": len(content),
                        "lines": len(content.split('\n')),
                        "last_modified": datetime.fromtimestamp(stat.st_mtime)
                    })
                except Exception:
                    # Skip files that can't be read
                    continue
            
            # Sort by last modified time, most recent first
            documents.sort(key=lambda x: x['last_modified'], reverse=True)
        except Exception:
            pass
        
        return documents

