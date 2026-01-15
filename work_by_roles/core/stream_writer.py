"""
Stream writer for real-time output in Cursor IDE conversations.
"""

import sys
from typing import Optional, TextIO
from pathlib import Path


class StreamWriter:
    """Stream writer for real-time output with immediate flushing"""
    
    def __init__(self, output_stream: Optional[TextIO] = None, buffer_size: int = 1024):
        """
        Initialize stream writer.
        
        Args:
            output_stream: Output stream (defaults to sys.stdout)
            buffer_size: Buffer size in bytes (for future use)
        """
        self.output_stream = output_stream or sys.stdout
        self.buffer_size = buffer_size
        self.flush_immediately = True  # Cursor IDE needs immediate flushing
        self.is_tty = hasattr(self.output_stream, 'isatty') and self.output_stream.isatty()
    
    def write(self, text: str, flush: bool = True) -> None:
        """
        Write text to stream.
        
        Args:
            text: Text to write
            flush: Whether to flush immediately (default: True for Cursor IDE)
        """
        self.output_stream.write(text)
        if flush or self.flush_immediately:
            self.output_stream.flush()
    
    def writeline(self, line: str, flush: bool = True) -> None:
        """
        Write a line with newline.
        
        Args:
            line: Line to write
            flush: Whether to flush immediately
        """
        self.write(line + '\n', flush=flush)
    
    def flush(self) -> None:
        """Flush the output stream"""
        self.output_stream.flush()
    
    def clear_line(self) -> None:
        """
        Clear current line (for progress updates).
        Uses ANSI escape codes if TTY, otherwise does nothing.
        """
        if self.is_tty:
            # ANSI escape code: \r to return to start, \033[K to clear to end
            self.write('\r\033[K', flush=True)
        # If not TTY, do nothing (can't clear line in non-interactive mode)
    
    def write_progress(self, message: str, percentage: Optional[float] = None) -> None:
        """
        Write progress message with optional percentage.
        
        Args:
            message: Progress message
            percentage: Optional percentage (0.0-1.0)
        """
        if percentage is not None:
            pct = int(percentage * 100)
            self.write(f"\r{message} [{pct}%]", flush=True)
        else:
            self.write(f"\r{message}", flush=True)
    
    def write_markdown(self, content: str, flush: bool = True) -> None:
        """
        Write markdown content (already formatted).
        
        Args:
            content: Markdown content
            flush: Whether to flush immediately
        """
        self.write(content, flush=flush)
    
    def is_interactive(self) -> bool:
        """Check if output is interactive (TTY)"""
        return self.is_tty

