"""앱 진입점 (Streamlit Community Cloud가 실행하는 파일).

화면은 app/page_*.py에 있고, 여기서는 페이지 목록과 공통 머리말·꼬리말만 정한다.
판정 로직은 engine/에만 있다.
디자인 원칙: 이모티콘 없음, 남색 강조색 하나, 상태는 글자 배지 (app/ui_common.py).
"""

from pathlib import Path

import streamlit as st

from app import as_of, policies, telemetry
from app.branding import MOBILE_APP_URL, SERVICE_NAME, TAGLINE
from app.page_about import render as render_about
from app.page_check import render as render_check
from app.page_report import render as render_report
from app.ui_common import footer, page_header

# 실행 위치(저장소 루트 / 이 폴더)와 상관없이 찾도록 이 파일 기준 경로를 쓴다
ASSETS = Path(__file__).parent / "assets"
FAVICON = str(ASSETS / "favicon.png")
WORDMARK = str(ASSETS / "wordmark.png")  # '되나요?' 글자 로고 (Noto Sans CJK, OFL)

st.set_page_config(page_title=f"{SERVICE_NAME} — {TAGLINE}", page_icon=FAVICON, layout="centered")


def check_page() -> None:
    page_header(
        "자격 판정",
        f"{TAGLINE} · 청년정책 {len(policies())}건 (부산 + 중앙부처) · 판정 기준일 {as_of()}",
    )
    st.caption(f"휴대폰에서는 [청년용 앱]({MOBILE_APP_URL})으로 쓰면 더 편합니다 (홈 화면에 추가).")
    st.caption(
        f"휴대폰에서는 [청년용 앱]({MOBILE_APP_URL})으로 쓰는 것이 편합니다. 이 화면은 PC용입니다."
    )
    render_check()


st.logo(WORDMARK, size="large")

pages = [
    st.Page(check_page, title="자격 판정", url_path="check", default=True),
    st.Page(render_report, title="지자체 리포트", url_path="report"),
    st.Page(render_about, title="서비스 안내", url_path="about"),
]
# 상단 메뉴: 화면 폭을 본문에 모두 쓰고, 행정 문서처럼 위에서 아래로 읽히게 한다
st.navigation(pages, position="top").run()
footer(telemetry.load_config(st.secrets) is not None)
