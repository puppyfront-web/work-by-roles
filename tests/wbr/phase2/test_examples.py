"""TC-2-DEMO-1：阶段2 双示例子进程冒烟。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "phase2"


def test_legacy_plugin_example_runs():
    r = subprocess.run(
        [sys.executable, str(EXAMPLES / "legacy_plugin_integration.py")],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "3 行代码接入" in r.stdout or "存量图接入成功" in r.stdout


def test_native_graph_example_runs():
    r = subprocess.run(
        [sys.executable, str(EXAMPLES / "native_graph.py")],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "原生会审图运行完成" in r.stdout
    assert "HITL 断点续跑" in r.stdout
