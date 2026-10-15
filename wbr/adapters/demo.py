"""Schema 驱动的通用演示 Invoker：按契约输出 Schema 生成合法形状的确定性回放。

任意官方模板 / 用户自建团队无需逐字段适配，演示会审即可零违例跑通。
无外部 LLM 依赖；禁止在任何路径发起网络调用。
"""
from __future__ import annotations

import json
from typing import Any

from wbr.core.contract.models import RoleType
from wbr.core.orchestration.invoker import ModelRequest, ModelResponse, TokenUsage

_DEMO_TEXT = "演示内容：离线演示模式的确定性占位输出，不代表真实模型结论。"


def build_demo_payload(schema: Any, depth: int = 0) -> Any:
    """按 JSON Schema 递归生成满足 required 约束的演示值。

    enum 取首项；number 取 0.85；integer 取 1；boolean 取 True；字符串用占位文本
    并保证满足 minLength；数组生成单元素；对象仅填充 required 字段。
    """
    if not isinstance(schema, dict) or depth > 4:
        return _DEMO_TEXT
    schema_type = schema.get("type")
    if schema_type == "object":
        required = schema.get("required") or []
        return {
            name: build_demo_payload(prop, depth + 1)
            for name, prop in (schema.get("properties") or {}).items()
            if name in required
        }
    if schema_type == "array":
        items = schema.get("items")
        return [build_demo_payload(items, depth + 1)] if isinstance(items, dict) else []
    if schema_type in ("number", "integer"):
        return 1 if schema_type == "integer" else 0.85
    if schema_type == "boolean":
        return True
    if schema_type == "string":
        enum = schema.get("enum")
        if enum:
            return enum[0]
        min_len = schema.get("minLength") or 0
        text = _DEMO_TEXT
        return text if len(text) >= min_len else text.ljust(min_len, "示")
    return _DEMO_TEXT


class SchemaDemoInvoker:
    """按契约 Schema 生成确定性演示输出；协调者自动分派全部专家。

    expert_ids 供协调者生成 assignments（由调用方在构造会审后注入）。
    """

    def __init__(self, question: str = "（未提供问题）") -> None:
        self.question = question
        self.expert_ids: list[str] = []

    def invoke(self, request: ModelRequest) -> ModelResponse:
        contract = request.role_contract
        question = self.question
        if isinstance(request.memory_snapshot, dict):
            question = request.memory_snapshot.get("__question__", question)

        if contract.role_type == RoleType.COORDINATOR:
            payload: dict[str, Any] = {"assignments": [
                {"expert_role_id": cid, "sub_question": f"处理: {question}"}
                for cid in sorted(self.expert_ids)
            ]}
        else:
            payload = build_demo_payload(contract.output_spec.schema_)
            if isinstance(payload, dict):
                props = (contract.output_spec.schema_ or {}).get("properties") or {}
                if "final_answer" in props:
                    payload["final_answer"] = f"演示综合结论: {question}"
                if "comments" in payload:
                    payload["comments"] = "演示复核通过"

        return ModelResponse(
            text=json.dumps(payload, ensure_ascii=False),
            usage=TokenUsage(prompt_tokens=100, completion_tokens=60),
            raw=payload,
        )
