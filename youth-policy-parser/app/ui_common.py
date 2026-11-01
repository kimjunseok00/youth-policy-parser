"""여러 화면이 같이 쓰는 표시 도우미와 하단 안내.

디자인 원칙 (A안 '행정 문서형')
- 이모티콘을 쓰지 않는다. 상태는 색 + 글자 배지(충족·불충족·확인 필요·참고)로만 표시한다.
- 색만으로 구분하지 않도록 배지에는 항상 글자가 들어간다 (색각 이상 사용자 배려).
- 강조색은 남색 하나. 판정 색은 .streamlit/config.toml의 green/red/orange/gray를 쓴다.
"""

from __future__ import annotations

import streamlit as st

from app.branding import FEEDBACK_URL, PRIVACY_URL, SERVICE_NAME, SITE_URL, TERMS_URL, VERSION
from engine.schemas import ReasonNode, Verdict

# 화면에 보이는 판정 이름 (엔진 값 '확인필요'는 띄어쓰기를 넣어 보여준다)
LABEL = {Verdict.PASS: "충족", Verdict.FAIL: "불충족", Verdict.UNKNOWN: "확인 필요"}
COLOR = {Verdict.PASS: "green", Verdict.FAIL: "red", Verdict.UNKNOWN: "orange"}


def badge(verdict: Verdict) -> str:
    """판정 배지 (Streamlit 마크다운 문법). 예: ':green-badge[충족]'"""
    return f":{COLOR[verdict]}-badge[{LABEL[verdict]}]"


def node_badge(node: ReasonNode) -> str:
    """사유 트리 노드용 배지. 참고 안내문은 판정과 무관하므로 회색 '참고'."""
    return ":gray-badge[참고]" if node.notice else badge(node.verdict)


def tag(text: str, color: str = "gray") -> str:
    """판정이 아닌 보조 표시 (예: '신청 기간 아님', '바꿀 수 있음')."""
    return f":{color}-badge[{text}]"


def won(n: int | None) -> str:
    return f"{n:,}원" if n is not None else "금액 산정 불가"


def man(n: int) -> str:
    """좁은 칸용 짧은 금액: 3,600,000 → '360만 원'."""
    return f"{n / 10_000:,.0f}만 원" if n >= 10_000 else f"{n:,}원"


def page_header(title: str, caption: str) -> None:
    """모든 페이지가 같은 모양으로 시작하도록: 제목 + 한 줄 설명 + 구분선."""
    st.header(title, divider="gray")
    st.caption(caption)


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
