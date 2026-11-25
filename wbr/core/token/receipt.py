"""会审节省回执（savings-receipt-v1）。

同一次会审的反事实基线，不发起第二次模型调用。
费用只在调用方给出单价时计算；未给单价时费用为 0，token 仍可核对。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from wbr.core.orchestration.invoker import TokenUsage

FORMULA_ID = "savings-receipt-v1"

RECEIPT_NOTES = (
    "skipped_unassigned 只计反事实提示 token（与 skip_unassigned_experts=False 同一条用户输入），不估算未发生调用的补全。",
    "专家调用上供应商回报的 cached_prompt_tokens 全部记入 shared_prefix。供应商不按段落拆分，因此不按安全护栏或团队共享上下文的长度再切。供应商回报 0 时该杠杆为 0。",
    "cache_hit 只计本地响应缓存（cache_scope=local），以及协调者与复核人的供应商缓存。本地命中的实际费用按 0 计，因为没有供应商请求。",
    "included 范围内的缓存命中已经含在 prompt_tokens 里，对应的 token 节省为 0，费用仍按未缓存输入单价对比。additional 范围把缓存读与缓存写加进基线 token。",
    "token_budget 跳过的角色不计入节省。协调者未完成时，不估计尚未分派的专家。",
    "未提供单价时费用为 0。cache_write 未单独标价时按输入单价计。",
)

_STEP_RANK = {"coordinator": 0, "expert": 1, "verifier": 2}
_LEVER_ORDER = ("shared_prefix", "skipped_unassigned", "cache_hit")


class UsageFact(BaseModel):
    """一次已经发生的调用（含本地缓存命中）。不含提示词正文。"""

    role_id: str
    step: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_prompt_tokens: int = 0
    cache_write_tokens: int = 0
    cache_scope: str = "unknown"


class UnassignedFact(BaseModel):
    role_id: str
    prompt_tokens: int = 0


class BudgetSkip(BaseModel):
    role_id: str
    step: str


class SavingsPrices(BaseModel):
    input_price: float
    output_price: float
    cached_input_price: float | None = None
    cache_write_price: float | None = None


class SavingsLever(BaseModel):
    id: str
    tokens: int = 0
    cost: float = 0.0
    cached_tokens: int = 0
    roles: list[str] = Field(default_factory=list)


class SavingsReceipt(BaseModel):
    formula: str = FORMULA_ID
    live_run: bool = True
    baseline_tokens: int = 0
    actual_tokens: int = 0
    saved_tokens: int = 0
    baseline_cost: float = 0.0
    actual_cost: float = 0.0
    saved_cost: float = 0.0
    cached_prompt_tokens: int = 0
    prices: dict[str, float | None] = Field(default_factory=dict)
    levers: list[SavingsLever] = Field(default_factory=list)
    calls: list[UsageFact] = Field(default_factory=list)
    unassigned: list[UnassignedFact] = Field(default_factory=list)
    budget_skipped: list[BudgetSkip] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=lambda: list(RECEIPT_NOTES))

    def priced(
        self,
        *,
        input_price: float,
        output_price: float,
        cached_input_price: float | None = None,
        cache_write_price: float | None = None,
    ) -> SavingsReceipt:
        return build_savings_receipt(
            self.calls,
            self.unassigned,
            self.budget_skipped,
            prices=SavingsPrices(
                input_price=input_price,
                output_price=output_price,
                cached_input_price=cached_input_price,
                cache_write_price=cache_write_price,
            ),
            live_run=self.live_run,
        )

    def lever(self, lever_id: str) -> SavingsLever:
        for item in self.levers:
            if item.id == lever_id:
                return item
        return SavingsLever(id=lever_id)


def token_delta(call: UsageFact) -> int:
    """基线比实际多出来的 token。

    included：缓存命中已在 prompt_tokens 内，只有 cache_write 不在计费 token 合计里。
    additional：缓存读和缓存写都在 prompt_tokens 之外。
    local：计费 token 为 0，基线补上当时省下的提示 token。
    """
    cached = _nonneg(call.cached_prompt_tokens)
    write = _nonneg(call.cache_write_tokens)
    if call.cache_scope == "local":
        return cached
    if call.cache_scope == "additional":
        return cached + write
    if call.cache_scope == "included":
        return write
    return 0


def call_costs(call: UsageFact, prices: SavingsPrices | None) -> tuple[float, float]:
    """返回 (actual_cost, saved_cost)。saved_cost = baseline_cost - actual_cost。"""
    if prices is None:
        return 0.0, 0.0
    resolved = _resolve_prices(prices)
    if call.cache_scope == "local":
        return 0.0, _nonneg(call.cached_prompt_tokens) * resolved["input"]
    if call.cache_scope not in ("included", "additional"):
        usage = _usage(call)
        return usage.estimate_cost(**_estimate_kwargs(prices))["total"], 0.0
    estimate = _usage(call).estimate_cost(**_estimate_kwargs(prices))
    return estimate["total"], estimate["savings"]


def build_savings_receipt(
    calls: list[UsageFact],
    unassigned: list[UnassignedFact] | None = None,
    budget_skipped: list[BudgetSkip] | None = None,
    *,
    prices: SavingsPrices | None = None,
    live_run: bool = True,
) -> SavingsReceipt:
    ordered_calls = sorted(calls, key=lambda item: (_STEP_RANK.get(item.step, 9), item.role_id))
    ordered_unassigned = sorted(unassigned or [], key=lambda item: item.role_id)
    ordered_budget = sorted(
        budget_skipped or [],
        key=lambda item: (_STEP_RANK.get(item.step, 9), item.role_id),
    )
    buckets: dict[str, dict[str, Any]] = {
        lever_id: {"tokens": 0, "cost": 0.0, "cached_tokens": 0, "roles": set()}
        for lever_id in _LEVER_ORDER
    }
    actual_tokens = 0
    actual_cost = 0.0
    observed_cached = 0
    for call in ordered_calls:
        actual_tokens += _nonneg(call.prompt_tokens) + _nonneg(call.completion_tokens)
        observed_cached += _nonneg(call.cached_prompt_tokens)
        spent, saved = call_costs(call, prices)
        actual_cost += spent
        lever_id = _lever_for_call(call)
        if lever_id is None:
            continue
        bucket = buckets[lever_id]
        bucket["tokens"] += token_delta(call)
        bucket["cost"] += saved
        bucket["cached_tokens"] += _nonneg(call.cached_prompt_tokens)
        bucket["roles"].add(call.role_id)
    input_price = 0.0 if prices is None else _resolve_prices(prices)["input"]
    for fact in ordered_unassigned:
        prompt = _nonneg(fact.prompt_tokens)
        bucket = buckets["skipped_unassigned"]
        bucket["tokens"] += prompt
        bucket["cost"] += prompt * input_price
        bucket["roles"].add(fact.role_id)
    levers = [
        SavingsLever(
            id=lever_id,
            tokens=buckets[lever_id]["tokens"],
            cost=buckets[lever_id]["cost"],
            cached_tokens=buckets[lever_id]["cached_tokens"],
            roles=sorted(buckets[lever_id]["roles"]),
        )
        for lever_id in _LEVER_ORDER
    ]
    saved_tokens = sum(item.tokens for item in levers)
    saved_cost = sum(item.cost for item in levers)
    return SavingsReceipt(
        live_run=live_run,
        baseline_tokens=actual_tokens + saved_tokens,
        actual_tokens=actual_tokens,
        saved_tokens=saved_tokens,
        baseline_cost=actual_cost + saved_cost,
        actual_cost=actual_cost,
        saved_cost=saved_cost,
        cached_prompt_tokens=observed_cached,
        prices=_price_snapshot(prices),
        levers=levers,
        calls=ordered_calls,
        unassigned=ordered_unassigned,
        budget_skipped=ordered_budget,
        notes=list(RECEIPT_NOTES),
    )


def _lever_for_call(call: UsageFact) -> str | None:
    cached = _nonneg(call.cached_prompt_tokens)
    write = _nonneg(call.cache_write_tokens)
    if call.cache_scope == "local":
        return "cache_hit" if cached else None
    if call.cache_scope in ("included", "additional") and (cached or write):
        return "shared_prefix" if call.step == "expert" else "cache_hit"
    return None


def _usage(call: UsageFact) -> TokenUsage:
    return TokenUsage(
        prompt_tokens=_nonneg(call.prompt_tokens),
        completion_tokens=_nonneg(call.completion_tokens),
        cached_prompt_tokens=_nonneg(call.cached_prompt_tokens),
        cache_write_tokens=_nonneg(call.cache_write_tokens),
        cache_scope=call.cache_scope,
    )


def _estimate_kwargs(prices: SavingsPrices) -> dict[str, float]:
    kwargs = {"input_price": prices.input_price, "output_price": prices.output_price}
    if prices.cached_input_price is not None:
        kwargs["cached_input_price"] = prices.cached_input_price
    if prices.cache_write_price is not None:
        kwargs["cache_write_price"] = prices.cache_write_price
    return kwargs


def _resolve_prices(prices: SavingsPrices) -> dict[str, float]:
    cached = prices.input_price if prices.cached_input_price is None else prices.cached_input_price
    write = prices.input_price if prices.cache_write_price is None else prices.cache_write_price
    return {
        "input": prices.input_price,
        "output": prices.output_price,
        "cached": cached,
        "write": write,
    }


def _price_snapshot(prices: SavingsPrices | None) -> dict[str, float | None]:
    if prices is None:
        return {
            "input_price": None,
            "output_price": None,
            "cached_input_price": None,
            "cache_write_price": None,
        }
    return {
        "input_price": prices.input_price,
        "output_price": prices.output_price,
        "cached_input_price": prices.cached_input_price,
        "cache_write_price": prices.cache_write_price,
    }


def _nonneg(value: int) -> int:
    return max(0, value)
