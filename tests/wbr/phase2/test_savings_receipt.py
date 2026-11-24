"""节省回执：三条杠杆拆分，以及优化关闭时节省为 0。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import coordinator_contract, expert_contract, verifier_contract
from tests.wbr.phase1.test_review_flow import GOOD_OUTPUT, plan_for
from wbr.core.cache import ContractBoundCache
from wbr.core.contract.compiler import ContractCompiler
from wbr.core.loop_config import LoopSummarySnapshot
from wbr.core.orchestration.invoker import ModelResponse, ScriptedInvoker, TokenUsage
from wbr.core.orchestration.review import ReviewSession
from wbr.core.token.meter import (
    BudgetAction,
    BudgetPolicy,
    HeuristicTokenCounter,
    TokenBudget,
    TokenMeter,
)
from wbr.core.token.receipt import (
    FORMULA_ID,
    BudgetSkip,
    SavingsPrices,
    UnassignedFact,
    UsageFact,
    build_savings_receipt,
    token_delta,
)

PRICES = SavingsPrices(
    input_price=3.0,
    output_price=15.0,
    cached_input_price=0.3,
    cache_write_price=3.75,
)


def _scripts(assignments: dict[str, str]) -> dict:
    scripts = {
        "coordinator": plan_for(assignments),
        "verifier": {
            "passed": True,
            "scores": {"completeness": 0.8, "accuracy": 0.8},
            "comments": "ok",
            "final_answer": "结论",
        },
    }
    for role_id in ("expert_a", "expert_b"):
        scripts[role_id] = {**GOOD_OUTPUT, "conclusion": role_id}
    return scripts


def _session(invoker, **kwargs) -> ReviewSession:
    return ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[expert_contract("expert_a"), expert_contract("expert_b")],
        verifier_contract=verifier_contract(),
        invoker=invoker,
        **kwargs,
    )


class _UsageInvoker:
    def __init__(self, scripts: dict, usage_for) -> None:
        self._inner = ScriptedInvoker(scripts)
        self._usage_for = usage_for
        self.calls = self._inner.calls

    def invoke(self, request):
        response = self._inner.invoke(request)
        return ModelResponse(text=response.text, usage=self._usage_for(request), raw=response.raw)


def _assert_identity(receipt) -> None:
    assert receipt.formula == FORMULA_ID
    assert receipt.saved_tokens == receipt.baseline_tokens - receipt.actual_tokens
    assert receipt.saved_cost == pytest.approx(receipt.baseline_cost - receipt.actual_cost)
    assert sum(item.tokens for item in receipt.levers) == receipt.saved_tokens
    assert sum(item.cost for item in receipt.levers) == pytest.approx(receipt.saved_cost)
    assert [item.id for item in receipt.levers] == [
        "shared_prefix",
        "skipped_unassigned",
        "cache_hit",
    ]


def _counterfactual_prompt_tokens(role_id: str, question: str, shared: str, evidence: list[str]) -> int:
    compiled = ContractCompiler().compile(
        expert_contract(role_id),
        question,
        evidence=evidence,
        shared_context=shared or None,
    )
    return HeuristicTokenCounter().count(compiled.system_prompt + "\n" + compiled.user_block)


def test_builder_splits_three_levers_without_overlap():
    calls = [
        UsageFact(
            role_id="coordinator",
            step="coordinator",
            prompt_tokens=100,
            completion_tokens=10,
            cached_prompt_tokens=10,
            cache_scope="included",
        ),
        UsageFact(
            role_id="expert_a",
            step="expert",
            prompt_tokens=100,
            completion_tokens=10,
            cached_prompt_tokens=80,
            cache_write_tokens=5,
            cache_scope="included",
        ),
        UsageFact(
            role_id="verifier",
            step="verifier",
            prompt_tokens=0,
            completion_tokens=0,
            cached_prompt_tokens=40,
            cache_scope="local",
        ),
    ]
    receipt = build_savings_receipt(
        calls,
        [UnassignedFact(role_id="expert_b", prompt_tokens=25)],
        [BudgetSkip(role_id="expert_c", step="expert")],
        prices=PRICES,
    )
    _assert_identity(receipt)
    shared = receipt.lever("shared_prefix")
    skipped = receipt.lever("skipped_unassigned")
    cache = receipt.lever("cache_hit")
    assert shared.roles == ["expert_a"]
    assert shared.cached_tokens == 80
    assert shared.tokens == token_delta(calls[1]) == 5
    assert shared.cost == pytest.approx(80 * (3.0 - 0.3) + 5 * (3.0 - 3.75))
    assert skipped.roles == ["expert_b"]
    assert skipped.tokens == 25
    assert skipped.cost == pytest.approx(75.0)
    assert skipped.cached_tokens == 0
    assert cache.roles == ["coordinator", "verifier"]
    assert cache.cached_tokens == 50
    assert cache.tokens == 40
    assert cache.cost == pytest.approx(10 * (3.0 - 0.3) + 40 * 3.0)
    assert receipt.budget_skipped[0].role_id == "expert_c"
    assert receipt.saved_tokens == shared.tokens + skipped.tokens + cache.tokens
    assert "不按安全护栏" in " ".join(receipt.notes)
    assert "不计入节省" in " ".join(receipt.notes)


def test_builder_zero_when_nothing_was_optimized():
    calls = [
        UsageFact(role_id="coordinator", step="coordinator", prompt_tokens=120, completion_tokens=80),
        UsageFact(role_id="expert_a", step="expert", prompt_tokens=120, completion_tokens=80),
        UsageFact(role_id="verifier", step="verifier", prompt_tokens=120, completion_tokens=80),
    ]
    receipt = build_savings_receipt(calls, prices=PRICES)
    _assert_identity(receipt)
    assert receipt.saved_tokens == 0
    assert receipt.saved_cost == 0
    assert all(item.tokens == 0 and item.cost == 0 for item in receipt.levers)
    assert receipt.actual_tokens == 600
    assert receipt.baseline_tokens == 600


def test_skipped_unassigned_matches_full_independent_prompt():
    shared = "全体先读同一份团队约定"
    question = "原始问题必须保留"
    snap = LoopSummarySnapshot(
        role_id="expert_b",
        sub_question="",
        rounds_used=1,
        conclusion="乙",
        evidence=["材料"],
        stopped_because="evidence_satisfied",
    )
    evidence = ["[内循环快照 expert_b] 轮次=1 结论=乙 证据=['材料']"]
    session = _session(
        ScriptedInvoker(_scripts({"expert_a": "只问甲"})),
        shared_context=shared,
    )
    result = session.run(question, loop_snapshots=[snap])
    receipt = result.savings.priced(
        input_price=PRICES.input_price,
        output_price=PRICES.output_price,
        cached_input_price=PRICES.cached_input_price,
        cache_write_price=PRICES.cache_write_price,
    )
    expected = _counterfactual_prompt_tokens("expert_b", question, shared, evidence)
    _assert_identity(receipt)
    skipped = receipt.lever("skipped_unassigned")
    assert skipped.roles == ["expert_b"]
    assert skipped.tokens == expected
    assert skipped.tokens > 0
    assert skipped.cost == pytest.approx(expected * PRICES.input_price)
    assert receipt.lever("shared_prefix").tokens == 0
    assert receipt.lever("shared_prefix").cost == 0
    assert receipt.lever("cache_hit").tokens == 0
    assert receipt.lever("cache_hit").cost == 0
    assert receipt.saved_tokens == expected
    assert receipt.actual_tokens == 200 * 3
    assert result.outcome_by_role("expert_b").skip_reason == "unassigned"


def test_shared_prefix_is_expert_provider_cache_only():
    def usage_for(request):
        role = request.role_contract.role_id
        if role == "coordinator":
            return TokenUsage(
                prompt_tokens=100,
                completion_tokens=10,
                cached_prompt_tokens=10,
                cache_scope="included",
            )
        if role == "verifier":
            return TokenUsage(prompt_tokens=50, completion_tokens=5)
        return TokenUsage(
            prompt_tokens=100,
            completion_tokens=10,
            cached_prompt_tokens=80,
            cache_scope="included",
        )

    session = _session(_UsageInvoker(
        _scripts({"expert_a": "甲", "expert_b": "乙"}),
        usage_for,
    ))
    receipt = session.run("问题").savings.priced(
        input_price=3.0,
        output_price=15.0,
        cached_input_price=0.3,
    )
    _assert_identity(receipt)
    shared = receipt.lever("shared_prefix")
    cache = receipt.lever("cache_hit")
    assert shared.roles == ["expert_a", "expert_b"]
    assert shared.tokens == 0
    assert shared.cached_tokens == 160
    assert shared.cost == pytest.approx(160 * (3.0 - 0.3))
    assert cache.roles == ["coordinator"]
    assert cache.tokens == 0
    assert cache.cached_tokens == 10
    assert cache.cost == pytest.approx(10 * (3.0 - 0.3))
    assert receipt.lever("skipped_unassigned").tokens == 0
    assert receipt.saved_tokens == 0
    assert receipt.saved_cost == pytest.approx(shared.cost + cache.cost)


def test_additional_cache_adds_cached_and_write_tokens_on_experts():
    def usage_for(request):
        if request.role_contract.role_type.value != "expert":
            return TokenUsage(prompt_tokens=100, completion_tokens=10)
        return TokenUsage(
            prompt_tokens=100,
            completion_tokens=10,
            cached_prompt_tokens=80,
            cache_write_tokens=20,
            cache_scope="additional",
        )

    session = _session(_UsageInvoker(
        _scripts({"expert_a": "甲", "expert_b": "乙"}),
        usage_for,
    ))
    receipt = session.run("问题").savings.priced(
        input_price=3.0,
        output_price=15.0,
        cached_input_price=0.3,
        cache_write_price=3.75,
    )
    per_call = TokenUsage(
        prompt_tokens=100,
        completion_tokens=10,
        cached_prompt_tokens=80,
        cache_write_tokens=20,
        cache_scope="additional",
    ).estimate_cost(input_price=3.0, output_price=15.0, cached_input_price=0.3, cache_write_price=3.75)
    _assert_identity(receipt)
    shared = receipt.lever("shared_prefix")
    assert shared.tokens == 2 * (80 + 20)
    assert shared.cost == pytest.approx(2 * per_call["savings"])
    assert shared.cost == pytest.approx(2 * (80 * (3.0 - 0.3) + 20 * (3.0 - 3.75)))
    assert receipt.lever("cache_hit").tokens == 0
    assert receipt.lever("skipped_unassigned").tokens == 0
    assert receipt.saved_tokens == shared.tokens


def test_local_cache_hit_bills_cached_prompt_as_uncached():
    cache = ContractBoundCache()
    invoker = ScriptedInvoker(_scripts({"expert_a": "甲", "expert_b": "乙"}))
    session = _session(invoker, response_cache=cache, token_meter=TokenMeter())
    first = session.run("同一个问题")
    first_receipt = first.savings.priced(input_price=3.0, output_price=15.0, cached_input_price=0.0)
    assert first_receipt.saved_tokens == 0
    assert first_receipt.saved_cost == 0
    billed = len(invoker.calls)
    second = session.run("同一个问题")
    receipt = second.savings.priced(input_price=3.0, output_price=15.0, cached_input_price=0.0)
    _assert_identity(receipt)
    assert len(invoker.calls) == billed
    cache_hit = receipt.lever("cache_hit")
    assert cache_hit.tokens == 120 * billed
    assert cache_hit.cost == pytest.approx(120 * billed * 3.0)
    assert cache_hit.roles == ["coordinator", "expert_a", "expert_b", "verifier"]
    assert receipt.lever("shared_prefix").tokens == 0
    assert receipt.lever("shared_prefix").cost == 0
    assert receipt.actual_tokens == 0
    assert receipt.actual_cost == 0
    assert receipt.saved_tokens == cache_hit.tokens


def test_saved_is_zero_when_optimizations_are_off_or_equivalent():
    prices = {"input_price": 3.0, "output_price": 15.0, "cached_input_price": 0.3}
    called = _session(
        ScriptedInvoker(_scripts({"expert_a": "只问甲"})),
        skip_unassigned_experts=False,
        shared_context="团队约定还在，但没有缓存命中",
    ).run("原始问题")
    off = called.savings.priced(**prices)
    _assert_identity(off)
    assert called.outcome_by_role("expert_b").status.value == "completed"
    assert off.saved_tokens == 0
    assert off.saved_cost == 0
    assert off.actual_tokens == off.baseline_tokens
    assert all(item.tokens == 0 and item.cost == 0 for item in off.levers)

    equivalent = _session(
        ScriptedInvoker(_scripts({"expert_a": "甲", "expert_b": "乙"})),
        shared_context="共享上下文本身不产生节省",
    ).run("问题")
    same = equivalent.savings.priced(**prices)
    _assert_identity(same)
    assert same.saved_tokens == 0
    assert same.saved_cost == 0
    assert equivalent.savings.saved_cost == 0


def test_budget_skips_are_listed_and_not_counted_as_savings():
    meter = TokenMeter()
    budget = TokenBudget(
        BudgetPolicy(max_total_tokens=100_000, per_role={"expert_a": 1}, on_exceed=BudgetAction.DEGRADE),
        meter,
    )
    session = _session(
        ScriptedInvoker(_scripts({"expert_a": "甲", "expert_b": "乙"})),
        token_budget=budget,
        token_meter=meter,
    )
    result = session.run("问题")
    receipt = result.savings.priced(input_price=3.0, output_price=15.0, cached_input_price=0.3)
    _assert_identity(receipt)
    assert result.outcome_by_role("expert_a").skip_reason == "budget"
    assert [item.role_id for item in receipt.budget_skipped] == ["expert_a"]
    assert receipt.lever("skipped_unassigned").tokens == 0
    assert receipt.saved_tokens == 0
    assert receipt.saved_cost == 0


def test_offline_report_uses_receipt_schema_and_is_not_a_live_run():
    import json
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "scripts/token_savings_report.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(proc.stdout)
    assert report["kind"] == "offline_heuristic_demo"
    assert report["live_run_receipt"] is False
    assert report["formula"] == FORMULA_ID
    for team in report["teams"]:
        for key in ("first_run_receipt", "second_run_receipt"):
            receipt = team[key]
            assert receipt["live_run"] is False
            assert receipt["formula"] == FORMULA_ID
            assert {item["id"] for item in receipt["levers"]} == {
                "shared_prefix",
                "skipped_unassigned",
                "cache_hit",
            }
            assert receipt["saved_tokens"] == receipt["baseline_tokens"] - receipt["actual_tokens"]
        skipped = next(
            item for item in team["first_run_receipt"]["levers"] if item["id"] == "skipped_unassigned"
        )
        replay = next(
            item for item in team["second_run_receipt"]["levers"] if item["id"] == "cache_hit"
        )
        assert skipped["tokens"] > 0
        assert replay["tokens"] > 0
        assert team["second_run_receipt"]["saved_tokens"] >= replay["tokens"]
