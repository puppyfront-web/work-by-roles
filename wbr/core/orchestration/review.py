"""会审数据模型与执行引擎（SPEC-002 §6）。

流程：Coordinator 拆解 → 多专家并行 → Verifier 独立复核 → 分歧留存。
专家失败降级不阻断全场；strict 契约违规 → 该专家 FAILED 并留审计。
"""
from __future__ import annotations

import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from wbr.core.audit.models import AuditEvent, AuditEventType, RoleBehaviorRecord
from wbr.core.audit.trail import AuditTrail
from wbr.core.context import apply_context, current_context, new_trace_id, set_trace_id
from wbr.core.constants import MemoryLayer
from wbr.core.contract.compiler import ContractCompiler
from wbr.core.contract.models import RoleContract, RoleType
from wbr.core.exceptions import OrchestrationError
from wbr.core.memory.hub import MemoryHub
from wbr.core.orchestration.invoker import (
    ModelInvoker,
    ModelRequest,
    parse_json_output,
)
from wbr.core.schema.validator import validate as schema_validate

_CONCLUSION_KEY = "conclusion"  # 分歧检测读取的结论键
_CITATIONS_KEY = "citations"


class ExpertStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ViolationKind(str, Enum):
    SCHEMA = "schema"
    FORBIDDEN = "forbidden"
    EVIDENCE = "evidence"


class Violation(BaseModel):
    kind: ViolationKind
    detail: str
    path: str = ""


class ExpertOutcome(BaseModel):
    role_id: str
    contract_hash: str = ""
    status: ExpertStatus = ExpertStatus.PENDING
    sub_question: str = ""
    output: dict[str, Any] | None = None
    raw_text: str = ""
    violations: list[Violation] = Field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class Verdict(BaseModel):
    passed: bool
    scores: dict[str, float] = Field(default_factory=dict)
    comments: str = ""
    judge_role_id: str = ""
    raw_output: dict[str, Any] = Field(default_factory=dict)


class Disagreement(BaseModel):
    """分歧留存：专家结论冲突时记录，禁止仲裁抹平。"""

    between: list[str]
    topic: str
    positions: list[dict[str, Any]] = Field(default_factory=list)


class ReviewStatus(str, Enum):
    COMPLETED = "completed"
    COMPLETED_WITH_FAILURES = "completed_with_failures"
    FAILED = "failed"


class ReviewResult(BaseModel):
    review_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    trace_id: str = ""
    question: str = ""
    coordinator_plan: dict[str, Any] = Field(default_factory=dict)
    expert_outcomes: list[ExpertOutcome] = Field(default_factory=list)
    verifier_verdict: Verdict | None = None
    disagreements: list[Disagreement] = Field(default_factory=list)
    final_answer: str = ""
    status: ReviewStatus = ReviewStatus.COMPLETED
    error: str | None = None
    started_at: float = Field(default_factory=time.time)
    finished_at: float | None = None

    def outcome_by_role(self, role_id: str) -> ExpertOutcome | None:
        for o in self.expert_outcomes:
            if o.role_id == role_id:
                return o
        return None

    def to_json(self) -> str:
        return self.model_dump_json()

    def save(self, path: str) -> None:
        from pathlib import Path

        Path(path).write_text(self.to_json(), encoding="utf-8")


