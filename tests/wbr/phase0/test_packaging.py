"""TC-0-PKG-1：包可安装、版本与公共 API。"""
from __future__ import annotations

import wbr


def test_version_and_exports():
    assert wbr.__version__ == "2.0.0"
    assert "WBRError" in wbr.__all__
    assert wbr.WBRError is not None
    assert wbr.AuditBus is not None
    assert wbr.WBRConfig is not None


def test_distribution_metadata():
    from importlib import metadata

    assert metadata.version("work-by-roles") == wbr.__version__
