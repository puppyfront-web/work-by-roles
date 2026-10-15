"""共享测试夹具与工厂（tests/wbr）。"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _scrub_llm_env(monkeypatch):
    """屏蔽真实模型环境变量：测试永远走确定性 Invoker，不产生真实调用与费用。"""
    for key in ("WBR_LLM_BASE_URL", "WBR_LLM_API_KEY", "WBR_LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    yield


@pytest.fixture()
def clean_bus():
    """提供隔离的 AuditBus，测试后清理全局单例。"""
    from wbr.core.audit_bus import reset_default_bus

    reset_default_bus()
    yield
    reset_default_bus()
