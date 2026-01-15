"""
Tests for code writing tracker.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from work_by_roles.core.code_writing_tracker import CodeWritingTracker


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace"""
    temp_dir = tempfile.mkdtemp(prefix="test_code_tracker_")
    workspace = Path(temp_dir)
    yield workspace
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_track_file_creation(temp_workspace):
    """Test tracking file creation"""
    tracker = CodeWritingTracker(temp_workspace)
    
    content = "def hello():\n    print('hello')\n"
    tracker.track_file_creation("test.py", content, "stage1", "python_engineering")
    
    changes = tracker.get_recent_changes(limit=1)
    assert len(changes) == 1
    assert changes[0]["action"] == "create"
    assert changes[0]["file"] == "test.py"
    assert changes[0]["stage"] == "stage1"
    assert changes[0]["skill"] == "python_engineering"
    assert changes[0]["size"] == len(content)
    assert changes[0]["lines"] == 2


def test_track_file_modification(temp_workspace):
    """Test tracking file modification"""
    tracker = CodeWritingTracker(temp_workspace)
    
    old_content = "def hello():\n    print('hello')\n"
    new_content = "def hello():\n    print('hello')\n    print('world')\n"
    
    tracker.track_file_modification("test.py", old_content, new_content, "stage1")
    
    changes = tracker.get_recent_changes(limit=1)
    assert len(changes) == 1
    assert changes[0]["action"] == "modify"
    assert changes[0]["file"] == "test.py"
    assert changes[0]["changes"] > 0
    assert "additions" in changes[0]
    assert "deletions" in changes[0]


def test_get_changes_by_stage(temp_workspace):
    """Test getting changes by stage"""
    tracker = CodeWritingTracker(temp_workspace)
    
    tracker.track_file_creation("file1.py", "content1", "stage1")
    tracker.track_file_creation("file2.py", "content2", "stage2")
    tracker.track_file_creation("file3.py", "content3", "stage1")
    
    stage1_changes = tracker.get_changes_by_stage("stage1")
    assert len(stage1_changes) == 2
    assert all(c["stage"] == "stage1" for c in stage1_changes)


def test_format_code_changes_for_display(temp_workspace):
    """Test formatting code changes for display"""
    tracker = CodeWritingTracker(temp_workspace)
    
    tracker.track_file_creation("test.py", "def hello():\n    pass\n", "stage1")
    
    formatted = tracker.format_code_changes_for_display()
    
    assert "代码编写过程" in formatted
    assert "test.py" in formatted
    assert "stage1" in formatted


def test_get_recent_changes_limit(temp_workspace):
    """Test limiting recent changes"""
    tracker = CodeWritingTracker(temp_workspace)
    
    # Create 10 changes
    for i in range(10):
        tracker.track_file_creation(f"file{i}.py", f"content{i}", "stage1")
    
    recent = tracker.get_recent_changes(limit=5)
    assert len(recent) == 5
    # Should be sorted by timestamp (most recent first)
    assert recent[0]["file"] == "file9.py"

