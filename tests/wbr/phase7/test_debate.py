"""TC-V2-DEBATE：受控专家辩论。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import (
    EXPERT_OUTPUT_SCHEMA,
    coordinator_contract,
    expert_contract,
    verifier_contract,
)
from wbr.core.audit.trail import AuditTrail
from wbr.core.orchestration import ScriptedInvoker
from wbr.core.orchestration.debate import (
    DebateConfig,
    DebateModerator,
    DebateTurn,
)
from wbr.core.orchestration.review import Disagreement
from wbr.core.contract.models import OutputSpec


def make_disagreement() -> Disagreement:
    return Disagreement(
        between=["expert_a", "expert_b"],
        topic="缓存选型",
        positions=[
            {"role_id": "expert_a", "conclusion": "多级缓存"},
            {"role_id": "expert_b", "conclusion": "单级缓存"},
        ],
    )


DEBATE_SCHEMA = {
    "type": "object",
    "required": ["statement", "agrees_with", "concedes"],
    "properties": {
        "statement": {"type": "string", "minLength": 2},
        "agrees_with": {"type": "array", "items": {"type": "string"}},
        "concedes": {"type": "boolean"},
    },
}


def make_contracts():
    return {
        "expert_a": expert_contract("expert_a", output_schema=DEBATE_SCHEMA),
        "expert_b": expert_contract("expert_b", output_schema=DEBATE_SCHEMA),
        "referee": verifier_contract("referee"),
    }


def turn_script(statement, *, agrees=None, concedes=False, extra=None):
    payload = {"statement": statement, "agrees_with": agrees or [], "concedes": concedes}
    if extra:
        payload.update(extra)
    return payload


def test_two_rounds_then_cap():
    """无人让步 → 打满 max_rounds 轮，分歧 unresolved 留存。"""
    contracts = make_contracts()
    scripts = {}
    for rid in ("expert_a", "expert_b"):
        scripts[rid] = lambda req, rid=rid: turn_script(f"{rid}: 我坚持己见", agrees=[])
    moderator = DebateModerator(
        contracts=contracts, invoker=ScriptedInvokerShim(scripts),
        config=DebateConfig(max_rounds=2),
    )
    result = moderator.run("缓存选型？", [make_disagreement()])
    assert len(result.rounds) == 2
    assert all(len(r) == 2 for r in result.rounds)  # 双专家各一轮发言
    assert result.unresolved_disagreements and not result.concessions


def test_concession_terminates_early():
    """专家让步 → 提前终止，concessions 记录。"""
    contracts = make_contracts()

    def a_turn(req):
        return turn_script("被 B 说服", agrees=["expert_b"], concedes=True)

    def b_turn(req):
        return turn_script("坚持单级缓存", agrees=[])

    moderator = DebateModerator(
        contracts=contracts, invoker=ScriptedInvokerShim({"expert_a": a_turn, "expert_b": b_turn}),
        config=DebateConfig(max_rounds=3),
    )
    result = moderator.run("缓存选型？", [make_disagreement()])
    assert result.concessions == ["expert_a"]
    assert len(result.rounds) == 1  # 第 1 轮即有人让步


def test_violating_expert_muted_for_round():
    """输出违反契约（缺 agrees_with）→ 该专家本轮禁言并留审计。"""
    contracts = make_contracts()
    scripts = {
        "expert_a": turn_script("正常发言", agrees=[]),
        "expert_b": {"statement": "缺字段的违规发言"},  # 缺 agrees_with/concedes
    }
    audit = AuditTrail()
    moderator = DebateModerator(
        contracts=contracts, invoker=ScriptedInvokerShim(scripts),
        config=DebateConfig(max_rounds=1), audit=audit,
    )
    result = moderator.run("q", [make_disagreement()])
    b_turns = [t for t in result.rounds[0] if t.role_id == "expert_b"]
    assert b_turns and b_turns[0].muted and not b_turns[0].statement  # 禁言留痕但不发声
    assert any("禁言" in e.payload.get("detail", "") for e in audit.events)


def test_no_dispute_means_no_debate():
    moderator = DebateModerator(
        contracts=make_contracts(), invoker=ScriptedInvokerShim({}),
    )
    result = moderator.run("q", [])
    assert result.rounds == [] and result.unresolved_disagreements == []


def test_debate_history_preserved_not_arbitrated():
    """R26：辩论历史原样留存。"""
    contracts = make_contracts()
    scripts = {rid: turn_script(f"{rid} 立场不变", agrees=[]) for rid in ("expert_a", "expert_b")}
    moderator = DebateModerator(
        contracts=contracts, invoker=ScriptedInvokerShim(scripts),
        config=DebateConfig(max_rounds=1),
    )
    result = moderator.run("q", [make_disagreement()])
    texts = [t.statement for rnd in result.rounds for t in rnd]
    assert texts == ["expert_a 立场不变", "expert_b 立场不变"]  # 双方立场原样留档


def test_referee_required():
    contracts = make_contracts()
    contracts["expert_c"] = expert_contract("expert_c", output_schema=DEBATE_SCHEMA)
    del contracts["referee"]
    with pytest.raises(ValueError, match="verifier"):
        DebateModerator(contracts=contracts, invoker=ScriptedInvokerShim({}))

ScriptedInvokerShim = ScriptedInvoker  # 兼容别名
