"""청년정책 자격 판정 앱.

입력 화면 → [판정하기] → 결과 화면 → [정보 수정] → 입력 화면
화면 전환은 st.session_state["page"]로 관리한다.
판정·제안·일정·조합은 전부 app 모듈(→ engine)에서 받는다. 이 파일에는 판정 로직이 없다.

(입력·결과 화면 구조는 팀원이 만든 feature/ui 브랜치를 기반으로 확장했다)
"""

from datetime import date

import streamlit as st

from app import (
    BENEFIT_NAMES,
    BUSAN_SIGUNGU,
    SIDO,
    as_of,
    get_insights,
    get_results,
    personas,
    policies,
)
from engine.evaluator import full_age
from engine.income import load_table
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
EVENT_ICON = {"자격 발생": "🟢", "자격 상실": "🔴", "신청 마감": "⏰"}
FIXABLE_ORDER = {"행동": 0, "시간": 1, "변경 어려움": 2}
BUSAN = "부산광역시"


def won(n: int | None) -> str:
    return f"{n:,}원" if n is not None else "금액 산정 불가"


def man(n: int) -> str:
    """지표 칸처럼 좁은 곳에 쓰는 짧은 표기: 3,600,000 → '360만 원'."""
    return f"{n / 10_000:,.0f}만 원" if n >= 10_000 else f"{n:,}원"


# ---------------------------------------------------------------------------
# 헬퍼: session_state
# ---------------------------------------------------------------------------
def _fill_from_profile(p: dict) -> None:
    """프로필 dict 값을 폼 필드(session_state)에 넣는다."""
    st.session_state.update(
        {
            "f_birth_date": date.fromisoformat(str(p["birth_date"])),
            "f_sido": p["sido"],
            "f_sigungu": p["sigungu"],
            "f_residence_since": date.fromisoformat(str(p["residence_since"])),
            "f_education": p["education"],
            "f_employment": p["employment"],
            "f_personal_income": int(p["personal_income_monthly"]),
            "f_household_size": int(p["household_size"]),
            "f_household_income": int(p["household_income_monthly"]),
            "f_benefits": [b for b in p["current_benefits"] if b in BENEFIT_NAMES],
        }
    )


def _init_state() -> None:
    """앱 최초 실행 시 기본값: 첫 번째 예시 인물."""
    if "page" not in st.session_state:
        st.session_state.update({"page": "input", "profile": None, "result": None})
        _fill_from_profile(personas()[0]["profile"])


# ---------------------------------------------------------------------------
# 입력 화면
# ---------------------------------------------------------------------------
def render_income_calculator() -> None:
    """소득 환산기: 내 소득이 기준중위소득 몇 %인지 바로 계산 (정책 조건 대부분이 % 기준이라서)."""
    table = load_table()
    with st.expander(f"🧮 소득 환산기 — 내 소득은 기준중위소득 몇 %? ({table.year}년 기준)"):
        c1, c2 = st.columns(2)
        income = c1.number_input(
            "월소득 (원)", min_value=0, value=3_000_000, step=100_000, key="calc_income"
        )
        size = c2.number_input(
            "가구원 수", min_value=1, max_value=12, value=1, step=1, key="calc_size"
        )
        pct = table.pct(int(income), int(size))
        st.metric("기준중위소득 대비", f"{pct:.1f}%")
        base = table.monthly(int(size))
        rows = [
            f"| {p}% | {int(base * p / 100):,}원 | {'✅' if pct <= p else '❌'} |"
            for p in (50, 60, 100, 120, 150, 200)
        ]
        st.markdown(
            "| 정책에서 자주 쓰는 기준 | 월소득 상한 | 내 소득 |\n|---|---|---|\n" + "\n".join(rows)
        )
        st.caption(
            "출처: 보건복지부고시 제2025-135호. "
            "실제 정책은 건강보험료 등 다른 방식으로 소득을 볼 수 있습니다."
        )


