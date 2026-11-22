"""版本号、changelog、安装说明与可选依赖保持一致。"""
from __future__ import annotations

import re
from pathlib import Path

import wbr

ROOT = Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_package_version_matches_pyproject_and_changelog():
    pyproject = _read("pyproject.toml")
    match = re.search(r'(?m)^version = "([^"]+)"$', pyproject)
    assert match is not None
    version = match.group(1)
    assert version == wbr.__version__ == "2.2.0"
    changelog = _read("CHANGELOG.md")
    assert f"## [{version}]" in changelog
    released = changelog.split(f"## [{version}]", 1)[1].split("\n## [", 1)[0]
    assert "WBR_API_KEY" in released
    unreleased = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
    assert "Phase 0 省 Token" in unreleased


def test_readmes_point_at_git_install_and_docs():
    for name in ("README.md", "README_EN.md"):
        text = _read(name)
        assert f"version-{wbr.__version__}" in text
        assert "version-2.1.1" not in text
        assert "370+" not in text
        assert "https://puppyfront-web.github.io/work-by-roles/" in text
        assert "git+https://github.com/puppyfront-web/work-by-roles.git" in text
        assert "PyPI" in text


def test_requirements_match_runtime_dependencies():
    lines = [
        line.strip()
        for line in _read("requirements.txt").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert lines == ["pydantic>=2.5", "pyyaml>=6.0", "jsonschema>=4.0.0"]


def test_llm_extra_declares_httpx_and_publish_workflow_is_tag_only():
    pyproject = _read("pyproject.toml")
    assert re.search(r"(?s)llm = \[[^\]]*httpx>=0\.26", pyproject)
    workflow = _read(".github/workflows/publish.yml")
    assert "pull_request" not in workflow
    assert "pypa/gh-action-pypi-publish" in workflow
    assert 'tags:' in workflow
