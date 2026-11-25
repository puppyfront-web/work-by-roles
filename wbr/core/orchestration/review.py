"""会审数据模型与执行引擎（SPEC-002 §6）。

流程：Coordinator 拆解 → 多专家并行 → Verifier 独立复核 → 分歧留存。
专家失败降级不阻断全场；strict 契约违规 → 该专家 FAILED 并留审计。
未分配子任务的专家默认跳过。可选接入 TokenBudget（超限跳过并审计，不向外抛）
与契约缓存（默认关闭，仅精确命中；语义命中需显式打开）。
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from wbr.core.audit.models import AuditEvent, AuditEventType, RoleBehaviorRecord
from wbr.core.audit.trail import AuditTrail
from wbr.core.cache.contract_cache import ContractBoundCache
from wbr.core.cache.semantic import SemanticCache
from wbr.core.constants import MemoryLayer
from wbr.core.context import apply_context, current_context, new_trace_id, set_trace_id
from wbr.core.contract.compiler import ContractCompiler
from wbr.core.contract.models import RoleContract, RoleType
from wbr.core.exceptions import OrchestrationError, TokenBudgetExceededError
from wbr.core.loop_config import LoopSummarySnapshot
from wbr.core.memory.hub import MemoryHub
from wbr.core.orchestration.invoker import (
    ModelInvoker,
    ModelRequest,
    ModelResponse,
    TokenUsage,
    completion_cap,
    parse_json_output,
)
from wbr.core.schema.validator import validate as schema_validate
from wbr.core.token.meter import BudgetAction, HeuristicTokenCounter, TokenBudget
from wbr.core.token.receipt import (
    BudgetSkip,
    SavingsReceipt,
    UnassignedFact,
    UsageFact,
    build_savings_receipt,
)

_CACHE_KIND = "review_output_v1"

_CONCLUSION_KEY = "conclusion"  # 分歧检测读取的结论键
_CITATIONS_KEY = "citations"


class ExpertStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


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
    cached_prompt_tokens: int = 0
    cache_hit: str = ""
    skip_reason: str = ""


class _BudgetSkip(Exception):
    """预算门禁内部信号：会审层转成跳过或停止，不向外抛。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _pack_cache(output: dict[str, Any], raw_text: str, usage) -> dict[str, Any]:
    return {
        "_wbr": _CACHE_KIND,
        "output": output,
        "raw_text": raw_text,
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
    }


