"""模型调用协议与会审数据结构（SPEC-002 §6 / D-06）。

Core 永不发起真实网络调用；真实模型接入位于 Adapter 层。
ScriptedInvoker 提供确定性回放（示例/测试/离线演示用）。
"""
from __future__ import annotations

import json
import re
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from wbr.core.contract.compiler import CompiledPrompt
from wbr.core.contract.models import RoleContract


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class ModelRequest(BaseModel):
    role_contract: RoleContract
    compiled_prompt: CompiledPrompt
    trace_id: str = ""
    memory_snapshot: dict[str, Any] = Field(default_factory=dict)


class ModelResponse(BaseModel):
    text: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    raw: Any = None


@runtime_checkable
class ModelInvoker(Protocol):
    def invoke(self, request: ModelRequest) -> ModelResponse: ...


def parse_json_output(text: str) -> dict[str, Any]:
    """从模型输出解析 JSON 对象：容忍 ```json 围栏与前后杂文。"""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        # 尝试截取第一个 { 到最后一个 }
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError(f"输出不是合法 JSON 对象: {text[:120]!r}")
        obj = json.loads(cleaned[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError(f"输出 JSON 不是对象: {type(obj).__name__}")
    return obj


class ScriptedInvoker:
    """确定性脚本 Invoker：按 role_id 回放预设 JSON 输出。

    值可以是 callable(request) -> dict 以支持动态逻辑。
    """

    def __init__(
        self,
        scripts: dict[str, Any],
        *,
        default_usage: tuple[int, int] = (120, 80),
        fail_on: dict[str, Exception] | None = None,
    ) -> None:
        self._scripts = scripts
        self._usage = default_usage
        self._fail_on = fail_on or {}
        self.calls: list[ModelRequest] = []

    def invoke(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        role_id = request.role_contract.role_id
        if role_id in self._fail_on:
            raise self._fail_on[role_id]
        script = self._scripts[role_id]
        payload = script(request) if callable(script) else script
        if isinstance(payload, str):
            text, raw = payload, None
        else:
            text = json.dumps(payload, ensure_ascii=False)
            raw = payload
        return ModelResponse(
            text=text,
            usage=TokenUsage(prompt_tokens=self._usage[0], completion_tokens=self._usage[1]),
            raw=raw,
        )
