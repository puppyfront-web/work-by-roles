"""TC-V2.1-LOOP：类型A 单角色内部推理循环。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import expert_contract
from wbr.core.audit.models import AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.cache import ContractBoundCache
from wbr.core.constants import MemoryLayer
from wbr.core.exceptions import MemoryPermissionDeniedError
from wbr.core.memory.hub import MemoryHub
from wbr.core.loop_config import InnerLoopConfig, QuotaExhaustedAction
from wbr.core.orchestration import ScriptedInvoker
from wbr.core.orchestration.inner_loop import InnerLoopExecutor
from wbr.core.token.meter import TokenMeter

LOOP_SCHEMA = {
    "type": "object",
    "required": ["conclusion", "evidence", "continue_loop", "reason"],
    "properties": {
        "conclusion": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "continue_loop": {"type": "boolean"},
        "reason": {"type": "string"},
    },
}


def make_executor(scripts, *, config=None, audit=None, memory=None, cache=None, meter=None,
                  contract=None):
    contract = contract or expert_contract("expert_a", output_schema=LOOP_SCHEMA)
    return InnerLoopExecutor(
        contract=contract, invoker=ScriptedInvoker(scripts, default_usage=(30, 20)),
        config=config, memory=memory, cache=cache, meter=meter, audit=audit,
        session_id="s1",
    )


def round_out(conclusion="中间结论", evidence=None, cont=True, reason="证据不足"):
    return {"conclusion": conclusion, "evidence": evidence or [f"证据{conclusion}"],
            "continue_loop": cont, "reason": reason}


def test_evidence_sufficient_early_exit():
    """第 1 轮即证据充足（continue_loop=False）→ 退出 reason=evidence_satisfied。"""
    scripts = {"expert_a": round_out("最终结论", ["[^1] 文档"], cont=False)}
    executor = make_executor(scripts)
    snap = executor.run("安全审计子任务")
    assert snap.rounds_used == 1
    assert snap.stopped_because == "evidence_satisfied"
    assert snap.conclusion == "最终结论"
    assert snap.escalated_hitl is False


def test_max_rounds_forced_exit_marks_risk():
    """永不满足 → 打满轮次强制退出并标记 max_rounds_risk。"""
    scripts = {"expert_a": round_out("还不够", ["更多证据"], cont=True)}
    executor = make_executor(scripts, config=InnerLoopConfig(max_rounds=3))
    snap = executor.run("q")
    assert snap.rounds_used == 3
    assert snap.stopped_because == "max_rounds_risk"
    assert snap.escalated_hitl is False


def test_quota_exhausted_escalates_hitl():
    """独立循环 token 配额耗尽（默认 escalate_hitl）。"""
    scripts = {"expert_a": round_out("继续", ["证据"], cont=True)}
    executor = make_executor(scripts, config=InnerLoopConfig(max_rounds=10, loop_quota_tokens=100))
    snap = executor.run("q")
    assert snap.stopped_because == "quota_exhausted_hitl"
    assert snap.escalated_hitl is True


def test_quota_exhausted_force_exit_mode():
    scripts = {"expert_a": round_out("继续", [], cont=True)}
    executor = make_executor(scripts, config=InnerLoopConfig(
        max_rounds=10, loop_quota_tokens=100,
        on_quota_exhausted=QuotaExhaustedAction.FORCE_EXIT))
    snap = executor.run("q")
    assert snap.stopped_because == "quota_exhausted_exit"
    assert snap.escalated_hitl is False


def test_loop_memory_only_role_session_and_audited_per_round():
    """每轮写本角色 ROLE_SESSION；每轮发 LOOP_STEP 审计。"""
    audit = AuditTrail()
    hub = MemoryHub(audit=audit)
    c = expert_contract("expert_a", output_schema=LOOP_SCHEMA,
                        read_layers=[MemoryLayer.ROLE_SESSION],
                        write_layers=[MemoryLayer.ROLE_SESSION])
    scripts = {"expert_a": round_out("结论", ["E1"], cont=False)}
    executor = make_executor(scripts, memory=hub, audit=audit, contract=c)
    executor.run("q")
    events = [e for e in audit.events if e.event_type == AuditEventType.LOOP_STEP]
    assert len(events) == 1
    # 循环 trace 已写入角色私有记忆
    found = hub.read(MemoryLayer.ROLE_SESSION, "inner_loop_trace", contract=c, session_id="s1")
    assert found and found[0]["round"] == 1
    # 无 ROLE_SESSION 写权限的角色 → 记忆写被拒但循环不崩
    c2 = expert_contract("expert_x", output_schema=LOOP_SCHEMA)
    scripts_x = {"expert_x": round_out("结论", ["E1"], cont=False)}
    executor2 = make_executor(scripts_x, memory=hub, contract=c2)
    snap = executor2.run("q")
    assert snap.conclusion == "结论"


def test_cache_hit_skips_loop():
    audit = AuditTrail()
    cache = ContractBoundCache()
    scripts = {"expert_a": round_out("首轮", cont=False)}
    executor = make_executor(scripts, cache=cache, audit=audit)
    snap1 = executor.run("相同子问题")
    assert snap1.rounds_used == 1
    snap2 = executor.run("相同子问题")
    assert snap2.conclusion == snap1.conclusion
    events = [e for e in audit.events if e.event_type == AuditEventType.LOOP_STEP]
    assert len(events) == 1  # 第二次命中缓存，未执行新一轮


def test_snapshot_is_summary_not_raw_messages():
    """快照只含结论/证据/统计，不含原始消息（控上下文膨胀）。"""
    scripts = {"expert_a": round_out("结论X", ["E"], cont=False)}
    snap = make_executor(scripts).run("q")
    keys = set(snap.model_dump().keys())
    assert keys == {"role_id", "sub_question", "rounds_used", "conclusion", "evidence",
                    "stopped_because", "token_used", "escalated_hitl"}


def test_token_metering_recorded():
    meter = TokenMeter()
    scripts = {"expert_a": round_out("c", cont=False)}
    make_executor(scripts, meter=meter).run("q")
    assert meter.usage_total > 0
    assert meter.usage_by_step("inner_loop") == meter.usage_total


def test_contract_default_config_used():
    """config 缺省读契约 inner_loop 字段（契约约束，无上限构造不存在）。"""
    c = expert_contract("expert_a", output_schema=LOOP_SCHEMA).with_changes(
        inner_loop=InnerLoopConfig(max_rounds=1))
    scripts = {"expert_a": round_out("继续", cont=True)}
    snap = make_executor(scripts, contract=c).run("q")
    assert snap.rounds_used == 1  # 契约 max_rounds=1 生效
    assert snap.stopped_because == "max_rounds_risk"


def test_snapshot_feeds_review_session():
    """快照作为主会审流程输入：对应专家的编译 prompt 含快照结论。"""
    from tests.wbr.factories import coordinator_contract, verifier_contract
    from wbr.core.orchestration import ReviewSession

    scripts = {"expert_a": round_out("内循环沉淀结论", ["[^1] 内部证据"], cont=False)}
    executor = make_executor(scripts)
    snap = executor.run("缓存选型")

    captured = {}

    def expert_spy(request):
        captured["system_prompt"] = request.compiled_prompt.system_prompt
        return {"conclusion": "综合内循环结论", "confidence": 0.9}

    full_scripts = {
        "coordinator": {"assignments": [{"expert_role_id": "expert_a", "sub_question": "缓存选型"}]},
        "expert_a": expert_spy,
        "verifier": {"passed": True, "scores": {"completeness": 0.8, "accuracy": 0.8},
                     "comments": "ok", "final_answer": "A"},
    }
    session = ReviewSession(
        coordinator_contract=coordinator_contract(),
        expert_contracts=[expert_contract("expert_a")],
        verifier_contract=verifier_contract(),
        invoker=ScriptedInvoker(full_scripts),
    )
    result = session.run("主问题", loop_snapshots=[snap])
    # 快照经证据规范段进入专家系统上下文（evidence 通道）
    assert "内循环沉淀结论" in captured["system_prompt"]
    assert result.status.value == "completed"