def _unpack_cache(value: Any) -> tuple[dict[str, Any], str, TokenUsage] | None:
    if not isinstance(value, dict) or value.get("_wbr") != _CACHE_KIND:
        return None
    output = value.get("output")
    if not isinstance(output, dict):
        return None
    usage = TokenUsage(
        prompt_tokens=0,
        completion_tokens=0,
        cached_prompt_tokens=int(value.get("prompt_tokens") or 0),
        cache_scope="local",
    )
    return output, str(value.get("raw_text") or ""), usage


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
    savings: SavingsReceipt | None = None
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
        token_budget: TokenBudget | None = None,
        session_id: str | None = None,
        skip_unassigned_experts: bool = True,
        shared_context: str = "",
        response_cache: Any | None = None,
        allow_semantic_cache: bool = False,
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
        self._budget = token_budget
        if token_budget is not None and token_meter is None:
            token_meter = token_budget.meter
        self._token_meter = token_meter
        self._session_id = session_id
        self._skip_unassigned = skip_unassigned_experts
        self._shared_context = shared_context or ""
        self._response_cache = response_cache
        self._allow_semantic_cache = allow_semantic_cache
        self._active_shared = self._shared_context
        self._verifier_budget_reason = ""
        self._loop_snapshots: dict[str, Any] = {}
        self._compiler = ContractCompiler()
        self._facts_lock = threading.Lock()
        self._usage_facts: list[UsageFact] = []
        self._unassigned_facts: list[UnassignedFact] = []
        self._budget_skips: list[BudgetSkip] = []

    # ---- 公共入口 ----
    def run(
        self,
        question: str,
        *,
        context: dict[str, Any] | None = None,
        loop_snapshots: list[LoopSummarySnapshot] | None = None,
        shared_context: str | None = None,
    ) -> ReviewResult:
        """执行会审。

        loop_snapshots：可选的内循环总结快照（InnerLoopExecutor 产出），
        按角色注入对应专家的证据/上下文（SPEC-009 §4.4：快照进主流程，原始消息不进）。
        """
        result = ReviewResult(question=question)
        result.trace_id = new_trace_id()
        set_trace_id(result.trace_id)
        self._active_shared = self._shared_context if shared_context is None else shared_context
        self._verifier_budget_reason = ""
        self._loop_snapshots = {
            s.role_id: s for s in (loop_snapshots or [])
        }
        with self._facts_lock:
            self._usage_facts = []
            self._unassigned_facts = []
            self._budget_skips = []
        self._emit(AuditEventType.SESSION_STARTED, payload={"question_digest": _digest(question)})
        started = time.time()
        try:
            plan = self._run_coordinator(question, result)
            result.coordinator_plan = plan
            assignments = self._normalize_assignments(plan, question)
            outcomes = self._run_experts(assignments, result.trace_id, question=question)
            result.expert_outcomes = outcomes
            result.disagreements = self._detect_disagreements(outcomes)
            verdict = self._run_verifier(question, plan, outcomes)
            result.verifier_verdict = verdict
            if verdict is None and self._verifier_budget_reason:
                result.final_answer = (
                    f"复核未完成：Token 预算超限，已跳过（{self._verifier_budget_reason}）"
                )
            else:
                result.final_answer = self._compose_final_answer(verdict, outcomes)
            budget_hit = bool(self._verifier_budget_reason) or any(
                o.skip_reason == "budget" for o in outcomes
            )
            has_failures = any(o.status == ExpertStatus.FAILED for o in outcomes) or budget_hit
            result.status = (
                ReviewStatus.COMPLETED_WITH_FAILURES if has_failures else ReviewStatus.COMPLETED
            )
            if budget_hit and not result.error:
                result.error = self._verifier_budget_reason or "部分角色因 Token 预算超限已跳过"
        except OrchestrationError as e:
            result.status = ReviewStatus.FAILED
            result.error = str(e)
        except Exception as e:
            result.status = ReviewStatus.FAILED
            result.error = f"内部错误: {e}"
        finally:
            result.finished_at = time.time()
            result.savings = self._savings_receipt()
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
        try:
            response, cache_kind = self._obtain_model(
                self._coordinator, compiled, question, None, result.trace_id, "coordinator"
            )
        except _BudgetSkip as exc:
            self._remember_budget(self._coordinator.role_id, "coordinator")
            raise OrchestrationError(f"Coordinator 因 Token 预算超限已停止: {exc.reason}") from exc
        try:
            plan = parse_json_output(response.text)
        except ValueError as e:
            raise OrchestrationError(f"Coordinator 输出解析失败: {e}") from e
        self._check_contract_output(self._coordinator, plan, raw_text=response.text)
        if not cache_kind:
            self._store_cache(self._coordinator, question, None, plan, response.text, response.usage)
        return plan

    @staticmethod
    def _normalize_assignments(plan: dict[str, Any], question: str) -> dict[str, str]:
        assignments: dict[str, str] = {}
        for a in plan.get("assignments", []):
            if isinstance(a, dict) and a.get("expert_role_id") and a.get("sub_question"):
                assignments[a["expert_role_id"]] = str(a["sub_question"])
        return assignments

    # ---- 阶段：专家并行 ----
    def _run_experts(
        self, assignments: dict[str, str], trace_id: str, *, question: str = ""
    ) -> list[ExpertOutcome]:
        ctx = current_context()
        # 有预算时串行，使前一个角色的实际用量能挡住后一个角色。
        workers = 1 if self._budget is not None else (self._max_workers or min(len(self._experts), 8))
        with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="wbr-expert") as pool:
            futures = [
                pool.submit(self._run_one_expert, contract, assignments, ctx, question)
                for contract in self._experts
            ]
            outcomes = [f.result() for f in futures]
        outcomes.sort(key=lambda o: o.role_id)  # 确定性排序
        return outcomes

    def _run_one_expert(
        self, contract: RoleContract, assignments: dict[str, str], ctx, question: str = ""
    ) -> ExpertOutcome:
        apply_context(ctx)
        sub_question = assignments.get(contract.role_id, "")
        outcome = ExpertOutcome(
            role_id=contract.role_id, contract_hash=contract.content_hash, sub_question=sub_question
        )
        started = time.time()
        try:
            if self._skip_unassigned and not sub_question:
                outcome.status = ExpertStatus.SKIPPED
                outcome.skip_reason = "unassigned"
                outcome.error = "未分配子任务，已跳过"
                self._remember_unassigned(contract, question)
            else:
                self._emit(
                    AuditEventType.EXPERT_STARTED, role_id=contract.role_id,
                    payload={"sub_question": sub_question},
                )
                expert_input, evidence = self._prepare_expert_call(contract, sub_question, question)
                compiled = self._compile(contract, expert_input, evidence=evidence)
                try:
                    response, cache_kind = self._obtain_model(
                        contract, compiled, expert_input, evidence, _trace_of(ctx) or "", "expert"
                    )
                except _BudgetSkip as exc:
                    self._remember_budget(contract.role_id, "expert")
                    outcome.status = ExpertStatus.SKIPPED
                    outcome.skip_reason = "budget"
                    outcome.error = f"Token 预算超限，已跳过: {exc.reason}"
                else:
                    self._apply_model_output(outcome, contract, response, cache_kind)
                    if outcome.output is not None and not cache_kind:
                        self._store_cache(
                            contract, expert_input, evidence,
                            outcome.output, response.text, response.usage,
                        )
        except Exception as e:
            outcome.status = ExpertStatus.FAILED
            outcome.error = str(e)
        finally:
            outcome.duration_ms = int((time.time() - started) * 1000)
        if outcome.status == ExpertStatus.COMPLETED:
            finished = AuditEventType.EXPERT_COMPLETED
        elif outcome.status == ExpertStatus.SKIPPED:
            finished = AuditEventType.EXPERT_SKIPPED
        else:
            finished = AuditEventType.EXPERT_FAILED
        self._emit(
            finished,
            role_id=contract.role_id,
            payload={
                "status": outcome.status.value,
                "violations": [v.kind.value for v in outcome.violations],
                "duration_ms": outcome.duration_ms,
                "skip_reason": outcome.skip_reason,
                "cache_hit": outcome.cache_hit,
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
    def _run_verifier(self, question: str, plan: dict, outcomes: list[ExpertOutcome]) -> Verdict | None:
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
        try:
            response, cache_kind = self._obtain_model(
                self._verifier, compiled, summary, None,
                _trace_of(current_context()) or "", "verifier",
            )
        except _BudgetSkip as exc:
            self._remember_budget(self._verifier.role_id, "verifier")
            self._verifier_budget_reason = exc.reason
            self._emit(
                AuditEventType.VERIFIER_VERDICT,
                role_id=self._verifier.role_id,
                payload={"skipped": True, "reason": exc.reason},
            )
            return None
        try:
            raw = parse_json_output(response.text)
        except ValueError as e:
            raise OrchestrationError(f"Verifier 输出解析失败: {e}") from e
        self._check_contract_output(self._verifier, raw, raw_text=response.text)
        if not cache_kind:
            self._store_cache(self._verifier, summary, None, raw, response.text, response.usage)
        verdict = Verdict(
            passed=bool(raw.get("passed", False)),
            scores=self._coerce_scores(raw.get("scores")),
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

    # ---- 真实模型输出的容错 ----
    _NEGATIONS = ("未", "不", "没有", "不会", "不能", "不得", "切勿", "禁止", "避免", "严禁")

    @staticmethod
    def _coerce_scores(raw_scores: Any) -> dict[str, float]:
        """把 Verifier 的 scores 容错转换为 dict[str, float]。

        真实模型常返回嵌套结构（如 {"维度": {"score": 0.8, "评语": "…"}}）：
        dict 优先取常见分数字段，否则取数值叶子的均值；字符串尝试转 float；
        无法转换的键跳过（演示/老模板的平铺数字映射行为不变）。
        """
        if not isinstance(raw_scores, dict):
            return {}
        out: dict[str, float] = {}
        for key, value in raw_scores.items():
            num = ReviewSession._coerce_number(value)
            if num is not None:
                out[str(key)] = num
        return out

    @staticmethod
    def _coerce_number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        if isinstance(value, dict):
            for field in ("score", "value", "rating", "points"):
                if field in value:
                    num = ReviewSession._coerce_number(value[field])
                    if num is not None:
                        return num
            leafs = [n for n in (ReviewSession._coerce_number(v) for v in value.values()) if n is not None]
            return sum(leafs) / len(leafs) if leafs else None
        return None

    @staticmethod
    def _rule_segments(rule: str) -> list[str]:
        """把禁区规则按标点拆成 ≥4 字语义段，作为字面 tripwire 的匹配单元。"""
        segments = [p.strip() for p in re.split(r"[、，,;；。/]", rule) if len(p.strip()) >= 4]
        if not segments and rule.strip():
            segments = [rule.strip()]
        return segments

    @classmethod
    def _forbidden_hit(cls, rule: str, text: str) -> bool:
        """禁区字面 tripwire：规则段出现在输出、且前方紧邻无否定/自我约束词才计命中。

        禁区规则会编译进 system prompt，模型在自检中复述规则（"我未编造数据"）
        属于合规表现——纯字面匹配会把复述系统性误判为违规。
        """
        for segment in cls._rule_segments(rule):
            start = text.find(segment)
            while start != -1:
                window = text[max(0, start - 12): start]
                if not any(neg in window for neg in cls._NEGATIONS):
                    return True
                start = text.find(segment, start + 1)
        return False

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
            if b and self._forbidden_hit(b, raw_text):
                violations.append(
                    Violation(kind=ViolationKind.FORBIDDEN, detail=f"命中禁止行为: {b}")
                )
        for d in contract.forbidden.domains:
            if d and self._forbidden_hit(d, raw_text):
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

    def _prepare_expert_call(
        self, contract: RoleContract, sub_question: str, question: str
    ) -> tuple[str, list[str] | None]:
        evidence = self._collect_evidence(contract)
        snapshot = (self._loop_snapshots or {}).get(contract.role_id)
        if snapshot is not None:
            loop_ctx = (
                f"[内循环快照 {snapshot.role_id}] 轮次={snapshot.rounds_used} "
                f"结论={snapshot.conclusion} 证据={snapshot.evidence}"
            )
            evidence = [*(evidence or []), loop_ctx]
        # 专家输入必须携带原始问题：协调者的 sub_question 是聚焦指令，
        # 不保证自包含（真实协调者常产出"写故事型初稿"这类薄指令）。
        expert_input = f"{question}\n\n[你的子任务] {sub_question}" if sub_question else question
        return expert_input, evidence

    def _compile(self, contract: RoleContract, user_input: str, *, evidence: list[str] | None = None):
        compiled = self._compiler.compile(
            contract, user_input, evidence=evidence, shared_context=self._active_shared or None
        )
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
            except Exception:
                continue
        return items or None

    def _invoke(self, contract: RoleContract, compiled, trace_id: str, *, max_tokens: int | None = None):
        snapshot = {}
        if self._memory is not None:
            snapshot = self._memory_snapshot(contract)
        request = ModelRequest(
            role_contract=contract,
            compiled_prompt=compiled,
            trace_id=trace_id,
            memory_snapshot=snapshot,
            max_tokens=completion_cap(contract, max_tokens),
        )
        return self._invoker.invoke(request)

    def _obtain_model(
        self,
        contract: RoleContract,
        compiled,
        cache_input: str,
        evidence: list[str] | None,
        trace_id: str,
        step: str,
    ) -> tuple[ModelResponse, str]:
        """返回 (response, cache_kind)。cache_kind 为空表示真实调用。预算不足抛 _BudgetSkip。"""
        cached = self._take_cache(contract, cache_input, evidence)
        if cached is not None:
            response, kind = cached
            self._record_usage(contract.role_id, step, response.usage, trace_id)
            self._emit(
                AuditEventType.CACHE_HIT,
                role_id=contract.role_id,
                payload={
                    "step": step,
                    "hit_kind": kind,
                    "cached_prompt_tokens": response.usage.cached_prompt_tokens,
                },
            )
            return response, kind
        max_tokens = self._budget_gate(contract, compiled)
        response = self._invoke(contract, compiled, trace_id, max_tokens=max_tokens)
        self._record_usage(contract.role_id, step, response.usage, trace_id)
        return response, ""

    def _budget_gate(self, contract: RoleContract, compiled) -> int:
        cap = completion_cap(contract)
        if self._budget is None:
            return cap
        estimate = self._budget.meter.count_text(compiled.system_prompt + "\n" + compiled.user_block)
        try:
            decision = self._budget.check(contract.role_id, incoming=estimate)
        except TokenBudgetExceededError as exc:
            self._emit(
                AuditEventType.TOKEN_BUDGET_EXCEEDED,
                role_id=contract.role_id,
                payload={"action": "reject", "reason": str(exc), "estimate": estimate},
            )
            raise _BudgetSkip(str(exc)) from exc
        if decision.action != BudgetAction.OK:
            self._emit(
                AuditEventType.TOKEN_BUDGET_EXCEEDED,
                role_id=contract.role_id,
                payload={
                    "action": decision.action.value,
                    "reason": decision.reason,
                    "estimate": estimate,
                },
            )
            raise _BudgetSkip(decision.reason)
        room = self._budget.remaining(contract.role_id) - estimate
        if room < 1:
            reason = f"剩余预算不足以生成输出（剩余 {self._budget.remaining(contract.role_id)}，提示估计 {estimate}）"
            self._emit(
                AuditEventType.TOKEN_BUDGET_EXCEEDED,
                role_id=contract.role_id,
                payload={"action": "degrade", "reason": reason, "estimate": estimate},
            )
            raise _BudgetSkip(reason)
        return min(cap, room)

    def _apply_model_output(
        self, outcome: ExpertOutcome, contract: RoleContract, response: ModelResponse, cache_kind: str
    ) -> None:
        outcome.raw_text = response.text
        outcome.prompt_tokens = response.usage.prompt_tokens
        outcome.completion_tokens = response.usage.completion_tokens
        outcome.cached_prompt_tokens = response.usage.cached_prompt_tokens
        outcome.cache_hit = cache_kind
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

    def _record_usage(self, role_id: str, step: str, usage, trace_id: str) -> None:
        fact = UsageFact(
            role_id=role_id,
            step=step,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            cached_prompt_tokens=int(getattr(usage, "cached_prompt_tokens", 0) or 0),
            cache_write_tokens=int(getattr(usage, "cache_write_tokens", 0) or 0),
            cache_scope=str(getattr(usage, "cache_scope", "unknown") or "unknown"),
        )
        with self._facts_lock:
            self._usage_facts.append(fact)
        meters: list[Any] = []
        if self._budget is not None:
            meters.append(self._budget.meter)
        if self._token_meter is not None and all(meter is not self._token_meter for meter in meters):
            meters.append(self._token_meter)
        for meter in meters:
            meter.record(role_id, step, usage, trace_id or "")

    def _counter(self):
        meter = self._token_meter
        if meter is None and self._budget is not None:
            meter = self._budget.meter
        counter = getattr(meter, "counter", None) if meter is not None else None
        return counter or HeuristicTokenCounter()

    def _count_prompt(self, compiled) -> int:
        return self._counter().count(compiled.system_prompt + "\n" + compiled.user_block)

    def _remember_unassigned(self, contract: RoleContract, question: str) -> None:
        expert_input, evidence = self._prepare_expert_call(contract, "", question)
        compiled = self._compiler.compile(
            contract,
            expert_input,
            evidence=evidence,
            shared_context=self._active_shared or None,
        )
        fact = UnassignedFact(role_id=contract.role_id, prompt_tokens=self._count_prompt(compiled))
        with self._facts_lock:
            self._unassigned_facts.append(fact)

    def _remember_budget(self, role_id: str, step: str) -> None:
        fact = BudgetSkip(role_id=role_id, step=step)
        with self._facts_lock:
            self._budget_skips.append(fact)

    def _savings_receipt(self) -> SavingsReceipt:
        with self._facts_lock:
            calls = list(self._usage_facts)
            unassigned = list(self._unassigned_facts)
            budget_skipped = list(self._budget_skips)
        return build_savings_receipt(calls, unassigned, budget_skipped)

    def _cache_question(self, user_input: str) -> str:
        shared = (self._active_shared or "").strip()
        if not shared:
            return user_input
        return f"[shared]\n{shared}\n[input]\n{user_input}"

    def _take_cache(self, contract: RoleContract, user_input: str, evidence: list[str] | None):
        cache = self._response_cache
        if cache is None:
            return None
        question = self._cache_question(user_input)
        if isinstance(cache, SemanticCache):
            value, kind = cache.get(
                contract, question, evidence, semantic=self._allow_semantic_cache
            )
        elif isinstance(cache, ContractBoundCache):
            value = cache.get(contract, question, evidence)
            kind = "exact" if value is not None else "miss"
        else:
            got = cache.get(contract, question, evidence)
            if isinstance(got, tuple) and len(got) == 2:
                value, kind = got
            else:
                value, kind = got, ("exact" if got is not None else "miss")
        unpacked = _unpack_cache(value)
        if unpacked is None:
            return None
        output, raw_text, usage = unpacked
        text = raw_text or json.dumps(output, ensure_ascii=False)
        return ModelResponse(text=text, usage=usage, raw=output), kind

    def _store_cache(
        self,
        contract: RoleContract,
        user_input: str,
        evidence: list[str] | None,
        output: dict[str, Any],
        raw_text: str,
        usage,
    ) -> None:
        cache = self._response_cache
        if cache is None:
            return
        cache.put(
            contract,
            self._cache_question(user_input),
            evidence,
            _pack_cache(output, raw_text, usage),
        )

    def _memory_snapshot(self, contract: RoleContract) -> dict[str, Any]:
        snap: dict[str, Any] = {}
        for layer in contract.memory_permissions.read_layers:
            try:
                for key in self._memory.keys_of(layer, contract=contract):
                    snap[f"{layer.value}:{key}"] = self._memory.read(layer, key, contract=contract)
            except Exception:
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
