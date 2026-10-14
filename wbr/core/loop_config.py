"""意图与内循环的配置模型（SPEC-009 §1/§2）。

独立模块：被 contract.models 与 intent/inner_loop 共同引用，避免循环导入。
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class IntentPolicy(BaseModel):
    """意图策略：全部控制参数声明于此（可挂 Coordinator 契约，禁止硬编码）。"""

    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    allow_lightweight: bool = False
    ambiguous_to_hitl: bool = True
    custom_rules: dict[str, str] = Field(default_factory=dict)


class ExitCondition(str, Enum):
    EVIDENCE_SUFFICIENT = "evidence_sufficient"
    CONVERGED = "converged"


class QuotaExhaustedAction(str, Enum):
    ESCALATE_HITL = "escalate_hitl"
    FORCE_EXIT = "force_exit"


class InnerLoopConfig(BaseModel):
    """单角色内部循环控制参数：全部契约可配置（禁止硬编码阈值）。"""

    max_rounds: int = Field(default=3, ge=1, le=20)
    exit_when: ExitCondition = ExitCondition.EVIDENCE_SUFFICIENT
    loop_quota_tokens: int = Field(default=4000, gt=0)
    on_quota_exhausted: QuotaExhaustedAction = QuotaExhaustedAction.ESCALATE_HITL


class StopReason(str, Enum):
    EVIDENCE_SATISFIED = "evidence_satisfied"
    MAX_ROUNDS_RISK = "max_rounds_risk"
    QUOTA_EXHAUSTED_HITL = "quota_exhausted_hitl"
    QUOTA_EXHAUSTED_EXIT = "quota_exhausted_exit"


class LoopRound(BaseModel):
    round_no: int
    conclusion: str
    evidence: list[str] = Field(default_factory=list)
    continue_loop: bool
    reason: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LoopSummarySnapshot(BaseModel):
    """循环总结快照：作为主会审流程输入（控上下文膨胀）。"""

    role_id: str
    sub_question: str
    rounds_used: int
    conclusion: str
    evidence: list[str] = Field(default_factory=list)
    stopped_because: str
    token_used: int = 0
    escalated_hitl: bool = False


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
