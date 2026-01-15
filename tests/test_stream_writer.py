"""
Tests for stream writer.
"""

import pytest
import sys
from io import StringIO
from work_by_roles.core.stream_writer import StreamWriter


def test_stream_writer_write():
    """Test basic write functionality"""
    output = StringIO()
    writer = StreamWriter(output_stream=output)
    
    writer.write("Hello")
    writer.flush()
    
    assert output.getvalue() == "Hello"


def test_stream_writer_writeline():
    """Test writeline functionality"""
    output = StringIO()
    writer = StreamWriter(output_stream=output)
    
    writer.writeline("Hello")
    
    assert output.getvalue() == "Hello\n"


def test_stream_writer_auto_flush():
    """Test automatic flushing"""
    output = StringIO()
    writer = StreamWriter(output_stream=output)
    
    writer.write("Hello", flush=True)
    
    # In real scenario, flush would be called
    # Here we just verify the method works
    assert "Hello" in output.getvalue() or output.getvalue() == "Hello"


def test_stream_writer_progress():
    """Test progress writing"""
    output = StringIO()
    writer = StreamWriter(output_stream=output)
    
    writer.write_progress("Processing", 0.5)
    
    # Should contain progress message and percentage
    content = output.getvalue()
    assert "Processing" in content
    assert "50%" in content


def test_stream_writer_markdown():
    """Test markdown writing"""
    output = StringIO()
    writer = StreamWriter(output_stream=output)
    
    markdown = "# Title\n\nContent"
    writer.write_markdown(markdown)
    
    assert markdown in output.getvalue()


def test_stream_writer_is_interactive():
    """Test interactive detection"""
    # With real stdout (TTY)
    writer = StreamWriter()
    # Result depends on actual environment, so just test it doesn't crash
    result = writer.is_interactive()
    assert isinstance(result, bool)

