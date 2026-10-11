"""앱 레이어 공개 인터페이스.

화면(streamlit_app.py)은 이 모듈의 함수만 호출한다. 판정 로직은 전부 engine/에 있다.
(팀원이 만든 get_results() 구조를 그대로 유지하고, 안쪽만 진짜 엔진으로 교체했다)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

from engine.benefits import BENEFIT_NAMES
from engine.counterfactual import NearMiss, Suggestion, near_misses, suggestions
from engine.evaluator import evaluate, load_policies, today_kst
from engine.optimizer import OptimalPlan, optimize
from engine.regions import BUSAN_SIGUNGU, SIDO
from engine.schemas import EvaluationResult, Policy, Profile
from engine.timeline import TimelineEvent, timeline

ROOT = Path(__file__).resolve().parent.parent
PERSONAS_PATH = ROOT / "data" / "personas.json"

__all__ = [
    "BENEFIT_NAMES",
    "BUSAN_SIGUNGU",
    "SIDO",
    "Insights",
    "as_of",
    "get_insights",
    "get_results",
    "personas",
    "policies",
]


def as_of() -> date:
    """판정 기준일 = 오늘(한국 기준). 테스트·데모에서 바꾸려면 이 함수만 고치면 된다."""
    return today_kst()


@cache
def policies() -> tuple[Policy, ...]:
    """data/policies/*.json. 서버가 떠 있는 동안 한 번만 읽는다."""
    return tuple(load_policies())


@cache
def personas() -> tuple[dict, ...]:
    """예시 인물 (data/personas.json). 각 항목: label, scenario, profile."""
    return tuple(json.loads(PERSONAS_PATH.read_text(encoding="utf-8")))


def get_results(profile: Profile) -> EvaluationResult:
    """프로필을 받아 전체 정책 판정 결과를 반환한다."""
    return evaluate(profile, policies(), as_of())


@dataclass(frozen=True)
class Insights:
    """판정 결과 위에 얹는 차별 기능 묶음."""

    suggestions: list[Suggestion]  # 이것만 바꾸면 (행동 제안)
    near_misses: list[NearMiss]  # 조건 하나만 어긋난 정책
    timeline: list[TimelineEvent]  # 자격 발생·상실·마감 일정
    plan: OptimalPlan  # 충족 정책만으로 만든 최적 조합
    plan_with_unknown: OptimalPlan  # 확인 필요까지 포함한 최적 조합


def get_insights(profile: Profile, result: EvaluationResult) -> Insights:
    pols, today = list(policies()), as_of()
    return Insights(
        suggestions=suggestions(profile, pols, today),
        near_misses=near_misses(profile, pols, today),
        timeline=timeline(profile, pols, today),
        plan=optimize(result, pols, include_unknown=False),
        plan_with_unknown=optimize(result, pols, include_unknown=True),
    )
