"""契约测试工厂（builder）：全阶段测试共用的契约构造器。"""
from __future__ import annotations

from typing import Any

from wbr.core.constants import MemoryLayer
from wbr.core.contract.models import (
    EvidenceSpec,
    ForbiddenRule,
    MemoryPermissions,
    OutputSpec,
    ReviewCriteria,
    ReviewDimension,
    RoleContract,
    RoleIdentity,
    RoleType,
    Sop,
    SopStep,
    TokenQuota,
    ToolPolicy,
)

EXPERT_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["conclusion", "confidence"],
    "properties": {
        "conclusion": {"type": "string", "minLength": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "citations": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
}

VERDICT_SCHEMA = {
    "type": "object",
    "required": ["passed", "scores", "comments"],
    "properties": {
        "passed": {"type": "boolean"},
        "scores": {"type": "object"},
        "comments": {"type": "string", "minLength": 1},
        "final_answer": {"type": "string"},
    },
}

PLAN_SCHEMA = {
    "type": "object",
    "required": ["assignments"],
    "properties": {
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["expert_role_id", "sub_question"],
                "properties": {
                    "expert_role_id": {"type": "string"},
                    "sub_question": {"type": "string", "minLength": 1},
                },
            },
        },
        "strategy": {"type": "string"},
    },
}


def expert_contract(
    role_id: str = "expert_a",
    *,
    output_schema: dict | None = None,
    strict: bool = True,
    forbidden: ForbiddenRule | None = None,
    evidence: EvidenceSpec | None = None,
    tools: list[str] | None = None,
    read_layers: list[MemoryLayer] | None = None,
    write_layers: list[MemoryLayer] | None = None,
    allow_global_write: bool = False,
    quota: TokenQuota | None = None,
    version: str = "1.0.0",
) -> RoleContract:
    contract = RoleContract.build(
        identity=RoleIdentity(
            role_id=role_id, name=f"专家{role_id}", role_type=RoleType.EXPERT, description="测试专家"
        ),
        sop=Sop(steps=[
            SopStep(step_id="analyze", title="分析", instruction="分析子问题并给出结论"),
            SopStep(step_id="conclude", title="结论", instruction="按 Schema 输出结论"),
        ]),
        forbidden=forbidden or ForbiddenRule(),
        output_spec=OutputSpec(schema=output_schema or EXPERT_OUTPUT_SCHEMA, strict=strict),
        evidence_spec=evidence or EvidenceSpec(),
        tool_policy=ToolPolicy(whitelist=tools or [], deny_by_default=True),
        memory_permissions=MemoryPermissions(
            read_layers=read_layers or [],
            write_layers=write_layers or [],
            allow_global_write=allow_global_write,
        ),
        token_quota=quota or TokenQuota(),
    )
    contract.meta.version = version
    return contract


def coordinator_contract(role_id: str = "coordinator") -> RoleContract:
    return RoleContract.build(
        identity=RoleIdentity(
            role_id=role_id, name="协调者", role_type=RoleType.COORDINATOR, description="任务拆解与分派"
        ),
        sop=Sop(steps=[
            SopStep(step_id="decompose", title="拆解", instruction="把问题拆解为专家子问题"),
        ]),
        output_spec=OutputSpec(schema=PLAN_SCHEMA, strict=True),
    )


def verifier_contract(
    role_id: str = "verifier",
    criteria: ReviewCriteria | None = None,
    *,
    overall: float = 0.6,
) -> RoleContract:
    criteria = criteria or ReviewCriteria(
        dimensions=[
            ReviewDimension(name="completeness", description="完整性", weight=0.5, pass_threshold=0.6),
            ReviewDimension(name="accuracy", description="准确性", weight=0.5, pass_threshold=0.6),
        ],
        overall_pass_threshold=overall,
    )
    return RoleContract.build(
        identity=RoleIdentity(
            role_id=role_id, name="复核者", role_type=RoleType.VERIFIER, description="独立复核裁决"
        ),
        sop=Sop(steps=[
            SopStep(step_id="review", title="复核", instruction="按评审标准独立复核专家结论"),
        ]),
        output_spec=OutputSpec(schema=VERDICT_SCHEMA, strict=True),
        review_criteria=criteria,
    )
