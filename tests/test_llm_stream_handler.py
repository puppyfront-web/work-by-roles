"""
Tests for LLM stream handler.
"""

import pytest
from io import StringIO
from work_by_roles.core.stream_writer import StreamWriter
from work_by_roles.core.llm_stream_handler import LLMStreamHandler


@pytest.fixture
def stream_writer():
    """Create a stream writer for testing"""
    output = StringIO()
    return StreamWriter(output_stream=output)


def test_handle_chunk(stream_writer):
    """Test handling a single chunk"""
    handler = LLMStreamHandler(stream_writer)
    
    handler.handle_chunk("Hello")
    handler.handle_chunk(" World")
    
    assert handler.full_response == "Hello World"


def test_handle_stream(stream_writer):
    """Test handling a stream"""
    handler = LLMStreamHandler(stream_writer)
    
    chunks = ["Hello", " ", "World", "!"]
    result = handler.handle_stream(iter(chunks))
    
    assert result == "Hello World!"
    assert handler.full_response == "Hello World!"


def test_format_markdown(stream_writer):
    """Test markdown formatting"""
    handler = LLMStreamHandler(stream_writer, markdown_mode=True)
    
    text = "# Title\n\nContent"
    formatted = handler.format_markdown(text)
    
    assert "# Title" in formatted
    assert "Content" in formatted


def test_extract_text_from_response(stream_writer):
    """Test extracting text from various response formats"""
    handler = LLMStreamHandler(stream_writer)
    
    # String response
    assert handler._extract_text_from_response("Hello") == "Hello"
    
    # Dict response
    assert handler._extract_text_from_response({"content": "Hello"}) == "Hello"
    assert handler._extract_text_from_response({"text": "Hello"}) == "Hello"
    
    # Other object
    assert handler._extract_text_from_response(123) == "123"


def test_reset(stream_writer):
    """Test resetting handler"""
    handler = LLMStreamHandler(stream_writer)
    
    handler.handle_chunk("Hello")
    handler.reset()
    
    assert handler.buffer == ""
    assert handler.full_response == ""

