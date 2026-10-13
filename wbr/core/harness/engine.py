"""批量回归引擎（SPEC-004 §1.3 / §1.5）。"""
from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any, Callable

from pydantic import BaseModel, Field

from wbr.core.audit.trail import AuditTrail
from wbr.core.exceptions import HarnessError
from wbr.core.harness.metrics import HarnessMetrics, from_case_results
from wbr.core.memory.hub import MemoryHub
from wbr.core.orchestration.review import (
    ExpertStatus,
    ReviewSession,
    ReviewStatus,
    ViolationKind,
)

if TYPE_CHECKING:  # pragma: no cover
    from wbr.core.contract.models import RoleContract
    from wbr.core.harness.baseline import BaselineSnapshot
    from wbr.core.harness.cases import CaseSuite, GoldenCase


class CaseResult(BaseModel):
    case_id: str
    review_id: str = ""
    trace_id: str = ""
    per_expert: dict[str, dict[str, Any]] = Field(default_factory=dict)
    verdict_passed: bool | None = None
    final_answer: str = ""
    failures: list[str] = Field(default_factory=list)
    judge_score: float | None = None
    judge_rationale: str = ""
    stability_conclusion: bool | None = None   # None=未测稳定性
    expect_disagreement: bool = False
    disagreement_detected: bool = False
    passed: bool = False
    duration_ms: int = 0


class RegressionReport(BaseModel):
    report_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    suite_id: str = ""
    baseline_id: str | None = None
    case_results: list[CaseResult] = Field(default_factory=list)
    metrics: HarnessMetrics = Field(default_factory=HarnessMetrics)
    started_at: float = Field(default_factory=time.time)
    finished_at: float | None = None
    stability_runs: int = 1

    def to_json(self) -> str:
        return self.model_dump_json()

    def save(self, path: str) -> None:
        from pathlib import Path

        Path(path).write_text(self.to_json(), encoding="utf-8")

    def compare_with(self, previous: "RegressionReport", *, threshold: float = -0.05) -> dict[str, Any]:
        from wbr.core.harness.metrics import detect_degradation

        return {
            "metrics_delta": self.metrics.delta(previous.metrics),
            "degradations": detect_degradation(previous.metrics, self.metrics, threshold=threshold),
        }