def render_input_page() -> None:
    """프로필 입력 폼."""
    st.write("**예시 인물로 채우기**")
    people = personas()
    for row_start in range(0, len(people), 3):
        cols = st.columns(3)
        for col, i in zip(cols, range(row_start, min(row_start + 3, len(people))), strict=False):
            if col.button(
                people[i]["label"], key=f"sample_{i}", help=people[i]["scenario"], width="stretch"
            ):
                _fill_from_profile(people[i]["profile"])
                st.rerun()

    st.divider()

    # 시·도는 폼 밖에 둔다: 바꾸는 즉시 시·군·구 선택지가 따라 바뀌어야 하기 때문
    sido = st.selectbox(
        "거주 시·도",
        options=list(SIDO),
        index=list(SIDO).index(st.session_state["f_sido"])
        if st.session_state["f_sido"] in SIDO
        else 1,
    )
    st.session_state["f_sido"] = sido

    with st.form("profile_form"):
        col1, col2 = st.columns(2)

        with col1:
            birth_date = st.date_input(
                "생년월일",
                value=st.session_state["f_birth_date"],
                min_value=date(1970, 1, 1),
                max_value=as_of(),
            )
            residence_since = st.date_input(
                "현 주소 전입일",
                value=st.session_state["f_residence_since"],
                min_value=date(1970, 1, 1),
                max_value=as_of(),
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
                max_value=12,
                value=st.session_state["f_household_size"],
                step=1,
            )

        with col2:
            if sido == BUSAN:
                current = st.session_state["f_sigungu"]
                sigungu = st.selectbox(
                    "시·군·구",
                    options=list(BUSAN_SIGUNGU),
                    index=list(BUSAN_SIGUNGU).index(current) if current in BUSAN_SIGUNGU else 0,
                )
            else:
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
                help="부모님과 따로 산다면 본인 가구(독립가구) 기준으로 입력하세요.",
            )
            benefits = st.multiselect(
                "현재 받고 있는 지원",
                options=list(BENEFIT_NAMES),
                default=st.session_state["f_benefits"],
                help="중복수혜 제한을 판정하는 데 씁니다.",
            )

        submitted = st.form_submit_button("판정하기", type="primary", width="stretch")

    render_income_calculator()

    if submitted:
        st.session_state.update(
            {
                "f_birth_date": birth_date,
                "f_sigungu": sigungu,
                "f_residence_since": residence_since,
                "f_education": education,
                "f_employment": employment,
                "f_personal_income": int(personal_income),
                "f_household_size": int(household_size),
                "f_household_income": int(household_income),
                "f_benefits": benefits,
            }
        )
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
                current_benefits=benefits,
            )
        except (
            Exception
        ) as e:  # 스키마 검증 실패(예: 전입일 < 생년월일)를 사용자에게 그대로 보여준다
            st.error(f"입력 오류: {e}")
            st.stop()

        result = get_results(profile)
        st.session_state.update(
            {
                "profile": profile,
                "result": result,
                "insights": get_insights(profile, result),
                "page": "result",
            }
        )
        st.rerun()


# ---------------------------------------------------------------------------
# 결과 화면
# ---------------------------------------------------------------------------
def render_reason(node: ReasonNode, depth: int = 0, show_quote: bool = True) -> None:
    """판정 사유 트리를 들여쓰기 목록으로 그린다."""
    indent = "&nbsp;" * 4 * depth
    detail = f" — {node.detail}" if node.detail else ""
    st.markdown(f"{indent}{ICON[node.verdict]} **{node.label}**{detail}", unsafe_allow_html=True)
    for child in node.children:
        render_reason(child, depth + 1, show_quote=False)
    if depth == 0 and show_quote and node.source_quote:
        with st.expander("자격요건 원문 보기"):
            st.write(node.source_quote)


def render_policy_card(p: PolicyResult) -> None:
    """정책 카드 1장. 충족은 사유를 접어두고, 불충족·확인필요는 사유를 바로 노출한다."""
    if p.apply_start or p.apply_end:
        period = f"{p.apply_start or ''} ~ {p.apply_end or ''}"
    else:
        period = "상시 · 기간 공고 확인"

    with st.container(border=True):
        head = f"**{ICON[p.verdict]} {p.policy_name}**"
        if not p.is_open:
            head += " &nbsp; `신청 기간 아님`"
        st.markdown(head, unsafe_allow_html=True)
        st.caption(f"{p.agency} · {won(p.amount_krw)} · 신청 {period}")
        if p.amount_text:
            st.caption(p.amount_text)

        if p.verdict == Verdict.PASS:
            with st.expander("판정 사유 보기"):
                render_reason(p.reason)
        else:
            render_reason(p.reason)
        if p.source_url:
            st.caption(f"[출처]({p.source_url})")


def _profile_summary(profile: Profile, on: date) -> str:
    return (
        f"{profile.sido} {profile.sigungu} / 만 {full_age(profile.birth_date, on)}세 / "
        f"{profile.employment.value} / 가구 {profile.household_size}인"
    )


