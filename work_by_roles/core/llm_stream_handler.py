"""
LLM stream handler for processing streaming LLM responses.
"""

import re
from typing import Optional, Iterator, Any
from .stream_writer import StreamWriter


class LLMStreamHandler:
    """Handler for streaming LLM responses"""
    
    def __init__(self, stream_writer: StreamWriter, markdown_mode: bool = True, role_name: Optional[str] = None):
        """
        Initialize LLM stream handler.
        
        Args:
            stream_writer: Stream writer instance
            markdown_mode: Whether to format output as markdown
            role_name: Optional role name to prefix output
        """
        self.stream_writer = stream_writer
        self.markdown_mode = markdown_mode
        self.role_name = role_name
        self.buffer = ""
        self.full_response = ""
    
    def handle_chunk(self, chunk: str) -> None:
        """
        Handle a single response chunk.
        
        Args:
            chunk: Text chunk from LLM
        """
        self.buffer += chunk
        self.full_response += chunk
        
        # Try to extract meaningful text (skip control characters)
        display_chunk = self._clean_chunk(chunk)
        if display_chunk:
            if self.markdown_mode:
                display_chunk = self._format_markdown_chunk(display_chunk)
            
            # 如果有角色名称，在流式输出中添加标识（仅在每行开始时添加）
            if self.role_name and display_chunk.strip():
                # 检查是否是行首（buffer 为空或最后一个字符是换行）
                if not self.buffer.rstrip() or self.buffer.rstrip()[-1] == '\n':
                    display_chunk = f"[{self.role_name}] {display_chunk}"
            
            self.stream_writer.write(display_chunk, flush=True)
    
    def handle_stream(self, stream: Iterator[str]) -> str:
        """
        Handle a complete streaming response.
        
        Args:
            stream: Iterator of text chunks
            
        Returns:
            Complete response text
        """
        self.buffer = ""
        self.full_response = ""
        
        try:
            for chunk in stream:
                self.handle_chunk(chunk)
        except Exception as e:
            self.stream_writer.writeline(f"\n\n⚠️ Stream error: {e}", flush=True)
        
        # Final newline
        self.stream_writer.writeline("", flush=True)
        
        return self.full_response
    
    def handle_llm_response(
        self,
        llm_client: Any,
        prompt: str,
        use_streaming: bool = True
    ) -> str:
        """
        Handle LLM response with optional streaming.
        
        Args:
            llm_client: LLM client instance
            prompt: Prompt to send
            use_streaming: Whether to use streaming if available
            
        Returns:
            Complete response text
        """
        # Check if LLM client supports streaming
        if use_streaming and hasattr(llm_client, 'stream'):
            try:
                stream = llm_client.stream(prompt)
                return self.handle_stream(stream)
            except Exception:
                # Fall back to non-streaming
                pass
        
        # Non-streaming fallback
        if hasattr(llm_client, 'chat'):
            response = llm_client.chat([{"role": "user", "content": prompt}])
        elif hasattr(llm_client, 'complete'):
            response = llm_client.complete(prompt)
        elif callable(llm_client):
            response = llm_client(prompt)
        else:
            raise ValueError("LLM client interface not supported")
        
        # Format and display
        response_text = self._extract_text_from_response(response)
        if self.markdown_mode:
            response_text = self.format_markdown(response_text)
        
        self.stream_writer.writeline(response_text, flush=True)
        return response_text
    
    def _clean_chunk(self, chunk: str) -> str:
        """Clean chunk of control characters"""
        # Remove null bytes and other control characters (except newlines)
        cleaned = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', chunk)
        return cleaned
    
    def _format_markdown_chunk(self, chunk: str) -> str:
        """Format chunk as markdown (basic formatting)"""
        # For now, just return as-is
        # Could add more sophisticated markdown formatting here
        return chunk
    
    def format_markdown(self, text: str) -> str:
        """
        Format complete text as markdown.
        
        Args:
            text: Text to format
            
        Returns:
            Formatted markdown text
        """
        # Basic markdown formatting
        # Ensure code blocks are properly formatted
        lines = text.split('\n')
        formatted_lines = []
        in_code_block = False
        
        for line in lines:
            # Detect code blocks
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                formatted_lines.append(line)
            elif in_code_block:
                formatted_lines.append(line)
            else:
                # Format headers, lists, etc.
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def _extract_text_from_response(self, response: Any) -> str:
        """Extract text from various LLM response formats"""
        if isinstance(response, str):
            return response
        elif isinstance(response, dict):
            return response.get('content', response.get('text', str(response)))
        else:
            return str(response)
    
    def get_full_response(self) -> str:
        """Get the complete accumulated response"""
        return self.full_response
    
    def reset(self) -> None:
        """Reset buffer and full response"""
        self.buffer = ""
        self.full_response = ""

