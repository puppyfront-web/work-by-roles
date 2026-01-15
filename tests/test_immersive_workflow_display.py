"""
Tests for immersive workflow display.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from work_by_roles.core.immersive_workflow_display import ImmersiveWorkflowDisplay


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with temp directory"""
    temp_dir = tempfile.mkdtemp(prefix="test_immersive_")
    workspace = Path(temp_dir)
    temp_path = workspace / ".workflow" / "temp"
    temp_path.mkdir(parents=True, exist_ok=True)
    yield workspace
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_display_stage_start(temp_workspace):
    """Test displaying stage start"""
    display = ImmersiveWorkflowDisplay(temp_workspace)
    display.progress_manager.start_workflow("test_workflow")
    
    msg = display.display_stage_start("stage1", "Stage 1")
    
    assert "开始阶段" in msg
    assert "Stage 1" in msg
    assert "stage1" in msg


def test_display_stage_progress(temp_workspace):
    """Test displaying stage progress"""
    display = ImmersiveWorkflowDisplay(temp_workspace)
    display.progress_manager.start_workflow("test_workflow")
    display.progress_manager.start_stage("stage1", "Stage 1")
    
    msg = display.display_stage_progress("stage1", "执行中", {"workflows": 2})
    
    assert "执行中" in msg
    assert "workflows" in msg


def test_display_document_generated(temp_workspace):
    """Test displaying document generation"""
    display = ImmersiveWorkflowDisplay(temp_workspace)
    display.progress_manager.start_workflow("test_workflow")
    display.progress_manager.start_stage("stage1", "Stage 1")
    
    # Create a test document
    doc_path = temp_workspace / ".workflow" / "temp" / "test.md"
    doc_path.write_text("# Test\n\nContent", encoding='utf-8')
    
    msg = display.display_document_generated("test.md")
    
    assert "文档已生成" in msg
    assert "test.md" in msg


def test_display_code_written(temp_workspace):
    """Test displaying code writing"""
    display = ImmersiveWorkflowDisplay(temp_workspace)
    
    content = "def hello():\n    print('hello')\n"
    msg = display.display_code_written("test.py", content, "stage1", "python_engineering")
    
    assert "代码已编写" in msg
    assert "test.py" in msg
    assert "python_engineering" in msg
    assert "def hello()" in msg


def test_display_quality_check(temp_workspace):
    """Test displaying quality check results"""
    display = ImmersiveWorkflowDisplay(temp_workspace)
    
    quality_report = {
        "passed": False,
        "issues": [
            {"severity": "critical", "message": "Test failed"},
            {"severity": "warning", "message": "Minor issue"}
        ],
        "auto_fixed": 1
    }
    
    msg = display.display_quality_check("stage1", quality_report)
    
    assert "质量检查结果" in msg
    assert "未通过" in msg
    assert "Test failed" in msg
    assert "自动修复" in msg


def test_display_stage_complete(temp_workspace):
    """Test displaying stage completion"""
    display = ImmersiveWorkflowDisplay(temp_workspace)
    display.progress_manager.start_workflow("test_workflow")
    display.progress_manager.start_stage("stage1", "Stage 1")
    
    msg = display.display_stage_complete("stage1", "Summary text")
    
    assert "阶段完成" in msg
    assert "Summary text" in msg
    assert "工作流进度" in msg


def test_display_workflow_status(temp_workspace):
    """Test displaying complete workflow status"""
    display = ImmersiveWorkflowDisplay(temp_workspace)
    display.progress_manager.start_workflow("test_workflow")
    display.progress_manager.start_stage("stage1", "Stage 1")
    display.progress_manager.update_stage("stage1", status="completed")
    
    # Create a test document
    doc_path = temp_workspace / ".workflow" / "temp" / "test.md"
    doc_path.write_text("# Test", encoding='utf-8')
    
    # Track some code changes
    display.code_tracker.track_file_creation("test.py", "content", "stage1")
    
    status = display.display_workflow_status()
    
    assert "工作流进度" in status
    assert "生成的文档" in status
    assert "代码编写过程" in status

