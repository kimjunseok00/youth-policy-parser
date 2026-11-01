"""scripts/build_app.py: 화면 파일만 바뀌어도 서비스 워커 캐시 이름이 달라지는지.

캐시 이름이 그대로면, 이미 앱을 열어 본 기기는 CSS·JS를 고쳐 다시 배포해도 예전 화면을 계속 본다.
"""

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_app.py"


@pytest.fixture(scope="module")
def build_app():
    spec = importlib.util.spec_from_file_location("build_app", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_frontend_digest_changes_with_content(build_app, tmp_path):
    (tmp_path / "style.css").write_text("body{color:#000}", "utf-8")
    before = build_app.frontend_digest(tmp_path)
    (tmp_path / "style.css").write_text("body{color:#111}", "utf-8")
    assert build_app.frontend_digest(tmp_path) != before


def test_frontend_digest_changes_with_new_file(build_app, tmp_path):
    (tmp_path / "app.js").write_text("a", "utf-8")
    before = build_app.frontend_digest(tmp_path)
    (tmp_path / "install.js").write_text("b", "utf-8")
    assert build_app.frontend_digest(tmp_path) != before


def test_frontend_digest_is_stable(build_app, tmp_path):
    (tmp_path / "app.js").write_text("a", "utf-8")
    assert build_app.frontend_digest(tmp_path) == build_app.frontend_digest(tmp_path)
