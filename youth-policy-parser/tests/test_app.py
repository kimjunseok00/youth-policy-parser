"""화면 실행 테스트 (Streamlit AppTest).

브라우저 없이 앱을 실제로 돌려서, 예시 인물 → 판정하기 → 결과 화면까지 에러 없이 가는지 확인한다.
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


def run_persona(index: int) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    at.button(key=f"sample_{index}").click().run()
    submit = next(b for b in at.button if b.label == "판정하기")
    submit.click().run()
    assert not at.exception, at.exception
    return at


def test_input_page_renders():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value == "청년정책 자격 판정"
    assert "2026-10-10" in at.caption[0].value  # 기준일 고정이 화면까지 반영되는지
    assert len([b for b in at.button if b.key and b.key.startswith("sample_")]) == len(personas())


@pytest.mark.parametrize("index", range(len(personas())))
def test_every_persona_reaches_result_page(index):
    at = run_persona(index)
    assert at.session_state["page"] == "result"
    labels = [m.label for m in at.metric]
    assert "💰 최대 수령액" in labels
    tab_labels = [t.label for t in at.tabs]
    for name in ("정책별 결과", "이것만 바꾸면", "최적 조합", "일정"):
        assert name in tab_labels


def test_seoul_persona_shows_move_suggestion():
    seoul = next(i for i, p in enumerate(personas()) if p["profile"]["sido"] != "부산광역시")
    at = run_persona(seoul)
    text = " ".join(m.value for m in at.markdown)
    assert "부산광역시(으)로 전입" in text


def test_optimizer_toggle_runs():
    at = run_persona(0)
    at.toggle[0].set_value(True).run()
    assert not at.exception
