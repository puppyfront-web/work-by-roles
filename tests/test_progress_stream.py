"""
Tests for progress stream.
"""

import pytest
from io import StringIO
from work_by_roles.core.stream_writer import StreamWriter
from work_by_roles.core.progress_stream import ProgressStream


@pytest.fixture
def stream_writer():
    """Create a stream writer for testing"""
    output = StringIO()
    return StreamWriter(output_stream=output)


def test_update_progress(stream_writer):
    """Test updating progress"""
    progress = ProgressStream(stream_writer)
    
    progress.update(0.5, "Processing")
    
    # Progress should be updated
    assert progress.current_progress == 0.5
    assert progress.last_message == "Processing"


def test_update_stage(stream_writer):
    """Test updating stage progress"""
    progress = ProgressStream(stream_writer)
    
    progress.update_stage("stage1", "running", {"current_action": "Executing"})
    
    # Should have written to stream
    content = stream_writer.output_stream.getvalue()
    assert "stage1" in content or "running" in content


def test_complete(stream_writer):
    """Test marking progress as complete"""
    progress = ProgressStream(stream_writer)
    
    progress.complete("Done")
    
    content = stream_writer.output_stream.getvalue()
    assert "Done" in content or "100%" in content


def test_generate_progress_bar(stream_writer):
    """Test progress bar generation"""
    progress = ProgressStream(stream_writer)
    
    bar = progress._generate_progress_bar(0.5, length=10)
    assert len(bar) == 10
    assert "█" in bar
    assert "░" in bar


def test_write_status(stream_writer):
    """Test writing status message"""
    progress = ProgressStream(stream_writer)
    
    progress.write_status("Status message")
    
    content = stream_writer.output_stream.getvalue()
    assert "Status message" in content

