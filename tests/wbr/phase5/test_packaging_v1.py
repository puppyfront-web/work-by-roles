"""TC-5-CLI-1 / TC-5-PKG-1 / TC-5-QUAL-1：CLI、打包版本与质量门禁。"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import wbr

REPO = Path(__file__).resolve().parents[3]


def test_version_is_1_0_0():
    assert wbr.__version__ >= "1.0.0"
    from importlib import metadata

    assert metadata.version("work-by-roles") == wbr.__version__


def test_cli_subcommands():
    bin = REPO / ".venv" / "bin" / "wbr"
    if not bin.is_file():  # 非 venv 环境退化为模块调用
        bin = None
    def run(*args):
        if bin:
            return subprocess.run([str(bin), *args], capture_output=True, text=True, timeout=60)
        return subprocess.run([sys.executable, "-m", "wbr.cli", *args], capture_output=True, text=True, timeout=60)

    r = run("version")
    assert r.returncode == 0 and "wbr 1." in r.stdout
    r = run("list-teams")
    assert r.returncode == 0
    assert "arch_review_team" in r.stdout and "security_audit_team" in r.stdout
    r = run("run-team", "security_audit_team", "审计登录接口", "--demo-output")
    assert r.returncode == 0
    body = r.stdout
    assert '"status": "completed"' in body
    r = run("show-team", "no_such_team")
    assert r.returncode != 0


def test_no_bare_except_pass_in_core():
    """质量门禁：core 禁止裸 except: pass。"""
    core = REPO / "wbr" / "core"
    offenders = []
    for py in sorted(core.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    bare = any(isinstance(n, ast.Pass) for n in ast.walk(node.body[0])) if node.body else True
                    if bare:
                        offenders.append(f"{py.name}:{node.lineno} bare except-pass")
    assert not offenders, offenders


def test_all_exceptions_are_wbr_subclasses():
    import inspect

    from wbr.core import exceptions as exc_mod

    classes = [
        obj for name, obj in vars(exc_mod).items()
        if inspect.isclass(obj) and issubclass(obj, Exception) and obj is not Exception
    ]
    assert classes
    for cls in classes:
        assert issubclass(cls, exc_mod.WBRError), cls.__name__


def test_wbr_exports_surface():
    """SDK 公共 API 完整性冒烟。"""
    import wbr as m

    for name in ("RoleContract", "ContractCompiler", "ContractDiffEngine", "MemoryHub",
                 "ReviewSession", "AuditTrail", "ContractBoundCache"):
        assert hasattr(m, name), name