class ReviewSession:
    """最简无框架会审流程：Coordinator → 多专家并行 → Verifier 复核。"""

    def __init__(
        self,
        *,
        coordinator_contract: RoleContract,
        expert_contracts: list[RoleContract],
        verifier_contract: RoleContract,
        invoker: ModelInvoker,
        memory: MemoryHub | None = None,
        audit: AuditTrail | None = None,
        bus=None,
        max_workers: int | None = None,
        token_meter: Any | None = None,
        session_id: str | None = None,
    ) -> None:
        if coordinator_contract.role_type != RoleType.COORDINATOR:
            raise OrchestrationError("coordinator_contract 角色类型必须为 coordinator")
        if verifier_contract.role_type != RoleType.VERIFIER:
            raise OrchestrationError("verifier_contract 角色类型必须为 verifier")
        if not expert_contracts:
            raise OrchestrationError("至少需要一个专家契约")
        for c in expert_contracts:
            if c.role_type != RoleType.EXPERT:
                raise OrchestrationError(f"专家契约 {c.role_id} 角色类型必须为 expert")
        self._coordinator = coordinator_contract
        self._experts = sorted(expert_contracts, key=lambda c: c.role_id)  # 确定性顺序
        self._verifier = verifier_contract
        self._invoker = invoker
        self._memory = memory
        self._audit = audit
        self._bus = bus
        self._max_workers = max_workers
        self._token_meter = token_meter
        self._session_id = session_id
        self._compiler = ContractCompiler()

    # ---- 公共入口 ----
    def run(self, question: str, *, context: dict[str, Any] | None = None) -> ReviewResult:
        result = ReviewResult(question=question)
        result.trace_id = new_trace_id()
        set_trace_id(result.trace_id)
        self._emit(AuditEventType.SESSION_STARTED, payload={"question_digest": _digest(question)})
        started = time.time()
        try:
            plan = self._run_coordinator(question, result)
            result.coordinator_plan = plan
            assignments = self._normalize_assignments(plan, question)
            outcomes = self._run_experts(assignments, result.trace_id)
            result.expert_outcomes = outcomes
            result.disagreements = self._detect_disagreements(outcomes)
            verdict = self._run_verifier(question, plan, outcomes)
            result.verifier_verdict = verdict
            result.final_answer = self._compose_final_answer(verdict, outcomes)
            has_failures = any(o.status == ExpertStatus.FAILED for o in outcomes)
            result.status = (
                ReviewStatus.COMPLETED_WITH_FAILURES if has_failures else ReviewStatus.COMPLETED
            )
        except OrchestrationError as e:
            result.status = ReviewStatus.FAILED
            result.error = str(e)
        except Exception as e:  # noqa: BLE001 - 会审不向调用方抛裸异常
            result.status = ReviewStatus.FAILED
            result.error = f"内部错误: {e}"
        finally:
            result.finished_at = time.time()
            self._emit(
                AuditEventType.REVIEW_COMPLETED,
                payload={
                    "status": result.status.value,
                    "disagreements": len(result.disagreements),
                    "duration_ms": int((result.finished_at - started) * 1000),
                },
            )
        return result

    # ---- 阶段：协调 ----
    def _run_coordinator(self, question: str, result: ReviewResult) -> dict[str, Any]:
        compiled = self._compile(self._coordinator, question)
        response = self._invoke(self._coordinator, compiled, result.trace_id)
        try:
            plan = parse_json_output(response.text)
        except ValueError as e:
            raise OrchestrationError(f"Coordinator 输出解析失败: {e}") from e
        self._check_contract_output(self._coordinator, plan, raw_text=response.text)
        return plan

    @staticmethod
    def _normalize_assignments(plan: dict[str, Any], question: str) -> dict[str, str]:
        assignments: dict[str, str] = {}
        known = None
        for a in plan.get("assignments", []):
            if isinstance(a, dict) and a.get("expert_role_id") and a.get("sub_question"):
                assignments[a["expert_role_id"]] = str(a["sub_question"])
        return assignments

    # ---- 阶段：专家并行 ----
    def _run_experts(self, assignments: dict[str, str], trace_id: str) -> list[ExpertOutcome]:
        ctx = current_context()
        workers = self._max_workers or min(len(self._experts), 8)
        with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="wbr-expert") as pool:
            futures = [
                pool.submit(self._run_one_expert, contract, assignments, ctx)
                for contract in self._experts
            ]
            outcomes = [f.result() for f in futures]
        outcomes.sort(key=lambda o: o.role_id)  # 确定性排序
        return outcomes

    def _run_one_expert(
        self, contract: RoleContract, assignments: dict[str, str], ctx
    ) -> ExpertOutcome:
        apply_context(ctx)
        sub_question = assignments.get(contract.role_id, "")
        outcome = ExpertOutcome(
            role_id=contract.role_id, contract_hash=contract.content_hash, sub_question=sub_question
        )
        started = time.time()
        self._emit(
            AuditEventType.EXPERT_STARTED, role_id=contract.role_id,
            payload={"sub_question": sub_question},
        )
        try:
            evidence = self._collect_evidence(contract)
            compiled = self._compile(contract, sub_question, evidence=evidence)
            response = self._invoke(contract, compiled, _trace_of(ctx))
            outcome.raw_text = response.text
            outcome.prompt_tokens = response.usage.prompt_tokens
            outcome.completion_tokens = response.usage.completion_tokens
            if self._token_meter is not None:
                self._token_meter.record(
                    contract.role_id, "expert", response.usage, _trace_of(ctx) or ""
                )
            try:
                output = parse_json_output(response.text)
            except ValueError as e:
                outcome.violations.append(Violation(kind=ViolationKind.SCHEMA, detail=str(e)))
                output = None
            if output is not None:
                outcome.output = output
                outcome.violations.extend(
                    self._check_contract_output(contract, output, raw_text=response.text)
                )
            if contract.output_spec.strict and outcome.violations:
                outcome.status = ExpertStatus.FAILED
                outcome.error = "; ".join(v.detail for v in outcome.violations)
            else:
                outcome.status = ExpertStatus.COMPLETED
        except Exception as e:  # noqa: BLE001 - 单专家失败降级
            outcome.status = ExpertStatus.FAILED
            outcome.error = str(e)
        finally:
            outcome.duration_ms = int((time.time() - started) * 1000)
        self._emit(
            AuditEventType.EXPERT_COMPLETED
            if outcome.status == ExpertStatus.COMPLETED
            else AuditEventType.EXPERT_FAILED,
            role_id=contract.role_id,
            payload={
                "status": outcome.status.value,
                "violations": [v.kind.value for v in outcome.violations],
                "duration_ms": outcome.duration_ms,
            },
        )
        if self._audit is not None:
            self._audit.append_behavior(
                RoleBehaviorRecord.from_texts(
                    role_id=contract.role_id,
                    action="expert_review",
                    trace_id=_trace_of(ctx) or "",
                    input_text=sub_question,
                    output_text=outcome.raw_text,
                    violations=[v.kind.value for v in outcome.violations],
                )
            )
        return outcome

    # ---- 阶段：复核 ----
    def _run_verifier(self, question: str, plan: dict, outcomes: list[ExpertOutcome]) -> Verdict:
        summary = json.dumps(
            {
                "question": question,
                "plan": plan,
                "expert_outputs": [
                    {
                        "role_id": o.role_id,
                        "status": o.status.value,
                        "sub_question": o.sub_question,
                        "output": o.output,
                        "violations": [v.model_dump() for v in o.violations],
                    }
                    for o in outcomes
                ],
                "disagreements": [d.model_dump() for d in self._detect_disagreements(outcomes)],
            },
            ensure_ascii=False,
        )
        compiled = self._compile(self._verifier, summary)
        response = self._invoke(self._verifier, compiled, _trace_of(current_context()) or "")
        try:
            raw = parse_json_output(response.text)
        except ValueError as e:
            raise OrchestrationError(f"Verifier 输出解析失败: {e}") from e
        self._check_contract_output(self._verifier, raw, raw_text=response.text)
        verdict = Verdict(
            passed=bool(raw.get("passed", False)),
            scores={str(k): float(v) for k, v in (raw.get("scores") or {}).items()},
            comments=str(raw.get("comments", "")),
            judge_role_id=self._verifier.role_id,
            raw_output=raw,
        )
        if self._audit is not None:
            self._audit.append_behavior(
                RoleBehaviorRecord.from_texts(
                    role_id=self._verifier.role_id,
                    action="verifier_review",
                    trace_id=_trace_of(current_context()) or "",
                    input_text=summary,
                    output_text=response.text,
                )
            )
        self._emit(
            AuditEventType.VERIFIER_VERDICT,
            role_id=self._verifier.role_id,
            payload={"passed": verdict.passed, "scores": verdict.scores},
        )
        return verdict

    # ---- 分歧检测（留存不仲裁） ----
    def _detect_disagreements(self, outcomes: list[ExpertOutcome]) -> list[Disagreement]:
        groups: dict[str, list[ExpertOutcome]] = {}
        for o in outcomes:
            if o.status == ExpertStatus.COMPLETED and o.sub_question:
                groups.setdefault(o.sub_question.strip(), []).append(o)
        disagreements: list[Disagreement] = []
        for topic, group in sorted(groups.items()):
            if len(group) < 2:
                continue
            positions = []
            for o in sorted(group, key=lambda x: x.role_id):
                conclusion = (o.output or {}).get(_CONCLUSION_KEY)
                if conclusion is not None:
                    positions.append({"role_id": o.role_id, _CONCLUSION_KEY: conclusion})
            distinct = {str(p[_CONCLUSION_KEY]) for p in positions}
            if len(distinct) > 1:
                disagreements.append(
                    Disagreement(
                        between=sorted(p["role_id"] for p in positions),
                        topic=topic,
                        positions=positions,
                    )
                )
        return disagreements

    # ---- 工具 ----
    def _compose_final_answer(self, verdict: Verdict | None, outcomes: list[ExpertOutcome]) -> str:
        if verdict is None:
            return "复核未完成：Verifier 输出不可用"
        if verdict.passed:
            raw = verdict.raw_output
            if isinstance(raw.get("final_answer"), str) and raw["final_answer"]:
                return raw["final_answer"]
            parts = []
            for o in sorted(outcomes, key=lambda x: x.role_id):
                if o.status == ExpertStatus.COMPLETED and o.output:
                    parts.append(f"{o.role_id}: {o.output.get(_CONCLUSION_KEY, o.raw_text[:200])}")
            return "\n".join(parts)
        return f"复核未通过：{verdict.comments}"

    def _check_contract_output(
        self, contract: RoleContract, output: dict[str, Any], *, raw_text: str
    ) -> list[Violation]:
        violations: list[Violation] = []
        if contract.output_spec.schema_:
            errs = schema_validate(output, contract.output_spec.schema_)
            violations.extend(
                Violation(kind=ViolationKind.SCHEMA, detail=f"{e.path}: {e.message}")
                for e in errs
            )
        for b in contract.forbidden.behaviors:
            if b and b in raw_text:
                violations.append(
                    Violation(kind=ViolationKind.FORBIDDEN, detail=f"命中禁止行为: {b}")
                )
        for d in contract.forbidden.domains:
            if d and d in raw_text:
                violations.append(
                    Violation(kind=ViolationKind.FORBIDDEN, detail=f"命中禁止回答域: {d}")
                )
        ev = contract.evidence_spec
        if ev.required and ev.min_citations > 0:
            citations = output.get(_CITATIONS_KEY)
            if not isinstance(citations, list) or len(citations) < ev.min_citations:
                violations.append(
                    Violation(
                        kind=ViolationKind.EVIDENCE,
                        detail=f"证据引用不足: 需要≥{ev.min_citations}, 实得 {citations if not isinstance(citations, list) else len(citations)}",
                    )
                )
        for v in violations:
            event_type = (
                AuditEventType.SCHEMA_VIOLATION
                if v.kind == ViolationKind.SCHEMA
                else AuditEventType.FORBIDDEN_VIOLATION
            )
            self._emit(event_type, role_id=contract.role_id, payload={"detail": v.detail})
        return violations

    def _compile(self, contract: RoleContract, user_input: str, *, evidence: list[str] | None = None):
        compiled = self._compiler.compile(contract, user_input, evidence=evidence)
        self._emit(
            AuditEventType.CONTRACT_COMPILED,
            role_id=contract.role_id,
            payload={"contract_hash": contract.content_hash[:16]},
        )
        return compiled

    def _collect_evidence(self, contract: RoleContract) -> list[str] | None:
        """从可读记忆层收集证据材料（契约声明的 read_layers 中 GLOBAL_SHARED/ROLE_STATIC 的 evidence_* 键）。"""
        if self._memory is None:
            return None
        items: list[str] = []
        for layer in (MemoryLayer.GLOBAL_SHARED, MemoryLayer.ROLE_STATIC):
            if layer not in contract.memory_permissions.read_layers:
                continue
            try:
                for key in self._memory.keys_of(layer, contract=contract):
                    if key.startswith("evidence_"):
                        value = self._memory.read(layer, key, contract=contract)
                        if value is not None:
                            items.append(str(value))
            except Exception:  # noqa: BLE001 - 证据收集失败不阻断
                continue
        return items or None

    def _invoke(self, contract: RoleContract, compiled, trace_id: str):
        snapshot = {}
        if self._memory is not None:
            snapshot = self._memory_snapshot(contract)
        request = ModelRequest(
            role_contract=contract,
            compiled_prompt=compiled,
            trace_id=trace_id,
            memory_snapshot=snapshot,
        )
        return self._invoker.invoke(request)

    def _memory_snapshot(self, contract: RoleContract) -> dict[str, Any]:
        snap: dict[str, Any] = {}
        for layer in contract.memory_permissions.read_layers:
            try:
                for key in self._memory.keys_of(layer, contract=contract):
                    snap[f"{layer.value}:{key}"] = self._memory.read(layer, key, contract=contract)
            except Exception:  # noqa: BLE001
                continue
        return snap

    def _emit(self, event_type: AuditEventType, role_id: str | None = None, payload: dict | None = None):
        trace_id = _trace_of(current_context()) or "no-trace"
        if self._audit is not None:
            self._audit.append(
                AuditEvent(
                    event_type=event_type, trace_id=trace_id, role_id=role_id, payload=payload or {}
                )
            )
        if self._bus is not None:
            self._bus.publish_safe(
                AuditEvent(
                    event_type=event_type, trace_id=trace_id, role_id=role_id, payload=payload or {}
                ).to_bus_event()
            )


def _digest(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _trace_of(ctx) -> str | None:
    return ctx.trace_id if ctx is not None else None
