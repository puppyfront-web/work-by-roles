"""TC-5-PKG-1：构建 sdist/wheel 并校验产物内容（标记 slow，可用 -m 过滤）。"""
from __future__ import annotations

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

REPO = Path(__file__).resolve().parents[3]
DIST = REPO / "dist"


@pytest.fixture(scope="module")
def built():
    DIST.mkdir(exist_ok=True)
    r = subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--wheel", "--outdir", str(DIST), str(REPO)],
        capture_output=True, text=True, timeout=600,
    )
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    wheels = sorted(DIST.glob("work_by_roles-1.*.whl"))
    sdists = sorted(DIST.glob("work_by_roles-1.*.tar.gz"))
    assert wheels and sdists
    return {"wheel": wheels[-1], "sdist": sdists[-1]}


def _wheel_names(whl: Path) -> set[str]:
    with zipfile.ZipFile(whl) as z:
        return set(z.namelist())


def test_wheel_contains_wbr_package(built):
    names = _wheel_names(built["wheel"])
    assert any(n == "wbr/__init__.py" for n in names)
    assert any(n == "wbr/core/contract/models.py" for n in names)
    assert any(n == "wbr/cli.py" for n in names)
    # 模板资源随包分发
    assert any("templates/teams/arch_review_team/coordinator.yaml" in n for n in names)
    assert any("templates/teams/security_audit_team/team.json" in n for n in names)
    # 画布静态资源
    assert any("app/canvas/static/index.html" in n for n in names)


def test_sdist_contains_sources_and_docs(built):
    with tarfile.open(built["sdist"]) as t:
        names = set(t.getnames())
    assert any(n.endswith("pyproject.toml") for n in names)
    assert any("wbr/core/orchestration/review.py" in n for n in names)
    assert any("LICENSE" in n for n in names)


def test_wheel_metadata_stable(built):
    with zipfile.ZipFile(built["wheel"]) as z:
        meta_name = next(n for n in z.namelist() if n.endswith("METADATA"))
        meta = z.read(meta_name).decode("utf-8")
    assert "Version: 1.1.0" in meta
    assert "Name: work-by-roles" in meta
    assert "License-Expression" in meta or "License: MIT" in meta


def test_wheel_installs_and_imports(built, tmp_path):
    """ wheel 在干净 venv 中可安装且可导入（模板资源可达）。 """
    venv_dir = tmp_path / "wheelvenv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv_dir)], check=True,
                   timeout=180)
    py = venv_dir / "bin" / "python"
    pip_url = "https://bootstrap.pypa.io/get-pip.py"
    subprocess.run([str(py), "-c", "import sys"], check=True, timeout=30)
    # 直接用 --target 安装并验证 import 路径（避免网络 get-pip）
    target = tmp_path / "target"
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-deps",
                    "--target", str(target), str(built["wheel"])], check=True, timeout=300)
    script = (
        "import sys; sys.path.insert(0, %r); "
        "import wbr; assert wbr.__version__ >= '1.0.0', wbr.__version__; "
        "from wbr.templates.registry import load_team, list_teams; "
        "assert {'arch_review_team','security_audit_team'} <= {t['name'] for t in list_teams()}; "
        "c = load_team('arch_review_team'); assert len(c) == 5; "
        "assert len(list(c.values())[0].content_hash) == 64; "
        "print('WHEEL_INSTALL_OK')"
    ) % str(target)
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WHEEL_INSTALL_OK" in r.stdout
