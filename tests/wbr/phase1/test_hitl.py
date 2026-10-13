"""TC-2-LG-HITL-1：审批状态机（Core 框架无关部分）。"""
from __future__ import annotations

import pytest

from wbr.core.exceptions import OrchestrationError
from wbr.core.orchestration.hitl import ApprovalState, ApprovalStateMachine


def test_create_and_pending():
    sm = ApprovalStateMachine()
    req = sm.create("是否执行删除操作?", role_id="expert_a", payload={"n": 1}, trace_id="t1")
    assert req.state == ApprovalState.PENDING
    assert sm.pending() == [req]
    assert sm.is_approved(req.request_id) is False


def test_legal_transitions():
    sm = ApprovalStateMachine()
    a = sm.create("q1")
    sm.decide(a.request_id, ApprovalState.APPROVED, decided_by="human", comment="同意")
    assert sm.is_approved(a.request_id)
    r = sm.get(a.request_id)
    assert r.decided_by == "human" and r.decided_at is not None

    b = sm.create("q2")
    sm.decide(b.request_id, ApprovalState.ESCALATED)
    assert sm.get(b.request_id).state == ApprovalState.ESCALATED

    c = sm.create("q3")
    sm.decide(c.request_id, ApprovalState.REJECTED)
    assert not sm.is_approved(c.request_id)


def test_illegal_transitions():
    sm = ApprovalStateMachine()
    a = sm.create("q")
    with pytest.raises(OrchestrationError, match="非法裁决"):
        sm.decide(a.request_id, ApprovalState.PENDING)  # 终态回退禁止
    sm.decide(a.request_id, ApprovalState.APPROVED)
    with pytest.raises(OrchestrationError, match="非法状态迁移"):
        sm.decide(a.request_id, ApprovalState.REJECTED)  # 终态不可再裁


def test_unknown_request():
    sm = ApprovalStateMachine()
    with pytest.raises(OrchestrationError, match="不存在"):
        sm.get("missing")
