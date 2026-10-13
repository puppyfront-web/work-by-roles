"""TC-5-PERF-1：性能基准（宽松阈值防环境抖动；脚本化 Invoker，无外部依赖）。"""
from __future__ import annotations

import json
import time

import pytest

pytestmark = pytest.mark.performance

from tests.wbr.factories import coordinator_contract, expert_contract, verifier_contract
from wbr.core.audit.pack import AuditPackBuilder
from wbr.core.audit.trail import AuditTrail
from wbr.core.cache import ContractBoundCache
from wbr.core.harness import RegressionEngine
from wbr.core.orchestration import ReviewSession, ScriptedInvoker


def _team(n_experts: int):
    contracts = {"coordinator": coordinator_contract()}
    for i in range(n_experts):
        contracts[f"expert_{i}"] = expert_contract(f"expert_{i}")
    contracts["verifier"] = verifier_contract()
    return contracts


def _scripts(contracts, conclusion="结论A"):
    scripts = {}
    for rid, c in contracts.items():
        from wbr.core.contract.models import RoleType

        if c.role_type == RoleType.COORDINATOR:
            scripts[rid] = {"assignments": [
                {"expert_role_id": e, "sub_question": "q"} for e in contracts if e.startswith("expert_")
            ]}
        elif c.role_type == RoleType.VERIFIER:
            scripts[rid] = {"passed": True, "scores": {"x": 0.9}, "comments": "ok", "final_answer": "A"}
        else:
            scripts[rid] = {"conclusion": conclusion, "confidence": 0.9}
    return scripts


def test_bench_review_5_experts_parallel():
    contracts = _team(5)
    session = ReviewSession(
        coordinator_contract=contracts["coordinator"],
        expert_contracts=[contracts[f"expert_{i}"] for i in range(5)],
        verifier_contract=contracts["verifier"],
        invoker=ScriptedInvoker(_scripts(contracts)),
    )
    start = time.perf_counter()
    result = session.run("基准问题")
    elapsed = time.perf_counter() - start
    assert result.status.value == "completed"
    assert elapsed < 2.0, f"5 专家会审耗时 {elapsed:.2f}s"


def test_bench_cache_hit_latency():
    cache = ContractBoundCache()
    c = expert_contract("expert_a")
    cache.put(c, "问题", None, {"v": 1})
    start = time.perf_counter()
    for _ in range(1000):
        assert cache.get(c, "问题") == {"v": 1}
    avg_ms = (time.perf_counter() - start) / 1000 * 1000
    assert avg_ms < 1.0, f"缓存命中均值 {avg_ms:.3f}ms"


def test_bench_audit_pack_export_10k_events():
    trail = AuditTrail()
    from wbr.core.audit.models import AuditEvent, AuditEventType

    events = [
        AuditEvent(event_type=AuditEventType.MEMORY_ACCESS, trace_id=f"wbr-{i % 50}",
                   role_id=f"expert_{i % 5}", payload={"n": i, "detail": "x" * 40})
        for i in range(10000)
    ]
    for e in events:
        trail.append(e)
    start = time.perf_counter()
    pack = AuditPackBuilder(trail).build()
    payload = pack.to_json()
    elapsed = time.perf_counter() - start
    assert pack.integrity["event_count"] == 10000
    assert elapsed < 5.0, f"10k 事件导出耗时 {elapsed:.2f}s"
    json.loads(payload)  # 可解析


def test_bench_regression_batch():
    contracts = _team(2)
    engine = RegressionEngine(contracts=contracts, invoker=ScriptedInvoker(_scripts(contracts)))
    from wbr.core.harness import CaseSuite, GoldenCase

    suite = CaseSuite(suite_id="bench")
    for i in range(10):
        suite.add(GoldenCase(case_id=f"c{i}", question=f"问题{i}",
                             expert_role_ids=["expert_0", "expert_1"]))
    start = time.perf_counter()
    report = engine.run_suite(suite)
    elapsed = time.perf_counter() - start
    assert report.metrics.overall_pass_rate == 1.0
    assert elapsed < 5.0, f"10 用例回归耗时 {elapsed:.2f}s"
