"""共享测试夹具与工厂（tests/wbr）。"""
from __future__ import annotations

import pytest


@pytest.fixture()
def clean_bus():
    """提供隔离的 AuditBus，测试后清理全局单例。"""
    from wbr.core.audit_bus import reset_default_bus

    reset_default_bus()
    yield
    reset_default_bus()
