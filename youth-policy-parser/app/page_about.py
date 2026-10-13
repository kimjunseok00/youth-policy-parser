"""서비스 안내: 무엇을 하는 서비스인지, 데이터 출처, 한계, 개인정보."""

from __future__ import annotations

import streamlit as st

from app import as_of, policies
from app.branding import DESCRIPTION, FEEDBACK_URL, PRIVACY_URL, SERVICE_NAME, TAGLINE, TERMS_URL
from app.ui_common import page_header, won
from engine.income import load_table


def render() -> None:
    page_header(
        "서비스 안내", f"{SERVICE_NAME}가 무엇을 하는 서비스인지, 데이터 출처와 한계를 안내합니다."
    )
    st.markdown(f"**{TAGLINE}** {DESCRIPTION}")

    st.subheader("이렇게 판정합니다")
    st.markdown(
        """
1. 공고문의 자격요건을 **조건식(DSL)** 으로 옮깁니다. 예: `age(19..34) AND income_pct(household) <= 60`
2. 입력하신 정보로 조건마다 **충족 / 불충족 / 확인 필요**를 판정합니다.
3. 자동으로 판정할 수 없는 조건(예: 무주택 여부)은 억지로 판정하지 않고 **확인 질문**으로 묻습니다.
4. 결과 위에 **이것만 바꾸면**, **최적 조합**(중복수혜 반영), **일정**(자격이 생기거나 사라지는 날)을 계산합니다.
"""
    )

    st.subheader(f"정책 {len(policies())}건과 출처")
    day = as_of()
    for p in policies():
        status = "신청 가능" if not p.apply_end or p.apply_end >= day else "신청 기간 지남"
        st.markdown(
            f"- **{p.name}** · {p.agency} · {won(p.amount_krw)} · {status} · [출처]({p.source_url})"
        )
    st.caption(
        f"기준중위소득: {load_table().year}년, 보건복지부고시 제2025-135호. "
        "일부 정책은 언론 보도 등 2차 출처를 바탕으로 작성되어, 공식 공고문과 다를 수 있습니다."
    )

    st.subheader("알아두실 점")
    st.markdown(
        """
- 판정 결과는 **참고용**입니다. 최종 자격은 각 공고문과 담당 기관에서 확인하세요.
- 건강보험료로 소득을 보는 정책은 입력하신 월소득으로 근사합니다.
- 재산 기준, 원가구(부모님 포함) 소득처럼 입력받지 않는 조건은 '확인 필요'로 표시합니다.
"""
    )

    st.subheader("개인정보")
    st.markdown(
        f"""
- 입력하신 정보는 판정에만 쓰고 **저장하지 않습니다.**
- **익명 통계 제공에 동의한 경우에만** 연령대·구·탈락 조건처럼 개인을 알아볼 수 없는 요약을 저장합니다.
- 자세한 내용: [개인정보처리방침]({PRIVACY_URL}) · [이용약관]({TERMS_URL})
"""
    )
    st.link_button("의견 보내기", FEEDBACK_URL)
