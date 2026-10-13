"""화면 실행 테스트 (Streamlit AppTest).

브라우저 없이 앱을 실제로 돌려서 주요 흐름이 에러 없이 끝나는지 확인한다.
"""

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app as app_module
from app import personas

APP = str(Path(__file__).resolve().parent.parent / "streamlit_app.py")
FIXED_DAY = date(2026, 10, 10)  # 실제 날짜가 바뀌어도 결과가 같도록 기준일 고정


@pytest.fixture(autouse=True)
def fixed_as_of(monkeypatch):
    monkeypatch.setattr(app_module, "as_of", lambda: FIXED_DAY)


def start() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    return at


def run_persona(index: int) -> AppTest:
    at = start()
    at.button(key=f"sample_{index}").click().run()
    next(b for b in at.button if b.label == "판정하기").click().run()
    assert not at.exception, at.exception
    return at


def test_input_page_renders():
    at = start()
    assert at.header[0].value == "자격 판정"
    assert any("2026-10-10" in c.value for c in at.caption)
    assert len([b for b in at.button if b.key and b.key.startswith("sample_")]) == len(personas())


@pytest.mark.parametrize("index", range(len(personas())))
def test_every_persona_reaches_result_page(index):
    at = run_persona(index)
    assert at.session_state["page"] == "result"
    assert "최대 수령액" in [m.label for m in at.metric]
    tab_labels = [t.label for t in at.tabs]
    for name in ("정책별 결과", "이것만 바꾸면", "최적 조합", "일정"):
        assert name in tab_labels


def test_seoul_persona_shows_move_suggestion():
    seoul = next(i for i, p in enumerate(personas()) if p["profile"]["sido"] != "부산광역시")
    at = run_persona(seoul)
    assert "부산광역시(으)로 전입" in " ".join(m.value for m in at.markdown)


def test_optimizer_toggle_runs():
    at = run_persona(0)
    at.toggle[0].set_value(True).run()
    assert not at.exception


def test_answering_questions_reduces_unknown():
    at = run_persona(0)
    before = sum(1 for r in at.session_state["result"].results if r.verdict.value == "확인필요")
    assert before > 0
    for radio in at.radio:
        if radio.key and radio.key.startswith("q_"):
            radio.set_value("예")
    next(b for b in at.button if b.label == "답변 반영해서 다시 판정").click().run()
    assert not at.exception, at.exception
    after = sum(1 for r in at.session_state["result"].results if r.verdict.value == "확인필요")
    assert after < before
    assert at.session_state["answers"]


def test_contradictory_income_shows_friendly_error():
    at = start()
    labels = {ni.label: ni for ni in at.number_input}
    labels["본인 월소득 (원)"].set_value(5_000_000)
    labels["가구 월소득 (원)"].set_value(1_000_000)
    next(b for b in at.button if b.label == "판정하기").click().run()
    assert at.session_state["page"] == "input"
    assert any("가구 월소득" in e.value for e in at.error)


def _page_script(name):
    """AppTest가 이 함수의 '소스'를 실행하므로, 필요한 값은 args로 넘긴다."""
    import importlib

    importlib.import_module(f"app.{name}").render()


def _run_page(name: str) -> AppTest:
    at = AppTest.from_function(_page_script, args=(name,), default_timeout=120).run()
    assert not at.exception, at.exception
    return at


def test_report_page_renders_with_synthetic_warning():
    at = _run_page("page_report")
    assert at.header[0].value == "지자체 리포트"
    assert any("가상 인구" in w.value for w in at.warning)
    at.slider(key="sim_age").set_value(5).run()
    assert not at.exception, at.exception
    assert any(m.label == "대상 가능 인원" for m in at.metric)


def test_about_page_lists_policy_sources():
    at = _run_page("page_about")
    text = " ".join(m.value for m in at.markdown)
    assert "출처" in text and "개인정보" in " ".join(s.value for s in at.subheader)


def test_no_emoji_in_ui_source():
    """디자인 원칙: 화면에는 이모티콘을 쓰지 않는다 (상태는 글자 배지로 표시)."""
    import re
    from pathlib import Path

    emoji = re.compile("[\U0001f300-\U0001faff\u2600-\u27bf]")
    root = Path(__file__).resolve().parents[1]
    files = [root / "streamlit_app.py", *sorted((root / "app").glob("*.py"))]
    found = {f.name: emoji.findall(f.read_text("utf-8")) for f in files}
    assert not {k: v for k, v in found.items() if v}
