"""TC-0-STRUCT-1/2：目录结构对齐 + Core 依赖纯净静态扫描。"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WBR = REPO / "wbr"

REQUIRED_PATHS = [
    "wbr/__init__.py",
    "wbr/core/exceptions.py",
    "wbr/core/context.py",
    "wbr/core/constants.py",
    "wbr/core/config.py",
    "wbr/core/logging.py",
    "wbr/core/audit_bus.py",
    "wbr/core/contract",
    "wbr/core/audit",
    "wbr/core/memory",
    "wbr/core/orchestration",
    "wbr/core/security",
    "wbr/core/token",
    "wbr/core/cache",
    "wbr/core/schema",
    "wbr/core/harness",
    "wbr/adapters/langgraph",
    "wbr/adapters/storage",
    "wbr/app/api",
    "wbr/app/tasks",
    "wbr/app/canvas",
    "wbr/config_loader.py",
    "wbr/templates/teams",
]

# 阶段0 即可导入的模块（后续阶段逐步扩充）
PHASE0_IMPORTS = [
    "wbr",
    "wbr.core.exceptions",
    "wbr.core.context",
    "wbr.core.constants",
    "wbr.core.config",
    "wbr.core.logging",
    "wbr.core.audit_bus",
]


def test_directory_structure_aligned():
    for rel in REQUIRED_PATHS:
        assert (REPO / rel).exists(), f"缺少规定路径: {rel}"


def test_phase0_modules_importable():
    for mod in PHASE0_IMPORTS:
        __import__(mod)


def test_core_import_purity():
    """Core 层只允许 stdlib + pydantic（D-01）；相对导入 wbr.* 允许。"""
    allowed = set(sys.stdlib_module_names) | {"pydantic", "wbr", "_wbr_tests_probe"}
    violations: list[str] = []
    for py in sorted(WBR.joinpath("core").rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in allowed:
                        violations.append(f"{py.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue  # 相对导入
                root = (node.module or "").split(".")[0]
                if root and root not in allowed:
                    violations.append(f"{py.name}: from {node.module}")
    assert not violations, f"Core 引入了未许可依赖: {violations}"
