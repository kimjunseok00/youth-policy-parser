"""앱 진입점 (Streamlit Community Cloud가 실행하는 파일).

화면은 app/page_*.py에 있고, 여기서는 페이지 목록과 공통 머리말·꼬리말만 정한다.
판정 로직은 engine/에만 있다.
"""

import streamlit as st

from app import as_of, policies, telemetry
from app.branding import SERVICE_NAME, TAGLINE
from app.page_about import render as render_about
from app.page_check import render as render_check
from app.page_report import render as render_report
from app.ui_common import footer

st.set_page_config(page_title=f"{SERVICE_NAME} — {TAGLINE}", page_icon="🧾", layout="centered")


def check_page() -> None:
    st.title(SERVICE_NAME)
    st.caption(
        f"{TAGLINE} · 청년정책 {len(policies())}건 (부산 + 중앙부처) · 판정 기준일 {as_of()}"
    )
    render_check()


pages = [
    st.Page(check_page, title="자격 판정", icon="🧾", url_path="check", default=True),
    st.Page(render_report, title="지자체 리포트", icon="📊", url_path="report"),
    st.Page(render_about, title="서비스 안내", icon="ℹ️", url_path="about"),
]
st.navigation(pages).run()
footer(telemetry.load_config(st.secrets) is not None)
