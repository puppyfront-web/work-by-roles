"""AI Judge 评估钩子 + 启发式基础实现（SPEC-004 §1.5）。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover
    from wbr.core.harness.cases import GoldenCase
    from wbr.core.orchestration.review import ReviewResult


class JudgeScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    rationale: str = ""
    judge_id: str = "heuristic"


@runtime_checkable
class JudgeHook(Protocol):
    """AI Judge 钩子：回归引擎可注入任意外部评估器（含 LLM Judge）。"""

    def judge(self, case: GoldenCase, result: ReviewResult) -> JudgeScore: ...


class HeuristicJudge:
    """基础规则 Judge：关键词命中率 + Schema 通过 + 证据引用的加权分。"""

    def __init__(
        self,
        *,
        keyword_weight: float = 0.5,
        schema_weight: float = 0.3,
        evidence_weight: float = 0.2,
        judge_id: str = "heuristic",
    ) -> None:
        total = keyword_weight + schema_weight + evidence_weight
        self.keyword_weight = keyword_weight / total
        self.schema_weight = schema_weight / total
        self.evidence_weight = evidence_weight / total
        self.judge_id = judge_id

    def judge(self, case: GoldenCase, result: ReviewResult) -> JudgeScore:
        # 关键词命中
        text_pool = result.final_answer + "\n" + "\n".join(
            o.raw_text for o in result.expert_outcomes
        )
        if case.expected_keywords:
            hit = sum(1 for kw in case.expected_keywords if kw in text_pool)
            keyword_score = hit / len(case.expected_keywords)
        else:
            keyword_score = 1.0
        # Schema 达标
        from wbr.core.schema.validator import validate as schema_validate

        if case.expected_schema:
            outs = [o.output for o in result.expert_outcomes if isinstance(o.output, dict)]
            ok = sum(1 for o in outs if not schema_validate(o, case.expected_schema))
            schema_score = ok / len(outs) if outs else 0.0
        else:
            schema_score = 1.0
        # 证据引用
        if result.expert_outcomes:
            with_citations = sum(
                1 for o in result.expert_outcomes
                if isinstance(o.output, dict) and o.output.get("citations")
            )
            evidence_score = with_citations / len(result.expert_outcomes)
        else:
            evidence_score = 0.0
        score = (
            self.keyword_weight * keyword_score
            + self.schema_weight * schema_score
            + self.evidence_weight * evidence_score
        )
        return JudgeScore(
            score=round(min(1.0, score), 4),
            rationale=(
                f"keywords={keyword_score:.2f} schema={schema_score:.2f} evidence={evidence_score:.2f}"
            ),
            judge_id=self.judge_id,
        )
