"""离线提示词用量对比（启发式计数，不调用模型）。"""
from __future__ import annotations

from typing import Any

from wbr.core.contract.compiler import SAFETY_GUARD_HEADER, ContractCompiler, common_text_prefix
from wbr.core.contract.models import RoleContract
from wbr.core.token.meter import HeuristicTokenCounter

# 真实的团队约定，不是为了凑供应商缓存长度。
SAMPLE_SHARED_CONTEXT = (
    "本团队会审共用约定：系统规则优先于角色契约，角色契约优先于子任务；"
    "结论必须能回溯到给定材料，禁止编造证据。"
)


def _prompt_tokens(counter: HeuristicTokenCounter, compiled) -> int:
    return counter.count(compiled.system_prompt) + counter.count(compiled.user_block)


def measure_prompt_savings(
    *,
    name: str,
    coordinator: RoleContract,
    experts: list[RoleContract],
    verifier: RoleContract,
    question: str,
    shared_context: str = SAMPLE_SHARED_CONTEXT,
    counter: HeuristicTokenCounter | None = None,
) -> dict[str, Any]:
    """对比「全员作答、无共享段」与「只跑被分配的专家、并带上共享段」。

    只统计提示侧。未分配专家在旧行为里仍会收到原始问题。
    """
    counter = counter or HeuristicTokenCounter()
    compiler = ContractCompiler()
    if not experts:
        raise ValueError("experts 不能为空")
    assigned = experts[0]
    sub_question = "只评估当前分派的子问题"
    assigned_input = f"{question}\n\n[你的子任务] {sub_question}"
    verifier_input = "复核摘要：专家输出汇总"

    def compile_of(contract: RoleContract, user: str, shared: str):
        return compiler.compile(contract, user, shared_context=shared or None)

    before = 0
    before += _prompt_tokens(counter, compile_of(coordinator, question, ""))
    for expert in experts:
        user = assigned_input if expert.role_id == assigned.role_id else question
        before += _prompt_tokens(counter, compile_of(expert, user, ""))
    before += _prompt_tokens(counter, compile_of(verifier, verifier_input, ""))

    after = 0
    after += _prompt_tokens(counter, compile_of(coordinator, question, shared_context))
    after += _prompt_tokens(counter, compile_of(assigned, assigned_input, shared_context))
    after += _prompt_tokens(counter, compile_of(verifier, verifier_input, shared_context))

    before_systems = [
        compile_of(expert, assigned_input, "").system_prompt for expert in experts
    ]
    after_systems = [
        compile_of(expert, assigned_input, shared_context).system_prompt for expert in experts
    ]
    prefix_before = common_text_prefix(before_systems)
    prefix_after = common_text_prefix(after_systems)
    return {
        "team": name,
        "experts": len(experts),
        "assigned_experts": 1,
        "calls_before": 2 + len(experts),
        "calls_after": 3,
        "prompt_tokens_before": before,
        "prompt_tokens_after": after,
        "prompt_tokens_saved": before - after,
        "shared_prefix_tokens_before": counter.count(prefix_before),
        "shared_prefix_tokens_after": counter.count(prefix_after),
        "safety_header_tokens": counter.count(SAFETY_GUARD_HEADER),
        "prefix_includes_shared_context": shared_context in prefix_after,
        "max_completion_tokens": {
            contract.role_id: contract.token_quota.max_completion_tokens
            for contract in (coordinator, *experts, verifier)
        },
    }
