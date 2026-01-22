"""
CLI parser setup.
"""

import argparse
import sys
from .init import cmd_init
from .setup import cmd_setup
from .workflow import cmd_start, cmd_complete, cmd_status, cmd_wfauto, cmd_role_execute, cmd_replay_workflow, cmd_dry_run_stage
from .inspect import cmd_analyze, cmd_list_stages, cmd_list_roles, cmd_export_graph, cmd_check_team

def setup_parser():
    parser = argparse.ArgumentParser(
        description="Multi-Role Skills Workflow 命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s start requirements product_analyst
  %(prog)s complete requirements
  %(prog)s status
  %(prog)s list-stages
  %(prog)s list-roles
        """
    )
    
    parser.add_argument("--workspace", "-w", help="工作空间路径 (默认: 当前目录)")
    parser.add_argument("--roles", "-r", help="角色定义文件 (默认: role_schema.yaml)")
    parser.add_argument("--workflow", "-f", help="工作流定义文件 (默认: workflow_schema.yaml)")
    parser.add_argument("--skills", "-k", help="技能库目录 (默认: skills)")
    parser.add_argument("--context", "-c", help="项目上下文文件 (默认: .workflow/project_context.yaml)")
    parser.add_argument("--state", "-s", help="工作流状态文件 (默认: .workflow/state.yaml)")
    parser.add_argument("--team", "-t", help="指定使用的团队（覆盖当前团队）")
    parser.add_argument("--no-restore-state", action="store_true", help="禁用自动恢复状态")
    parser.add_argument("--no-auto-save", action="store_true", help="禁用自动保存状态")
    
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize project workflow")
    init_parser.add_argument("--template", help="Template name")
    init_parser.add_argument("--quick", action="store_true", help="Quick initialization")
    init_parser.set_defaults(func=cmd_init)

    # setup
    setup_parser = subparsers.add_parser("setup", help="Setup project for role-based execution")
    setup_parser.set_defaults(func=cmd_setup)

    # start
    start_parser = subparsers.add_parser("start", help="Start a workflow stage")
    start_parser.add_argument("stage", nargs="?", help="Stage ID")
    start_parser.add_argument("role", nargs="?", help="Role ID")
    start_parser.set_defaults(func=cmd_start)

    # complete
    complete_parser = subparsers.add_parser("complete", help="Complete a workflow stage")
    complete_parser.add_argument("stage", nargs="?", help="Stage ID")
    complete_parser.set_defaults(func=cmd_complete)

    # status
    status_parser = subparsers.add_parser("status", help="Show workflow status")
    status_parser.set_defaults(func=cmd_status)

    # wfauto
    wfauto_parser = subparsers.add_parser("wfauto", help="Run full workflow automatically")
    wfauto_parser.add_argument("--intent", "-i", help="User intent description")
    wfauto_parser.add_argument("--use-llm", action="store_true", help="Force LLM for intent recognition")
    wfauto_parser.add_argument("--no-llm", action="store_true", help="Force rule-based for intent recognition")
    wfauto_parser.add_argument("--no-agent", action="store_true", help="Disable Agent + Skills execution")
    wfauto_parser.add_argument("--keep-state", action="store_true", help="Keep previous state")
    wfauto_parser.add_argument("--parallel", action="store_true", help="Parallel execution (experimental)")
    wfauto_parser.set_defaults(func=cmd_wfauto)

    # role-execute
    role_execute_parser = subparsers.add_parser("role-execute", help="Execute a role directly")
    role_execute_parser.add_argument("role_id", help="Role ID")
    role_execute_parser.add_argument("requirement", help="User requirement")
    role_execute_parser.add_argument("--inputs", "-i", help="Input data (JSON)")
    role_execute_parser.add_argument("--use-llm", action="store_true", help="Use LLM for response")
    role_execute_parser.set_defaults(func=cmd_role_execute)

    # replay
    replay_parser = subparsers.add_parser("replay", help="Replay workflow")
    replay_parser.set_defaults(func=cmd_replay_workflow)

    # dry-run
    dry_run_parser = subparsers.add_parser("dry-run", help="Dry run a stage")
    dry_run_parser.add_argument("stage_id", help="Stage ID")
    dry_run_parser.set_defaults(func=cmd_dry_run_stage)

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analyze current workflow state")
    analyze_parser.set_defaults(func=cmd_analyze)

    # list-stages
    list_stages_parser = subparsers.add_parser("list-stages", help="List all workflow stages")
    list_stages_parser.set_defaults(func=cmd_list_stages)

    # list-roles
    list_roles_parser = subparsers.add_parser("list-roles", help="List all roles")
    list_roles_parser.set_defaults(func=cmd_list_roles)

    # export-graph
    export_graph_parser = subparsers.add_parser("export-graph", help="Export workflow graph")
    export_graph_parser.add_argument("--output", "-o", help="Output file path")
    export_graph_parser.add_argument("--no-roles", action="store_true", help="Don't include roles")
    export_graph_parser.set_defaults(func=cmd_export_graph)

    # check-team
    check_team_parser = subparsers.add_parser("check-team", help="Check team health")
    check_team_parser.set_defaults(func=cmd_check_team)

    return parser
