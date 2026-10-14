"""类型A：单角色内部推理 Loop（补充方案 §三 / SPEC-009 §2）。

受控循环：max_rounds 封顶 / 证据充足退出 / 独立 token 配额（耗尽转 HITL 或强制退出）；
每轮结构化产出并入审计（LOOP_STEP）；退出输出快照摘要（不灌原始消息）；支持缓存跳过。
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from wbr.core.audit.models import AuditEvent, AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.cache.contract_cache import ContractBoundCache
from wbr.core.constants import MemoryLayer
from wbr.core.contract.compiler import ContractCompiler
from wbr.core.contract.models import RoleContract
from wbr.core.orchestration.invoker import ModelInvoker, ModelRequest, parse_json_output
from wbr.core.loop_config import (
    InnerLoopConfig,
    LoopRound,
    LoopSummarySnapshot,
    LOOP_SCHEMA,
    QuotaExhaustedAction,
    StopReason,
)
from wbr.core.schema.validator import validate as schema_validate
from wbr.core.token.meter import TokenBudget, TokenMeter

LOOP_SCHEMA = {
    "type": "object",
    "required": ["conclusion", "evidence", "continue_loop", "reason"],
    "properties": {
        "conclusion": {"type": "string", "minLength": 1},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "continue_loop": {"type": "boolean"},
        "reason": {"type": "string"},
    },
}


class InnerLoopExecutor:
    """单角色内部推理循环执行器。config 缺省读契约 inner_loop 字段（契约约束，无上限构造不存在）。"""

    def __init__(
        self,
        *,
        contract: RoleContract,
        invoker: ModelInvoker,
        config: InnerLoopConfig | None = None,
        memory: Any = None,
        cache: ContractBoundCache | None = None,
        meter: TokenMeter | None = None,
        audit: AuditTrail | None = None,
        session_id: str | None = None,
    ) -> None:
        self._contract = contract
        self._invoker = invoker
        self._config = config or contract.inner_loop or InnerLoopConfig()
        self._memory = memory
        self._cache = cache
        self._meter = meter or TokenMeter()
        self._audit = audit
        self._session_id = session_id
        self._compiler = ContractCompiler()

    # ---- 入口 ----
    def run(self, sub_question: str, *, session_id: str | None = None) -> LoopSummarySnapshot:
        session_id = session_id or self._session_id
        # 缓存：相同子问题+证据快照直接跳过循环
        if self._cache is not None:
            cached = self._cache.get(self._contract, f"inner-loop:{sub_question}", None)
            if cached is not None:
                snap = LoopSummarySnapshot.model_validate(cached)
                snap.stopped_because = StopReason.EVIDENCE_SATISFIED.value
                return snap

        evidence: list[str] = []
        conclusion = ""
        rounds_used = 0
        tokens = 0
        stopped = StopReason.MAX_ROUNDS_RISK
        escalated = False

        for round_no in range(1, self._config.max_rounds + 1):
            if self._quota_left(tokens) <= 0:
                if self._config.on_quota_exhausted == QuotaExhaustedAction.ESCALATE_HITL:
                    stopped = StopReason.QUOTA_EXHAUSTED_HITL
                    escalated = True
                else:
                    stopped = StopReason.QUOTA_EXHAUSTED_EXIT
                break
            rnd, err = self._run_round(round_no, sub_question, evidence)
            if err is not None:
                self._emit(round_no, err, degraded=True)
                stopped = StopReason.MAX_ROUNDS_RISK
                break
            rounds_used = round_no
            conclusion = rnd.conclusion
            evidence = rnd.evidence
            tokens += rnd.prompt_tokens + rnd.completion_tokens
            self._emit(round_no, f"round {round_no}: {rnd.reason[:80]}",
                       payload={"conclusion": conclusion[:80],
                                "continue_loop": rnd.continue_loop,
                                "evidence_count": len(evidence)})
            self._memory_write(rnd)
            if not rnd.continue_loop:
                stopped = StopReason.EVIDENCE_SATISFIED
                break
            if round_no == self._config.max_rounds:
                stopped = StopReason.MAX_ROUNDS_RISK  # 达到上限强制退出并标记风险

        snapshot = LoopSummarySnapshot(
            role_id=self._contract.role_id,
            sub_question=sub_question,
            rounds_used=rounds_used,
            conclusion=conclusion,
            evidence=evidence,
            stopped_because=stopped.value,
            token_used=tokens,
            escalated_hitl=escalated,
        )
        if self._cache is not None:
            self._cache.put(self._contract, f"inner-loop:{sub_question}", None,
                            snapshot.model_dump())
        return snapshot

    # ---- 内部 ----
    def _quota_left(self, used: int) -> int:
        return self._config.loop_quota_tokens - used

    def _run_round(self, round_no: int, sub_question: str, evidence: list[str]):
        prompt = (
            f"子任务：{sub_question}\n"
            f"已有证据（{len(evidence)} 条）：{json_dumps(evidence)}\n"
            "推理并判断证据是否充足。输出 JSON：conclusion/evidence（新增证据列表）/"
            "continue_loop（证据不足且未达上限时 true）/reason。"
            f"本轮序号 {round_no}，最大轮次 {self._config.max_rounds}。"
        )
        compiled = self._compiler.compile(self._contract, prompt)
        response = self._invoker.invoke(
            ModelRequest(role_contract=self._contract, compiled_prompt=compiled,
                         trace_id="", memory_snapshot={})
        )
        usage = response.usage
        output = parse_json_output(response.text)
        errs = schema_validate(output, LOOP_SCHEMA)
        if errs:
            return None, f"{errs[0].path}: {errs[0].message}"
        rnd = LoopRound(
            round_no=round_no,
            conclusion=output["conclusion"],
            evidence=list(output.get("evidence", [])),
            continue_loop=bool(output["continue_loop"]),
            reason=output["reason"],
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )
        if self._meter is not None:
            self._meter.record(self._contract.role_id, "inner_loop", usage, degraded=False)
        return rnd, None

    def _memory_write(self, rnd: LoopRound) -> None:
        """循环内记忆只写本角色 ROLE_SESSION（契约权限门复用）。"""
        if self._memory is None:
            return
        try:
            self._memory.append(
                MemoryLayer.ROLE_SESSION, "inner_loop_trace",
                {"round": rnd.round_no, "conclusion": rnd.conclusion[:120]},
                contract=self._contract, session_id=self._session_id,
            )
        except Exception:  # noqa: BLE001 - 记忆失败不阻断循环
            pass

    def _emit(self, round_no: int, detail: str, *, degraded: bool = False,
              payload: dict | None = None) -> None:
        if self._audit is not None:
            self._audit.append(
                AuditEvent(event_type=AuditEventType.LOOP_STEP, trace_id="no-trace",
                           role_id=self._contract.role_id,
                           payload={"round": round_no, "detail": detail,
                                    "degraded": degraded, **(payload or {})}))


def json_dumps(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)
