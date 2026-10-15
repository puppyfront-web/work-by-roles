"""wbr 命令行入口（V1.0）：version / list-teams / show-team / run-team。"""
from __future__ import annotations

import argparse
import json
import sys

import wbr


def cmd_version(_args) -> int:
    print(f"wbr {wbr.__version__} · work-by-roles 专家团治理系统")
    return 0


def cmd_list_teams(_args) -> int:
    from wbr.templates.registry import list_teams

    teams = list_teams()
    if not teams:
        print("（无模板）")
        return 0
    for t in teams:
        roles = ", ".join(f"{r['role_id']}({r['role_type']})" for r in t["roles"])
        print(f"{t['name']}  v{t['version']}  角色: {roles}")
    return 0


def cmd_show_team(args) -> int:
    from wbr.templates.registry import load_team

    contracts = load_team(args.team)
    for rid in sorted(contracts):
        c = contracts[rid]
        print(f"== {rid} [{c.role_type.value}] v{c.meta.version}")
        print(f"   name={c.identity.name} hash={c.content_hash[:12]}…")
        print(f"   SOP {len(c.sop.steps)} 步, 禁区 {len(c.forbidden.behaviors)} 条, "
              f"工具白名单 {c.tool_policy.whitelist}")
        if c.review_criteria:
            dims = ", ".join(d.name for d in c.review_criteria.dimensions)
            print(f"   评审维度: {dims}")
    return 0


def cmd_run_team(args) -> int:
    from wbr.templates.registry import load_team_spec

    spec = load_team_spec(args.team)
    from wbr.adapters.demo import SchemaDemoInvoker
    from wbr.core.audit.trail import AuditTrail
    from wbr.core.orchestration import ReviewSession

    if getattr(args, "live", False):
        from wbr.adapters.llm import OpenAICompatInvoker

        invoker = OpenAICompatInvoker.from_env()
        if invoker is None:
            print("错误: --live 需要环境变量 WBR_LLM_API_KEY 与 WBR_LLM_MODEL"
                  "（自定义端点另设 WBR_LLM_BASE_URL）。\n"
                  "示例: export WBR_LLM_API_KEY=sk-... WBR_LLM_MODEL=deepseek-chat",
                  file=sys.stderr)
            return 2
    else:
        invoker = SchemaDemoInvoker(question=args.question)
        if not args.demo_output:
            print("提示: run-team 默认使用内置演示 Invoker（确定性输出，不调用外部 LLM）。\n"
                  "      接入真实模型: export WBR_LLM_API_KEY=... WBR_LLM_MODEL=... 后加 --live。",
                  file=sys.stderr)
    audit = AuditTrail()
    session = ReviewSession(
        coordinator_contract=spec.coordinator,
        expert_contracts=spec.experts,
        verifier_contract=spec.verifier,
        invoker=invoker,
        audit=audit,
    )
    if isinstance(invoker, SchemaDemoInvoker):
        invoker.expert_ids = [e.role_id for e in spec.experts]
    result = session.run(args.question)
    print(json.dumps({
        "status": result.status.value,
        "final_answer": result.final_answer,
        "experts": [o.role_id for o in result.expert_outcomes],
        "disagreements": len(result.disagreements),
        "audit_events": len(audit.events),
    }, ensure_ascii=False, indent=2))
    return 0 if result.status.value.startswith("completed") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wbr", description="work-by-roles 专家团治理系统 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="显示版本").set_defaults(func=cmd_version)
    sub.add_parser("list-teams", help="列出官方专家团模板").set_defaults(func=cmd_list_teams)

    show = sub.add_parser("show-team", help="查看模板详情")
    show.add_argument("team")
    show.set_defaults(func=cmd_show_team)

    run = sub.add_parser("run-team", help="用官方模板运行一次会审（默认演示输出，--live 走真实模型）")
    run.add_argument("team")
    run.add_argument("question")
    run.add_argument("--live", action="store_true",
                     help="调用真实模型（需 WBR_LLM_API_KEY / WBR_LLM_MODEL，可选 WBR_LLM_BASE_URL）")
    run.add_argument("--demo-output", action="store_true", help="静默演示提示")
    run.set_defaults(func=cmd_run_team)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
