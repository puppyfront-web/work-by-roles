"""标准化审计包导出（SPEC-004 §3）：全链路可追溯 JSON 交付物。"""
from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

import wbr
from wbr.core.audit.models import AuditEvent
from wbr.core.audit.trail import AuditTrail
from wbr.core.canonical import canonical_json, sha256_hex
from wbr.core.orchestration.review import ReviewResult

FORMAT_VERSION = "1.0"


class _SessionSummary(BaseModel):
    review_id: str
    trace_id: str
    question_digest: str
    status: str
    coordinator_plan: dict[str, Any] = Field(default_factory=dict)
    expert_summaries: list[dict[str, Any]] = Field(default_factory=list)
    verdict: dict[str, Any] | None = None
    disagreements: list[dict[str, Any]] = Field(default_factory=list)
    final_answer: str = ""


class AuditPack(BaseModel):
    format_version: str = FORMAT_VERSION
    exported_at: float = Field(default_factory=time.time)
    generator: dict[str, str] = Field(
        default_factory=lambda: {"name": "wbr", "version": wbr.__version__}
    )
    sessions: list[_SessionSummary] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    integrity: dict[str, Any] = Field(default_factory=dict)

    def to_json(self, indent: int | None = 2) -> str:
        import json

        return json.dumps(self.model_dump(), ensure_ascii=False, indent=indent)

    def save(self, path: str) -> None:
        from pathlib import Path

        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> AuditPack:
        import json
        from pathlib import Path

        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _digest(text: str) -> str:
    return sha256_hex(text)[:16]


class AuditPackBuilder:
    """从审计轨迹（可选 + ReviewResult）构建标准化审计包。

    include_contents=False（默认）时专家全文以摘要替代（脱敏导出）。
    """

    def __init__(
        self,
        trail: AuditTrail | None = None,
        *,
        include_contents: bool = False,
    ) -> None:
        self.trail = trail
        self.include_contents = include_contents

    def build(
        self,
        trace_ids: list[str] | None = None,
        results: list[ReviewResult] | None = None,
    ) -> AuditPack:
        events = self._select_events(trace_ids)
        sessions = self._build_sessions(trace_ids, results or [])
        pack = AuditPack(sessions=sessions, events=[e.model_dump() for e in events])
        pack.integrity = {
            "event_count": len(pack.events),
            "sessions_count": len(pack.sessions),
            "include_contents": self.include_contents,
            "content_digest": sha256_hex(canonical_json({
                "events": pack.events,
                "sessions": [s.model_dump() for s in pack.sessions],
            })),
        }
        return pack

    def _select_events(self, trace_ids: list[str] | None) -> list[AuditEvent]:
        if self.trail is None:
            return []
        if trace_ids is None:
            return sorted(self.trail.events, key=lambda e: e.ts)
        wanted = set(trace_ids)
        return sorted((e for e in self.trail.events if e.trace_id in wanted), key=lambda e: e.ts)

    def _build_sessions(
        self, trace_ids: list[str] | None, results: list[ReviewResult]
    ) -> list[_SessionSummary]:
        wanted = set(trace_ids) if trace_ids is not None else None
        out: list[_SessionSummary] = []
        for r in results:
            if wanted is not None and r.trace_id not in wanted:
                continue
            experts = []
            for o in r.expert_outcomes:
                item: dict[str, Any] = {
                    "role_id": o.role_id,
                    "contract_hash": o.contract_hash,
                    "status": o.status.value,
                    "sub_question": o.sub_question,
                    "violations": [v.model_dump() for v in o.violations],
                    "usage": {"prompt": o.prompt_tokens, "completion": o.completion_tokens},
                    "duration_ms": o.duration_ms,
                }
                if self.include_contents:
                    item["output"] = o.output
                    item["raw_text"] = o.raw_text
                else:
                    from wbr.core.canonical import digest_of_text

                    item["output_digest"] = digest_of_text(o.raw_text)
                experts.append(item)
            out.append(
                _SessionSummary(
                    review_id=r.review_id,
                    trace_id=r.trace_id,
                    question_digest=_digest(r.question),
                    status=r.status.value,
                    coordinator_plan=r.coordinator_plan if self.include_contents else {},
                    expert_summaries=experts,
                    verdict=r.verifier_verdict.model_dump() if r.verifier_verdict else None,
                    disagreements=[d.model_dump() for d in r.disagreements],
                    final_answer=r.final_answer,
                )
            )
        return out
