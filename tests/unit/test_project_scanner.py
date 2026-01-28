from pathlib import Path

from work_by_roles.core.project_scanner import ProjectScanner
from work_by_roles.core.models import ProjectContext


def test_scanner_sets_learning_history_default(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    scanner = ProjectScanner(tmp_path)
    context = scanner.scan()
    assert context.paths["learning_history"] == "docs/LEARNING_HISTORY.md"


def test_scanner_sets_learning_history_without_docs(tmp_path: Path):
    scanner = ProjectScanner(tmp_path)
    context = scanner.scan()
    assert context.paths["learning_history"] == "docs/LEARNING_HISTORY.md"


def test_project_context_overrides_learning_history(tmp_path: Path):
    data = {"paths": {"learning_history": "custom/learning.md"}}
    context = ProjectContext.from_dict(tmp_path, data)
    assert context.paths["learning_history"] == "custom/learning.md"
