"""지자체용 웹(Streamlit)의 공개 인터페이스.

화면(streamlit_app.py, app/page_*.py)은 이 모듈의 함수만 호출한다.
판정과 차별 기능 계산은 engine/service.py에 있고, 청년용 앱(PWA)도 같은 함수를 쓴다.
여기서는 '판정 기준일 = 오늘'만 정해서 넘긴다 (테스트에서 as_of를 바꿔 끼우기 쉽게).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from engine import service
from engine.benefits import BENEFIT_NAMES
from engine.evaluator import evaluate, today_kst
from engine.regions import BUSAN_SIGUNGU, SIDO
from engine.schemas import EvaluationResult, Profile
from engine.service import Insights, manual_questions, personas, policies

__all__ = [
    "BENEFIT_NAMES",
    "BUSAN_SIGUNGU",
    "SIDO",
    "Insights",
    "as_of",
    "get_insights",
    "get_results",
    "manual_questions",
    "personas",
    "policies",
]


def as_of() -> date:
    """판정 기준일 = 오늘(한국 기준). 테스트·데모에서 바꾸려면 이 함수만 고치면 된다."""
    return today_kst()


def get_results(profile: Profile, answers: Mapping[str, bool] | None = None) -> EvaluationResult:
    """프로필(+확인 질문 답변)을 받아 전체 정책 판정 결과를 반환한다."""
    return evaluate(profile, policies(), as_of(), answers=answers)


def get_insights(
    profile: Profile, result: EvaluationResult, answers: Mapping[str, bool] | None = None
) -> Insights:
    return service.insights(profile, result, policies(), as_of(), answers)
