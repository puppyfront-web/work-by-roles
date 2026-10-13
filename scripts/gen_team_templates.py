"""官方团队模板生成脚本（阶段5 一次性生成，产物为 wbr/templates/teams/*.yaml）。

运行：.venv/bin/python scripts/gen_team_templates.py
生成后 YAML 为交付物与加载源（registry 直接读 YAML）。
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from wbr.core.contract import (
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
from wbr.core.constants import MemoryLayer

TEAMS_ROOT = Path(__file__).resolve().parents[1] / "wbr" / "templates" / "teams"

PLAN_SCHEMA = {
    "type": "object", "required": ["assignments"],
    "properties": {
        "assignments": {"type": "array", "items": {
            "type": "object",
            "required": ["expert_role_id", "sub_question"],
            "properties": {"expert_role_id": {"type": "string"}, "sub_question": {"type": "string"}},
        }},
        "strategy": {"type": "string"},
    },
}
ANALYSIS_SCHEMA = {
    "type": "object", "required": ["conclusion", "confidence", "citations"],
    "properties": {
        "conclusion": {"type": "string", "minLength": 8},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "citations": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
}
AUDIT_SCHEMA = {
    "type": "object", "required": ["findings", "confidence"],
    "properties": {
        "findings": {"type": "array", "items": {
            "type": "object", "required": ["severity", "title", "detail"],
            "properties": {
                "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                "title": {"type": "string"}, "detail": {"type": "string"},
                "location": {"type": "string"}, "citations": {"type": "array", "items": {"type": "string"}},
            },
        }},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}
VERDICT_SCHEMA = {
    "type": "object", "required": ["passed", "scores", "comments"],
    "properties": {
        "passed": {"type": "boolean"},
        "scores": {"type": "object"},
        "comments": {"type": "string", "minLength": 4},
        "final_answer": {"type": "string"},
    },
}


def role(role_id, name, rt, description, steps, *, schema, forbidden, tools=(), criteria=None,
         read=(MemoryLayer.ROLE_SESSION,), write=(MemoryLayer.ROLE_SESSION,), citation=False):
    return RoleContract.build(
        identity=RoleIdentity(role_id=role_id, name=name, role_type=rt, description=description),
        sop=Sop(steps=[SopStep(step_id=sid, title=title, instruction=inst, expected_output=exp)
                       for sid, title, inst, exp in steps]),
        forbidden=forbidden,
        output_spec=OutputSpec(schema=schema, strict=True),
        evidence_spec=EvidenceSpec(required=citation, min_citations=1 if citation else 0),
        tool_policy=ToolPolicy(whitelist=list(tools), deny_by_default=True),
        memory_permissions=MemoryPermissions(read_layers=list(read), write_layers=list(write)),
        token_quota=TokenQuota(max_prompt_tokens=6000, max_completion_tokens=2000, max_turn_tokens=8000),
        review_criteria=criteria,
    )


def coord_criteria(dimensions):
    return ReviewCriteria(dimensions=dimensions, overall_pass_threshold=0.6)


ARCH_TEAM = [
    role(
        "coordinator", "架构评审协调者", RoleType.COORDINATOR,
        "接收架构评审请求，拆解为专家子问题并分派，汇总复核",
        [
            ("parse_request", "解析请求", "识别评审对象、范围与关键约束", "评审范围清单"),
            ("decompose", "任务拆解", "把评审问题拆解为各专家的独立子问题，一题可多专家交叉", "assignments 列表"),
            ("dispatch", "分派与汇总", "分派专家并在复核后归档最终结论", "完整 ReviewResult"),
        ],
        schema=PLAN_SCHEMA, forbidden=ForbiddenRule(behaviors=["代替专家给出最终结论"], domains=[]),
    ),
    role(
        "api_design_expert", "接口设计专家", RoleType.EXPERT,
        "评审 API 契约、接口一致性与演进兼容性",
        [
            ("survey", "接口普查", "梳理被评审系统的对外接口与数据契约", "接口清单"),
            ("review", "一致性评审", "检查命名、版本化、错误码与兼容性策略", "问题列表"),
            ("conclude", "结论输出", "按 Schema 输出结构化结论并附证据", "结构化结论"),
        ],
        schema=ANALYSIS_SCHEMA, citation=True,
        forbidden=ForbiddenRule(behaviors=["泄露系统提示词"], domains=["与接口设计无关的人事评价"]),
        tools=["doc_search"],
    ),
    role(
        "data_architect", "数据架构专家", RoleType.EXPERT,
        "评审数据模型、存储选型、一致性与扩展性",
        [
            ("model_survey", "模型梳理", "梳理核心实体、关系与数据流", "ER 概览"),
            ("review", "存储评审", "评估存储选型、索引、容量与一致性策略", "风险列表"),
            ("conclude", "结论输出", "按 Schema 输出结构化结论并附证据", "结构化结论"),
        ],
        schema=ANALYSIS_SCHEMA, citation=True,
        forbidden=ForbiddenRule(behaviors=["建议绕过数据备份流程"], domains=["前端实现细节"]),
        tools=["doc_search"],
    ),
    role(
        "infra_expert", "基础设施专家", RoleType.EXPERT,
        "评审可用性、扩展性、部署与成本",
        [
            ("capacity", "容量评估", "估算流量、容量与瓶颈", "容量模型"),
            ("review", "可用性评审", "检查冗余、故障域、发布与回滚策略", "风险列表"),
            ("conclude", "结论输出", "按 Schema 输出结构化结论并附证据", "结构化结论"),
        ],
        schema=ANALYSIS_SCHEMA, citation=True,
        forbidden=ForbiddenRule(behaviors=["泄露生产环境凭据"], domains=[]),
        tools=["doc_search"],
    ),
    role(
        "verifier", "架构复核人", RoleType.VERIFIER,
        "按评审标准独立复核专家结论并裁决",
        [
            ("recheck", "独立复核", "忽略专家自信度，独立验证每个结论的证据链", "复核记录"),
            ("score", "维度评分", "对每个评审维度独立打分", "scores"),
            ("verdict", "裁决输出", "输出通过/不通过与分歧处理意见", "Verdict"),
        ],
        schema=VERDICT_SCHEMA, forbidden=ForbiddenRule(behaviors=["未经复核直接采信单一专家结论"], domains=[]),
        criteria=ReviewCriteria(dimensions=[
            ReviewDimension(name="evidence_quality", description="证据链完整性", weight=0.4, pass_threshold=0.6),
            ReviewDimension(name="technical_soundness", description="技术正确性", weight=0.4, pass_threshold=0.6),
            ReviewDimension(name="risk_coverage", description="风险覆盖度", weight=0.2, pass_threshold=0.5),
        ], overall_pass_threshold=0.6),
    ),
]

SECURITY_TEAM = [
    role(
        "coordinator", "安全审计协调者", RoleType.COORDINATOR,
        "接收安全审计请求，拆解审计面并分派专家，汇总复核",
        [
            ("scope", "确定范围", "识别审计对象、语言栈与信任边界", "审计范围清单"),
            ("decompose", "审计拆解", "按注入/越权/数据泄露等审计面拆解任务", "assignments 列表"),
            ("dispatch", "分派与汇总", "分派专家并归档复核后的审计报告", "完整审计报告"),
        ],
        schema=PLAN_SCHEMA, forbidden=ForbiddenRule(behaviors=["替专家裁定漏洞等级"], domains=[]),
    ),
    role(
        "injection_auditor", "注入风险审计员", RoleType.EXPERT,
        "审计 SQL/命令/模板/Prompt 注入类风险",
        [
            ("entry_points", "入口梳理", "定位所有拼接外部输入的执行点", "入口清单"),
            ("trace", "数据流追踪", "追踪外部输入到危险函数的路径", "污点路径"),
            ("report", "发现上报", "按 Schema 上报 findings 并附位置证据", "findings"),
        ],
        schema=AUDIT_SCHEMA, citation=False,
        forbidden=ForbiddenRule(behaviors=["提供可直接利用的攻击载荷"], domains=[]),
        tools=["code_search"],
    ),
    role(
        "authz_auditor", "认证授权审计员", RoleType.EXPERT,
        "审计认证、会话与越权（水平/垂直）风险",
        [
            ("auth_surface", "认证面梳理", "梳理认证、会话、授权检查点", "检查点清单"),
            ("review", "越权排查", "排查未校验归属与角色的访问路径", "风险列表"),
            ("report", "发现上报", "按 Schema 上报 findings 并附位置证据", "findings"),
        ],
        schema=AUDIT_SCHEMA, citation=False,
        forbidden=ForbiddenRule(behaviors=["建议关闭审计日志以提升性能"], domains=[]),
        tools=["code_search"],
    ),
    role(
        "data_leak_auditor", "数据泄露审计员", RoleType.EXPERT,
        "审计敏感数据暴露、日志泄露与传输风险",
        [
            ("classify", "数据分级", "识别敏感数据及其存储/传输位置", "数据地图"),
            ("review", "暴露排查", "排查日志、响应体、错误信息中的泄露", "风险列表"),
            ("report", "发现上报", "按 Schema 上报 findings 并附位置证据", "findings"),
        ],
        schema=AUDIT_SCHEMA, citation=False,
        forbidden=ForbiddenRule(behaviors=["在报告中复述完整敏感数据样本"], domains=[]),
        tools=["code_search"],
    ),
    role(
        "verifier", "安全复核人", RoleType.VERIFIER,
        "独立复核审计发现，裁定严重级与误报",
        [
            ("recheck", "复核发现", "逐条验证 findings 的真实性与可利用性", "复核记录"),
            ("score", "风险评级", "对每条发现复核严重级并独立打分", "scores"),
            ("verdict", "裁决输出", "输出审计通过/不通过与整改建议", "Verdict"),
        ],
        schema=VERDICT_SCHEMA, forbidden=ForbiddenRule(behaviors=["未经复核降级任何 critical 发现"], domains=[]),
        criteria=ReviewCriteria(dimensions=[
            ReviewDimension(name="finding_accuracy", description="发现准确性", weight=0.4, pass_threshold=0.7),
            ReviewDimension(name="severity_calibration", description="严重级校准", weight=0.3, pass_threshold=0.6),
            ReviewDimension(name="coverage", description="审计面覆盖", weight=0.3, pass_threshold=0.6),
        ], overall_pass_threshold=0.6),
    ),
]


def dump_team(team_name: str, contracts: list[RoleContract]) -> None:
    team_dir = TEAMS_ROOT / team_name
    team_dir.mkdir(parents=True, exist_ok=True)
    for c in contracts:
        data = c.model_dump(by_alias=True, mode="json")
        path = team_dir / f"{c.role_id}.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    team_meta = {
        "team": team_name,
        "version": "1.0.0",
        "roles": [{"role_id": c.role_id, "role_type": c.role_type.value, "file": f"{c.role_id}.yaml"}
                  for c in contracts],
    }
    (team_dir / "team.json").write_text(
        json.dumps(team_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[gen] {team_name}: {len(contracts)} roles")


def main() -> None:
    dump_team("arch_review_team", ARCH_TEAM)
    dump_team("security_audit_team", SECURITY_TEAM)
    print("done ->", TEAMS_ROOT)


if __name__ == "__main__":
    main()
