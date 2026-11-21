"""Phase 0：前缀对齐、跳过未分配专家、预算、契约缓存、缓存用量。"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from tests.wbr.factories import coordinator_contract, expert_contract, verifier_contract
from tests.wbr.phase1.test_review_flow import GOOD_OUTPUT, plan_for
from wbr.core.audit.models import AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.cache import ContractBoundCache
from wbr.core.cache.semantic import SemanticCache
from wbr.core.contract.compiler import SAFETY_GUARD_HEADER
from wbr.core.loop_config import LoopSummarySnapshot
from wbr.core.orchestration import ReviewSession, ScriptedInvoker, parse_provider_usage
from wbr.core.orchestration.invoker import TokenUsage
from wbr.core.token.meter import (
    BudgetAction,
    BudgetPolicy,
    HeuristicTokenCounter,
    TokenBudget,
    TokenMeter,
)
from wbr.core.token.savings import measure_prompt_savings


def _scripts(assignments: dict[str, str], experts: dict | None = None) -> dict:
    scripts = {
        "coordinator": plan_for(assignments),
        "verifier": {
            "passed": True,
            "scores": {"completeness": 0.8, "accuracy": 0.8},
            "comments": "ok",
            "final_answer": "结论",
        },
    }
    scripts.update(experts or {})
    return scripts


def test_two_experts_in_one_run_share_prompt_prefix():
    shared = "全体先读同一份团队约定，再按各自契约作答"
    captured: dict[str, str] = {}

    def spy(role_id, marker):
        def _script(request):
            captured[role_id] = request.compiled_prompt.system_prompt
            captured[role_id + ":user"] = request.compiled_prompt.user_block
            assert request.max_tokens == request.role_contract.token_quota.max_completion_tokens
            return {**GOOD_OUTPUT, "conclusion": marker}
        return _script

    scripts = _scripts(
        {"expert_a": "子任务甲", "expert_b": "子任务乙"},
        {"expert_a": spy("expert_a", "甲"), "expert_b": spy("expert_b", "乙")},
    )
    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[expert_contract("expert_a"), expert_contract("expert_b")],
        verifier_contract=verifier_contract(),
        invoker=ScriptedInvoker(scripts),
        shared_context=shared,
    )
    snaps = [
        LoopSummarySnapshot(
            role_id="expert_a", sub_question="子任务甲", rounds_used=1,
            conclusion="快照甲", evidence=["证据甲"], stopped_because="evidence_satisfied",
        ),
        LoopSummarySnapshot(
            role_id="expert_b", sub_question="子任务乙", rounds_used=1,
            conclusion="快照乙", evidence=["证据乙"], stopped_because="evidence_satisfied",
        ),
    ]
    result = session.run("原始问题必须保留", loop_snapshots=snaps)
    assert result.status.value == "completed"
    prompt_a = captured["expert_a"]
    prompt_b = captured["expert_b"]
    block = f"{SAFETY_GUARD_HEADER}\n\n【团队共享上下文】\n{shared}"
    assert prompt_a.startswith(block)
    assert prompt_b.startswith(block)
    assert "id=expert_a" not in block
    assert "快照甲" in prompt_a and "快照甲" not in prompt_b
    assert prompt_a.index("快照甲") > len(block)
    assert "子任务甲" not in prompt_a[: len(block)]
    assert "原始问题必须保留" in captured["expert_a:user"]
    assert "[你的子任务] 子任务甲" in captured["expert_a:user"]
    assert "[你的子任务] 子任务乙" in captured["expert_b:user"]


def test_skip_unassigned_expert_by_default():
    invoker = ScriptedInvoker(_scripts(
        {"expert_a": "只问甲"},
        {"expert_a": GOOD_OUTPUT, "expert_b": GOOD_OUTPUT},
    ))
    audit = AuditTrail()
    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[expert_contract("expert_a"), expert_contract("expert_b")],
        verifier_contract=verifier_contract(),
        invoker=invoker,
        audit=audit,
    )
    result = session.run("问题")
    called = [c.role_contract.role_id for c in invoker.calls]
    assert called.count("expert_b") == 0
    skipped = result.outcome_by_role("expert_b")
    assert skipped.status.value == "skipped"
    assert skipped.skip_reason == "unassigned"
    assert result.status.value == "completed"
    assert AuditEventType.EXPERT_SKIPPED in audit.event_types_for(result.trace_id)


def test_skip_unassigned_can_be_turned_off():
    invoker = ScriptedInvoker(_scripts(
        {"expert_a": "只问甲"},
        {"expert_a": GOOD_OUTPUT, "expert_b": GOOD_OUTPUT},
    ))
    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[expert_contract("expert_a"), expert_contract("expert_b")],
        verifier_contract=verifier_contract(),
        invoker=invoker,
        skip_unassigned_experts=False,
    )
    result = session.run("原始问题")
    expert_b = [c for c in invoker.calls if c.role_contract.role_id == "expert_b"]
    assert len(expert_b) == 1
    assert "原始问题" in expert_b[0].compiled_prompt.user_block
    assert "[你的子任务]" not in expert_b[0].compiled_prompt.user_block
    assert result.outcome_by_role("expert_b").status.value == "completed"


def test_budget_skips_role_without_raising():
    meter = TokenMeter()
    budget = TokenBudget(
        BudgetPolicy(max_total_tokens=100_000, per_role={"expert_a": 1}, on_exceed=BudgetAction.DEGRADE),
        meter,
    )
    invoker = ScriptedInvoker(_scripts(
        {"expert_a": "甲", "expert_b": "乙"},
        {"expert_a": GOOD_OUTPUT, "expert_b": GOOD_OUTPUT},
    ))
    audit = AuditTrail()
    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[expert_contract("expert_a"), expert_contract("expert_b")],
        verifier_contract=verifier_contract(),
        invoker=invoker,
        audit=audit,
        token_budget=budget,
        token_meter=meter,
    )
    result = session.run("问题")
    assert result.status.value == "completed_with_failures"
    skipped = result.outcome_by_role("expert_a")
    assert skipped.skip_reason == "budget"
    assert "预算" in (skipped.error or "")
    assert result.outcome_by_role("expert_b").status.value == "completed"
    assert all(c.role_contract.role_id != "expert_a" for c in invoker.calls)
    events = [e for e in audit.events if e.event_type == AuditEventType.TOKEN_BUDGET_EXCEEDED]
    assert events and events[0].role_id == "expert_a"


def test_budget_reject_stops_session_cleanly():
    meter = TokenMeter()
    meter.record("seed", "seed", TokenUsage(prompt_tokens=50, completion_tokens=0))
    budget = TokenBudget(
        BudgetPolicy(max_total_tokens=50, on_exceed=BudgetAction.REJECT),
        meter,
    )
    invoker = ScriptedInvoker(_scripts({"expert_a": "甲"}, {"expert_a": GOOD_OUTPUT}))
    audit = AuditTrail()
    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[expert_contract("expert_a")],
        verifier_contract=verifier_contract(),
        invoker=invoker,
        audit=audit,
        token_budget=budget,
    )
    result = session.run("问题")
    assert result.status.value == "failed"
    assert "预算" in (result.error or "")
    assert invoker.calls == []
    assert any(e.event_type == AuditEventType.TOKEN_BUDGET_EXCEEDED for e in audit.events)


def test_budget_shrinks_max_tokens_to_remaining_room():
    question = "问题"
    sub = "甲"
    user = f"{question}\n\n[你的子任务] {sub}"
    from wbr.core.contract.compiler import ContractCompiler

    expert = expert_contract("expert_a")
    compiled = ContractCompiler().compile(expert, user)
    estimate = HeuristicTokenCounter().count(compiled.system_prompt + "\n" + compiled.user_block)
    room = 16
    meter = TokenMeter()
    budget = TokenBudget(
        BudgetPolicy(max_total_tokens=1_000_000, per_role={"expert_a": estimate + room}),
        meter,
    )
    invoker = ScriptedInvoker(_scripts({"expert_a": sub}, {"expert_a": GOOD_OUTPUT}))
    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[expert],
        verifier_contract=verifier_contract(),
        invoker=invoker,
        token_budget=budget,
    )
    result = session.run(question)
    assert result.outcome_by_role("expert_a").status.value == "completed"
    expert_call = next(c for c in invoker.calls if c.role_contract.role_id == "expert_a")
    assert expert_call.max_tokens == room


def test_contract_cache_skips_second_run():
    cache = ContractBoundCache()
    invoker = ScriptedInvoker(_scripts({"expert_a": "甲"}, {"expert_a": GOOD_OUTPUT}))
    meter = TokenMeter()
    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[expert_contract("expert_a")],
        verifier_contract=verifier_contract(),
        invoker=invoker,
        response_cache=cache,
        token_meter=meter,
    )
    first = session.run("同一个问题")
    billed_first = meter.usage_total
    calls_first = len(invoker.calls)
    second = session.run("同一个问题")
    assert len(invoker.calls) == calls_first
    assert meter.usage_total == billed_first
    assert second.outcome_by_role("expert_a").cache_hit == "exact"
    assert second.outcome_by_role("expert_a").output["conclusion"] == first.outcome_by_role("expert_a").output["conclusion"]
    assert meter.cached_prompt_tokens > 0


def test_semantic_cache_is_opt_in():
    class Embedder:
        def embed(self, text: str) -> list[float]:
            return [1.0, 1.0] if "登录" in text else [0.0, 1.0]

    scripts = _scripts({"expert_a": "认证"}, {"expert_a": GOOD_OUTPUT})

    def make(cache, allow: bool, invoker):
        return ReviewSession(
            coordinator_contract=coordinator_contract(),
            expert_contracts=[expert_contract("expert_a")],
            verifier_contract=verifier_contract(),
            invoker=invoker,
            response_cache=cache,
            allow_semantic_cache=allow,
        )

    def fresh():
        return SemanticCache(ContractBoundCache(), embedder=Embedder(), threshold=0.8)

    primed = fresh()
    make(primed, True, ScriptedInvoker(scripts)).run("登录认证怎么设计")
    strict = ScriptedInvoker(scripts)
    make(primed, False, strict).run("登录怎么做认证")
    assert any(c.role_contract.role_id == "expert_a" for c in strict.calls)

    semantic = fresh()
    make(semantic, True, ScriptedInvoker(scripts)).run("登录认证怎么设计")
    fuzzy = ScriptedInvoker(scripts)
    result = make(semantic, True, fuzzy).run("登录怎么做认证")
    assert all(c.role_contract.role_id != "expert_a" for c in fuzzy.calls)
    assert result.outcome_by_role("expert_a").cache_hit == "semantic"


def test_parse_provider_usage_openai_deepseek_anthropic():
    openai = parse_provider_usage({
        "prompt_tokens": 1000,
        "completion_tokens": 10,
        "prompt_tokens_details": {"cached_tokens": 800},
    })
    assert openai.cache_scope == "included"
    assert openai.cached_prompt_tokens == 800
    assert openai.uncached_prompt_tokens == 200
    cost = openai.estimate_cost(input_price=3.0, output_price=15.0, cached_input_price=0.3)
    assert cost["input"] == pytest.approx(200 * 3.0 + 800 * 0.3)
    assert cost["savings"] == pytest.approx(800 * (3.0 - 0.3))

    deepseek = parse_provider_usage({
        "prompt_tokens": 20,
        "completion_tokens": 10,
        "prompt_cache_hit_tokens": 15,
        "prompt_cache_miss_tokens": 5,
    })
    assert deepseek.cache_scope == "included"
    assert deepseek.cached_prompt_tokens == 15
    assert deepseek.cache_miss_tokens == 5

    anthropic = parse_provider_usage({
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_input_tokens": 80,
        "cache_creation_input_tokens": 20,
    })
    assert anthropic.cache_scope == "additional"
    assert anthropic.prompt_tokens == 100
    assert anthropic.cached_prompt_tokens == 80
    assert anthropic.cache_write_tokens == 20
    assert anthropic.completion_tokens == 50


def test_meter_keeps_cache_fields_out_of_billed_total():
    meter = TokenMeter()
    usage = TokenUsage(
        prompt_tokens=0,
        completion_tokens=0,
        cached_prompt_tokens=40,
        cache_scope="local",
    )
    meter.record("expert_a", "expert", usage, "t")
    assert meter.usage_total == 0
    assert meter.cached_prompt_tokens == 40
    cost = meter.estimate_cost(input_price=2.0, output_price=1.0, cached_input_price=0.0)
    assert cost["savings"] == pytest.approx(80.0)
    assert cost["total"] == pytest.approx(0.0)


def test_budget_incoming_counts_before_the_call():
    meter = TokenMeter()
    budget = TokenBudget(BudgetPolicy(max_total_tokens=100, on_exceed=BudgetAction.DEGRADE), meter)
    assert budget.check("expert_a", incoming=100).action == BudgetAction.DEGRADE
    assert budget.check("expert_a", incoming=10).action == BudgetAction.OK


def test_official_templates_prompt_savings_and_report_script():
    from wbr.templates.registry import list_teams, load_team_spec

    for item in list_teams():
        spec = load_team_spec(item["name"])
        measured = measure_prompt_savings(
            name=item["name"],
            coordinator=spec.coordinator,
            experts=spec.experts,
            verifier=spec.verifier,
            question="评审：订单系统是否应该拆成微服务？",
        )
        assert measured["prompt_tokens_after"] < measured["prompt_tokens_before"]
        assert measured["prefix_includes_shared_context"] is True
        assert measured["shared_prefix_tokens_after"] > measured["shared_prefix_tokens_before"]
        assert measured["shared_prefix_tokens_before"] >= measured["safety_header_tokens"]

    proc = subprocess.run(
        [sys.executable, "scripts/token_savings_report.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(proc.stdout)
    assert report["teams"]
    for team in report["teams"]:
        assert team["replay_billed_second"] == 0
        assert len(team["unassigned_skipped"]) == team["experts"] - 1
        assert team["second_run_cache_hits"]
