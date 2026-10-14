"""反馈闭环（V1.x F4 / SPEC-007 §4）：线上反馈 → 黄金用例 → 回归修正。

复用既有 Harness 通道（GoldenCase + RegressionEngine），不新建评估体系；事件入审计。
"""
from __future__ import annotations

import time
import uuid
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, Field

from wbr.core.audit.models import AuditEvent, AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.harness.cases import CaseSuite, GoldenCase

Rating = Literal["up", "down"]


class FeedbackRecord(BaseModel):
    feedback_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    review_id: str
    trace_id: str = ""
    rating: str                     # up | down
    question: str = ""
    comment: str = ""
    reviewer: str = "anonymous"
    categories: list[str] = Field(default_factory=list)
    ts: float = Field(default_factory=time.time)


class FeedbackLoop:
    """反馈闭环：记录人工反馈 → 统计 → 负反馈聚合为黄金用例。"""

    def __init__(self, *, audit: AuditTrail | None = None) -> None:
        self._records: list[FeedbackRecord] = []
        self._aggregated: set[str] = set()   # 已转用例的问题
        self._audit = audit

    def record(
        self,
        *,
        review_id: str,
        trace_id: str = "",
        rating: Rating,
        question: str = "",
        comment: str = "",
        reviewer: str = "anonymous",
        categories: list[str] | None = None,
    ) -> FeedbackRecord:
        if rating not in ("up", "down"):
            raise ValueError("rating 必须是 'up' 或 'down'")
        rec = FeedbackRecord(
            review_id=review_id, trace_id=trace_id, rating=rating, question=question,
            comment=comment, reviewer=reviewer, categories=categories or [],
        )
        self._records.append(rec)
        self._emit(rec)
        return rec

    def stats(self) -> dict[str, Any]:
        total = len(self._records)
        ups = sum(1 for r in self._records if r.rating == "up")
        downs = total - ups
        by_category: Counter[str] = Counter(
            c for r in self._records for c in r.categories
        )
        return {
            "total": total,
            "up": ups,
            "down": downs,
            "down_rate": round(downs / total, 6) if total else 0.0,
            "by_category": dict(by_category),
        }

    def pending_questions(self) -> list[str]:
        """有 down 反馈、尚未聚合为黄金用例的问题（去重，稳定排序）。"""
        questions = {
            r.question.strip() for r in self._records
            if r.rating == "down" and r.question.strip()
        }
        return sorted(q for q in questions if q not in self._aggregated)

    def to_golden_cases(self, *, min_samples: int = 3, suite_id: str = "feedback-suite") -> CaseSuite:
        """把 down 反馈按问题聚合为黄金用例（回归负样本）；达到 min_samples 才收录。"""
        suite = CaseSuite(suite_id=suite_id)
        groups: dict[str, list[FeedbackRecord]] = {}
        for r in self._records:
            if r.rating == "down" and r.question.strip():
                groups.setdefault(r.question.strip(), []).append(r)
        for question in sorted(groups):
            records = groups[question]
            if len(records) < min_samples:
                continue
            tags = sorted({c for r in records for c in r.categories})
            notes = "；".join(
                r.comment for r in records if r.comment
            ) or f"{len(records)} 条负反馈"
            suite.add(GoldenCase(
                case_id=f"fb-{uuid.uuid4().hex[:8]}",
                question=question,
                tags=[*tags, "from_feedback"],
                notes=notes,
            ))
            self._aggregated.add(question)
        return suite

    def records(self) -> list[FeedbackRecord]:
        return list(self._records)

    def _emit(self, rec: FeedbackRecord) -> None:
        if self._audit is not None:
            self._audit.append(
                AuditEvent(
                    event_type=AuditEventType.MEMORY_ACCESS,
                    trace_id=rec.trace_id or "no-trace",
                    payload={
                        "fb_event": "feedback",
                        "rating": rec.rating,
                        "review_id": rec.review_id,
                        "question": rec.question[:80],
                        "categories": rec.categories,
                    },
                )
            )
