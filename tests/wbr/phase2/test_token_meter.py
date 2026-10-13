"""TC-2-TOK-1~3：Token 计数、计量与预算降级。"""
from __future__ import annotations

import pytest

from wbr.core.exceptions import TokenBudgetExceededError
from wbr.core.orchestration.invoker import TokenUsage
from wbr.core.token.meter import (
    BudgetAction,
    BudgetPolicy,
    HeuristicTokenCounter,
    TokenBudget,
    TokenMeter,
    degrade_history,
)


def test_heuristic_counter_deterministic():
    c = HeuristicTokenCounter()
    zh = "分析登录认证方案"
    en = "analyze the login authentication design"
    mixed = "使用 JWT 实现 auth 功能"
    for text in (zh, en, mixed):
        assert c.count(text) == c.count(text)
    # CJK ≈ 1 token/字
    assert c.count(zh) == len(zh)
    # 拉丁 ≈ 1/4 字符向上取整
    assert c.count("abcd") == 1 and c.count("abcde") == 2
    assert c.count("") == 0
    assert c.count(en) > c.count(zh)  # 混合文本更贵


def test_meter_aggregation_by_role_step_task():
    meter = TokenMeter()
    meter.record("expert_a", "expert", TokenUsage(prompt_tokens=100, completion_tokens=50), "t1")
    meter.record("expert_a", "expert", TokenUsage(prompt_tokens=10, completion_tokens=5), "t1")
    meter.record("expert_b", "verifier", TokenUsage(prompt_tokens=200, completion_tokens=100), "t1")
    assert meter.usage_by_role("expert_a") == 165
    assert meter.usage_by_role("expert_b") == 300
    assert meter.usage_by_step("expert") == 165
    assert meter.usage_by_step("verifier") == 300
    assert meter.usage_total == 465
    assert len(meter.records) == 3


def test_meter_audits_token_records():
    from wbr.core.audit.models import AuditEventType
    from wbr.core.audit.trail import AuditTrail

    trail = AuditTrail()
    meter = TokenMeter(audit=trail)
    meter.record("expert_a", "expert", TokenUsage(prompt_tokens=1, completion_tokens=1), "tr")
    events = [e for e in trail.events if e.event_type == AuditEventType.TOKEN_RECORD]
    assert len(events) == 1
    assert events[0].payload["prompt_tokens"] == 1


def test_budget_ok_then_degrade():
    meter = TokenMeter()
    budget = TokenBudget(
        BudgetPolicy(max_total_tokens=100, per_role={"expert_a": 50}, on_exceed=BudgetAction.DEGRADE),
        meter,
    )
    assert budget.check("expert_a").action == BudgetAction.OK
    meter.record("expert_a", "expert", TokenUsage(prompt_tokens=60, completion_tokens=0))
    d = budget.check("expert_a")
    assert d.action == BudgetAction.DEGRADE
    assert "expert_a" in d.reason
    # 未超限角色不受影响
    assert budget.check("expert_b").action == BudgetAction.OK
    # 总量超限
    meter.record("expert_b", "expert", TokenUsage(prompt_tokens=60, completion_tokens=0))
    assert budget.check().action == BudgetAction.DEGRADE


def test_budget_reject_raises():
    meter = TokenMeter()
    budget = TokenBudget(
        BudgetPolicy(max_total_tokens=10, on_exceed=BudgetAction.REJECT), meter
    )
    budget.check()
    meter.record("x", "s", TokenUsage(prompt_tokens=20, completion_tokens=0))
    with pytest.raises(TokenBudgetExceededError):
        budget.check()


def test_degrade_history_keeps_system_and_recent():
    counter = HeuristicTokenCounter()
    history = [
        {"role": "system", "content": "系统规则" * 10},
        {"role": "user", "content": "旧问题" * 30},
        {"role": "assistant", "content": "旧回答" * 30},
        {"role": "user", "content": "最新问题"},
    ]
    trimmed = degrade_history(history, counter=counter, max_tokens=80)
    assert trimmed[0]["role"] == "system"  # system 保留
    assert trimmed[-1]["content"] == "最新问题"  # 最近保留
    total = sum(counter.count(str(m["content"])) for m in trimmed)
    assert total <= 80 + 30  # 允许 system 超出预算的宽容度


def test_degrade_history_empty():
    assert degrade_history([], counter=HeuristicTokenCounter(), max_tokens=10) == []
