"""
Tests for document preview generator.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from work_by_roles.core.document_preview_generator import DocumentPreviewGenerator


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with temp directory"""
    temp_dir = tempfile.mkdtemp(prefix="test_doc_preview_")
    workspace = Path(temp_dir)
    temp_path = workspace / ".workflow" / "temp"
    temp_path.mkdir(parents=True, exist_ok=True)
    yield workspace
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_document_preview_nonexistent(temp_workspace):
    """Test preview for non-existent document"""
    generator = DocumentPreviewGenerator(temp_workspace)
    preview = generator.get_document_preview("nonexistent.md")
    
    assert preview["exists"] is False
    assert "尚未生成" in preview["message"]


def test_document_preview_existing(temp_workspace):
    """Test preview for existing document"""
    generator = DocumentPreviewGenerator(temp_workspace)
    
    # Create a test document
    doc_path = temp_workspace / ".workflow" / "temp" / "test.md"
    content = "# Test Document\n\nThis is a test document.\n" * 10
    doc_path.write_text(content, encoding='utf-8')
    
    preview = generator.get_document_preview("test.md")
    
    assert preview["exists"] is True
    assert preview["name"] == "test.md"
    assert preview["total_lines"] > 0
    assert len(preview["preview"]) > 0


def test_document_preview_truncation(temp_workspace):
    """Test document preview truncation"""
    generator = DocumentPreviewGenerator(temp_workspace)
    
    # Create a long document
    doc_path = temp_workspace / ".workflow" / "temp" / "long.md"
    content = "\n".join([f"Line {i}" for i in range(100)])
    doc_path.write_text(content, encoding='utf-8')
    
    preview = generator.get_document_preview("long.md", max_lines=50)
    
    assert preview["exists"] is True
    assert preview["truncated"] is True
    assert "还有" in preview["preview"]


def test_document_preview_format_display(temp_workspace):
    """Test formatting document for display"""
    generator = DocumentPreviewGenerator(temp_workspace)
    
    # Create a test document
    doc_path = temp_workspace / ".workflow" / "temp" / "test.md"
    doc_path.write_text("# Test\n\nContent", encoding='utf-8')
    
    formatted = generator.format_document_for_display("test.md")
    
    assert "test.md" in formatted
    assert "路径" in formatted
    assert "大小" in formatted
    assert "Test" in formatted


def test_list_all_documents(temp_workspace):
    """Test listing all documents"""
    generator = DocumentPreviewGenerator(temp_workspace)
    
    # Create multiple documents
    for i in range(3):
        doc_path = temp_workspace / ".workflow" / "temp" / f"doc{i}.md"
        doc_path.write_text(f"Content {i}", encoding='utf-8')
    
    docs = generator.list_all_documents()
    
    assert len(docs) == 3
    assert all(doc["name"].startswith("doc") for doc in docs)
    assert all("size" in doc for doc in docs)
    assert all("last_modified" in doc for doc in docs)

