"""청년정책 자격 판정 앱.

사이드바에서 프로필을 입력하면 app.get_results()를 통해 판정 결과를 받아 화면에 그린다.
엔진 완성 후 app.get_results() 내부만 교체하면 이 파일은 변경이 없다.
Streamlit Community Cloud는 저장소 루트의 streamlit_app.py를 기본 진입점으로 쓴다.
"""

from datetime import date

import streamlit as st

from app import get_results
from engine.schemas import (
    Education,
    Employment,
    EvaluationResult,
    PolicyResult,
    Profile,
    ReasonNode,
    Verdict,
)

# 판정 결과별 아이콘: 화면에서 한눈에 구분되도록 한다.
ICON = {Verdict.PASS: "✅", Verdict.FAIL: "❌", Verdict.UNKNOWN: "⚠️"}


def sidebar_profile() -> Profile:
    """사이드바에서 Profile 전 필드를 입력받아 반환한다."""
    st.sidebar.header("내 정보 입력")

    birth_date = st.sidebar.date_input(
        "생년월일",
        value=date(1999, 1, 1),
        min_value=date(1900, 1, 1),
        max_value=date.today(),
    )
    sido = st.sidebar.text_input("시·도", value="부산광역시")
    sigungu = st.sidebar.text_input("시·군·구", value="부산진구")
    residence_since = st.sidebar.date_input(
        "현 주소 전입일",
        value=date(2023, 1, 1),
        min_value=date(1900, 1, 1),
        max_value=date.today(),
    )
    education = st.sidebar.selectbox(
        "학력/재학 상태",
        options=[e.value for e in Education],
    )
    employment = st.sidebar.selectbox(
        "취업 상태",
        options=[e.value for e in Employment],
    )
    personal_income_monthly = st.sidebar.number_input(
        "본인 월소득 (원)",
        min_value=0,
        value=0,
        step=100_000,
    )
    household_size = st.sidebar.number_input(
        "가구원 수",
        min_value=1,
        value=3,
        step=1,
    )
    household_income_monthly = st.sidebar.number_input(
        "가구 월소득 (원)",
        min_value=0,
        value=4_500_000,
        step=100_000,
    )
    benefits_input = st.sidebar.text_area(
        "현재 받고 있는 지원 (줄바꿈으로 구분)",
        value="",
        help="예: 국민취업지원제도",
    )
    current_benefits = [b.strip() for b in benefits_input.splitlines() if b.strip()]

    # birth_date는 date_input이 date를 반환하지만, 타입 힌트 일치를 위해 명시적으로 처리한다.
    return Profile(
        birth_date=birth_date,  # type: ignore[arg-type]
        sido=sido,
        sigungu=sigungu,
        residence_since=residence_since,  # type: ignore[arg-type]
        education=Education(education),
        employment=Employment(employment),
        personal_income_monthly=int(personal_income_monthly),
        household_size=int(household_size),
        household_income_monthly=int(household_income_monthly),
        current_benefits=current_benefits,
    )


def render_reason(node: ReasonNode, depth: int = 0) -> None:
    """판정 사유 트리를 들여쓰기 목록으로 그린다. (4주차에 그래프 시각화로 교체 예정)"""
    indent = "&nbsp;" * 4 * depth
    detail = f" — {node.detail}" if node.detail else ""
    st.markdown(f"{indent}{ICON[node.verdict]} **{node.label}**{detail}", unsafe_allow_html=True)
    if node.source_quote:
        st.caption(f'{indent}원문: "{node.source_quote}"', unsafe_allow_html=True)
    for child in node.children:
        render_reason(child, depth + 1)


def render_policy(p: PolicyResult) -> None:
    """정책 카드 1장."""
    amount = f"{p.amount_krw:,}원" if p.amount_krw is not None else "금액 산정 불가"
    deadline = p.apply_end.isoformat() if p.apply_end else "상시"
    with st.expander(f"{ICON[p.verdict]} {p.policy_name} · {amount} · 마감 {deadline}"):
        st.caption(p.agency)
        render_reason(p.reason)


def render_results(result: EvaluationResult) -> None:
    """판정 결과 전체를 탭으로 나눠 그린다."""
    # 충족 정책 예상 총액
    st.metric("받을 수 있는 예상 총액 (단순 합계)", f"{result.total_expected_krw:,}원")

    # 정책별 결과 탭
    tabs = st.tabs([f"{ICON[v]} {v.value}" for v in Verdict])
    for tab, verdict in zip(tabs, Verdict, strict=True):
        with tab:
            items = result.by_verdict(verdict)
            if not items:
                st.write("해당 정책이 없습니다.")
            for p in items:
                render_policy(p)

    st.divider()

    # "이것만 바꾸면" 카드 자리 (3주차 구현 예정)
    with st.expander("💡 이것만 바꾸면 — 3주차 구현 예정"):
        st.info("조건 하나만 바꾸면 충족되는 정책 목록이 여기에 표시됩니다.")

    # 최적 조합 자리 (3주차 구현 예정)
    with st.expander("🔢 최적 조합 — 3주차 구현 예정"):
        st.info("중복수혜 제한을 고려한 최대 수령액 조합이 여기에 표시됩니다.")


def main() -> None:
    st.set_page_config(page_title="청년정책 자격 판정", page_icon="🧾", layout="wide")
    st.title("청년정책 자격 판정")
    st.info("아래 결과는 가짜 데이터입니다. 프로필을 입력해도 판정 결과는 아직 바뀌지 않습니다.")

    # 사이드바에서 프로필을 받아 판정 결과를 가져온다.
    try:
        profile = sidebar_profile()
    except Exception as e:
        st.sidebar.error(f"입력 오류: {e}")
        st.stop()

    result = get_results(profile)
    render_results(result)


main()
