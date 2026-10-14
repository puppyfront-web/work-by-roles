"""灰度 A/B 实验（V2.0 E5 / SPEC-008 §5）：确定性分流 + 双变体回归对比。

winner 三级判定（R27）：pass_rate 高者 → forbidden_rate 低者 → None（保守不切换）。
"""
from __future__ import annotations

import time
import uuid
from typing import Callable

from pydantic import BaseModel, Field

from wbr.core.canonical import sha256_hex
from wbr.core.exceptions import HarnessError
from wbr.core.harness import BaselineSnapshot, CaseSuite, RegressionEngine
from wbr.core.harness.baseline import BaselineSnapshot as _Snap
from wbr.core.orchestration.invoker import ModelInvoker


class ABVariant(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    name: str
    contracts: dict            # role_id -> RoleContract（运行时对象）
    suite: CaseSuite | None = None   # 变体独立用例库（默认共享实验套件）


class ABReport(BaseModel):
    experiment_id: str
    per_variant: dict = Field(default_factory=dict)     # name -> RegressionReport dict
    winner: str | None = None
    decision_reason: str = ""


class ABExperiment:
    """契约变体灰度实验：同构校验 → 确定性分流 → 各变体全量回归 → 裁决。"""

    def __init__(
        self,
        *,
        experiment_id: str | None = None,
        suite: CaseSuite,
        invoker: ModelInvoker,
        traffic_fn: Callable[[str, int], int] | None = None,
        audit=None,
        memory_factory=None,
    ) -> None:
        self.experiment_id = experiment_id or uuid.uuid4().hex
        self.suite = suite
        self.invoker = invoker
        self.traffic_fn = traffic_fn
        self.audit = audit
        self.memory_factory = memory_factory
        self.variants: dict[str, ABVariant] = {}
        self.baselines: dict[str, _Snap] = {}

    # ---- 变体 ----
    def add_variant(self, variant: ABVariant, suite: CaseSuite | None = None) -> None:
        if not variant.contracts:
            raise HarnessError("变体契约集为空", code="E7001")
        if self.variants:
            known = set(next(iter(self.variants.values())).contracts)
            if set(variant.contracts) != known:
                raise HarnessError(
                    "变体契约集必须同构（role_id 集合一致）", code="E7001",
                    details={"expected": sorted(known), "got": sorted(variant.contracts)},
                )
        if variant.name in self.variants:
            raise HarnessError(f"变体名已存在: {variant.name}", code="E7001")
        if suite is not None:
            variant.suite = suite
        self.variants[variant.name] = variant
        self.baselines[variant.name] = BaselineSnapshot.capture(
            contracts=variant.contracts, suite=variant.suite or self.suite,
            model_fingerprint=f"variant:{variant.name}",
        )

    # ---- 确定性分流 ----
    def split(self, key: str) -> str:
        if len(self.variants) < 2:
            raise HarnessError("至少两个变体才能分流", code="E7001")
        names = sorted(self.variants)
        if self.traffic_fn is not None:
            return names[self.traffic_fn(key, len(names))]
        idx = int(sha256_hex(f"{self.experiment_id}|{key}"), 16) % len(names)
        return names[idx]

    # ---- 运行 ----
    def run(self, *, runs_per_case: int = 1) -> ABReport:
        if len(self.variants) < 2:
            raise HarnessError("至少两个变体才能实验", code="E7001")
        per_variant: dict[str, dict] = {}
        for name, variant in sorted(self.variants.items()):
            engine = RegressionEngine(
                contracts=dict(variant.contracts),
                invoker=self.invoker,
                audit=self.audit,
                memory_factory=self.memory_factory,
            )
            variant_suite = variant.suite or self.suite
            report = engine.run_suite(
                variant_suite, baseline=self.baselines[name], stability_runs=runs_per_case
            )
            per_variant[name] = {
                "report": report.to_json_dict() if hasattr(report, "to_json_dict") else _dump(report),
                "overall_pass_rate": report.metrics.overall_pass_rate,
                "forbidden_violation_rate": report.metrics.forbidden_violation_rate,
            }
        winner, reason = self._decide(per_variant)
        return ABReport(experiment_id=self.experiment_id, per_variant=per_variant,
                        winner=winner, decision_reason=reason)

    @staticmethod
    def _decide(per_variant: dict) -> tuple[str | None, str]:
        def sort_key(item):
            stats = item[1]
            pr = stats["overall_pass_rate"] if stats["overall_pass_rate"] is not None else -1.0
            fr = stats["forbidden_violation_rate"] if stats["forbidden_violation_rate"] is not None else 1.0
            return (-pr, fr)

        ranked = sorted(per_variant.items(), key=sort_key)
        top_name, top = ranked[0]
        if len(ranked) > 1:
            second_name, second = ranked[1]
            if top["overall_pass_rate"] == second["overall_pass_rate"]:
                if (top["forbidden_violation_rate"] or 0) == (second["forbidden_violation_rate"] or 0):
                    return None, f"并列（pass_rate={top['overall_pass_rate']}），保守不切换"
                if (top["forbidden_violation_rate"] or 0) <= (second["forbidden_violation_rate"] or 0):
                    return top_name, f"pass_rate 并列，forbidden_violation_rate 更低（{top['forbidden_violation_rate']}）"
                return second_name, f"pass_rate 并列，forbidden_violation_rate 更低（{second['forbidden_violation_rate']}）"
        return top_name, f"overall_pass_rate 最高（{top['overall_pass_rate']}）"


def _dump(report) -> dict:
    import json

    return json.loads(report.to_json())
