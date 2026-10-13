"""LangGraph 适配器公共基础：可选依赖守卫（R15）。"""
from __future__ import annotations

from typing import Any

from wbr.core.exceptions import AdapterError

_INSTALL_HINT = (
    "LangGraph 适配器需要安装可选依赖: pip install 'work-by-roles[langgraph]' "
    "(即 langgraph + langchain-core)"
)


def require_langgraph() -> Any:
    try:
        import langgraph  # noqa: F401
        from langgraph import graph  # noqa: F401
    except ImportError as e:  # pragma: no cover - 环境相关
        raise AdapterError(_INSTALL_HINT) from e
    return langgraph


def require_langchain_core() -> Any:
    try:
        import langchain_core
    except ImportError as e:  # pragma: no cover - 环境相关
        raise AdapterError(_INSTALL_HINT) from e
    return langchain_core