def render_suggestions(ins) -> None:
    """💡 이것만 바꾸면: 행동 제안 + 조건 하나만 어긋난 정책."""
    st.subheader("💡 이것만 바꾸면")
    if ins.suggestions:
        for s in ins.suggestions[:3]:
            with st.container(border=True):
                st.markdown(
                    f"**{s.action}** → {len(s.gained)}건 추가, **+{s.gained_amount_krw:,}원**"
                )
                st.caption("새로 대상이 되는 정책: " + ", ".join(s.gained))
                if s.lost:
                    st.warning(f"대신 잃는 정책: {', '.join(s.lost)} (−{s.lost_amount_krw:,}원)")
    else:
        st.caption("지금 프로필에서 행동 하나로 새로 받을 수 있는 정책은 없습니다.")

    misses = sorted(
        ins.near_misses, key=lambda m: (FIXABLE_ORDER[m.fixable_by], -(m.amount_krw or 0))
    )
    if misses:
        st.markdown("**조건 하나만 어긋난 정책**")
        for m in misses:
            badge = {
                "행동": "🛠 바꿀 수 있음",
                "시간": "⏳ 시간이 지나면",
                "변경 어려움": "· 변경 어려움",
            }[m.fixable_by]
            st.markdown(
                f"- **{m.policy_name}** ({won(m.amount_krw)}) — {m.condition} · {m.gap}  `{badge}`"
            )


def render_plan(ins) -> None:
    """🔢 최적 조합: 중복수혜를 지키면서 금액이 가장 큰 묶음."""
    st.subheader("🔢 최적 조합")
    with_unknown = st.toggle("'확인 필요' 정책도 포함해서 계산", value=False)
    plan = ins.plan_with_unknown if with_unknown else ins.plan
    if not plan.selected:
        st.caption("지금 신청 가능한 정책이 없습니다. 위 토글로 '확인 필요' 정책을 포함해 보세요.")
        return
    st.metric("중복수혜를 반영한 최대 수령액", won(plan.total_krw))
    if plan.excluded:
        st.caption(
            f"조건만 보고 단순히 더하면 {plan.simple_sum_krw:,}원이지만, "
            f"중복수혜 제한 때문에 {plan.simple_sum_krw - plan.total_krw:,}원이 줄어듭니다."
        )
    for r in plan.selected:
        st.markdown(f"- {ICON[r.verdict]} **{r.policy_name}** · {won(r.amount_krw)}")
    for e in plan.excluded:
        st.caption(f"제외: {e.policy_name} ({e.amount_krw:,}원) — '{e.because_of}'와 중복수혜 불가")
    st.caption(f"계산 방법: {plan.method}")


def render_timeline(ins) -> None:
    """📅 일정: 자격이 생기거나 사라지는 날, 신청 마감."""
    st.subheader("📅 앞으로의 일정")
    if not ins.timeline:
        st.caption("앞으로 3년 안에 자격이 바뀌거나 60일 안에 마감되는 정책이 없습니다.")
        return
    for e in ins.timeline:
        icon = EVENT_ICON[e.kind]
        st.markdown(
            f"- {icon} **{e.on}** · {e.kind} · {e.policy_name} ({won(e.amount_krw)}) — {e.detail}"
        )


def render_result_page(profile: Profile, result: EvaluationResult, ins) -> None:
    summary_col, btn_col = st.columns([5, 1])
    summary_col.markdown(f"**{_profile_summary(profile, result.as_of)}**")
    if btn_col.button("정보 수정 →", width="stretch"):
        st.session_state["page"] = "input"
        st.rerun()

    st.divider()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("✅ 충족", f"{len(result.by_verdict(Verdict.PASS))}건")
    m2.metric("❌ 불충족", f"{len(result.by_verdict(Verdict.FAIL))}건")
    m3.metric("⚠️ 확인 필요", f"{len(result.by_verdict(Verdict.UNKNOWN))}건")
    m4.metric(
        "💰 최대 수령액", man(ins.plan.total_krw), help="지금 신청 가능한 충족 정책, 중복수혜 반영"
    )

    tab_result, tab_hint, tab_plan, tab_time = st.tabs(
        ["정책별 결과", "이것만 바꾸면", "최적 조합", "일정"]
    )

    with tab_result:
        sub = st.tabs([f"{ICON[v]} {v.value} ({len(result.by_verdict(v))})" for v in Verdict])
        for t, verdict in zip(sub, Verdict, strict=True):
            with t:
                items = result.by_verdict(verdict)
                if not items:
                    st.write("해당 정책이 없습니다.")
                for p in items:
                    render_policy_card(p)
    with tab_hint:
        render_suggestions(ins)
    with tab_plan:
        render_plan(ins)
    with tab_time:
        render_timeline(ins)


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="청년정책 자격 판정", page_icon="🧾", layout="centered")
    st.title("청년정책 자격 판정")
    st.caption(
        f"청년정책 {len(policies())}건 (부산 + 중앙부처) · 판정 기준일 {as_of()} · "
        "결과는 참고용이며 최종 자격은 각 공고문과 담당 기관에서 확인하세요."
    )

    _init_state()

    if st.session_state["page"] == "input":
        render_input_page()
    else:
        render_result_page(
            st.session_state["profile"], st.session_state["result"], st.session_state["insights"]
        )


main()
