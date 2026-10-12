"""서비스 이름·주소 등 브랜드 정보. 이름을 바꾸려면 이 파일만 고치면 된다.

랜딩 페이지(저장소 루트의 site/*.html)는 정적 HTML이라 주소·이름이 직접 적혀 있다. 함께 바꾼다.
"""

SERVICE_NAME = "되나요"
TAGLINE = "청년정책, 나도 되나요?"
DESCRIPTION = (
    "부산 청년정책 자격요건을 조건식으로 판정해 되는 것과 안 되는 것을 이유까지 알려드립니다."
)
VERSION = "1.0.0"

# 배포 주소. Streamlit Cloud의 앱 설정에서 사용자 지정 주소로 바꿨다면 여기도 바꾼다.
APP_URL = "https://youth-policy-parser-kenjdcyvrqqgkjbfxtebmw.streamlit.app"
REPO_URL = "https://github.com/kimjunseok00/youth-policy-parser"
SITE_URL = "https://kimjunseok00.github.io/youth-policy-parser"

PRIVACY_URL = f"{SITE_URL}/privacy.html"
TERMS_URL = f"{SITE_URL}/terms.html"
FEEDBACK_URL = f"{REPO_URL}/issues/new?labels=feedback&title=%5B%ED%94%BC%EB%93%9C%EB%B0%B1%5D%20"
