"""契约 → LangGraph Message 映射（SPEC-003 §1.1）。"""
from __future__ import annotations

from typing import Any

from wbr.adapters.langgraph.base import require_langchain_core
from wbr.core.contract.compiler import ContractCompiler
from wbr.core.contract.models import RoleContract


def contract_to_messages(
    contract: RoleContract,
    user_input: str,
    *,
    evidence: list[str] | None = None,
    history: list[dict[str, str]] | None = None,
) -> list[Any]:
    """编译契约并转换为 [SystemMessage, *history, HumanMessage] 序列。"""
    require_langchain_core()
    from langchain_core.messages import HumanMessage, SystemMessage

    compiled = ContractCompiler().compile(contract, user_input, evidence=evidence, history=history)
    messages: list[Any] = [SystemMessage(content=compiled.system_prompt)]
    if history:
        for h in history:
            role = h.get("role", "user")
            content = h.get("content", "")
            messages.append(HumanMessage(content=content) if role == "user" else SystemMessage(content=content))
    messages.append(HumanMessage(content=compiled.user_block))
    return messages
