"""Harness 专项指标扩展（补充方案 §六 / SPEC-009 §5）。

三组指标：意图识别 / 角色内部 Loop / 辩论 Loop。全部 0~1，None=分母为 0。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover
    from wbr.core.loop_config import LoopSummarySnapshot
    from wbr.core.orchestration.intent import IntentResult, IntentType
    from wbr.core.orchestration.debate import DebateResult


class IntentMetrics(BaseModel):
    accuracy: float | None = None              # 意图分类准确率（需期望标签）
    false_reject_rate: float | None = None     # 误拒绝率（非越界被拒）
    ambiguous_detection_rate: float | None = None  # 模糊请求识别率
    sample_sizes: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def from_results(cls, results, expected: list | None = None) -> "IntentMetrics":
        from wbr.core.orchestration.intent import IntentType

        total = len(results)
        if not total:
            return cls()
        rejects = sum(1 for r in results
                      if r.intent_type == IntentType.OUT_OF_SCOPE)
        ambiguous = sum(1 for r in results
                        if r.intent_type == IntentType.AMBIGUOUS)
        accuracy = None
        if expected is not None and len(expected) == total:
            correct = sum(1 for r, e in zip(results, expected)
                          if r.intent_type == e)
            accuracy = round(correct / total, 6)
        # 误拒：intent != OUT_OF_SCOPE 但被建议 reject
        false_rejects = sum(1 for r in results
                            if r.next_action.value == "reject"
                            and r.intent_type != IntentType.OUT_OF_SCOPE)
        ambiguous_total = sum(1 for e in (expected or [])
                              if e == IntentType.AMBIGUOUS)
        detected = sum(1 for r, e in zip(results, expected or [])
                       if e == IntentType.AMBIGUOUS
                       and r.intent_type == IntentType.AMBIGUOUS)
        return cls(
            accuracy=accuracy,
            false_reject_rate=round(false_rejects / total, 6),
            ambiguous_detection_rate=(round(detected / ambiguous_total, 6)
                                      if ambiguous_total else None),
            sample_sizes={"total": total, "rejects": rejects,
                          "ambiguous_expected": ambiguous_total},
        )


class LoopMetrics(BaseModel):
    avg_rounds: float | None = None
    timeout_rate: float | None = None          # max_rounds_risk 占比（循环超时率）
    loop_token_ratio: float | None = None      # 循环 token / 主任务 token
    escalate_rate: float | None = None         # 转入 HITL 占比（提前终止风险率）
    sample_sizes: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def from_snapshots(cls, snapshots, *, main_task_tokens: int = 0) -> "LoopMetrics":
        from wbr.core.loop_config import StopReason

        total = len(snapshots)
        if not total:
            return cls()
        timeouts = sum(1 for s in snapshots
                       if s.stopped_because == StopReason.MAX_ROUNDS_RISK.value)
        escalations = sum(1 for s in snapshots if s.escalated_hitl)
        loop_tokens = sum(s.token_used for s in snapshots)
        return cls(
            avg_rounds=round(sum(s.rounds_used for s in snapshots) / total, 6),
            timeout_rate=round(timeouts / total, 6),
            loop_token_ratio=(round(loop_tokens / main_task_tokens, 6)
                              if main_task_tokens else None),
            escalate_rate=round(escalations / total, 6),
            sample_sizes={"loops": total, "timeouts": timeouts,
                          "escalations": escalations},
        )


class DebateLoopMetrics(BaseModel):
    convergence_rate: float | None = None           # 辩论分歧收敛率
    round_limit_exceeded_rate: float | None = None  # 辩论轮次超限比例（转 HITL）
    sample_sizes: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def from_results(cls, results) -> "DebateLoopMetrics":
        total = len(results)
        if not total:
            return cls()
        converged = sum(1 for r in results if not r.escalated_to_hitl)
        exceeded = sum(1 for r in results if r.escalated_to_hitl)
        return cls(
            convergence_rate=round(converged / total, 6),
            round_limit_exceeded_rate=round(exceeded / total, 6),
            sample_sizes={"debates": total, "converged": converged,
                          "exceeded": exceeded},
        )

