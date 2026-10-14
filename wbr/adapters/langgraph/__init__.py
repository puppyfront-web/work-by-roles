"""LangGraph 适配器公共导出（可选依赖，缺失时给出安装指引）。"""
from wbr.adapters.langgraph.base import require_langchain_core, require_langgraph
from wbr.adapters.langgraph.guard import WBRGuard, WBRGuardedGraph
from wbr.adapters.langgraph.interceptors import (
    ForbiddenDetectorInterceptor,
    InterceptResult,
    SchemaValidationInterceptor,
    ToolDecision,
    ToolPermissionGate,
)
from wbr.adapters.langgraph.mapping import contract_to_messages
from wbr.adapters.langgraph.state import WBR_META_KEY, inject_meta, merge_state, read_meta

__all__ = [
    "WBR_META_KEY",
    "ForbiddenDetectorInterceptor",
    "InterceptResult",
    "SchemaValidationInterceptor",
    "ToolDecision",
    "ToolPermissionGate",
    "WBRGuard",
    "WBRGuardedGraph",
    "contract_to_messages",
    "inject_meta",
    "merge_state",
    "read_meta",
    "require_langchain_core",
    "require_langgraph",
]


def __getattr__(name: str):
    # 惰性导出：builder/hitl 依赖 langgraph 本体，import 失败给出安装指引
    if name == "build_review_graph":
        from wbr.adapters.langgraph.builder import build_review_graph

        return build_review_graph
    if name in ("interrupt_for_approval", "resume_command", "apply_decision"):
        import wbr.adapters.langgraph.hitl as hitl

        return getattr(hitl, name)
    raise AttributeError(name)
