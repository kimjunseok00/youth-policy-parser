"""배포 확인용 첫 화면.

지금은 엔진이 없으므로 data/mock/mock_results.json(가짜 판정 결과)을 읽어서 보여준다.
엔진이 완성되면 load_mock_result() 대신 engine의 판정 함수를 호출하도록 바꾼다.
Streamlit Community Cloud는 저장소 루트의 streamlit_app.py를 기본 진입점으로 쓴다.
"""

from pathlib import Path

import streamlit as st

from engine.schemas import EvaluationResult, PolicyResult, ReasonNode, Verdict

MOCK_PATH = Path(__file__).parent / "data" / "mock" / "mock_results.json"

# 판정 결과별 아이콘: 화면에서 한눈에 구분되도록 한다.
ICON = {Verdict.PASS: "✅", Verdict.FAIL: "❌", Verdict.UNKNOWN: "⚠️"}


@st.cache_data
def load_mock_result() -> EvaluationResult:
    """가짜 판정 결과를 스키마로 검증하면서 읽는다. 스키마와 어긋나면 여기서 바로 에러가 난다."""
    return EvaluationResult.model_validate_json(MOCK_PATH.read_text(encoding="utf-8"))


def render_reason(node: ReasonNode, depth: int = 0) -> None:
    """탈락 사유 트리를 들여쓰기 목록으로 그린다. (4주차에 그래프 시각화로 교체 예정)"""
    indent = "&nbsp;" * 4 * depth
    detail = f" — {node.detail}" if node.detail else ""
    st.markdown(f"{indent}{ICON[node.verdict]} **{node.label}**{detail}", unsafe_allow_html=True)
    if node.source_quote:
        st.caption(f"{indent}원문: “{node.source_quote}”", unsafe_allow_html=True)
    for child in node.children:
        render_reason(child, depth + 1)


def render_policy(p: PolicyResult) -> None:
    """정책 카드 1장."""
    amount = f"{p.amount_krw:,}원" if p.amount_krw is not None else "금액 산정 불가"
    deadline = p.apply_end.isoformat() if p.apply_end else "상시"
    with st.expander(f"{ICON[p.verdict]} {p.policy_name} · {amount} · 마감 {deadline}"):
        st.caption(p.agency)
        render_reason(p.reason)


def main() -> None:
    st.set_page_config(page_title="청년정책 자격 판정", page_icon="🧾")
    st.title("청년정책 자격 판정")
    st.info("배포 확인용 화면입니다. 아래 결과는 모두 가짜 데이터입니다.")

    result = load_mock_result()
    st.metric("받을 수 있는 예상 총액 (단순 합계)", f"{result.total_expected_krw:,}원")

    tabs = st.tabs([f"{ICON[v]} {v.value}" for v in Verdict])
    for tab, verdict in zip(tabs, Verdict, strict=True):
        with tab:
            items = result.by_verdict(verdict)
            if not items:
                st.write("해당 정책이 없습니다.")
            for p in items:
                render_policy(p)


main()
