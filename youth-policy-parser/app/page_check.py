"""자격 판정 화면: 입력 → [판정하기] → 결과 → [정보 수정].

(입력·결과 화면 구조는 팀원이 만든 feature/ui를 기반으로 확장했다)
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from app import (
    BENEFIT_NAMES,
    BUSAN_SIGUNGU,
    SIDO,
    as_of,
    get_insights,
    get_results,
    manual_questions,
    personas,
    telemetry,
)
from app.ui_common import ICON, man, won
from app.viz import reason_to_dot
from engine.anonymize import anonymize
from engine.dates import full_age
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

EVENT_ICON = {"자격 발생": "🟢", "자격 상실": "🔴", "신청 마감": "⏰"}
FIXABLE_ORDER = {"행동": 0, "시간": 1, "변경 어려움": 2}
ANSWER_OPTIONS = ["모름", "예", "아니오"]
BUSAN = "부산광역시"


def telemetry_config():
    return telemetry.load_config(st.secrets)


# ---------------------------------------------------------------------------
# 상태
# ---------------------------------------------------------------------------
def _fill_from_profile(p: dict) -> None:
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
            "f_benefits": [b for b in p.get("current_benefits", []) if b in BENEFIT_NAMES],
            "f_military": int(p.get("military_months", 0)),
            "answers": {},  # 다른 사람이 되었으니 확인 질문 답변은 초기화
        }
    )


def _init_state() -> None:
    if "page" not in st.session_state:
        st.session_state.update({"page": "input", "profile": None, "result": None})
        _fill_from_profile(personas()[0]["profile"])


def _judge(profile: Profile) -> None:
    """판정 + 차별 기능 계산을 한 번에 하고 결과 화면으로 넘어간다."""
    answers = st.session_state.get("answers", {})
    result = get_results(profile, answers)
    st.session_state.update(
        {
            "profile": profile,
            "result": result,
            "insights": get_insights(profile, result, answers),
            "page": "result",
        }
    )


# ---------------------------------------------------------------------------
# 입력 화면
# ---------------------------------------------------------------------------
def render_income_calculator() -> None:
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

    # 시·도는 폼 밖: 바꾸는 즉시 시·군·구 선택지가 따라 바뀌어야 한다
    sido = st.selectbox(
        "거주 시·도",
        options=list(SIDO),
        index=list(SIDO).index(st.session_state["f_sido"])
        if st.session_state["f_sido"] in SIDO
        else 1,
    )
    st.session_state["f_sido"] = sido
    config = telemetry_config()

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
            military = st.number_input(
                "군 복무 기간 (개월)",
                min_value=0,
                max_value=72,
                value=st.session_state["f_military"],
                step=1,
                help="일부 정책은 군 복무 기간만큼 연령 상한을 늘려 줍니다. 해당 없으면 0.",
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
                help="본인 소득을 포함한 가구 전체 소득. 부모님과 따로 산다면 본인 가구 기준.",
            )
            benefits = st.multiselect(
                "현재 받고 있는 지원",
                options=list(BENEFIT_NAMES),
                default=st.session_state["f_benefits"],
                help="중복수혜 제한을 판정하는 데 씁니다.",
            )

        consent = False
        if config is not None:
            consent = st.checkbox(
                "익명 통계 제공에 동의합니다 (선택)",
                help="연령대·구·탈락 조건처럼 개인을 알아볼 수 없는 요약만 저장해 "
                "지자체 정책 개선 자료로 씁니다. 생년월일·정확한 소득은 저장하지 않습니다.",
            )
        submitted = st.form_submit_button("판정하기", type="primary", width="stretch")

    render_income_calculator()

    if not submitted:
        return
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
            "f_military": int(military),
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
            military_months=int(military),
        )
    except Exception as e:  # 스키마 검증 메시지(예: 소득 모순)를 그대로 보여준다
        msg = str(e).split("Value error, ")[-1].split("[type=")[0].strip()
        st.error(f"입력을 확인해 주세요: {msg}")
        return

    _judge(profile)
    if consent:
        telemetry.record(config, anonymize(profile, st.session_state["result"]))
    st.rerun()


# ---------------------------------------------------------------------------
# 결과 화면
# ---------------------------------------------------------------------------
def render_reason(node: ReasonNode, depth: int = 0) -> None:
    indent = "&nbsp;" * 4 * depth
    detail = f" — {node.detail}" if node.detail else ""
    st.markdown(f"{indent}{ICON[node.verdict]} **{node.label}**{detail}", unsafe_allow_html=True)
    for child in node.children:
        render_reason(child, depth + 1)


def render_policy_card(p: PolicyResult) -> None:
    period = (
        f"{p.apply_start or ''} ~ {p.apply_end or ''}"
        if (p.apply_start or p.apply_end)
        else "상시 · 기간 공고 확인"
    )
    with st.container(border=True):
        head = f"**{ICON[p.verdict]} {p.policy_name}**"
        if not p.is_open:
            head += " &nbsp; `신청 기간 아님`"
        st.markdown(head, unsafe_allow_html=True)
        st.caption(f"{p.agency} · {won(p.amount_krw)} · 신청 {period}")
        if p.amount_text:
            st.caption(p.amount_text)
        if p.verdict == Verdict.UNKNOWN and p.amount_krw:
            st.caption(
                f"기대 수령액 약 {man(p.expected_krw)} (확인할 조건이 적을수록 높게 계산)",
                help="금액 × 통과 가능성. 확인할 조건 하나당 가능성을 절반으로 보는 단순 추정입니다.",
            )

        if p.verdict == Verdict.PASS:
            with st.expander("판정 사유 보기"):
                render_reason(p.reason)
        else:
            render_reason(p.reason)
        with st.expander("그림으로 보기 · 원문"):
            st.graphviz_chart(reason_to_dot(p.reason, p.policy_name))
            if p.reason.source_quote:
                st.caption("자격요건 원문")
                st.write(p.reason.source_quote)
            if p.source_url:
                st.caption(f"[출처]({p.source_url})")


def render_questions(result: EvaluationResult) -> None:
    """확인 질문: manual() 조건에 답하면 '확인 필요'가 충족/불충족으로 확정된다."""
    questions = manual_questions(result)
    answers: dict = st.session_state.get("answers", {})
    answered = {q: a for q, a in answers.items()}
    if not questions and not answered:
        return
    related = {name for _, names in questions for name in names}
    title = (
        f"🙋 확인 질문 {len(questions)}개 — 답하면 정책 {len(related)}건의 판정이 확정돼요"
        if questions
        else "🙋 확인 질문 — 지금 답할 질문이 없습니다"
    )
    with st.expander(title, expanded=bool(questions)):
        with st.form("questions"):
            picks = {}
            for i, (q, related) in enumerate(questions):
                current = answered.get(q)
                index = 0 if current is None else (1 if current else 2)
                picks[q] = st.radio(
                    f"다음에 해당하나요? **{q}**",
                    ANSWER_OPTIONS,
                    index=index,
                    horizontal=True,
                    key=f"q_{i}",
                )
                st.caption("관련 정책: " + ", ".join(related))
            if answered:
                st.caption(f"이미 답한 질문 {len(answered)}개는 판정에 반영되어 있습니다.")
            c1, c2 = st.columns(2)
            apply = c1.form_submit_button(
                "답변 반영해서 다시 판정", type="primary", width="stretch"
            )
            reset = c2.form_submit_button("답변 모두 지우기", width="stretch")
        if apply or reset:
            new = {} if reset else dict(answered)
            if apply:
                for q, pick in picks.items():
                    if pick == "모름":
                        new.pop(q, None)
                    else:
                        new[q] = pick == "예"
            st.session_state["answers"] = new
            _judge(st.session_state["profile"])
            st.rerun()


def render_suggestions(ins) -> None:
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
        badge = {
            "행동": "🛠 바꿀 수 있음",
            "시간": "⏳ 시간이 지나면",
            "변경 어려움": "· 변경 어려움",
        }
        for m in misses:
            st.markdown(
                f"- **{m.policy_name}** ({won(m.amount_krw)}) — {m.condition} · {m.gap}  "
                f"`{badge[m.fixable_by]}`"
            )


def render_plan(ins) -> None:
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
    st.subheader("📅 앞으로의 일정")
    if not ins.timeline:
        st.caption("앞으로 3년 안에 자격이 바뀌거나 60일 안에 마감되는 정책이 없습니다.")
        return
    for e in ins.timeline:
        st.markdown(
            f"- {EVENT_ICON[e.kind]} **{e.on}** · {e.kind} · {e.policy_name} "
            f"({won(e.amount_krw)}) — {e.detail}"
        )


def render_result_page() -> None:
    profile: Profile = st.session_state["profile"]
    result: EvaluationResult = st.session_state["result"]
    ins = st.session_state["insights"]

    summary_col, btn_col = st.columns([5, 1])
    mil = f" / 군 복무 {profile.military_months}개월" if profile.military_months else ""
    summary_col.markdown(
        f"**{profile.sido} {profile.sigungu} / 만 {full_age(profile.birth_date, result.as_of)}세 / "
        f"{profile.employment.value} / 가구 {profile.household_size}인{mil}**"
    )
    if btn_col.button("정보 수정 →", width="stretch"):
        st.session_state["page"] = "input"
        st.rerun()

    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("✅ 충족", f"{len(result.by_verdict(Verdict.PASS))}건")
    m2.metric("❌ 불충족", f"{len(result.by_verdict(Verdict.FAIL))}건")
    m3.metric("⚠️ 확인 필요", f"{len(result.by_verdict(Verdict.UNKNOWN))}건")
    m4.metric(
        "💰 최대 수령액",
        man(ins.plan.total_krw),
        help="지금 신청 가능한 충족 정책, 중복수혜 반영",
    )

    render_questions(result)

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


def render() -> None:
    _init_state()
    if st.session_state["page"] == "input":
        render_input_page()
    else:
        render_result_page()
