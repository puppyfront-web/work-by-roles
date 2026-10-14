"""受控专家辩论（V2.0 E3 / SPEC-008 §3 / R26）。

仅对已检出 disagreement 组织辩论；轮次封顶；让步提前终止；
违规禁言；辩论历史原样留存（unresolved 不仲裁抹平）。
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from wbr.core.audit.models import AuditEvent, AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.contract.compiler import ContractCompiler
from wbr.core.contract.models import RoleContract, RoleType
from wbr.core.orchestration.invoker import ModelInvoker, ModelRequest, parse_json_output
from wbr.core.orchestration.review import Disagreement
from wbr.core.schema.validator import validate as schema_validate


class DebateConfig(BaseModel):
    max_rounds: int = Field(default=2, ge=1, le=10)
    require_rebuttal: bool = True


class DebateTurn(BaseModel):
    round_no: int
    role_id: str
    statement: str
    agrees_with: list[str] = Field(default_factory=list)
    concedes: bool = False
    muted: bool = False


class DebateResult(BaseModel):
    topic: str
    rounds: list[list[DebateTurn]] = Field(default_factory=list)
    concessions: list[str] = Field(default_factory=list)
    unresolved_disagreements: list[Disagreement] = Field(default_factory=list)


DEBATE_SCHEMA = {
    "type": "object",
    "required": ["statement", "agrees_with", "concedes"],
    "properties": {
        "statement": {"type": "string", "minLength": 2},
        "agrees_with": {"type": "array", "items": {"type": "string"}},
        "concedes": {"type": "boolean"},
    },
}


class DebateModerator:
    """辩论主持：受控轮次、违规禁言、历史留存。"""

    def __init__(
        self,
        *,
        contracts: dict[str, RoleContract],
        invoker: ModelInvoker,
        config: DebateConfig | None = None,
        audit: AuditTrail | None = None,
    ) -> None:
        self._experts = {
            rid: c for rid, c in contracts.items() if c.role_type == RoleType.EXPERT
        }
        referees = [c for c in contracts.values() if c.role_type == RoleType.VERIFIER]
        if not referees:
            raise ValueError("辩论需要至少一个 verifier 角色作为裁判")
        self._referee = referees[0]
        if not self._experts:
            raise ValueError("辩论需要至少一个 expert 角色")
        self._invoker = invoker
        self._config = config or DebateConfig()
        self._audit = audit
        self._compiler = ContractCompiler()

    # ---- 入口 ----
    def run(self, question: str, disputed: list[Disagreement]) -> DebateResult:
        result = DebateResult(topic=disputed[0].topic if disputed else "")
        if not disputed:
            return result
        active = {
            rid for d in disputed for rid in d.between if rid in self._experts
        }
        for round_no in range(1, self._config.max_rounds + 1):
            turns = self._run_round(round_no, question, disputed, sorted(active))
            result.rounds.append(turns)
            conceded = [t.role_id for t in turns if t.concedes]
            result.concessions.extend(conceded)
            active -= set(conceded)
            if conceded or not active:
                break
        # 未达成一致的分歧原样留存（不仲裁）
        if not result.concessions:
            result.unresolved_disagreements = list(disputed)
        return result

    # ---- 单轮 ----
    def _run_round(
        self, round_no: int, question: str, disputed: list[Disagreement], speakers: list[str]
    ) -> list[DebateTurn]:
        context = self._debate_context(disputed)
        turns: list[DebateTurn] = []
        for rid in speakers:
            contract = self._experts[rid]
            prompt = (
                f"辩论议题：{disputed[0].topic}\n问题：{question}\n"
                f"历史发言：{context}\n"
                f"请发言（可引用其他角色立场；若认可某方请在 agrees_with 列出其 role_id；"
                f"放弃己方立场则 concedes=true）"
            )
            statement, violation = self._speak(contract, prompt)
            if violation is not None:
                turns.append(DebateTurn(round_no=round_no, role_id=rid, statement="",
                                        muted=True))
                self._emit(rid, f"违规禁言: {violation}")
                continue
            turns.append(
                DebateTurn(round_no=round_no, role_id=rid, statement=statement["statement"],
                           agrees_with=statement.get("agrees_with", []),
                           concedes=bool(statement.get("concedes")))
            )
        return turns

    def _speak(self, contract: RoleContract, prompt: str) -> tuple[dict[str, Any] | None, str | None]:
        from wbr.core.orchestration.invoker import ModelRequest

        compiled = self._compiler.compile(contract, prompt)
        response = self._invoker.invoke(
            ModelRequest(role_contract=contract, compiled_prompt=compiled, trace_id="")
        )
        try:
            output = parse_json_output(response.text)
        except ValueError as e:
            return None, f"输出非 JSON: {e}"
        errs = schema_validate(output, DEBATE_SCHEMA)
        if errs:
            return None, f"{errs[0].path}: {errs[0].message}"
        return output, None

    @staticmethod
    def _debate_context(disputed: list[Disagreement]) -> str:
        return json.dumps(
            [{"topic": d.topic,
              "positions": d.positions} for d in disputed],
            ensure_ascii=False,
        )

    def _emit(self, role_id: str, detail: str) -> None:
        if self._audit is not None:
            self._audit.append(
                AuditEvent(event_type=AuditEventType.FORBIDDEN_VIOLATION, trace_id="no-trace",
                           role_id=role_id, payload={"detail": detail})
            )
