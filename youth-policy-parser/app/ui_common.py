"""여러 화면이 같이 쓰는 표시 도우미와 하단 안내."""

from __future__ import annotations

import streamlit as st

from app.branding import FEEDBACK_URL, PRIVACY_URL, SERVICE_NAME, SITE_URL, TERMS_URL, VERSION
from engine.schemas import Verdict

ICON = {Verdict.PASS: "✅", Verdict.FAIL: "❌", Verdict.UNKNOWN: "⚠️"}


def won(n: int | None) -> str:
    return f"{n:,}원" if n is not None else "금액 산정 불가"


def man(n: int) -> str:
    """좁은 칸용 짧은 금액: 3,600,000 → '360만 원'."""
    return f"{n / 10_000:,.0f}만 원" if n >= 10_000 else f"{n:,}원"


def footer(telemetry_on: bool) -> None:
    st.divider()
    stored = (
        "동의한 경우에만 개인을 알아볼 수 없는 익명 통계를 저장합니다."
        if telemetry_on
        else "입력하신 정보는 저장하지 않습니다."
    )
    st.caption(
        f"{SERVICE_NAME} v{VERSION} · 판정 결과는 참고용이며, 최종 자격은 각 공고문과 담당 기관에서 확인하세요. "
        f"{stored}"
    )
    st.caption(
        f"[서비스 소개]({SITE_URL}) · [개인정보처리방침]({PRIVACY_URL}) · "
        f"[이용약관]({TERMS_URL}) · [의견 보내기]({FEEDBACK_URL})"
    )
