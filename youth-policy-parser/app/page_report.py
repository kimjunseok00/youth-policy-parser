"""지자체 리포트 화면 (B2G): 청년이 어떤 조건 때문에 정책을 못 받는가.

데이터 원천
- 실사용 익명 통계: 동의한 사용자의 익명 요약이 MIN_GROUP건 이상 쌓였을 때만 선택할 수 있다.
- 가상 인구: 시연용. 화면에 '가상'임을 항상 표시한다.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import as_of, policies, telemetry
from app.ui_common import man, page_header
from engine.anonymize import MIN_GROUP
from engine.report import (
    SYNTHETIC_ASSUMPTIONS,
    adjustable,
    aggregate,
    aggregate_rows,
    evaluate_population,
    simulate,
    synthetic_population,
)

SYNTHETIC_N = 500


@st.cache_data(show_spinner="가상 인구로 판정하는 중…")
def _synthetic(n: int, day):
    people = synthetic_population(n, day)
    results = evaluate_population(people, list(policies()), day)
    return people, aggregate(people, results, list(policies()))


@st.cache_data(ttl=600, show_spinner="익명 통계를 불러오는 중…")
def _real_rows() -> list[dict]:
    return telemetry.fetch_rows(telemetry.load_config(st.secrets))


def _summary_table(stats) -> pd.DataFrame:
    rows = []
    for s in stats:
        top = s.fail_reasons.most_common(1)
        rows.append(
            {
                "정책": s.policy_name,
                "충족": f"{s.rate(s.passed):.0%}",
                "확인 필요": f"{s.rate(s.unknown):.0%}",
                "불충족": f"{s.rate(s.failed):.0%}",
                "가장 많은 탈락 원인": f"{top[0][0]} ({top[0][1] / s.n:.0%})" if top else "-",
            }
        )
    return pd.DataFrame(rows)


def render() -> None:
    page_header(
        "지자체 리포트",
        "청년이 '어떤 조건 때문에' 정책을 못 받는지 집계합니다. "
        "정책 설계·개선과 홍보 대상 선정에 쓰는 자료입니다.",
    )

    day = as_of()
    real = _real_rows()
    sources = ["가상 인구 (시연용)"]
    if len(real) >= MIN_GROUP:
        sources.insert(0, f"실사용 익명 통계 ({len(real):,}건)")
    source = st.radio("데이터", sources, horizontal=True)
    if len(sources) == 1:
        st.caption(
            f"실사용 익명 통계는 {MIN_GROUP}건 이상 쌓이면 선택할 수 있습니다 (현재 {len(real)}건)."
        )
    use_real = source.startswith("실사용")

    if use_real:
        stats = aggregate_rows(real, list(policies()))
        st.info(
            "동의한 사용자의 익명 요약만 집계했습니다. "
            f"{MIN_GROUP}명 미만인 구·군은 개인이 드러나지 않도록 표시하지 않습니다."
        )
    else:
        people, stats = _synthetic(SYNTHETIC_N, day)
        st.warning(
            f"**가상 인구 {SYNTHETIC_N}명으로 만든 시연용 리포트입니다. 실제 부산 청년 통계가 아닙니다.** "
            "실사용 익명 통계가 쌓이면 자동으로 선택할 수 있게 됩니다."
        )
        with st.expander("가상 인구를 만든 가정"):
            for k, v in SYNTHETIC_ASSUMPTIONS.items():
                st.markdown(f"- **{k}**: {v}")

    st.subheader("정책별 판정 분포")
    st.dataframe(_summary_table(stats), hide_index=True, width="stretch")

    st.subheader("정책 자세히 보기")
    names = [s.policy_name for s in stats]
    picked = st.selectbox("정책", names)
    s = next(x for x in stats if x.policy_name == picked)

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("충족", f"{s.rate(s.passed):.0%}")
        c2.metric("확인 필요", f"{s.rate(s.unknown):.0%}")
        c3.metric("불충족", f"{s.rate(s.failed):.0%}")

    if s.fail_reasons:
        st.markdown(
            "**탈락 원인** (불충족한 사람 중 이 조건에 걸린 비율, 한 사람이 여러 조건에 걸릴 수 있음)"
        )
        top = s.fail_reasons.most_common(8)
        reasons = pd.DataFrame(
            {
                "조건": [k for k, _ in top],
                "비율": [v / s.failed for _, v in top],
                "인원": [v for _, v in top],
            }
        )
        st.dataframe(
            reasons,
            hide_index=True,
            width="stretch",
            column_config={
                "비율": st.column_config.ProgressColumn(
                    "비율", format="percent", min_value=0, max_value=1
                )
            },
        )

    st.markdown("**구·군별 충족률**")
    area_rows = [
        {"구·군": area, "충족률": f"{ok / total:.0%}", "인원": total}
        for area, (ok, total) in s.pass_by_sigungu.items()
        if not use_real or total >= MIN_GROUP
    ]
    st.dataframe(pd.DataFrame(area_rows), hide_index=True, width="stretch")

    st.divider()
    render_simulator(day)


def _delta(n: int) -> str | None:
    return f"+{n}명" if n > 0 else None


def render_simulator(day) -> None:
    st.subheader("조건 완화 시뮬레이터")
    st.caption(
        "연령 상한이나 소득 기준을 바꾸면 새로 대상이 되는 인원과 추가 예산을 추정합니다. "
        "(가상 인구 기준)"
    )
    candidates = [p for p in policies() if any(adjustable(p))]
    pick = st.selectbox("정책", [p.name for p in candidates], key="sim_policy")
    policy = next(p for p in candidates if p.name == pick)
    has_age, has_income = adjustable(policy)
    c1, c2 = st.columns(2)
    age_delta = c1.slider("연령 상한 +", 0, 10, 0, format="%d세", key="sim_age") if has_age else 0
    income_delta = (
        c2.slider("소득 기준 +", 0, 100, 0, step=10, format="%d%%p", key="sim_income")
        if has_income
        else 0
    )
    if not (age_delta or income_delta):
        st.caption("슬라이더를 움직여 보세요.")
        return

    people, _ = _synthetic(SYNTHETIC_N, day)
    sim = simulate(policy, people, day, age_delta, income_delta)
    added_possible = sim.after_possible - sim.before_possible
    m1, m2, m3 = st.container(border=True).columns(3)
    # 변화가 없으면 증가 화살표를 그리지 않는다 (+0명에 초록 화살표는 오해를 부름)
    m1.metric("대상 가능 인원", f"{sim.after_possible}명", delta=_delta(added_possible))
    m2.metric("확정 대상(충족)", f"{sim.after_pass}명", delta=_delta(sim.added))
    if policy.amount_krw:
        m3.metric(
            "추가 예산 (최대)",
            man(added_possible * policy.amount_krw),
            help="새로 대상이 될 수 있는 인원 × 1인당 금액. 실제 신청률은 반영하지 않은 상한값.",
        )
    if added_possible == 0:
        st.caption(
            "이 범위에서는 새로 대상이 되는 사람이 없습니다. "
            "다른 조건(취업 상태·소득 등)에서 먼저 탈락하는 사람이 많은지 위의 탈락 원인을 확인해 보세요."
        )
    with st.expander("바뀐 조건식"):
        st.code(sim.new_dsl, language=None)
