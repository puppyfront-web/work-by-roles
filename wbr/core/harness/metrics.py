"""Harness 核心指标统计与能力退化检测（SPEC-004 §1.4）。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from wbr.core.orchestration.review import ExpertStatus, ViolationKind

if TYPE_CHECKING:  # pragma: no cover
    from wbr.core.harness.engine import CaseResult


class HarnessMetrics(BaseModel):
    """六项核心指标（全部 0~1；None = 分母为 0 无法计算）。"""

    contract_compliance_rate: float | None = None      # 契约合规率
    schema_pass_rate: float | None = None              # 输出 Schema 达标率
    forbidden_violation_rate: float | None = None      # 禁区违规率（越低越好）
    evidence_completeness_rate: float | None = None    # 证据完整率
    expert_conclusion_stability: float | None = None   # 专家结论稳定性
    disagreement_detection_rate: float | None = None   # 分歧检出率
    overall_pass_rate: float | None = None             # 用例通过率
    sample_sizes: dict[str, int] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items()}

    def delta(self, previous: HarnessMetrics) -> dict[str, float]:
        """相对上一份报告的指标变化（负值=恶化）。"""
        out: dict[str, float] = {}
        for field_name in (
            "contract_compliance_rate",
            "schema_pass_rate",
            "forbidden_violation_rate",
            "evidence_completeness_rate",
            "expert_conclusion_stability",
            "disagreement_detection_rate",
            "overall_pass_rate",
        ):
            prev = getattr(previous, field_name)
            cur = getattr(self, field_name)
            if prev is not None and cur is not None:
                out[field_name] = round(cur - prev, 6)
        return out


def from_case_results(
    case_results: list[CaseResult], *, stability_runs: int = 1
) -> HarnessMetrics:
    """由用例结果自动统计六项指标。"""

    total_exec = 0
    compliant = 0
    schema_ok = 0
    forbidden_hits = 0
    evidence_required = 0
    evidence_ok = 0
    for cr in case_results:
        for role_id, eo in cr.per_expert.items():
            total_exec += 1
            violations = eo.get("violations") or []
            kinds = {v.get("kind") for v in violations}
            if eo.get("status") == ExpertStatus.COMPLETED.value and not violations:
                compliant += 1
            if ViolationKind.SCHEMA.value not in kinds:
                schema_ok += 1
            if ViolationKind.FORBIDDEN.value in kinds:
                forbidden_hits += 1
            if eo.get("evidence_required"):
                evidence_required += 1
                if not ViolationKind.EVIDENCE.value in kinds:
                    evidence_ok += 1

    passed = sum(1 for cr in case_results if cr.passed)
    # 稳定性：跨重复运行结论一致的用例比例
    stability: float | None = None
    if stability_runs >= 2:
        stable_cases = sum(
            1 for cr in case_results if cr.stability_conclusion is not None and cr.stability_conclusion
        )
        measured = sum(1 for cr in case_results if cr.stability_conclusion is not None)
        stability = stable_cases / measured if measured else None
    # 分歧检出率：expect_disagreement 用例中被检出的比例
    expect_cases = [cr for cr in case_results if cr.expect_disagreement]
    detected = sum(1 for cr in expect_cases if cr.disagreement_detected)
    metrics = HarnessMetrics(
        contract_compliance_rate=round(compliant / total_exec, 6) if total_exec else None,
        schema_pass_rate=round(schema_ok / total_exec, 6) if total_exec else None,
        forbidden_violation_rate=round(forbidden_hits / total_exec, 6) if total_exec else None,
        evidence_completeness_rate=round(evidence_ok / evidence_required, 6) if evidence_required else None,
        expert_conclusion_stability=stability,
        disagreement_detection_rate=round(detected / len(expect_cases), 6) if expect_cases else None,
        overall_pass_rate=round(passed / len(case_results), 6) if case_results else None,
        sample_sizes={
            "expert_executions": total_exec,
            "cases": len(case_results),
            "evidence_required": evidence_required,
            "disagreement_cases": len(expect_cases),
        },
    )
    return metrics


def detect_degradation(
    previous: HarnessMetrics,
    current: HarnessMetrics,
    *,
    threshold: float = -0.05,
) -> list[dict[str, Any]]:
    """检测能力退化：任一指标下降超过 threshold（负数）即报告。"""
    degradations: list[dict[str, Any]] = []
    for metric, delta in current.delta(previous).items():
        if metric == "forbidden_violation_rate":
            # 该指标为"越低越好"：上升才是退化，换算为负向值参与判定
            effective = -delta
        else:
            effective = delta
        if effective <= threshold:
            degradations.append(
                {
                    "metric": metric,
                    "previous": getattr(previous, metric),
                    "current": getattr(current, metric),
                    "delta": round(delta, 6),
                }
            )
    return degradations
