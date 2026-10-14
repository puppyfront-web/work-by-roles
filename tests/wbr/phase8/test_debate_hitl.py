"""TC-V2.1-DEBATE-HITL：辩论 Loop 合规升级。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import expert_contract, verifier_contract
from wbr.core.audit.trail import AuditTrail
from wbr.core.orchestration import ScriptedInvoker
from wbr.core.orchestration.debate import DebateConfig, DebateModerator
from wbr.core.orchestration.review import Disagreement
from wbr.core.contract.models import OutputSpec

REF_CONVERGENCE_SCHEMA = {
    "type": "object",
    "required": ["converged", "degree", "reason"],
    "properties": {
        "converged": {"type": "boolean"},
        "degree": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
}
DEBATE_SCHEMA = {
    "type": "object",
    "required": ["statement", "agrees_with", "concedes"],
    "properties": {
        "statement": {"type": "string", "minLength": 2},
        "agrees_with": {"type": "array", "items": {"type": "string"}},
        "concedes": {"type": "boolean"},
    },
}


def dispute():
    return Disagreement(between=["expert_a", "expert_b"], topic="选型",
                        positions=[{"role_id": "expert_a", "conclusion": "A"},
                                   {"role_id": "expert_b", "conclusion": "B"}])


def make_contracts(ref_schema=None):
    del ref_schema  # 收敛评估校验走 DebateModerator.convergence_schema
    return {
        "expert_a": expert_contract("expert_a", output_schema=DEBATE_SCHEMA),
        "expert_b": expert_contract("expert_b", output_schema=DEBATE_SCHEMA),
        "referee": verifier_contract("referee"),
    }


def build(scripts, *, audit=None, config=None):
    return DebateModerator(
        contracts=make_contracts(), invoker=ScriptedInvoker(scripts),
        config=config or DebateConfig(max_rounds=2), audit=audit,
        convergence_schema=REF_CONVERGENCE_SCHEMA,
    )


def hold_scripts():
    s = {}
    for rid in ("expert_a", "expert_b"):
        s[rid] = {"statement": f"{rid} 坚持己见", "agrees_with": [], "concedes": False}
    return s


def test_referee_convergence_per_round_and_early_stop():
    """每轮由 referee 评估收敛；converged=True 提前终止。"""
    scripts = hold_scripts()
    scripts["referee"] = {"converged": True, "degree": 0.9, "reason": "双方立场已趋同"}
    moderator = build(scripts, config=DebateConfig(max_rounds=3))
    result = moderator.run("q", [dispute()])
    assert len(result.rounds) == 1  # 第 1 轮收敛即止
    assert len(result.convergence_evaluations) == 1
    assert result.convergence_evaluations[0]["converged"] is True
    assert result.escalated_to_hitl is False


def test_no_convergence_to_limit_escalates_hitl():
    """打满轮次仍未收敛 → escalated_to_hitl=True，全部分歧保留。"""
    scripts = hold_scripts()
    scripts["referee"] = {"converged": False, "degree": 0.2, "reason": "仍对立"}
    audit = AuditTrail()
    moderator = build(scripts, audit=audit, config=DebateConfig(max_rounds=2))
    result = moderator.run("q", [dispute()])
    assert len(result.rounds) == 2
    assert result.escalated_to_hitl is True
    assert result.unresolved_disagreements
    assert len(result.convergence_evaluations) == 2  # 每轮都评估
    assert audit.events


def test_referee_output_invalid_treated_as_not_converged():
    """referee 输出不合规 → 保守视为未收敛（不阻断辩论）。"""
    scripts = hold_scripts()
    scripts["referee"] = {"degree": 0.5}  # 缺 converged/reason
    moderator = build(scripts, config=DebateConfig(max_rounds=1))
    result = moderator.run("q", [dispute()])
    assert result.escalated_to_hitl is True
    assert result.convergence_evaluations[0]["converged"] is False


def test_convergence_disabled_backward_compatible():
    """referee_evaluates_convergence=False → 旧语义（无评估记录）。"""
    scripts = hold_scripts()
    moderator = build(scripts, config=DebateConfig(max_rounds=1,
                                                   referee_evaluates_convergence=False))
    result = moderator.run("q", [dispute()])
    assert result.convergence_evaluations == []
    assert result.escalated_to_hitl is True  # 打满仍未收敛（无评估通道）


def test_loop_metrics_debate_rate():
    from wbr.core.harness.loop_metrics import DebateLoopMetrics

    moderator_hold = build(hold_scripts(), config=DebateConfig(max_rounds=1))
    r1 = moderator_hold.run("q", [dispute()])
    moderator_conv = build({**hold_scripts(),
                            "referee": {"converged": True, "degree": 1.0, "reason": "ok"}},
                           config=DebateConfig(max_rounds=3))
    r2 = moderator_conv.run("q", [dispute()])
    m = DebateLoopMetrics.from_results([r1, r2])
    assert m.convergence_rate == pytest.approx(0.5)
    assert m.round_limit_exceeded_rate == pytest.approx(0.5)
