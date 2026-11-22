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
    """一次模型调用的用量。

    cache_scope:
    - included: cached_prompt_tokens 已包含在 prompt_tokens 内（OpenAI / DeepSeek）
    - additional: 缓存读写是 prompt_tokens 之外的增量（Anthropic cache_read / cache_creation）
    - local: 本地契约缓存命中，prompt/completion 为实际计费（通常为 0），cached_* 为省下的用量
    - unknown: 供应商未报告缓存字段
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_prompt_tokens: int = 0
    cache_write_tokens: int = 0
    cache_miss_tokens: int = 0
    cache_scope: str = "unknown"

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def uncached_prompt_tokens(self) -> int:
        if self.cache_scope == "included":
            return max(0, self.prompt_tokens - self.cached_prompt_tokens)
        if self.cache_scope == "local":
            return 0
        return self.prompt_tokens

    def estimate_cost(
        self,
        *,
        input_price: float,
        output_price: float,
        cached_input_price: float | None = None,
        cache_write_price: float | None = None,
    ) -> dict[str, float]:
        """按调用方给出的「每 token 单价」估算费用与缓存节省。

        不内置厂商价目。baseline_total 是缓存命中部分也按输入全价计的对照。
        """
        cached_price = input_price if cached_input_price is None else cached_input_price
        write_price = input_price if cache_write_price is None else cache_write_price
        if self.cache_scope == "additional":
            fresh = self.prompt_tokens
            cached = self.cached_prompt_tokens
            write = self.cache_write_tokens
            baseline_input_tokens = fresh + cached + write
        elif self.cache_scope == "local":
            fresh = 0
            cached = self.cached_prompt_tokens
            write = 0
            baseline_input_tokens = cached
        elif self.cache_scope == "included":
            cached = min(self.cached_prompt_tokens, self.prompt_tokens)
            fresh = self.prompt_tokens - cached
            write = self.cache_write_tokens
            baseline_input_tokens = self.prompt_tokens + write
        else:
            fresh = self.prompt_tokens
            cached = 0
            write = 0
            baseline_input_tokens = self.prompt_tokens
        input_cost = fresh * input_price + cached * cached_price + write * write_price
        output_cost = self.completion_tokens * output_price
        total = input_cost + output_cost
        baseline = baseline_input_tokens * input_price + output_cost
        return {
            "input": input_cost,
            "output": output_cost,
            "total": total,
            "baseline_total": baseline,
            "savings": baseline - total,
        }


def parse_provider_usage(usage_data: dict[str, Any] | None) -> TokenUsage:
    """从供应商 usage 对象提取用量，保留缓存命中字段。

    识别：
    - OpenAI: prompt_tokens_details.cached_tokens（计入 prompt_tokens）
    - DeepSeek: prompt_cache_hit_tokens / prompt_cache_miss_tokens（计入 prompt_tokens）
    - Anthropic: cache_read_input_tokens / cache_creation_input_tokens（相对 input_tokens 另计）
    """
    data = usage_data or {}
    has_prompt = "prompt_tokens" in data or "input_tokens" in data
    prompt = int(data.get("prompt_tokens") or data.get("input_tokens") or 0)
    completion = int(data.get("completion_tokens") or data.get("output_tokens") or 0)
    details = data.get("prompt_tokens_details") or {}
    if not isinstance(details, dict):
        details = {}
    cached = int(details.get("cached_tokens") or 0)
    miss = int(data.get("prompt_cache_miss_tokens") or 0)
    write = int(data.get("cache_creation_input_tokens") or 0)
    anthropic_read = int(data.get("cache_read_input_tokens") or 0)
    deepseek_hit = int(data.get("prompt_cache_hit_tokens") or 0)

    if anthropic_read or write:
        scope = "additional"
        cached = anthropic_read or cached
    elif cached or deepseek_hit or miss:
        scope = "included"
        cached = cached or deepseek_hit
        if not has_prompt:
            prompt = cached + miss
    else:
        scope = "unknown"
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        cached_prompt_tokens=cached,
        cache_write_tokens=write,
        cache_miss_tokens=miss,
        cache_scope=scope,
    )


def completion_cap(contract: RoleContract, override: int | None = None) -> int:
    """契约输出上限。override 用于预算把补全额度再收紧。"""
    if override is not None:
        return override
    return contract.token_quota.max_completion_tokens


class ModelRequest(BaseModel):
    role_contract: RoleContract
    compiled_prompt: CompiledPrompt
    trace_id: str = ""
    memory_snapshot: dict[str, Any] = Field(default_factory=dict)
    max_tokens: int | None = None


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
