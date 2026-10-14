"""意图识别推理流水线（补充方案 §二 / SPEC-009 §1）。

Coordinator 内核子模块：固定六步顺序、契约驱动结构化推理、阈值全部来自 IntentPolicy、
推理理由链强制留存并入审计。不做 NLP 模型，纯 Prompt 契约推理（D-06）。
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from wbr.core.audit.models import AuditEvent, AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.contract.compiler import ContractCompiler
from wbr.core.contract.models import RoleContract, RoleType
from wbr.core.loop_config import IntentPolicy
from wbr.core.orchestration.invoker import ModelInvoker, ModelRequest, parse_json_output
from wbr.core.schema.validator import validate as schema_validate
from wbr.core.security.guard import InjectionDetector, RiskLevel, guard_user_input

DEFAULT_INTENT_SCHEMA = {
    "type": "object",
    "required": ["intent_type", "confidence", "reasoning"],
    "properties": {
        "intent_type": {"type": "string",
                        "enum": ["standard_review", "missing_info", "out_of_scope",
                                 "ambiguous", "lightweight_query"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reasoning": {"type": "string", "minLength": 2},
        "goal": {"type": "string"},
        "deliverables": {"type": "string"},
        "constraints": {"type": "string"},
        "time_limits": {"type": "string"},
        "preferences": {"type": "string"},
    },
}


class IntentType(str, Enum):
    STANDARD_REVIEW = "standard_review"      # 标准会审任务
    MISSING_INFO = "missing_info"            # 信息缺失，需收集材料
    OUT_OF_SCOPE = "out_of_scope"            # 越界请求，拒绝
    AMBIGUOUS = "ambiguous"                  # 模糊请求，HITL 确认
    LIGHTWEIGHT_QUERY = "lightweight_query"  # 轻量查询（契约可开关）


class NextAction(str, Enum):
    RUN_DISASSEMBLE = "run_disassemble"
    ASK_USER = "ask_user"
    REJECT = "reject"
    LIGHTWEIGHT_SINGLE_EXPERT = "lightweight_single_expert"


class IntentReasoningStep(BaseModel):
    step: str            # safety_filter / classify / confidence_check / factor_extract / conflict_check / decision
    decision: str
    detail: str = ""


class ExtractedFactors(BaseModel):
    goal: str = ""
    deliverables: str = ""
    constraints: str = ""
    time_limits: str = ""
    preferences: str = ""


class IntentResult(BaseModel):
    intent_type: IntentType
    confidence: float
    extracted_factors: ExtractedFactors = Field(default_factory=ExtractedFactors)
    reasoning_trace: list[IntentReasoningStep] = Field(default_factory=list)
    next_action: NextAction
    sanitized_input: str = ""
    policy_snapshot: dict[str, Any] = Field(default_factory=dict)


class IntentPipeline:
    """意图推理流水线：固定六步，逐步落审计（INTENT_REASONING）。"""

    def __init__(
        self,
        *,
        contract: RoleContract,
        invoker: ModelInvoker,
        policy: IntentPolicy | None = None,
        detector: InjectionDetector | None = None,
        audit: AuditTrail | None = None,
        output_schema: dict | None = None,
    ) -> None:
        if contract.role_type != RoleType.COORDINATOR:
            from wbr.core.exceptions import OrchestrationError

            raise OrchestrationError("意图推理契约必须为 coordinator 角色")
        self._contract = contract
        self._invoker = invoker
        self._policy = policy if policy is not None else contract.intent_policy or IntentPolicy()
        self._detector = detector or InjectionDetector()
        self._audit = audit
        self._schema = output_schema or DEFAULT_INTENT_SCHEMA
        self._compiler = ContractCompiler()

    # ---- 入口 ----
    def run(self, user_input: str) -> IntentResult:
        trace: list[IntentReasoningStep] = []
        policy_snap = self._policy.model_dump()

        # 第 1 步：清洗与安全过滤（复用全局注入检测）
        guard = guard_user_input(user_input, detector=self._detector)
        sanitized = guard.sanitized
        if guard.report.is_suspicious and guard.report.risk_level == RiskLevel.HIGH:
            trace.append(IntentReasoningStep(
                step="safety_filter", decision="reject",
                detail=f"安全过滤：高危注入拦截（{guard.report.risk_level.value}），进入拒绝流程"))
            result = self._finish(IntentType.OUT_OF_SCOPE, 1.0, trace, sanitized, policy_snap)
            return result
        trace.append(IntentReasoningStep(
            step="safety_filter", decision="pass",
            detail=f"风险 {guard.report.risk_level.value}"))

        # 第 2 步：意图分类推理（契约驱动的结构化输出）
        classified, err = self._classify(sanitized)
        if err is not None:
            trace.append(IntentReasoningStep(step="classify", decision="fail_safe",
                                             detail=f"输出不合规，安全降级: {err}"))
            return self._finish(IntentType.AMBIGUOUS, 0.0, trace, sanitized, policy_snap)
        trace.append(IntentReasoningStep(
            step="classify", decision=classified["intent_type"],
            detail=classified["reasoning"]))

        # 第 3 步：置信度阈值判定（阈值来自 policy）
        confidence = float(classified["confidence"])
        intent = IntentType(classified["intent_type"])
        if confidence < self._policy.confidence_threshold:
            trace.append(IntentReasoningStep(
                step="confidence_check", decision="degrade_ambiguous",
                detail=f"置信度 {confidence} < 阈值 {self._policy.confidence_threshold}，降级模糊请求"))
            return self._finish(IntentType.AMBIGUOUS, confidence, trace, sanitized, policy_snap)
        trace.append(IntentReasoningStep(
            step="confidence_check", decision="pass", detail=f"置信度 {confidence}"))

        # 第 4 步：要素抽取
        factors = ExtractedFactors(
            goal=str(classified.get("goal", "")),
            deliverables=str(classified.get("deliverables", "")),
            constraints=str(classified.get("constraints", "")),
            time_limits=str(classified.get("time_limits", "")),
            preferences=str(classified.get("preferences", "")),
        )
        trace.append(IntentReasoningStep(step="factor_extract", decision="ok",
                                         detail=f"目标: {factors.goal[:60]}"))

        # 第 5 步：冲突检测（要素 vs Coordinator 契约禁区）
        conflict = self._conflict_check(factors)
        if conflict:
            trace.append(IntentReasoningStep(step="conflict_check", decision="reject",
                                             detail=conflict))
            return self._finish(IntentType.OUT_OF_SCOPE, confidence, trace, sanitized, policy_snap)
        trace.append(IntentReasoningStep(step="conflict_check", decision="pass", detail=""))

        # 第 6 步：决策映射
        next_action = self._map_action(intent)
        trace.append(IntentReasoningStep(step="decision", decision=next_action.value, detail=""))
        return self._finish(intent, confidence, trace, sanitized, policy_snap,
                            factors=factors, next_action=next_action)

    # ---- 内部 ----
    def _classify(self, sanitized: str) -> tuple[dict | None, str | None]:
        custom = ""
        if self._policy.custom_rules:
            custom = "\n补充规则：" + "；".join(f"{k}: {v}" for k, v in self._policy.custom_rules.items())
        prompt = (
            "对以下用户输入做意图分类推理。分类固定五类：standard_review（标准会审任务）/"
            "missing_info（信息缺失）/out_of_scope（越界请求）/ambiguous（模糊请求）/"
            "lightweight_query（轻量查询）。输出 JSON：intent_type/confidence/"
            "reasoning/goal/deliverables/constraints/time_limits/preferences。" + custom
        )
        compiled = self._compiler.compile(self._contract, prompt)
        response = self._invoker.invoke(
            ModelRequest(role_contract=self._contract, compiled_prompt=compiled, trace_id="")
        )
        try:
            output = parse_json_output(response.text)
        except ValueError as e:
            return None, str(e)
        errs = schema_validate(output, self._schema)
        if errs:
            return None, f"{errs[0].path}: {errs[0].message}"
        return output, None

    def _conflict_check(self, factors: ExtractedFactors) -> str | None:
        text = " ".join([factors.goal, factors.deliverables, factors.constraints])
        for behavior in self._contract.forbidden.behaviors:
            if behavior and behavior in text:
                return f"要素命中契约禁区行为: {behavior}"
        for domain in self._contract.forbidden.domains:
            if domain and domain in text:
                return f"要素命中契约禁区回答域: {domain}"
        return None

    def _map_action(self, intent: IntentType) -> NextAction:
        if intent == IntentType.STANDARD_REVIEW:
            return NextAction.RUN_DISASSEMBLE
        if intent in (IntentType.MISSING_INFO, IntentType.AMBIGUOUS):
            return NextAction.ASK_USER
        if intent == IntentType.OUT_OF_SCOPE:
            return NextAction.REJECT
        if intent == IntentType.LIGHTWEIGHT_QUERY:
            if self._policy.allow_lightweight:
                return NextAction.LIGHTWEIGHT_SINGLE_EXPERT
            return NextAction.RUN_DISASSEMBLE  # 开关关闭 → 回退标准会审
        return NextAction.RUN_DISASSEMBLE

    def _finish(
        self,
        intent: IntentType,
        confidence: float,
        trace: list[IntentReasoningStep],
        sanitized: str,
        policy_snap: dict,
        *,
        factors: ExtractedFactors | None = None,
        next_action: NextAction | None = None,
    ) -> IntentResult:
        result = IntentResult(
            intent_type=intent,
            confidence=confidence,
            extracted_factors=factors or ExtractedFactors(),
            reasoning_trace=trace,
            next_action=next_action or self._map_action(intent),
            sanitized_input=sanitized,
            policy_snapshot=policy_snap,
        )
        if self._audit is not None:
            self._audit.append(
                AuditEvent(
                    event_type=AuditEventType.INTENT_REASONING,
                    trace_id="no-trace",
                    role_id=self._contract.role_id,
                    payload={
                        "intent_type": result.intent_type.value,
                        "next_action": result.next_action.value,
                        "confidence": result.confidence,
                        "reasoning_trace": [s.model_dump() for s in trace],
                        "policy_snapshot": policy_snap,
                    },
                )
            )
        return result