class RegressionEngine:
    """批量回归：用例库 × 当前契约集 → 报告（指标 + 退化对比）。"""

    def __init__(
        self,
        *,
        contracts: dict[str, "RoleContract"],
        invoker: Any,
        coordinator: "RoleContract | None" = None,
        verifier: "RoleContract | None" = None,
        memory_factory: Callable[[], MemoryHub] | None = None,
        audit: AuditTrail | None = None,
    ) -> None:
        if not contracts:
            raise HarnessError("contracts 不能为空", code="E7001")
        self.contracts = dict(contracts)
        self.invoker = invoker
        self.coordinator = coordinator or self._find_role("coordinator")
        self.verifier = verifier or self._find_role("verifier")
        self.memory_factory = memory_factory
        self.audit = audit

    def _find_role(self, role_type: str) -> "RoleContract":
        from wbr.core.contract.models import RoleType

        for c in self.contracts.values():
            if c.role_type == RoleType(role_type):
                return c
        raise HarnessError(f"契约集中缺少 {role_type} 角色", code="E7001")

    # ---- 单用例执行 ----
    def _run_case_once(self, case: "GoldenCase") -> "ReviewResult":
        from wbr.core.contract.models import RoleType

        wanted = sorted(set(case.expert_role_ids)) if case.expert_role_ids else sorted(
            set(self.contracts) - {self.coordinator.role_id, self.verifier.role_id}
        )
        unknown = [rid for rid in wanted if rid not in self.contracts]
        if unknown:
            raise HarnessError(
                f"用例 {case.case_id} 引用了契约集中不存在的专家: {unknown}", code="E7001",
                details={"unknown_roles": unknown},
            )
        experts = [
            self.contracts[rid] for rid in wanted
            if self.contracts[rid].role_type == RoleType.EXPERT
        ]
        if not experts:
            raise HarnessError(
                f"用例 {case.case_id} 无可用专家契约", code="E7001",
            )
        session = ReviewSession(
            coordinator_contract=self.coordinator,
            expert_contracts=experts,
            verifier_contract=self.verifier,
            invoker=self.invoker,
            memory=self.memory_factory() if self.memory_factory else None,
            audit=self.audit,
        )
        return session.run(case.question, context=dict(case.context))

    # ---- 批量回归 ----
    def run_suite(
        self,
        suite: "CaseSuite",
        *,
        baseline: "BaselineSnapshot | None" = None,
        stability_runs: int = 1,
        judge=None,
        judge_pass_threshold: float = 0.6,
    ) -> RegressionReport:
        if not suite.cases:
            raise HarnessError("用例库为空", code="E7001")
        report = RegressionReport(
            suite_id=suite.suite_id,
            baseline_id=baseline.baseline_id if baseline else None,
            stability_runs=stability_runs,
        )
        for case in suite.cases:
            started = time.time()
            cr = CaseResult(case_id=case.case_id, expect_disagreement=case.expect_disagreement)
            runs: list[ReviewResult] = []
            run_count = max(1, stability_runs)
            try:
                for _ in range(run_count):
                    runs.append(self._run_case_once(case))
            except HarnessError:
                raise
            except Exception as e:  # noqa: BLE001 - 单用例失败记录后继续
                cr.failures.append(f"执行异常: {e}")
                cr.duration_ms = int((time.time() - started) * 1000)
                report.case_results.append(cr)
                continue
            primary = runs[0]
            cr.review_id = primary.review_id
            cr.trace_id = primary.trace_id
            cr.final_answer = primary.final_answer
            for o in primary.expert_outcomes:
                cr.per_expert[o.role_id] = {
                    "status": o.status.value,
                    "violations": [v.model_dump() for v in o.violations],
                    "output": o.output,
                    "evidence_required": _evidence_required_for(self.contracts.get(o.role_id)),
                }
            cr.verdict_passed = primary.verifier_verdict.passed if primary.verifier_verdict else None
            cr.disagreement_detected = bool(primary.disagreements)
            if primary.status == ReviewStatus.FAILED:
                cr.failures.append(primary.error or "会审失败")
            # 稳定性：多次运行结论一致性
            if run_count >= 2:
                conclusions = [
                    tuple(sorted(
                        (o.role_id, str((o.output or {}).get("conclusion", "")))
                        for o in r.expert_outcomes if o.status == ExpertStatus.COMPLETED
                    ))
                    for r in runs
                ]
                cr.stability_conclusion = len(set(conclusions)) == 1
            # 关键词与 Schema 断言
            for kw in case.expected_keywords:
                if kw not in cr.final_answer and not any(
                    kw in str(e.get("output", {})) for e in cr.per_expert.values()
                ):
                    cr.failures.append(f"缺少期望关键词: {kw}")
            if case.expected_schema:
                from wbr.core.schema.validator import validate as schema_validate

                for role_id, e in cr.per_expert.items():
                    out = e.get("output")
                    if isinstance(out, dict):
                        errs = schema_validate(out, case.expected_schema)
                        cr.failures.extend(
                            f"{role_id} 违反期望 Schema: {err.path} {err.message}" for err in errs
                        )
            # Judge 钩子
            if judge is not None:
                score = judge.judge(case, primary)
                cr.judge_score = score.score
                cr.judge_rationale = score.rationale
                if score.score < judge_pass_threshold:
                    cr.failures.append(f"AI Judge 低分: {score.score:.2f} < {judge_pass_threshold}")
            cr.passed = (
                cr.verdict_passed is True
                and not cr.failures
                and (cr.stability_conclusion is not False)
            )
            cr.duration_ms = int((time.time() - started) * 1000)
            report.case_results.append(cr)
        report.metrics = from_case_results(report.case_results, stability_runs=stability_runs)
        report.finished_at = time.time()
        return report


def _evidence_required_for(contract) -> bool:
    if contract is None:
        return False
    return bool(contract.evidence_spec.required and contract.evidence_spec.min_citations > 0)
