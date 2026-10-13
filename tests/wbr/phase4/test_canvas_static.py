"""TC-4-CANVAS-1：画布静态资源。"""
from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[3] / "wbr" / "app" / "canvas" / "static"


def test_canvas_page_served(client):
    r = client.get("/canvas")
    assert r.status_code == 200
    assert "专家画布" in r.text
    # HTML 引用的静态资源
    assert '/canvas/static/app.js' in r.text
    assert '/canvas/static/style.css' in r.text


def test_canvas_static_assets_served(client):
    for path, frag in [
        ("/canvas/static/app.js", "api-bootstrap"),
        ("/canvas/static/style.css", "expert-card"),
    ]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert frag in r.text


def test_canvas_static_files_exist():
    for name in ("index.html", "app.js", "style.css"):
        assert (STATIC / name).is_file(), name


def test_canvas_bootstrap_and_disagreement_marker(client):
    boot = client.get("/canvas/api-bootstrap")
    assert boot.status_code == 200
    assert "contracts" in boot.json()
    # 页面与脚本包含分歧高亮关键标识（SPEC-005 §2 分歧点高亮）
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "disputed" in js and "disagreements" in js
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "disagreements" in html


def test_canvas_html_references_resolve(client):
    import re

    html = client.get("/canvas").text
    refs = re.findall(r'/canvas/static/[\w.\-]+', html)
    assert refs
    for ref in set(refs):
        assert client.get(ref).status_code == 200, ref
