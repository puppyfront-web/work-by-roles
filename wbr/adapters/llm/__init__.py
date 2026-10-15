"""LLM 接入适配（Adapter 层）：OpenAI 兼容端点 /chat/completions。"""
from wbr.adapters.llm.openai_compat import OpenAICompatInvoker

__all__ = ["OpenAICompatInvoker"]
