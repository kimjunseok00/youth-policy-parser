"""청년정책 자격 판정 앱.

입력 화면 → [판정하기] → 결과 화면 → [정보 수정] → 입력 화면
화면 전환은 st.session_state["page"]로 관리한다.
결과는 app.get_results(profile)로만 받는다. 판정 로직은 이 파일에 없다.
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

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
ICON = {Verdict.PASS: "✅", Verdict.FAIL: "❌", Verdict.UNKNOWN: "⚠️"}

# 임시 예시 인물 2명. 페르소나 파일 완성 후 이 상수만 교체하면 된다.
# 필드 이름은 Profile 스키마와 동일하게 유지한다.
SAMPLE_PROFILES = [
    {
        "label": "예시 1 — 부산진구 구직 청년",
        "birth_date": date(1999, 5, 10),
        "sido": "부산광역시",
        "sigungu": "부산진구",
        "residence_since": date(2023, 2, 1),
        "education": Education.GRADUATED,
        "employment": Employment.JOB_SEEKING,
        "personal_income_monthly": 0,
        "household_size": 3,
        "household_income_monthly": 4_500_000,
        "current_benefits": [],
    },
    {
        "label": "예시 2 — 해운대구 재직 청년",
        "birth_date": date(1995, 11, 20),
        "sido": "부산광역시",
        "sigungu": "해운대구",
        "residence_since": date(2021, 6, 1),
        "education": Education.GRADUATED,
        "employment": Employment.EMPLOYED,
        "personal_income_monthly": 2_800_000,
        "household_size": 2,
        "household_income_monthly": 5_000_000,
        "current_benefits": ["국민취업지원제도"],
    },
]


# ---------------------------------------------------------------------------
# 헬퍼: session_state 초기화
# ---------------------------------------------------------------------------
def _init_state() -> None:
    """앱 최초 실행 시 session_state 기본값을 세운다."""
    defaults: dict = {
        "page": "input",
        "profile": None,
        "result": None,
        # 입력 폼 필드값: 예시 1의 값을 기본으로 쓴다.
        "f_birth_date": SAMPLE_PROFILES[0]["birth_date"],
        "f_sido": SAMPLE_PROFILES[0]["sido"],
        "f_sigungu": SAMPLE_PROFILES[0]["sigungu"],
        "f_residence_since": SAMPLE_PROFILES[0]["residence_since"],
        "f_education": SAMPLE_PROFILES[0]["education"].value,
        "f_employment": SAMPLE_PROFILES[0]["employment"].value,
        "f_personal_income": SAMPLE_PROFILES[0]["personal_income_monthly"],
        "f_household_size": SAMPLE_PROFILES[0]["household_size"],
        "f_household_income": SAMPLE_PROFILES[0]["household_income_monthly"],
        "f_benefits": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _load_sample(idx: int) -> None:
    """예시 인물 값을 session_state 폼 필드에 덮어쓴다."""
    s = SAMPLE_PROFILES[idx]
    st.session_state["f_birth_date"] = s["birth_date"]
    st.session_state["f_sido"] = s["sido"]
    st.session_state["f_sigungu"] = s["sigungu"]
    st.session_state["f_residence_since"] = s["residence_since"]
    st.session_state["f_education"] = s["education"].value
    st.session_state["f_employment"] = s["employment"].value
    st.session_state["f_personal_income"] = s["personal_income_monthly"]
    st.session_state["f_household_size"] = s["household_size"]
    st.session_state["f_household_income"] = s["household_income_monthly"]
    st.session_state["f_benefits"] = "\n".join(s["current_benefits"])


# ---------------------------------------------------------------------------
# 입력 화면
# ---------------------------------------------------------------------------
def render_input_page() -> None:
    """프로필 입력 폼을 본문 가운데에 2열로 그린다."""
    # 예시 인물 버튼 — st.form 바깥에 있어야 클릭 즉시 필드값이 바뀐다.
    st.write("**예시 인물로 채우기**")
    btn_cols = st.columns(len(SAMPLE_PROFILES))
    for i, sample in enumerate(SAMPLE_PROFILES):
        if btn_cols[i].button(sample["label"], key=f"sample_{i}"):
            _load_sample(i)
            st.rerun()

    st.divider()

    with st.form("profile_form"):
        col1, col2 = st.columns(2)

        with col1:
            birth_date = st.date_input(
                "생년월일",
                value=st.session_state["f_birth_date"],
                min_value=date(1900, 1, 1),
                max_value=date.today(),
            )
            residence_since = st.date_input(
                "현 주소 전입일",
                value=st.session_state["f_residence_since"],
                min_value=date(1900, 1, 1),
                max_value=date.today(),
            )
            education = st.selectbox(
                "학력/재학 상태",
                options=[e.value for e in Education],
                index=[e.value for e in Education].index(st.session_state["f_education"]),
            )
            personal_income = st.number_input(
                "본인 월소득 (원)",
                min_value=0,
                value=st.session_state["f_personal_income"],
                step=100_000,
            )
            household_size = st.number_input(
                "가구원 수",
                min_value=1,
                value=st.session_state["f_household_size"],
                step=1,
            )

        with col2:
            sido = st.text_input("시·도", value=st.session_state["f_sido"])
            sigungu = st.text_input("시·군·구", value=st.session_state["f_sigungu"])
            employment = st.selectbox(
                "취업 상태",
                options=[e.value for e in Employment],
                index=[e.value for e in Employment].index(st.session_state["f_employment"]),
            )
            household_income = st.number_input(
                "가구 월소득 (원)",
                min_value=0,
                value=st.session_state["f_household_income"],
                step=100_000,
            )
            benefits_input = st.text_area(
                "현재 받고 있는 지원 (줄바꿈으로 구분)",
                value=st.session_state["f_benefits"],
                help="예: 국민취업지원제도",
            )

        submitted = st.form_submit_button("판정하기", use_container_width=True, type="primary")

    if submitted:
        # 입력값을 session_state에 저장 — [정보 수정]으로 돌아올 때 복원된다.
        st.session_state.update(
            {
                "f_birth_date": birth_date,
                "f_sido": sido,
                "f_sigungu": sigungu,
                "f_residence_since": residence_since,
                "f_education": education,
                "f_employment": employment,
                "f_personal_income": int(personal_income),
                "f_household_size": int(household_size),
                "f_household_income": int(household_income),
                "f_benefits": benefits_input,
            }
        )
        current_benefits = [b.strip() for b in benefits_input.splitlines() if b.strip()]
        try:
            profile = Profile(
                birth_date=birth_date,  # type: ignore[arg-type]
                sido=sido,
                sigungu=sigungu,
                residence_since=residence_since,  # type: ignore[arg-type]
                education=Education(education),
                employment=Employment(employment),
                personal_income_monthly=int(personal_income),
                household_size=int(household_size),
                household_income_monthly=int(household_income),
                current_benefits=current_benefits,
            )
        except Exception as e:
            st.error(f"입력 오류: {e}")
            st.stop()

        st.session_state["profile"] = profile
        st.session_state["result"] = get_results(profile)
        st.session_state["page"] = "result"
        st.rerun()


# ---------------------------------------------------------------------------
# 결과 화면
# ---------------------------------------------------------------------------
def render_reason(node: ReasonNode, depth: int = 0) -> None:
    """판정 사유 트리를 들여쓰기 목록으로 그린다. (4주차에 그래프 시각화로 교체 예정)"""
    indent = "&nbsp;" * 4 * depth
    detail = f" — {node.detail}" if node.detail else ""
    st.markdown(f"{indent}{ICON[node.verdict]} **{node.label}**{detail}", unsafe_allow_html=True)
    if node.source_quote:
        st.caption(f'{indent}원문: "{node.source_quote}"', unsafe_allow_html=True)
    for child in node.children:
        render_reason(child, depth + 1)


def render_policy_card(p: PolicyResult) -> None:
    """정책 카드 1장. 충족은 사유를 접어두고, 불충족·확인필요는 사유를 바로 노출한다."""
    amount = f"{p.amount_krw:,}원" if p.amount_krw is not None else "금액 산정 불가"
    deadline = p.apply_end.isoformat() if p.apply_end else "상시"

    with st.container(border=True):
        st.markdown(f"**{ICON[p.verdict]} {p.policy_name}**")
        st.caption(f"{p.agency} · {amount} · 마감 {deadline}")

        if p.verdict == Verdict.PASS:
            # 충족: 사유는 클릭해야 보이게 접어둔다.
            with st.expander("판정 사유 보기"):
                render_reason(p.reason)
        else:
            # 불충족·확인필요: 사유를 카드 안에 바로 표시한다.
            render_reason(p.reason)


def _profile_summary(profile: Profile) -> str:
    """프로필을 한 줄 요약 문자열로 만든다."""
    ref = date(2026, 10, 1)  # 기준일
    age = (
        ref.year
        - profile.birth_date.year
        - ((ref.month, ref.day) < (profile.birth_date.month, profile.birth_date.day))
    )
    return (
        f"{profile.sigungu} 거주 / 만 {age}세 / "
        f"{profile.employment.value} / 가구 {profile.household_size}인"
    )


def render_result_page(profile: Profile, result: EvaluationResult) -> None:
    """판정 결과 화면을 그린다."""
    # 프로필 요약 한 줄 + [정보 수정] 버튼
    summary_col, btn_col = st.columns([5, 1])
    summary_col.markdown(f"**{_profile_summary(profile)}**")
    if btn_col.button("정보 수정 →", use_container_width=True):
        st.session_state["page"] = "input"
        st.rerun()

    st.divider()

    # 요약 metric 4개
    n_pass = len(result.by_verdict(Verdict.PASS))
    n_fail = len(result.by_verdict(Verdict.FAIL))
    n_unknown = len(result.by_verdict(Verdict.UNKNOWN))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("✅ 충족", f"{n_pass}건")
    m2.metric("❌ 불충족", f"{n_fail}건")
    m3.metric("⚠️ 확인 필요", f"{n_unknown}건")
    m4.metric("💰 예상 총액", f"{result.total_expected_krw:,}원")

    # 자리 표시 섹션 (3주차 구현 예정)
    ph1, ph2 = st.columns(2)
    ph1.info("💡 **이것만 바꾸면** — 3주차 구현 예정")
    ph2.info("🔢 **최적 조합** — 3주차 구현 예정")

    st.divider()

    # 정책별 결과 탭
    tabs = st.tabs([f"{ICON[v]} {v.value}" for v in Verdict])
    for tab, verdict in zip(tabs, Verdict, strict=True):
        with tab:
            items = result.by_verdict(verdict)
            if not items:
                st.write("해당 정책이 없습니다.")
            for p in items:
                render_policy_card(p)


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="청년정책 자격 판정", page_icon="🧾", layout="centered")
    st.title("청년정책 자격 판정")
    st.info("아래 결과는 가짜 데이터입니다. 프로필을 입력해도 판정 결과는 아직 바뀌지 않습니다.")

    _init_state()

    if st.session_state["page"] == "input":
        render_input_page()
    else:
        render_result_page(st.session_state["profile"], st.session_state["result"])


main()
